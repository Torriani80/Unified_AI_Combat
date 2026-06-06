import sys
import os
import subprocess
import threading
import time
import ctypes
from pathlib import Path
from queue import Queue, Empty

from logger import log

# Garante que a pasta do projeto está no path, mesmo no exe congelado
if getattr(sys, 'frozen', False):
    base = Path(sys._MEIPASS)
else:
    base = Path(__file__).parent
if str(base) not in sys.path:
    sys.path.insert(0, str(base))

# Garante que o Qt encontra os plugins no modo frozen (PyInstaller)
if getattr(sys, 'frozen', False):
    qt_plugins = base / 'PyQt5' / 'Qt5' / 'plugins'
    if qt_plugins.exists():
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = str(qt_plugins)

def global_excepthook(exc_type, exc_value, exc_traceback):
    import traceback
    lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    msg = "".join(lines)
    print(msg, flush=True)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "Erro no Macro", 0x10)
    except:
        pass

sys.excepthook = global_excepthook

# Minimiza o console no Windows quando rodar como .exe
if getattr(sys, 'frozen', False):
    try:
        ctypes.windll.kernel32.GetConsoleWindow.restype = ctypes.c_void_p
        console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if console_hwnd:
            ctypes.windll.user32.ShowWindow(console_hwnd, 6)
    except Exception:
        pass

def install_dependencies():
    if getattr(sys, 'frozen', False):
        return
    dependencies = ['PyQt5', 'numpy', 'opencv-python', 'mss', 'keyboard', 'firebase-admin']
    for dep in dependencies:
        try:
            __import__(dep.replace('opencv-python', 'cv2').replace('firebase-admin', 'firebase_admin'))
        except ImportError:
            print(f"Installing missing dependency: {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])

install_dependencies()

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                              QLabel, QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect,
                              QSizePolicy, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, QSize
from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, QPainterPath, 
                          QFont, QPixmap, QLinearGradient, QRadialGradient, QIcon)
from config import config, load_from_json
from screen_capture import ScreenCapturer
from UnifiedObjectDetector import UnifiedObjectDetector
from CombatCore import UnifiedCommandExecutor

from TacticalHUD import TacticalHUD

from CombatSecurity import CombatSecurity
from crosshair_overlay import CrosshairOverlay
import numpy as np

if getattr(sys, 'frozen', False):
    cfg_path = Path(sys._MEIPASS) / "config_pubg.json"
else:
    cfg_path = Path(__file__).parent / "config_pubg.json"
if cfg_path.exists():
    load_from_json(str(cfg_path))
    print(f"[CONFIG] Carregado: {cfg_path}")


class HelmetIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(130, 130)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        cx, cy = w/2, w/2
        r = w/2 - 4

        p.setPen(QPen(QColor("#B8860B"), 3))
        p.setBrush(QColor("#1A1A1A"))
        p.drawEllipse(QPointF(cx, cy), r, r)

        p.setPen(QPen(QColor("#FFD700"), 3))
        band = QRectF(cx - r*0.55, cy - r*0.55, r*1.1, r*1.1)
        p.drawArc(band, 30*16, 120*16)

        visor = QRectF(cx - r*0.5, cy - r*0.15, r*1.0, r*0.2)
        vg = QLinearGradient(visor.topLeft(), visor.bottomRight())
        vg.setColorAt(0, QColor("#8B6914"))
        vg.setColorAt(0.5, QColor("#FFD700"))
        vg.setColorAt(1, QColor("#8B6914"))
        p.setBrush(vg)
        p.setPen(QPen(QColor("#FFD700"), 1))
        p.drawRoundedRect(visor, 4, 4)

        p.setBrush(QColor("#FFD700"))
        p.setPen(Qt.NoPen)
        for i in range(3):
            y = cy + r*0.15 + i*10
            p.drawEllipse(QPointF(cx - r*0.65, y), 2.5, 2.5)
            p.drawEllipse(QPointF(cx + r*0.65, y), 2.5, 2.5)


