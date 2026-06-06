"""
AimTracker v2 - Template matching + Filtro Kalman + Predição de velocidade.

Combina three camadas:
1. Template matching (~2ms) - rastreamento visual frame-a-frame
2. Filtro Kalman - suaviza jitter e prediz posição quando tracker falha
3. Predição de velocidade - extrapolia posição baseado em movimento anterior

Resultado: mira gruda no alvo mesmo quando YOLO falha por vários frames.
"""

import cv2
import numpy as np
from typing import Optional, Tuple


class KalmanSmoother:
    """Filtro Kalman para suavização e predição de posição 2D."""

    def __init__(self, process_noise=0.03, measurement_noise=5.0):
        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], dtype=np.float32)
        self.kf.transitionMatrix = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], dtype=np.float32)
        self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * process_noise
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * measurement_noise
        self.kf.errorCovPost = np.eye(4, dtype=np.float32)
        self._initialized = False
        self.predicted_pos = None

    def init_state(self, x, y):
        self.kf.statePost = np.array([[x], [y], [0], [0]], dtype=np.float32)
        self._initialized = True
        self.predicted_pos = (x, y)

    def update(self, x, y):
        if not self._initialized:
            self.init_state(x, y)
            return (x, y)
        measurement = np.array([[np.float32(x)], [np.float32(y)]])
        self.kf.correct(measurement)
        state = self.kf.statePost
        self.predicted_pos = (float(state[0]), float(state[1]))
        return self.predicted_pos

    def predict(self):
        if not self._initialized:
            return None
        pred = self.kf.predict()
        self.predicted_pos = (float(pred[0]), float(pred[1]))
        return self.predicted_pos

    @property
    def velocity(self):
        if not self._initialized:
            return (0.0, 0.0)
        state = self.kf.statePost
        return (float(state[2]), float(state[3]))


class AimTracker:

    def __init__(self, search_margin: float = 1.5, confidence_threshold: float = 0.25):
        self._template = None
        self._last_bbox: Optional[Tuple[int, int, int, int]] = None
        self._search_margin = search_margin
        self._confidence_threshold = confidence_threshold
        self.initialized = False
        self.confidence = 0.0
        self.kalman = KalmanSmoother()
        self._frames_lost = 0
        self._max_prediction_frames = 10

    def init(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]):
        x, y, w, h = [int(v) for v in bbox]
        h_f, w_f = frame.shape[:2]
        x = max(0, x)
        y = max(0, y)
        w = min(w, w_f - x)
        h = min(h, h_f - y)
        if w < 4 or h < 4:
            return
        self._template = frame[y:y + h, x:x + w].copy()
        self._last_bbox = (x, y, w, h)
        self.initialized = True
        self.confidence = 1.0
        self._frames_lost = 0
        cx, cy = x + w / 2, y + h / 2
        self.kalman.init_state(cx, cy)

    def update(self, frame: np.ndarray) -> bool:
        if not self.initialized or self._template is None:
            return False

        x, y, w, h = self._last_bbox
        h_f, w_f = frame.shape[:2]

        margin_x = int(w * self._search_margin)
        margin_y = int(h * self._search_margin)
        rx1 = max(0, x - margin_x)
        ry1 = max(0, y - margin_y)
        rx2 = min(w_f, x + w + margin_x)
        ry2 = min(h_f, y + h + margin_y)

        roi = frame[ry1:ry2, rx1:rx2]
        tw, th = self._template.shape[1], self._template.shape[0]
        if roi.shape[0] < th or roi.shape[1] < tw:
            self._frames_lost += 1
            self.kalman.predict()
            return self._frames_lost <= self._max_prediction_frames

        result = cv2.matchTemplate(roi, self._template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        self.confidence = float(max_val)

        if max_val < self._confidence_threshold:
            self._frames_lost += 1
            self.kalman.predict()
            return self._frames_lost <= self._max_prediction_frames

        nx = rx1 + max_loc[0]
        ny = ry1 + max_loc[1]
        self._last_bbox = (nx, ny, w, h)
        self._frames_lost = 0

        cx, cy = nx + w / 2, ny + h / 2
        self.kalman.update(cx, cy)

        if max_val > 0.8:
            alpha = 0.05
            new_patch = frame[ny:ny + h, nx:nx + w].copy()
            if new_patch.shape == self._template.shape:
                self._template = cv2.addWeighted(self._template, 1 - alpha, new_patch, alpha, 0)

        return True

    @property
    def centroid(self) -> Optional[Tuple[float, float]]:
        if self.kalman.predicted_pos:
            return self.kalman.predicted_pos
        if self._last_bbox is None:
            return None
        x, y, w, h = self._last_bbox
        return (x + w / 2, y + h / 2)

    def reset(self):
        self._template = None
        self._last_bbox = None
        self.initialized = False
        self.confidence = 0.0
        self._frames_lost = 0
        self.kalman = KalmanSmoother()
