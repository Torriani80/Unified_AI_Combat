import ctypes
import ctypes.wintypes
import time
from typing import Optional, Dict, Tuple
from config import CMD
from logger import log


def _resolve_recoil(recoil_data: dict, nova_name: str, muzzle: str,
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

_LOG_SKIP_FIRST = 5
_LOG_INTERVAL = 30


user32 = ctypes.windll.user32
MOUSEEVENTF_MOVE = 0x0001


class UnifiedCommandExecutor:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.flat_recoil = False
        self.burst_ticks = 0
        self.shot_counter = 0
        self._last_recoil_time = 0.0
        self._last_release_time = 0.0
        self._last_vertical_applied = 0.0
        self._last_horizontal_applied = 0.0
        self.adjust_vertical = 0.0
        self.adjust_horizontal = 0.0
        self._game_hwnd = None
        self._clipping = False
        self._original_rect = (ctypes.c_int * 4)()

        # NOVA recoil data
        self.recoil_data: Optional[dict] = None
        self._nova_name: Optional[str] = None
        self._current_muzzle: str = "none"
        self._current_grip: str = "none"
        self.distance_mode: str = "normal"

    def configure_nova_recoil(self, recoil_data: dict):
        self.recoil_data = recoil_data

    def set_current_weapon(self, weapon_label: str):
        if not self.recoil_data:
            return
        name_map = self.recoil_data.get("weapon_name_map", {})
        nova = name_map.get(weapon_label, weapon_label.upper())
        self._nova_name = nova

    def set_attachments(self, muzzle: str = "none", grip: str = "none"):
        self._current_muzzle = muzzle
        self._current_grip = grip

    def start_clipping(self):
        try:
            self._game_hwnd = user32.GetForegroundWindow()
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(self._game_hwnd, ctypes.byref(rect))
            clip_rect = (ctypes.c_int * 4)(rect.left, rect.top, rect.right, rect.bottom)
            user32.ClipCursor(clip_rect)
            self._clipping = True
        except:
            pass

    def stop_clipping(self):
        try:
            user32.ClipCursor(None)
        except:
            pass
        self._clipping = False

    def update_modifier(self, attachment: str, value: float):
        pass

    def set_adjust(self, vertical: float = 0.0, horizontal: float = 0.0):
        self.adjust_vertical = vertical
        self.adjust_horizontal = horizontal

    def set_distance_mode(self, mode: str):
        if mode in ("normal", "meio", "pe", "pe_meio"):
            self.distance_mode = mode
            log(f"[RECOIL] Distance mode: {mode}")

    def move_mouse(self, dx: float, dy: float):
        if dx == 0 and dy == 0:
            return
        user32.mouse_event(MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)

    def _get_weapon_recoil_value(self) -> float:
        if not self.recoil_data or not self._nova_name:
            return 0.0
        value = _resolve_recoil(
            self.recoil_data, self._nova_name,
            self._current_muzzle, self._current_grip,
            self.distance_mode)
        calib = self.recoil_data.get("calibration_global", 95)
        return value * calib

    def execute_combat_step(self, recoil_cfg: Optional[dict] = None):
        if not self.enabled:
            return

        total_dx = 0.0
        total_dy = 0.0

        lbutton = (user32.GetAsyncKeyState(0x01) & 0x8000) != 0
        now = time.time()

        if lbutton:
            if recoil_cfg:
                if self.burst_ticks == 0:
                    self._last_release_time = now

                interval_ms = recoil_cfg.get("interval_ms", 50)
                if (now - self._last_recoil_time) >= interval_ms / 1000.0:
                    self._last_recoil_time = now
                    self.burst_ticks += 1

                    # NOVA recoil lookup ou fallback flat
                    nova_val = self._get_weapon_recoil_value()
                    if nova_val != 0 and self._nova_name:
                        v_base = nova_val
                        h_base = recoil_cfg.get("horizontal", 0) * 0.3
                    else:
                        v_base = recoil_cfg.get("vertical", 0)
                        h_base = recoil_cfg.get("horizontal", 0)

                    prog = 0 if self.flat_recoil else recoil_cfg.get("progression", 0)
                    limit = recoil_cfg.get("progression_limit", 10)
                    decay = recoil_cfg.get("progression_decay", 0.4)

                    if self.flat_recoil or self.burst_ticks <= limit:
                        v_recoil = v_base + self.adjust_vertical
                        h_recoil = h_base + self.adjust_horizontal
                    else:
                        factor = min((self.burst_ticks - limit) * decay, 1.0)
                        reduction = prog * factor
                        v_recoil = v_base * (1.0 - reduction) + self.adjust_vertical
                        h_recoil = h_base * (1.0 - reduction) + self.adjust_horizontal

                    if self._last_vertical_applied > 0:
                        v_blend = min(v_recoil, self._last_vertical_applied * 1.05)
                    else:
                        v_blend = v_recoil
                    if self._last_horizontal_applied > 0:
                        h_blend = min(h_recoil, self._last_horizontal_applied * 1.05)
                    else:
                        h_blend = h_recoil

                    total_dx += h_blend
                    total_dy += v_blend
                    self._last_vertical_applied = v_blend
                    self._last_horizontal_applied = h_blend
                    self.shot_counter += 1

                    if self._nova_name:
                        if self.shot_counter > _LOG_SKIP_FIRST and (self.shot_counter % _LOG_INTERVAL) != 0:
                            pass
                        else:
                            log(f"RECOIL weapon={self._nova_name} mode={self.distance_mode} "
                                f"tiro#{self.shot_counter} v={v_blend:.1f} h={h_blend:.1f}")
                    else:
                        if self.shot_counter > _LOG_SKIP_FIRST and (self.shot_counter % _LOG_INTERVAL) != 0:
                            pass
                        else:
                            prog_active = not self.flat_recoil and self.burst_ticks > limit
                            r = int((1 - (v_recoil - self.adjust_vertical) / v_base) * 100) if v_base and prog_active else 0
                            log(f"RECOIL tiro#{self.shot_counter} burst={self.burst_ticks} "
                                f"v={v_blend:.1f} h={h_blend:.1f} reducao={r}%")
            else:
                if self.shot_counter == 0:
                    log("RECOIL: lbutton=True but recoil_cfg=None!")
        else:
            if self.burst_ticks > 0:
                self._last_release_time = now
            self._last_vertical_applied = 0.0
            self._last_horizontal_applied = 0.0

            cooldown = 1.2
            if now - self._last_release_time > cooldown:
                self.burst_ticks = 0
                self._last_recoil_time = 0.0

        self.move_mouse(total_dx, total_dy)
