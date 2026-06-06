import os
import cv2
import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from logger import log

_REF_W = 1920
_REF_H = 1080


@dataclass
class WeaponState:
    weapon: str
    muzzle: str = "none"
    grip: str = "none"
    stock: str = "none"
    confidence: float = 0.0


class WeaponDetector:
    def __init__(self, template_dir: str, recoil_data: dict = None):
        self.templates: Dict[str, np.ndarray] = {}
        self.template_dir = template_dir
        self.recoil_data = recoil_data or {}
        self._load_templates()

    def _load_templates(self) -> None:
        if not os.path.isdir(self.template_dir):
            log(f"[WD] Template dir not found: {self.template_dir}")
            return
        for fname in os.listdir(self.template_dir):
            if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                path = os.path.join(self.template_dir, fname)
                template = cv2.imread(path, cv2.IMREAD_COLOR)
                if template is not None:
                    label = os.path.splitext(fname)[0]
                    self.templates[label] = template
                    log(f"[WD] Loaded template: {label} ({template.shape})")

    def detect_weapon(self, frame: np.ndarray, roi: Tuple[int, int, int, int]
                      ) -> Tuple[Optional[str], float]:
        fh, fw = frame.shape[:2]
        x, y, w, h = self._scale_coords(roi, fw, fh)
        if y + h > fh or x + w > fw:
            return None, 0.0
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            return None, 0.0

        best_label = None
        best_conf = 0.0
        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        hc, wc = gray_crop.shape

        for label, template in self.templates.items():
            gray_tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            ht, wt = gray_tmpl.shape
            if ht > hc or wt > wc:
                resized = cv2.resize(gray_tmpl, (wc, hc))
                result = cv2.matchTemplate(gray_crop, resized, cv2.TM_CCOEFF_NORMED)
            else:
                result = cv2.matchTemplate(gray_crop, gray_tmpl, cv2.TM_CCOEFF_NORMED)
            _, conf, _, _ = cv2.minMaxLoc(result)
            if conf > best_conf:
                best_conf = conf
                best_label = label

        return best_label, best_conf

    @staticmethod
    def _scale_coords(coords, fw, fh):
        sx = fw / _REF_W
        sy = fh / _REF_H
        return [int(coords[0] * sx), int(coords[1] * sy),
                int(coords[2] * sx), int(coords[3] * sy)]

    def detect_attachments(self, frame: np.ndarray,
                           regions: Dict[str, List[Dict]]
                           ) -> Dict[str, str]:
        result: Dict[str, str] = {}
        fh, fw = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        for slot, checks in regions.items():
            found = "none"
            best_match = 0.0
            for att in checks:
                name = att["name"]
                for key in ("check_area", "check_area2"):
                    coords = att.get(key)
                    if not coords:
                        continue
                    x1, y1, x2, y2 = self._scale_coords(coords, fw, fh)
                    if y2 > frame.shape[0] or x2 > frame.shape[1]:
                        continue
                    crop = gray[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue
                    mean_val = np.mean(crop)
                    var_val = np.var(crop)
                    # Lower mean + higher variance = attachment icon present
                    score = (255 - mean_val) / 255.0 + min(1.0, var_val / 2000.0)
                    if score > best_match:
                        best_match = score
                        found = name
            result[slot] = found if best_match > 0.6 else "none"

        return result

    def to_nova_name(self, weapon_name: str) -> str:
        name_map = self.recoil_data.get("weapon_name_map", {})
        return name_map.get(weapon_name, weapon_name.upper())

    @staticmethod
    def enumerate_attachment_keys(config: dict) -> Dict[str, List[Dict]]:
        return config.get("attachments", {})

    @staticmethod
    def resolve_recoil(recoil_data: dict, nova_name: str, muzzle: str,
                       grip: str, distance_mode: str = "normal") -> float:
        patterns = recoil_data.get("patterns", {})

        for att_name in [muzzle, grip]:
            if att_name not in ("none",) and att_name in patterns:
                entry = patterns[att_name]
                if nova_name in entry:
                    val = entry[nova_name].get(distance_mode, 0)
                    if val != 0:
                        return val

        entry = patterns.get("none", {}).get(nova_name, {})
        if isinstance(entry, dict):
            return entry.get(distance_mode, 0)
        return 0.0