class UnifiedCombatSystem:

    def __init__(self, user_nick, login_window=None):
        self.user_nick = user_nick
        self._login_window = login_window
        log(f"UnifiedCombatSystem init for user: {user_nick}")
        self.security = CombatSecurity()
        self._license_expiry = self.security.get_expiry(user_nick) if user_nick else "No License"
        self.executor = UnifiedCommandExecutor(enabled=True)
        log("Loading detector...")
        self.detector = UnifiedObjectDetector(method="template")
        log(f"Detector ready, method=template")
        log("Loading capturer...")
        self.capturer = ScreenCapturer(region=config.screen.region, target_fps=config.screen.target_fps)
        log("Capturer ready")
        self.running = True
        self.current_weapon_cfg = {
            "vertical": 5, "horizontal": 0,
            "progression": 0.35, "progression_limit": 10, 
            "progression_decay": 0.4, "interval_ms": 45
        }
        self.weapon_presets = self._load_presets()
        log(f"Loaded {len(self.weapon_presets)} weapon presets")

        self._init_nova_recoil()
        self.hud = TacticalHUD(user_nick)
        self.hud.toggle_signal.connect(self._toggle_system)
        self.hud.turbo_signal.connect(self._toggle_turbo)
        self.hud.param_change_signal.connect(self._update_params)
        self.hud.weapon_change_signal.connect(self._on_weapon_selected)
        self.hud.flat_recoil_signal.connect(self._on_flat_recoil)
        self.hud.save_preset_signal.connect(self._on_save_preset)
        self.hud.load_weapons(self.weapon_presets)
        self.hud.logout_signal.connect(self._logout)
        self.crosshair = CrosshairOverlay()
        self.hud.set_crosshair_overlay(self.crosshair)
        self.hud.update_license_time(self._license_expiry)
        self._manual_override = False
        self._home_was_down = False

        # Estado compartilhado (thread-safe: GIL protege atribuições simples)
        self._hud_fps = 0
        self._cap_fps = 0
        self._hud_slot1 = None
        self._hud_slot2 = None
        self._hud_burst = 0
        self._frame_queue = Queue(maxsize=2)

        self._alive = True

        # Sincroniza estado inicial com o HUD e ativa clipping
        self._toggle_system(True)

        # Timer para atualizar HUD na thread principal (evita crash Qt)
        self._hud_timer = QTimer()
        self._hud_timer.timeout.connect(self._sync_hud)
        self._hud_timer.start(100)  # ~10 fps

        self.pipeline_thread = threading.Thread(target=self._pipeline_loop, daemon=True)
        self.pipeline_thread.start()
        log("Pipeline thread started")

        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        log("Capture thread started")

    def _load_presets(self):
        import json
        base = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).parent
        presets = {}
        factory_path = base / "presets.json"
        if factory_path.exists():
            try:
                with open(factory_path) as f:
                    presets = json.load(f)
            except Exception as e:
                log(f"[PRESETS] Failed to load factory presets: {e}")
        user_path = Path(os.environ.get('APPDATA', Path.home())) / "Unified_AI_Combat" / "presets_user.json"
        if user_path.exists():
            try:
                with open(user_path) as f:
                    user_presets = json.load(f)
                for key, val in user_presets.items():
                    if key in presets:
                        presets[key].update(val)
                    else:
                        presets[key] = val
                log(f"[PRESETS] {len(user_presets)} user overrides loaded from {user_path}")
            except Exception as e:
                log(f"[PRESETS] Failed to load user presets: {e}")
        return presets

    def _init_nova_recoil(self):
        import json as _json
        base = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).parent
        recoil_path = base / "recoil_patterns.json"
        if not recoil_path.exists():
            log("[NOVA] recoil_patterns.json not found, skipping NOVA recoil")
            return
        try:
            with open(recoil_path, encoding="utf-8") as f:
                recoil_data = _json.load(f)
            self.executor.configure_nova_recoil(recoil_data)
            weapon_count = len(recoil_data.get("patterns", {}).get("none", {}))
            log(f"[NOVA] Weapon-specific recoil data loaded ({weapon_count} weapons)")
            for w, params in recoil_data.get("patterns", {}).get("none", {}).items():
                log(f"[NOVA]   {w}: {params}")
        except Exception as e:
            log(f"[NOVA] Failed to init: {e}")

    def _toggle_system(self, state):
        self.running = state
        self.executor.enabled = state
        self.hud._on = state
        self.hud.play_toggle_sound(state)
        if state:
            self.hud.toggle_btn.setText("SISTEMA ON")
            self.hud.ia_status_label.setText("ATIVADO")
            self.hud.ia_status_label.setStyleSheet("color: #00ff66; font-weight: bold; font-size: 12px; border: none; background: transparent;")
            self.hud.on_off_label.setStyleSheet("color: #00ff66; font-size: 22px; border: none; background: transparent;")
            self.hud.toggle_btn.setStyleSheet(
                "QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #00aa55,stop:0.5 #00ff66,stop:1 #00aa55);"
                "color:#000000;font-size:12px;font-weight:bold;border:none;border-radius:6px;}"
                "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #00cc66,stop:0.5 #33ff77,stop:1 #00cc66);}")
            self.executor.start_clipping()
        else:
            self.hud.toggle_btn.setText("SISTEMA OFF")
            self.hud.ia_status_label.setText("DESATIVADO")
            self.hud.ia_status_label.setStyleSheet("color: #ff3344; font-weight: bold; font-size: 12px; border: none; background: transparent;")
            self.hud.on_off_label.setStyleSheet("color: #ff3344; font-size: 22px; border: none; background: transparent;")
            self.hud.toggle_btn.setStyleSheet(
                "QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #cc2222,stop:0.5 #ff4444,stop:1 #cc2222);"
                "color:#FFFFFF;font-size:12px;font-weight:bold;border:none;border-radius:6px;}"
                "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #dd3333,stop:0.5 #ff5555,stop:1 #dd3333);}")
            self.executor.stop_clipping()
        self.hud.status_label.setText(f"SISTEMA: {'ATIVADO' if state else 'DESATIVADO'}")
        self.hud.status_label.setStyleSheet(f"color: {'#00ff66' if state else '#ff3344'}; font-size: 10px; font-weight: bold; border: none; background: transparent;")

    def _toggle_turbo(self, on):
        try:
            import psutil as _ps
            proc = _ps.Process()
            if on:
                proc.nice(_ps.HIGH_PRIORITY_CLASS)
                proc.cpu_affinity([0, 1, 2, 3, 4, 5, 6, 7])
                log("[TURBO] Modo Turbo ATIVADO: prioridade alta + 8 cores")
            else:
                proc.nice(_ps.NORMAL_PRIORITY_CLASS)
                log("[TURBO] Modo Turbo DESATIVADO: prioridade normal")
        except Exception as e:
            log(f"[TURBO] Erro: {e}")

    def _find_preset(self, name):
        if not name:
            return None
        lower = name.lower()
        for key in self.weapon_presets:
            if key.lower() == lower:
                return key
        return None

    def _on_weapon_selected(self, name):
        if name == "[ SELECIONE A ARMA ]":
            self._manual_override = False
            return
        preset_key = self._find_preset(name)
        if preset_key:
            self._manual_override = True
            cfg = dict(self.weapon_presets[preset_key])
            # Restaura ajuste por arma salvo (vertical/horizontal) se houver
            cfg.setdefault("adjust_vertical", 0.0)
            cfg.setdefault("adjust_horizontal", 0.0)
            self.current_weapon_cfg = cfg
            self.executor.set_adjust(cfg.get("adjust_vertical", 0.0), cfg.get("adjust_horizontal", 0.0))
            log(f"Weapon selected: {preset_key} -> {self.current_weapon_cfg}")
            # Atualiza UI para refletir os valores do preset/arma
            self.hud.param_vars.get("vertical") and self.hud.param_vars["vertical"].setValue(round(cfg.get("vertical", 0)))
            self.hud.param_vars.get("horizontal") and self.hud.param_vars["horizontal"].setValue(round(cfg.get("horizontal", 0)))

    def _on_save_preset(self):
        weapon_name = self._hud_slot1 or ""
        if not weapon_name:
            log("[PRESET] Nenhuma arma detectada/salvar")
            return
        import json
        import datetime
        appdata = Path(os.environ.get('APPDATA', Path.home())) / "Unified_AI_Combat"
        appdata.mkdir(parents=True, exist_ok=True)
        user_path = appdata / "presets_user.json"
        existing = {}
        if user_path.exists():
            try:
                with open(user_path) as f:
                    existing = json.load(f)
            except Exception:
                existing = {}
        cfg = dict(self.current_weapon_cfg)
        cfg["adjust_vertical"] = float(getattr(self.executor, "adjust_vertical", 0.0) or 0.0)
        cfg["adjust_horizontal"] = float(getattr(self.executor, "adjust_horizontal", 0.0) or 0.0)
        cfg["updated_at"] = datetime.datetime.now().isoformat()
        existing[weapon_name] = cfg
        with open(user_path, "w") as f:
            json.dump(existing, f, indent=2)
        log(f"[PRESET] Preset salvo para {weapon_name} -> {user_path}")
        self.weapon_presets[weapon_name] = cfg

    def _on_flat_recoil(self, state):
        self.executor.flat_recoil = state
        log(f"[FLAT RECOIL] {'ON' if state else 'OFF'}")

    def _update_params(self, key, value):
        if key.startswith("mod_"):
            attachment = key.replace("mod_", "")
            self.executor.update_modifier(attachment, value)
        elif key == "monitor_index":
            config.screen.monitor_index = int(value)
            self.capturer._init_backend()
        elif key == "resolution":
            config.screen.resolution = value
        elif key == "adjust":
            if isinstance(value, dict):
                self.executor.set_adjust(value.get("vertical", 0.0), value.get("horizontal", 0.0))
        elif self.current_weapon_cfg:
            self.current_weapon_cfg[key] = value

    def _sync_hud(self):
        try:
            active = self.running
            self.hud.update_ai_status(
                shots=self.executor.shot_counter,
                status="ACTIVE" if active else "READY",
                slot1=self._hud_slot1,
                slot2=self._hud_slot2,
                burst=self._hud_burst,
                fps=max(1, min(self._cap_fps, 999)),
                profiler=getattr(self, '_hud_profiler', None)
            )
            for key, val in self.current_weapon_cfg.items():
                if key in self.hud.param_vars:
                    display = int(val * 100) if key in ("progression", "progression_decay") else int(val)
                    if self.hud.param_vars[key].value() != display:
                        self.hud.param_vars[key].setValue(display)
        except RuntimeError:
            pass

    def _capture_loop(self):
        import time as _time
        _fps_cnt = 0
        _fps_acc = 0.0
        _t_last = _time.perf_counter()
        while self._alive:
            frame = self.capturer.grab() if hasattr(self.capturer, 'grab') else self.capturer.get_frame()
            if frame is not None:
                try:
                    self._frame_queue.put_nowait(frame)
                except:
                    pass
                _fps_cnt += 1
            _t_now = _time.perf_counter()
            _fps_acc += _t_now - _t_last
            _t_last = _t_now
            if _fps_acc >= 0.5:
                self._cap_fps = int(_fps_cnt / _fps_acc)
                _fps_cnt = 0
                _fps_acc = 0.0
            _time.sleep(1.0 / self.capturer.target_fps)

    def _pipeline_loop(self):
        log("Pipeline started (Anti-Recoil + Weapon Detection SLOT 1 & SLOT 2)")
        frame_count_total = 0
        slot1_weapon = None
        slot2_weapon = None
        auto_weapon = None
        CROSSHAIR_W = 160
        CROSSHAIR_H = 120
        CROSSHAIR_THRESHOLD = 38  # acima disso = alvo na mira (ajustar se precisar)

        # Profiling metrics
        import time as _time
        prof = {"capture": 0.0, "detect": 0.0, "recoil": 0.0}
        prof_count = {"capture": 0, "detect": 0, "recoil": 0}

        while self._alive:
            try:
                frame = None
                try:
                    frame = self._frame_queue.get_nowait()
                except Empty:
                    pass
                frame_count_total += 1

                t0 = _time.perf_counter()
                prof["capture"] += _time.perf_counter() - t0
                prof_count["capture"] += 1

                if frame is None:
                    time.sleep(1 / config.screen.target_fps)
                    continue

                # HOME key toggle (borda de subida)
                home_down = (ctypes.windll.user32.GetAsyncKeyState(0x24) & 0x8000) != 0
                if home_down and not self._home_was_down:
                    new_state = not self.running
                    self.hud.toggle_signal.emit(new_state)
                    self._home_was_down = True
                elif not home_down:
                    self._home_was_down = False

                if self.running:
                    # Detecta armas nos dois slots a cada 2 frames
                    if frame_count_total & 1:  # % 2
                        t1 = _time.perf_counter()
                        s1 = self.detector.detect_slot1(frame)
                        s2 = self.detector.detect_slot2(frame)
                        prof["detect"] += _time.perf_counter() - t1
                        prof_count["detect"] += 1

                        if s1:
                            slot1_weapon = s1
                        if s2:
                            slot2_weapon = s2

                        # Auto-select instantâneo: troca na primeira detecção
                        if not self._manual_override:
                            new_auto = s1 or s2
                            if new_auto and new_auto != auto_weapon:
                                auto_weapon = new_auto
                                self._last_detect_time = _time.monotonic()
                                preset_key = self._find_preset(auto_weapon)
                                if preset_key:
                                    self.current_weapon_cfg = dict(self.weapon_presets[preset_key])
                                    self.executor.set_current_weapon(auto_weapon)
                                    log(f"[ARMA DETECTADA] {auto_weapon} -> {preset_key}")

                    # Anti-Recoil ativado SOMENTE com botão direito pressionado
                    if (ctypes.windll.user32.GetAsyncKeyState(0x02) & 0x8000) != 0:
                        t2 = _time.perf_counter()
                        self.executor.execute_combat_step(self.current_weapon_cfg)
                        prof["recoil"] += _time.perf_counter() - t2
                        prof_count["recoil"] += 1
                    else:
                        self.executor.burst_ticks = 0
                        self.executor._last_recoil_time = 0.0

                # Atualiza estado compartilhado (timer _sync_hud le isto na main thread)
                self._hud_slot1 = slot1_weapon
                self._hud_slot2 = slot2_weapon
                self._hud_burst = self.executor.burst_ticks
                # Profile averages (ms)
                self._hud_profiler = {}
                for k in prof:
                    c = prof_count[k]
                    self._hud_profiler[k] = (prof[k] / c * 1000) if c > 0 else 0.0

            except Exception as e:
                log(f"PIPELINE ERROR: {e}")
                import traceback
                traceback.print_exc()

            time.sleep(1.0 / config.screen.target_fps)

    def _logout(self):
        sess_path = Path(os.environ.get('APPDATA', Path.home())) / "Unified_AI_Combat" / "session.json"
        if sess_path.exists():
            sess_path.unlink()
        log("[LOGOUT] Session deleted")
        self._alive = False
        self._hud_timer.stop()
        self.executor.stop_clipping()
        self.executor.enabled = False
        self.hud.close()
        if hasattr(self, 'pipeline_thread') and self.pipeline_thread.is_alive():
            self.pipeline_thread.join(timeout=2)
        if hasattr(self, 'capture_thread') and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2)

        def on_success(nick, window):
            window.close()
            new_system = UnifiedCombatSystem(user_nick=nick, login_window=window)
            new_system.run()

        login_win = LoginWindow(on_success=on_success, security=self.security)
        login_win.show()

    def closeEvent(self, event):
        self._alive = False
        self._hud_timer.stop()
        self.executor.stop_clipping()
        self.executor.enabled = False
        event.accept()

    def run(self):
        self.hud.show()


