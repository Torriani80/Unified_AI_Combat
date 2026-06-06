import cv2
import numpy as np
import sys
from pathlib import Path
from typing import Optional, Tuple
from logger import log


# Tamanho máximo de referência para pré-escala dos templates
_REF_TEMPLATE_W = 320
_REF_TEMPLATE_H = 160


class UnifiedObjectDetector:
    """
    Detector de armas por template matching para SLOT 1 e SLOT 2.
    """
    def __init__(self, method: str = "template"):
        self.method = method
        self.templates = {}
        self.weapon_names = []
        self.active_provider = "TEMPLATE"
        self.current_weapon = None
        self.current_confidence = 0.0
        self._load_weapon_templates()

    def _get_roi_slot1(self, frame_width: int, frame_height: int):
        roi_w = int(frame_width * 0.14)
        roi_h = int(frame_height * 0.10)
        roi_x = frame_width - roi_w - int(frame_width * 0.02)
        roi_y = frame_height - roi_h - int(frame_height * 0.02)
        return (roi_x, roi_y, roi_w, roi_h)

    def _get_roi_slot2(self, frame_width: int, frame_height: int):
        roi_w = int(frame_width * 0.12)
        roi_h = int(frame_height * 0.08)
        roi_x = frame_width - roi_w - int(frame_width * 0.02)
        roi_y = frame_height - int(frame_height * 0.12) - roi_h - int(frame_height * 0.02)
        return (roi_x, roi_y, roi_w, roi_h)

    def _load_weapon_templates(self):
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent

        template_dir = base_path / "weapon_templates"
        if not template_dir.exists():
            log(f"[ARMAS] Diretório de templates não encontrado: {template_dir}")
            return

        for fname in sorted(template_dir.iterdir()):
            if fname.suffix.lower() in (".png", ".jpg", ".jpeg"):
                img = cv2.imread(str(fname), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    name = fname.stem.upper()
                    # Pré-escala leve para evitar templates monstruosos
                    h, w = img.shape
                    if h > _REF_TEMPLATE_H or w > _REF_TEMPLATE_W:
                        factor = min(_REF_TEMPLATE_H / h, _REF_TEMPLATE_W / w) * 0.85
                        if factor > 0:
                            new_w = max(1, int(w * factor))
                            new_h = max(1, int(h * factor))
                            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    self.templates[name] = img
                    self.weapon_names.append(name)

        if not self.templates:
            log("[ARMAS] Nenhum template de arma encontrado em weapon_templates/")
        else:
            log(f"[ARMAS] {len(self.templates)} templates de armas carregados")

    def get_center_of_screen(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        return (w / 2.0, h / 2.0)

    def _match_weapon_in_roi(self, gray_roi: np.ndarray) -> Tuple[Optional[str], float]:
        rh, rw = gray_roi.shape
        best_name = None
        best_conf = 0.0

        for name, templ in self.templates.items():
            th, tw = templ.shape
            # Redimensiona template para o tamanho exato da ROI (matchTemplate requer templ <= roi)
            if th > rh or tw > rw:
                templ = cv2.resize(templ, (rw, rh), interpolation=cv2.INTER_AREA)
            try:
                result = cv2.matchTemplate(gray_roi, templ, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
            except Exception:
                continue

            if max_val > best_conf:
                best_conf = float(max_val)
                best_name = name
                if best_conf > 0.88:
                    return (best_name, best_conf)

        if best_conf >= 0.68:
            return (best_name, best_conf)
        return (None, 0.0)

    def detect_slot1(self, frame: np.ndarray) -> Optional[str]:
        """Detecta arma no SLOT 1."""
        if frame is None or not self.templates:
            return None
        h, w = frame.shape[:2]
        rx, ry, rw, rh = self._get_roi_slot1(w, h)
        if rw < 20 or rh < 20:
            return None
        roi = frame[ry:ry+rh, rx:rx+rw]
        if roi.size == 0:
            return None
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        name, conf = self._match_weapon_in_roi(gray_roi)
        if name:
            self.current_weapon = name
            self.current_confidence = conf
        return name

    def detect_slot2(self, frame: np.ndarray) -> Optional[str]:
        """Detecta arma no SLOT 2."""
        if frame is None or not self.templates:
            return None
        h, w = frame.shape[:2]
        rx, ry, rw, rh = self._get_roi_slot2(w, h)
        if rw < 20 or rh < 20:
            return None
        roi = frame[ry:ry+rh, rx:rx+rw]
        if roi.size == 0:
            return None
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        name, conf = self._match_weapon_in_roi(gray_roi)
        return name

    def detect_weapon(self, frame: np.ndarray) -> Optional[str]:
        """Detecta arma no SLOT 1 (compatibilidade)."""
        return self.detect_slot1(frame)

    def detect_enemies(self, frame: np.ndarray):
        """Compatibilidade - sempre retorna lista vazia."""
        return []