import cv2
import numpy as np
import sys
from pathlib import Path
from typing import Optional, Tuple
from logger import log


class UnifiedObjectDetector:
    """
    Detector de armas por template matching para SLOT 1 e SLOT 2.
    
    Monitora duas ROIs (canto inferior direito) onde as armas aparecem na tela
    e compara com templates para identificar qual arma está equipada em cada slot.
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
        """ROI do SLOT 1 (arma principal) - Parte inferior."""
        roi_w = int(frame_width * 0.14)
        roi_h = int(frame_height * 0.10)
        roi_x = frame_width - roi_w - int(frame_width * 0.02)
        roi_y = frame_height - roi_h - int(frame_height * 0.02)
        return (roi_x, roi_y, roi_w, roi_h)

    def _get_roi_slot2(self, frame_width: int, frame_height: int):
        """ROI do SLOT 2 (segunda arma) - Acima do slot 1, sem sobrepor."""
        roi_w = int(frame_width * 0.12)
        roi_h = int(frame_height * 0.08)
        roi_x = frame_width - roi_w - int(frame_width * 0.02)
        # Posiciona acima do Slot 1 (ROI 1 tem 10% + 2% margem)
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
            log("[ARMAS] Coloque imagens .png das armas em weapon_templates/")
            return

        for fname in sorted(template_dir.iterdir()):
            if fname.suffix.lower() in (".png", ".jpg", ".jpeg"):
                img = cv2.imread(str(fname), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    name = fname.stem.upper()
                    self.templates[name] = img
                    self.weapon_names.append(name)
                    log(f"[ARMAS] Template carregado: {name} ({img.shape})")

        if not self.templates:
            log("[ARMAS] Nenhum template de arma encontrado em weapon_templates/")
        else:
            log(f"[ARMAS] {len(self.templates)} templates de armas carregados")

    def get_center_of_screen(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        return (w / 2.0, h / 2.0)

    def _match_weapon_in_roi(self, gray_roi: np.ndarray) -> Tuple[Optional[str], float]:
        """Compara a ROI com todos os templates e retorna (nome, confiança)."""
        matches = []
        threshold = 0.70
        rh, rw = gray_roi.shape

        for name, templ in self.templates.items():
            th, tw = templ.shape
            if th > rh or tw > rw:
                factor = min(rh / th, rw / tw) * 0.85
                if factor <= 0:
                    continue
                new_w = max(1, int(tw * factor))
                new_h = max(1, int(th * factor))
                templ = cv2.resize(templ, (new_w, new_h), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(gray_roi, templ, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            matches.append((name, float(max_val)))

        if not matches:
            return (None, 0.0)

        matches.sort(key=lambda x: x[1], reverse=True)
        best_name, best_conf = matches[0]

        if len(matches) > 1:
            second_conf = matches[1][1]
            if (best_conf - second_conf) < 0.03: # Reduzido para 3%
                if best_conf < 0.80: # Limiar de "certeza absoluta" reduzido para 0.80
                    return (None, 0.0)

        if best_conf >= threshold:
            # log(f"[DEBUG ARMA] Match: {best_name} ({best_conf:.2f}) | Second: {matches[1][0] if len(matches)>1 else 'N/A'} ({matches[1][1]:.2f} if len(matches)>1 else 0)")
            return (best_name, best_conf)
        return (None, 0.0)

    def detect_slot1(self, frame: np.ndarray) -> Optional[str]:
        """Detecta arma no SLOT 1."""
        if frame is None or not self.templates:
            return None
        h, w = frame.shape[:2]
        rx, ry, rw, rh = self._get_roi_slot1(w, h)
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