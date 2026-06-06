"""
Controlador Proporcional com Decaimento

Quando não há detecção, o offset decai gradualmente para zero.
Isso permite que a mira continue corrigindo mesmo entre detecções,
evitando o "pulsar" causado por YOLO intermitente.
"""

import math
import random
from typing import List, Optional, Tuple
from collections import deque

from config import AIM, RANDOM, DETECTION
from object_detection import Detection


class AimCalculator:

    def __init__(self):
        self._smoothed_offset = (0.0, 0.0)
        self.last_target = None
        self.target_history: deque = deque(maxlen=5)
        self._frames_since_detect = 0
        self._last_box_h = 80
        self.smoothing_factor = 0.35

    def calculate(self, detections: List[Detection],
                  screen_center: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        """Calcula mira quando há detecção. Atualiza offset suavizado."""
        if not detections:
            self.last_target = None
            return None

        targets = [d for d in detections if d.class_label in DETECTION.target_classes]
        if not targets:
            targets = detections

        target = self._select_best_target(targets, screen_center)
        if target is None:
            return None

        self.last_target = target
        self._frames_since_detect = 0
        bx, by, bw, bh = target.bbox
        self._last_box_h = bh

        cx, cy = screen_center

        raw_dx, raw_dy = self._compute_raw_offset(target, cx, cy)

        max_offset = 120.0
        raw_dx = max(-max_offset, min(max_offset, raw_dx))
        raw_dy = max(-max_offset, min(max_offset, raw_dy))

        # EMA smoothing com clamp por frame
        sx, sy = self._smoothed_offset
        max_change = 30.0
        clamped_dx = sx + max(-max_change, min(max_change, raw_dx - sx))
        clamped_dy = sy + max(-max_change, min(max_change, raw_dy - sy))

        alpha = getattr(self, 'smoothing_factor', 0.35)
        sx = sx + (clamped_dx - sx) * alpha
        sy = sy + (clamped_dy - sy) * alpha
        self._smoothed_offset = (sx, sy)

        return self._apply_offset(screen_center)

    def _compute_raw_offset(self, target, cx, cy):
        """Calcula offset bruto usando proporção do bounding box."""
        bx, by, bw, bh = target.bbox
        ratio = self._get_aim_ratio()
        aim_y = by + bh * ratio
        aim_x = bx + bw / 2
        return (aim_x - cx + AIM.aim_offset_x, aim_y - cy + AIM.aim_offset_y)

    def _get_aim_ratio(self):
        zone = AIM.aim_zone
        if zone == 1:
            return 0.10
        elif zone == 3:
            return 0.45
        return 0.25

    def _apply_offset(self, screen_center):
        """Aplica gain e ruído ao offset atual. Retorna (x,y) ou None se deadzone."""
        sx, sy = self._smoothed_offset
        dist = math.hypot(sx, sy)

        deadzone = AIM.tracking_deadzone if self._frames_since_detect > 0 else AIM.deadzone_radius
        if dist <= deadzone:
            return None

        gain = AIM.aim_gain
        move_dx = sx * gain
        move_dy = sy * gain

        if RANDOM.position_noise_px > 0:
            move_dx += random.gauss(0, RANDOM.position_noise_px * 0.3)
            move_dy += random.gauss(0, RANDOM.position_noise_px * 0.3)

        cx, cy = screen_center
        return (cx + move_dx, cy + move_dy)

    def get_correction(self, screen_center) -> Optional[Tuple[float, float]]:
        """
        Retorna correção de mira BASEADA NO OFFSET ATUAL, mesmo sem nova detecção.
        Chame TODO frame enquanto aiming=True.
        O offset decai gradualmente quando não há detecção.
        """
        self._frames_since_detect += 1

        sx, sy = self._smoothed_offset

        if self._frames_since_detect > 0:
            decay = 0.92 ** self._frames_since_detect
            sx *= decay
            sy *= decay
            self._smoothed_offset = (sx, sy)

        return self._apply_offset(screen_center)

    @staticmethod
    def _select_best_target(targets, screen_center):
        if not targets:
            return None
        cx, cy = screen_center

        def score(t):
            dist = math.hypot(t.centroid[0] - cx, t.centroid[1] - cy)
            return dist - (t.confidence * 50) - (getattr(t, 'area', 0) * 0.01)

        return min(targets, key=score)

    def reset(self):
        self._smoothed_offset = (0.0, 0.0)
        self.last_target = None
        self.target_history.clear()
        self._frames_since_detect = 0
        self._last_box_h = 80

    def get_aim_vector(self, screen_center):
        return (self._smoothed_offset[0], self._smoothed_offset[1])


if __name__ == "__main__":
    calculator = AimCalculator()
    center = (320, 240)

    from object_detection import Detection
    targets = [
        Detection(bbox=(100, 100, 50, 80), confidence=0.85,
                  class_label="enemy", centroid=(125.0, 140.0)),
        Detection(bbox=(300, 200, 40, 60), confidence=0.75,
                  class_label="enemy", centroid=(320.0, 230.0)),
    ]

    for i in range(20):
        if i % 5 == 0:
            aim = calculator.calculate(targets, center)
        else:
            aim = calculator.get_correction(center)
        if aim:
            dx = aim[0] - center[0]
            dy = aim[1] - center[1]
            print(f"Iter {i+1}: aim=({aim[0]:.1f}, {aim[1]:.1f}) move=({dx:.1f}, {dy:.1f})")
        else:
            print(f"Iter {i+1}: no target / deadzone")