class RoundedContainer(QWidget):
    def __init__(self, parent=None, radius=25):
        super().__init__(parent)
        self._radius = radius
        self.setObjectName("RoundedContainer")
        self.setStyleSheet("""
            QWidget#RoundedContainer {
                background-color: #121212;
                border: 1.5px solid #D4AF37;
                border-radius: """ + str(radius) + """px;
            }
        """)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self._radius, self._radius)
        painter.setClipPath(path)
        super().paintEvent(event)


class LoginWindow(QWidget):
    def __init__(self, on_success, security=None):
        super().__init__()
        self.on_success = on_success
        self.security = security or CombatSecurity()
        self.poll_timer = None
        self.poll_nick = None
        self.poll_password = None
        self._drag_pos = QPoint()
        icon_path = str(Path(__file__).parent / "assets" / "logo.png")
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))
        self._build_ui()
        self._check_session()

    def _build_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(860, 960)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(50, 50, 50, 50)

        panel = RoundedContainer(radius=25)
        panel.setCursor(Qt.ArrowCursor)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor("#D4AF37"))
        shadow.setOffset(0, 0)
        panel.setGraphicsEffect(shadow)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(50, 35, 50, 30)
        layout.setSpacing(0)

        # Close button
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        close_btn = QPushButton("X")
        close_btn.setFixedSize(36, 36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #B0B0B0;
                font-size: 18px;
                font-weight: bold;
                border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 18px;
            }
            QPushButton:hover { color: #FF4444; border-color: #FF4444; }
        """)
        top_bar.addStretch()
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)

        # Logo no topo da tela de login
        logo_login = QLabel()
        logo_login.setAlignment(Qt.AlignCenter)
        logo_login.setFixedSize(180, 180)
        logo_login.setText("")
        logo_path = str(Path(__file__).parent / "assets" / "logo.png")
        if Path(logo_path).exists():
            pix = QPixmap(logo_path)
            logo_login.setPixmap(pix.scaled(logo_login.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            logo_login.setStyleSheet("border: none; background: transparent;")
        else:
            logo_login.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(logo_login, alignment=Qt.AlignCenter)

        layout.addSpacing(50)

        # Title
        title = QLabel("Bem-vindo de volta")
        title.setAlignment(Qt.AlignCenter)
        title.setMaximumWidth(640)
        title.setStyleSheet("color: #FFFFFF; font-size: 44px; font-weight: 700; border: none; background: transparent;")
        layout.addWidget(title, alignment=Qt.AlignCenter)

        layout.addSpacing(6)

        # Subtitle
        sub = QLabel("Acesse sua conta para continuar")
        sub.setAlignment(Qt.AlignCenter)
        sub.setMaximumWidth(640)
        sub.setStyleSheet("color: #A0A0A0; font-size: 21px; border: none; background: transparent;")
        layout.addWidget(sub, alignment=Qt.AlignCenter)

        layout.addSpacing(22)

        # Inputs
        self.u = QLineEdit()
        self._setup_input(self.u, "user", "Usuario")
        self.u.setMaximumWidth(640)
        layout.addWidget(self.u, alignment=Qt.AlignCenter)
        layout.addSpacing(20)

        self.p = QLineEdit()
        self._setup_input(self.p, "lock", "Senha", is_password=True)
        self.p.setMaximumWidth(640)
        layout.addWidget(self.p, alignment=Qt.AlignCenter)
        layout.addSpacing(20)

        self.k = QLineEdit()
        self._setup_input(self.k, "key", "Chave de Licenca")
        self.k.setMaximumWidth(640)
        layout.addWidget(self.k, alignment=Qt.AlignCenter)
        layout.addSpacing(8)

        # Lembrar checkbox
        self.remember_cb = QCheckBox("Lembrar dados de acesso")
        self.remember_cb.setStyleSheet("""
            QCheckBox {
                color: #B0B0B0;
                font-size: 15px;
                spacing: 8px;
                border: none;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #D4AF37;
                border-radius: 5px;
                background: #1E1E1E;
            }
            QCheckBox::indicator:checked {
                background: #D4AF37;
                border: 2px solid #FFD700;
            }
        """)
        self.remember_cb.setChecked(True)
        self.remember_cb.setMaximumWidth(640)
        layout.addWidget(self.remember_cb, alignment=Qt.AlignCenter)
        layout.addSpacing(8)

        # Status msg
        self.status_msg = QLabel("")
        self.status_msg.setAlignment(Qt.AlignCenter)
        self.status_msg.setWordWrap(True)
        self.status_msg.setMaximumWidth(640)
        self.status_msg.setStyleSheet("color: #FFD700; font-size: 13px; border: none; background: transparent;")
        layout.addWidget(self.status_msg, alignment=Qt.AlignCenter)

        layout.addSpacing(8)

        # Acessar button
        self.btn_access = QPushButton("  Acessar")
        self.btn_access.setCursor(Qt.PointingHandCursor)
        self.btn_access.setFixedHeight(70)
        self.btn_access.setMaximumWidth(640)
        self.btn_access.setIcon(self._create_icon("arrow", 24))
        self.btn_access.setIconSize(QSize(24, 24))

        btn_glow = QGraphicsDropShadowEffect()
        btn_glow.setBlurRadius(35)
        btn_glow.setColor(QColor("#FFD700"))
        btn_glow.setOffset(0, 0)
        self.btn_access.setGraphicsEffect(btn_glow)

        self.btn_access.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop: 0 #B8860B, stop: 0.3 #FFD700, stop: 0.7 #FFE44D, stop: 1 #B8860B);
                color: #000000;
                font-size: 27px;
                font-weight: 700;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop: 0 #D4A017, stop: 0.3 #FFE44D, stop: 0.7 #FFF3A0, stop: 1 #D4A017);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop: 0 #8B6914, stop: 1 #6B4F10);
            }
        """)
        self.btn_access.clicked.connect(self._activate)
        layout.addWidget(self.btn_access, alignment=Qt.AlignCenter)

        layout.addSpacing(22)

        # Divider "ou"
        div_wrap = QHBoxLayout()
        div_wrap.addStretch()
        div = QHBoxLayout()
        div.setSpacing(15)
        for _ in range(2):
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("background: rgba(212, 175, 55, 0.65); border: none; max-height: 1px;")
            line.setFixedHeight(1)
            div.addWidget(line)
            if _ == 0:
                ou = QLabel("ou")
                ou.setAlignment(Qt.AlignCenter)
                ou.setStyleSheet("color: #A0A0A0; font-size: 18px; border: none; background: transparent;")
                div.addWidget(ou)
        div_wrap.addLayout(div)
        div_wrap.addStretch()
        layout.addLayout(div_wrap)

        layout.addSpacing(20)

        # Bottom buttons
        bottom = QHBoxLayout()
        bottom.setSpacing(30)

        self.btn_register = QPushButton("Registrar")
        self.btn_register.setCursor(Qt.PointingHandCursor)
        self.btn_register.setFixedSize(315, 62)
        self.btn_register.setStyleSheet("""
            QPushButton {
                background: #2A2A2D;
                color: #FFFFFF;
                font-size: 21px;
                font-weight: 500;
                border: 1px solid #D4AF37;
                border-radius: 12px;
            }
            QPushButton:hover { background: rgba(212, 175, 55, 0.1); border: 1px solid #FFE44D; }
            QPushButton:pressed { background: rgba(212, 175, 55, 0.2); }
        """)
        self.btn_register.clicked.connect(self._register)

        self.btn_activate = QPushButton("Ativar")
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.setFixedSize(315, 62)
        self.btn_activate.setStyleSheet("""
            QPushButton {
                background: #2A2A2D;
                color: #FFFFFF;
                font-size: 21px;
                font-weight: 500;
                border: 1px solid #D4AF37;
                border-radius: 12px;
            }
            QPushButton:hover { background: rgba(212, 175, 55, 0.1); border: 1px solid #FFE44D; }
            QPushButton:pressed { background: rgba(212, 175, 55, 0.2); }
        """)
        self.btn_activate.clicked.connect(self._activate)

        bottom.addStretch()
        bottom.addWidget(self.btn_register)
        bottom.addWidget(self.btn_activate)
        bottom.addStretch()
        layout.addLayout(bottom)

        layout.addSpacing(8)

        outer.addWidget(panel)

    def _create_icon(self, icon_type, size=22):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor("#FFD700")
        p.setPen(QPen(col, 2))
        c = size / 2

        if icon_type == "user":
            p.drawEllipse(QPointF(c, c-4), 3.5, 3.5)
            path = QPainterPath(QPointF(c-5, c+9))
            path.lineTo(c-3, c+1)
            path.lineTo(c+3, c+1)
            path.lineTo(c+5, c+9)
            p.drawPath(path)
        elif icon_type == "lock":
            p.drawArc(QRectF(c-5, c-6, 10, 9), 180*16, 180*16)
            p.drawRoundedRect(QRectF(c-6, c-2, 12, 9), 2, 2)
        elif icon_type == "key":
            p.drawEllipse(QPointF(c-5, c), 4, 4)
            p.drawLine(QPointF(c-1, c), QPointF(c+7, c))
            p.drawLine(QPointF(c+7, c), QPointF(c+7, c+4))
            p.drawLine(QPointF(c+3, c), QPointF(c+3, c+3))
        elif icon_type == "eye":
            p.drawArc(QRectF(c-5, c-3.5, 10, 7), 0, 360*16)
            p.drawEllipse(QPointF(c, c), 1.5, 1.5)
        elif icon_type == "scan":
            p.drawRect(QRectF(c-4.5, c-4.5, 9, 9))
            p.setPen(QPen(col, 1.5))
            p.drawLine(QPointF(c-1, c-5), QPointF(c-1, c+5))
            p.drawLine(QPointF(c+1, c-5), QPointF(c+1, c+5))
        elif icon_type == "arrow":
            p.setPen(QPen(QColor("#000000"), 3))
            p.drawLine(QPointF(3, c), QPointF(size-3, c))
            p.drawLine(QPointF(size-8, 4), QPointF(size-3, c))
            p.drawLine(QPointF(size-8, size-4), QPointF(size-3, c))

        p.end()
        return QIcon(pm)

    def _setup_input(self, le, icon_type, placeholder, is_password=False):
        le.setPlaceholderText(placeholder)
        le.setFixedHeight(72)
        le.setStyleSheet("""
            QLineEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1.5px solid #555555;
                border-radius: 12px;
                padding: 0 50px;
                font-size: 20px;
                selection-background-color: #D4AF37;
                selection-color: #000000;
            }
            QLineEdit:focus {
                border: 1.5px solid #D4AF37;
            }
            QLineEdit::placeholder {
                color: #666666;
            }
        """)
        le.addAction(self._create_icon(icon_type), QLineEdit.LeadingPosition)
        if is_password:
            le.setEchoMode(QLineEdit.Password)
            eye = le.addAction(self._create_icon("eye"), QLineEdit.TrailingPosition)
            eye.triggered.connect(lambda checked, l=le: self._toggle_eye(l))
        if icon_type == "key":
            le.addAction(self._create_icon("scan"), QLineEdit.TrailingPosition)

    def _toggle_eye(self, le):
        le.setEchoMode(QLineEdit.Normal if le.echoMode() == QLineEdit.Password else QLineEdit.Password)

    def _check_session(self):
        sess = self.security.get_session()
        if sess:
            self.u.setText(sess.get("nick", ""))
            self.p.setText(sess.get("password", ""))
            self.k.setText(sess.get("key", ""))
            self.remember_cb.setChecked(sess.get("remember", False))

    def _safe_activate(self):
        try:
            if self.isVisible():
                self._activate()
        except Exception as e:
            print(f"[AUTO-LOGIN] {e}")
            self.status_msg.setText(f"Erro no auto-login: {e}")
            self.status_msg.setStyleSheet("color: #ff4444; font-size: 11px; border: none; background: transparent;")

    def _register(self):
        nick = self.u.text().strip()
        password = self.p.text().strip()
        if not nick or not password:
            self.status_msg.setText("Preencha USER e PASSWORD.")
            self.status_msg.setStyleSheet("color: #ff4444; font-size: 11px; border: none; background: transparent;")
            return

        self.status_msg.setText("Enviando cadastro...")
        QApplication.processEvents()

        success, msg = self.security.register_user(nick, password)
        if success:
            self.status_msg.setText(msg)
            self.status_msg.setStyleSheet("color: #00ffaa; font-size: 11px; border: none; background: transparent;")
            self._start_polling(nick, password)
        else:
            self.status_msg.setText(msg)
            self.status_msg.setStyleSheet("color: #ff4444; font-size: 11px; border: none; background: transparent;")

    def _start_polling(self, nick, password):
        if self.poll_timer:
            self.poll_timer.stop()
        self.poll_nick = nick
        self.poll_password = password
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self._safe_check_approval)
        self.poll_timer.start(5000)

    def _safe_check_approval(self):
        try:
            self._check_approval()
        except Exception as e:
            print(f"[POLL ERROR] {e}")

    def _check_approval(self):
        if not hasattr(self, 'poll_nick') or not self.poll_nick:
            return
        status, result = self.security.check_user_status(self.poll_nick, self.poll_password)
        if status == 'approved':
            if self.poll_timer:
                self.poll_timer.stop()
            if result and not result.startswith("Conta"):
                self.k.setText(result)
                self.status_msg.setText("CONTA APROVADA! Ativando licenca...")
                self.status_msg.setStyleSheet("color: #00ffaa; font-size: 11px; border: none; background: transparent;")
                QApplication.processEvents()
                success, msg = self.security.activate_license(self.poll_nick, self.poll_password, result)
                if success:
                    self.security.save_session(self.poll_nick, self.poll_password, result, self.remember_cb.isChecked())
                    self.status_msg.setText("Licenca ativada! Iniciando...")
                    QApplication.processEvents()
                    self.on_success(self.poll_nick, self)
                else:
                    self.status_msg.setText(msg)
                    self.status_msg.setStyleSheet("color: #ff4444; font-size: 11px; border: none; background: transparent;")
            else:
                self.status_msg.setText("CONTA APROVADA! Insira sua chave abaixo e clique ATIVAR.")
                self.status_msg.setStyleSheet("color: #00ffaa; font-size: 11px; border: none; background: transparent;")

    def _activate(self):
        nick = self.u.text().strip()
        password = self.p.text().strip()
        key = self.k.text().strip()

        if not nick or not password:
            self.status_msg.setText("Preencha USER e PASSWORD.")
            self.status_msg.setStyleSheet("color: #ff4444; font-size: 11px; border: none; background: transparent;")
            return

        if key:
            success, msg = self.security.activate_license(nick, password, key)
            if success:
                self.security.save_session(nick, password, key, self.remember_cb.isChecked())
                self.status_msg.setText("Licenca ativada! Iniciando...")
                QApplication.processEvents()
                self.on_success(nick, self)
            else:
                self.status_msg.setText(msg)
                self.status_msg.setStyleSheet("color: #ff4444; font-size: 11px; border: none; background: transparent;")
            return

        status, result = self.security.check_user_status(nick, password)

        if status == 'pending':
            self.status_msg.setText("Cadastro pendente. Aguarde aprovacao do admin.")
            self.status_msg.setStyleSheet("color: #ffff00; font-size: 11px; border: none; background: transparent;")
        elif status == 'approved':
            if result:
                self.k.setText(result)
                self.status_msg.setText("Conta aprovada! Ativando licenca...")
                QApplication.processEvents()
                success, msg = self.security.activate_license(nick, password, result)
                if success:
                    self.security.save_session(nick, password, result, self.remember_cb.isChecked())
                    self.status_msg.setText("Licenca ativada! Iniciando...")
                    QApplication.processEvents()
                    self.on_success(nick, self)
                else:
                    self.status_msg.setText(msg)
                    self.status_msg.setStyleSheet("color: #ff4444; font-size: 11px; border: none; background: transparent;")
            else:
                self.status_msg.setText("Conta aprovada! Insira sua chave fornecida pelo admin.")
                self.status_msg.setStyleSheet("color: #00ffaa; font-size: 11px; border: none; background: transparent;")
        elif status == 'not_found':
            self.status_msg.setText("Usuario nao encontrado. Clique em REGISTRAR.")
            self.status_msg.setStyleSheet("color: #ff4444; font-size: 11px; border: none; background: transparent;")
        else:
            self.status_msg.setText(result or "Erro desconhecido.")
            self.status_msg.setStyleSheet("color: #ff4444; font-size: 11px; border: none; background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)


def main():
    app = QApplication(sys.argv)
    security = CombatSecurity()

    def start_app(nick, window):
        global combat_system
        try:
            window.close()
            combat_system = UnifiedCombatSystem(user_nick=nick, login_window=window)
            combat_system.run()
        except Exception as e:
            import traceback
            traceback.print_exc()
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(e), "Erro ao iniciar", 0x10)

    login_win = LoginWindow(on_success=start_app, security=security)
    login_win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()