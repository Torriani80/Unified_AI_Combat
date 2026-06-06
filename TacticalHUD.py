import sys, os, time, ctypes, winsound, threading
import ctypes.wintypes
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSpinBox, QComboBox, QSlider,
    QFrame, QApplication, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QEvent
from PyQt5.QtGui import QColor, QFont, QIcon, QKeySequence
from logger import log

try:
    import wmi
    _WMI_AVAILABLE = True
except ImportError:
    _WMI_AVAILABLE = False

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

user32 = ctypes.windll.user32

def _play_sound(name):
    def _play():
        try:
            base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            wav_path = os.path.join(base, 'sounds', name.replace('.mp3', '.wav'))
            mp3_path = os.path.join(base, 'sounds', name)
            if os.path.exists(wav_path):
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif os.path.exists(mp3_path):
                winsound.PlaySound(mp3_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            log(f"[SOUND] Error: {e}")
    threading.Thread(target=_play, daemon=True).start()

class TacticalHUD(QWidget):
    toggle_signal = pyqtSignal(bool)
    param_change_signal = pyqtSignal(str, object)
    weapon_change_signal = pyqtSignal(str)
    flat_recoil_signal = pyqtSignal(bool)
    save_preset_signal = pyqtSignal()
    logout_signal = pyqtSignal()
    turbo_signal = pyqtSignal(bool)

    def __init__(self, user_nick):
        super().__init__()
        self.user_nick = user_nick
        self._on = True
        self._turbo_on = False
        self.oldPos = QPoint()
        self._calib_value = 95
        self.current_weapon = "[ SELECIONE ]"
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._build_ui()
        self._start_keybinds()

    def _build_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(900, 640)
        target = QApplication.primaryScreen().availableGeometry()
        self.move(target.x() + target.width() - 920, target.y() + 20)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(15, 15, 15, 15)

        self.container = QFrame()
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            QFrame#MainContainer {
                background-color: rgba(10, 10, 10, 200);
                border: 2px solid #D4AF37;
                border-radius: 22px;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(45)
        shadow.setColor(QColor(212, 175, 55, 180))
        shadow.setOffset(0, 0)
        self.container.setGraphicsEffect(shadow)
        outer.addWidget(self.container)

        content = QVBoxLayout(self.container)
        content.setContentsMargins(25, 15, 25, 20)
        content.setSpacing(10)

        # Header
        top = QHBoxLayout()
        top.addStretch()
        for txt, hov in [("_", "#D4AF37"), ("X", "#FF4444")]:
            b = QPushButton(txt)
            b.setFixedSize(28, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip("Minimizar" if txt == "_" else "Fechar")
            b.setStyleSheet(f"QPushButton{{background:transparent;color:#808080;font-size:14px;font-weight:bold;border:1px solid rgba(212,175,55,0.3);border-radius:14px;}}QPushButton:hover{{color:{hov};border-color:{hov};}}")
            b.clicked.connect(self.showMinimized if txt == "_" else self.close)
            top.addWidget(b)
        content.addLayout(top)

        title = QLabel("UNIFIED COMBAT SYSTEM")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #D4AF37; font-size: 22px; font-weight: bold; border: none; background: transparent;")
        content.addWidget(title)

        user_lbl = QLabel(f"JOGADOR: {self.user_nick.upper()}")
        user_lbl.setAlignment(Qt.AlignCenter)
        user_lbl.setStyleSheet("color: #808080; font-size: 10px; border: none; background: transparent;")
        content.addWidget(user_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(212,175,55,0.3); border: none;")
        content.addWidget(sep)

        # Body: 2 columns
        body = QHBoxLayout()
        body.setSpacing(12)

        # ========== LEFT COLUMN ==========
        left = QVBoxLayout()
        left.setSpacing(8)

        # Card: Status do Sistema
        c1 = self._card("STATUS DO SISTEMA")
        c1l = c1.layout()
        c1l.setContentsMargins(12, 8, 12, 8)
        c1l.setSpacing(4)

        status_row = QHBoxLayout()
        self.on_off_label = QLabel("●")
        self.on_off_label.setFixedSize(18, 18)
        self.on_off_label.setAlignment(Qt.AlignCenter)
        self.on_off_label.setStyleSheet("color: #00ff66; font-size: 22px; border: none; background: transparent;")
        status_row.addWidget(self.on_off_label)

        self.ia_status_label = QLabel("ATIVADO")
        self.ia_status_label.setStyleSheet("color: #00ff66; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        status_row.addWidget(self.ia_status_label)
        status_row.addStretch()
        c1l.addLayout(status_row)

        self.weapon_label = QLabel("ARMA: [ SELECIONE ]")
        self.weapon_label.setStyleSheet("color: #D4AF37; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        c1l.addWidget(self.weapon_label)

        self.shot_label = QLabel("TIROS: 0")
        self.shot_label.setStyleSheet("color: #D4AF37; font-family: Consolas; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        c1l.addWidget(self.shot_label)

        left.addWidget(c1)

        # Card: Configurações
        c2 = self._card("CONFIGURACOES")
        c2l = c2.layout()
        c2l.setContentsMargins(12, 8, 12, 8)
        c2l.setSpacing(4)

        conf_row = QHBoxLayout()
        mon_row = QVBoxLayout()
        mon_lbl = QLabel("Monitor:")
        mon_lbl.setStyleSheet("color: #B0B0B0; font-size: 10px; border: none; background: transparent;")
        mon_row.addWidget(mon_lbl)
        self.mon_combo = QComboBox()
        self.mon_combo.addItems(["1", "2", "3", "4"])
        self.mon_combo.setFixedWidth(50)
        self.mon_combo.setToolTip("Seleciona o monitor para captura")
        self.mon_combo.setStyleSheet(self._combo_css())
        self.mon_combo.currentTextChanged.connect(lambda v: self.param_change_signal.emit("monitor_index", v))
        mon_row.addWidget(self.mon_combo)
        conf_row.addLayout(mon_row)

        res_row = QVBoxLayout()
        res_lbl = QLabel("Resolucao:")
        res_lbl.setStyleSheet("color: #B0B0B0; font-size: 10px; border: none; background: transparent;")
        res_row.addWidget(res_lbl)
        self.res_combo = QComboBox()
        self.res_combo.addItems(["1920x1080", "2560x1440", "3440x1440", "2560x1080", "1728x1080", "1440x1080", "1600x900", "1366x768"])
        self.res_combo.setFixedWidth(100)
        self.res_combo.setToolTip("Resolucao do jogo")
        self.res_combo.setStyleSheet(self._combo_css())
        self.res_combo.currentTextChanged.connect(lambda v: self.param_change_signal.emit("resolution", v))
        res_row.addWidget(self.res_combo)
        conf_row.addLayout(res_row)
        conf_row.addStretch()
        c2l.addLayout(conf_row)

        self.flat_checkbox = QCheckBox("RECOIL CONSTANTE")
        self.flat_checkbox.setToolTip("Mantem o recoil constante sem progressao")
        self.flat_checkbox.setStyleSheet("""
            QCheckBox { color: #B0B0B0; font-size: 10px; spacing: 6px; border: none; background: transparent; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid #D4AF37; border-radius: 4px; background: #1E1E1E; }
            QCheckBox::indicator:checked { background: #D4AF37; }
        """)
        self.flat_checkbox.stateChanged.connect(lambda s: self.flat_recoil_signal.emit(s == 2))
        c2l.addWidget(self.flat_checkbox)

        left.addWidget(c2)

        # Card: Parâmetros de Recuo
        c4 = self._card("PARAMETROS DE RECUO")
        c4l = c4.layout()
        c4l.setContentsMargins(12, 8, 12, 8)
        c4l.setSpacing(4)

        self.param_vars = {}
        params = [
            ("VERTICAL", "vertical", -100, 100, 5),
            ("HORIZONTAL", "horizontal", -50, 50, 0),
        ]
        for label_text, key, from_val, to_val, default in params:
            row = QHBoxLayout()
            row.setSpacing(6)

            btn_left = QPushButton("◀")
            btn_left.setFixedSize(20, 20)
            btn_left.setCursor(Qt.PointingHandCursor)
            btn_left.setToolTip("Diminuir valor")
            btn_left.setStyleSheet("QPushButton{background:#1E1E1E;color:#D4AF37;font-size:10px;font-weight:bold;border:1px solid #444;border-radius:3px;}QPushButton:hover{background:#2A2A2D;border-color:#D4AF37;}")
            step = -1 if key == "vertical" else -1
            btn_left.clicked.connect(lambda _, k=key, s=step: self._emit_value(k, s))
            row.addWidget(btn_left)

            lbl = QLabel(label_text)
            lbl.setFixedWidth(80)
            lbl.setStyleSheet("color: #B0B0B0; font-size: 10px; border: none; background: transparent;")
            row.addWidget(lbl)

            spin = QSpinBox()
            spin.setRange(from_val, to_val)
            spin.setValue(default)
            spin.setFixedWidth(60)
            spin.setStyleSheet("QSpinBox{background:#1E1E1E;color:#D4AF37;border:1px solid #444;border-radius:4px;padding:2px 4px;font-size:10px;}QSpinBox::up-button,QSpinBox::down-button{width:14px;background:#2A2A2D;border:none;}")
            spin.valueChanged.connect(lambda v, k=key: self.param_change_signal.emit(k, v))
            row.addWidget(spin)
            self.param_vars[key] = spin

            btn_right = QPushButton("▶")
            btn_right.setFixedSize(20, 20)
            btn_right.setCursor(Qt.PointingHandCursor)
            btn_right.setToolTip("Aumentar valor")
            btn_right.setStyleSheet("QPushButton{background:#1E1E1E;color:#D4AF37;font-size:10px;font-weight:bold;border:1px solid #444;border-radius:3px;}QPushButton:hover{background:#2A2A2D;border-color:#D4AF37;}")
            btn_right.clicked.connect(lambda _, k=key, s=1: self._emit_value(k, s))
            row.addWidget(btn_right)

            row.addStretch()
            c4l.addLayout(row)

        save_btn = QPushButton("SALVAR PRESET")
        save_btn.setFixedHeight(22)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setToolTip("Salva as configuracoes atuais como preset")
        save_btn.setStyleSheet("QPushButton{background:#1E1E1E;color:#D4AF37;font-size:9px;font-weight:bold;border:1px solid #D4AF37;border-radius:4px;padding:0 8px;}QPushButton:hover{background:rgba(212,175,55,0.15);}")
        save_btn.clicked.connect(lambda: self.save_preset_signal.emit())
        c4l.addWidget(save_btn)

        left.addWidget(c4)

        # Card: Calibragem
        c_cal = self._card("CALIBRAGEM")
        c_cal_l = c_cal.layout()
        c_cal_l.setContentsMargins(12, 8, 12, 8)
        c_cal_l.setSpacing(4)

        cal_row = QHBoxLayout()
        cal_lbl = QLabel("Sense:")
        cal_lbl.setStyleSheet("color: #B0B0B0; font-size: 10px; border: none; background: transparent;")
        cal_row.addWidget(cal_lbl)

        self.calib_slider = QSlider(Qt.Horizontal)
        self.calib_slider.setRange(50, 200)
        self.calib_slider.setValue(self._calib_value)
        self.calib_slider.setFixedWidth(120)
        self.calib_slider.setToolTip("Ajuste de sensibilidade do mouse")
        self.calib_slider.valueChanged.connect(self._on_calib_changed)
        cal_row.addWidget(self.calib_slider)

        self.calib_value_label = QLabel(str(self._calib_value))
        self.calib_value_label.setStyleSheet("color: #D4AF37; font-family: Consolas; font-size: 12px; border: none; background: transparent;")
        cal_row.addWidget(self.calib_value_label)
        c_cal_l.addLayout(cal_row)

        calib_btn = QPushButton("REGISTRAR CALIBRAGEM")
        calib_btn.setFixedHeight(24)
        calib_btn.setCursor(Qt.PointingHandCursor)
        calib_btn.setToolTip("Aplica o valor de calibragem ao sistema")
        calib_btn.setStyleSheet("QPushButton{background:#1E1E1E;color:#D4AF37;font-size:9px;font-weight:bold;border:1px solid #D4AF37;border-radius:4px;padding:0 8px;}QPushButton:hover{background:rgba(212,175,55,0.15);}")
        calib_btn.clicked.connect(self._register_calibration)
        c_cal_l.addWidget(calib_btn)

        left.addWidget(c_cal)
        body.addLayout(left)

        # ========== RIGHT COLUMN ==========
        right = QVBoxLayout()
        right.setSpacing(8)

        # Card: Slots e Armas
        c3 = self._card("SLOTS E ARMAS")
        c3l = c3.layout()
        c3l.setContentsMargins(12, 8, 12, 8)
        c3l.setSpacing(4)

        self.slot1_label = QLabel("SLOT 1: Selecione o Slot 1")
        self.slot1_label.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        c3l.addWidget(self.slot1_label)

        self.slot2_label = QLabel("SLOT 2: Selecione o Slot 2")
        self.slot2_label.setStyleSheet("color: #B0B0B0; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        c3l.addWidget(self.slot2_label)

        weapon_row = QHBoxLayout()
        weapon_row.setSpacing(6)
        wep_lbl = QLabel("ARMA:")
        wep_lbl.setStyleSheet("color: #D4AF37; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        weapon_row.addWidget(wep_lbl)
        self.weapon_combo = QComboBox()
        self.weapon_combo.setStyleSheet(self._combo_css())
        self.weapon_combo.setMinimumWidth(160)
        self.weapon_combo.setToolTip("Seleciona arma manualmente (desativa deteccao automatica)")
        self.weapon_combo.currentTextChanged.connect(self._on_weapon_changed)
        weapon_row.addWidget(self.weapon_combo)
        weapon_row.addStretch()
        c3l.addLayout(weapon_row)

        right.addWidget(c3)

        # Card: Informacoes
        c5 = self._card("INFORMACOES")
        c5l = c5.layout()
        c5l.setContentsMargins(12, 8, 12, 8)
        c5l.setSpacing(4)

        self.timer_label = QLabel("TIME: --:--")
        self.timer_label.setStyleSheet("color: #ffcc00; font-family: Consolas; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        c5l.addWidget(self.timer_label)

        self.license_label = QLabel("LICENCA: --")
        self.license_label.setStyleSheet("color: #808080; font-family: Consolas; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        c5l.addWidget(self.license_label)

        # Card: Hardware (novo, no lugar do espaço vazio)
        c_hw = self._card("HARDWARE")
        c_hw_l = c_hw.layout()
        c_hw_l.setContentsMargins(12, 8, 12, 8)
        c_hw_l.setSpacing(4)

        self.cpu_label = QLabel("CPU: --")
        self.cpu_label.setStyleSheet("color: #B0B0B0; font-size: 10px; border: none; background: transparent;")
        c_hw_l.addWidget(self.cpu_label)

        self.gpu_label = QLabel("GPU: --")
        self.gpu_label.setStyleSheet("color: #B0B0B0; font-size: 10px; border: none; background: transparent;")
        c_hw_l.addWidget(self.gpu_label)

        self.ram_label = QLabel("RAM: --")
        self.ram_label.setStyleSheet("color: #B0B0B0; font-size: 10px; border: none; background: transparent;")
        c_hw_l.addWidget(self.ram_label)

        self.cap_label = QLabel("CAP: --")
        self.cap_label.setStyleSheet("color: #00ff66; font-size: 10px; border: none; background: transparent;")
        c_hw_l.addWidget(self.cap_label)

        self.cpu_uso_label = QLabel("CPU USO: --%")
        self.cpu_uso_label.setStyleSheet("color: #ff9944; font-size: 10px; border: none; background: transparent;")
        c_hw_l.addWidget(self.cpu_uso_label)

        self.profiler_label = QLabel("LAT: --/--/-- ms")
        self.profiler_label.setStyleSheet("color: #888888; font-size: 9px; border: none; background: transparent;")
        c_hw_l.addWidget(self.profiler_label)

        right.addWidget(c5)
        right.addWidget(c_hw)

        self.turbo_btn = QPushButton("TURBO: OFF")
        self.turbo_btn.setFixedHeight(24)
        self.turbo_btn.setCursor(Qt.PointingHandCursor)
        self.turbo_btn.setToolTip("Ativa prioridade maxima de CPU (8 nucleos)")
        self.turbo_btn.setStyleSheet(
            "QPushButton{background:#1E1E1E;color:#ff9944;font-size:9px;font-weight:bold;border:1px solid #ff9944;border-radius:4px;padding:0 8px;}"
            "QPushButton:hover{background:rgba(255,153,68,0.15);}"
            "QPushButton:pressed{background:rgba(255,153,68,0.3);}")
        self.turbo_btn.clicked.connect(self._toggle_turbo)
        right.addWidget(self.turbo_btn)

        self.toggle_btn = QPushButton("SISTEMA ON")
        self.toggle_btn.setFixedHeight(30)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setToolTip("Liga/Desliga o anti-recoil")
        self.toggle_btn.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #00aa55,stop:0.5 #00ff66,stop:1 #00aa55);"
            "color:#000000;font-size:12px;font-weight:bold;border:none;border-radius:6px;}"
            "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #00cc66,stop:0.5 #33ff77,stop:1 #00cc66);}")
        self.toggle_btn.clicked.connect(self._toggle)
        right.addWidget(self.toggle_btn)

        right.addStretch()

        body.addLayout(right)
        content.addLayout(body)

        # Footer
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: rgba(212,175,55,0.3); border: none;")
        content.addWidget(sep2)

        foot = QHBoxLayout()
        self.status_label = QLabel("SISTEMA: ATIVADO")
        self.status_label.setStyleSheet("color: #00ff66; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        foot.addWidget(self.status_label)
        foot.addStretch()

        home_hint = QLabel("HOME: ON/OFF | F5: RESET | F6: MIN | F10: SAIR")
        home_hint.setToolTip("Atalhos de teclado")
        home_hint.setStyleSheet("color: #555555; font-size: 9px; border: none; background: transparent;")
        foot.addWidget(home_hint)
        foot.addSpacing(10)

        logout_btn = QPushButton("SAIR DA CONTA")
        logout_btn.setFixedHeight(26)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setToolTip("Retorna para a tela de login")
        logout_btn.setStyleSheet("QPushButton{background:#1E1E1E;color:#D4AF37;font-size:9px;font-weight:bold;border:1px solid #D4AF37;border-radius:6px;padding:0 12px;}QPushButton:hover{background:rgba(212,175,55,0.15);}")
        logout_btn.clicked.connect(lambda: self.logout_signal.emit())
        foot.addWidget(logout_btn)

        exit_btn = QPushButton("FECHAR SISTEMA")
        exit_btn.setFixedHeight(26)
        exit_btn.setCursor(Qt.PointingHandCursor)
        exit_btn.setToolTip("Fecha o programa completamente")
        exit_btn.setStyleSheet("QPushButton{background:#1E1E1E;color:#FF4444;font-size:9px;font-weight:bold;border:1px solid #FF4444;border-radius:6px;padding:0 12px;}QPushButton:hover{background:rgba(255,68,68,0.15);}")
        exit_btn.clicked.connect(lambda: self._release_and_exit())
        foot.addWidget(exit_btn)
        content.addLayout(foot)

        # Timer para atualizar hardware
        self.hw_timer = QTimer()
        self.hw_timer.timeout.connect(self._refresh_hardware)
        self.hw_timer.start(2000)
        self._wmi_conn = wmi.WMI() if _WMI_AVAILABLE else None
        self._refresh_hardware()

        self._countdown_seconds = 0
        self._is_lifetime = False
        self._cd_timer = QTimer()
        self._cd_timer.timeout.connect(self._tick)
        self._cd_timer.start(1000)

    def _card(self, title):
        f = QFrame()
        f.setObjectName("Card")
        f.setStyleSheet("""
            QFrame#Card {
                background-color: rgba(18, 18, 18, 200);
                border: 1px solid rgba(212,175,55,0.3);
                border-radius: 10px;
            }
        """)
        l = QVBoxLayout(f)
        l.setContentsMargins(12, 8, 12, 8)
        tl = QLabel(title)
        tl.setStyleSheet("color: #D4AF37; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        l.addWidget(tl)
        return f

    def play_toggle_sound(self, on):
        _play_sound("on.mp3" if on else "off.mp3")

    def _combo_css(self):
        return ("QComboBox{background:#1E1E1E;color:#D4AF37;border:1px solid #444;border-radius:4px;padding:2px 6px;font-size:10px;}"
                "QComboBox::drop-down{border:none;width:16px;}"
                "QComboBox::down-arrow{image:none;border-left:4px solid transparent;border-right:4px solid transparent;border-top:5px solid #D4AF37;}"
                "QComboBox QAbstractItemView{background:#1E1E1E;color:#B0B0B0;selection-background-color:#D4AF37;selection-color:#000000;border:1px solid #D4AF37;}")

    def _on_calib_changed(self, value):
        self._calib_value = value
        self.calib_value_label.setText(str(value))

    def _register_calibration(self):
        self.param_change_signal.emit("calib_sense", self._calib_value)
        log(f"CALIBRAGEM registrada: sense={self._calib_value}")

    def _refresh_hardware(self):
        try:
            if self._wmi_conn:
                cpu = self._wmi_conn.Win32_Processor()[0]
                self.cpu_label.setText(f"CPU: {cpu.Name.strip()}")
                gpu = self._wmi_conn.Win32_VideoController()[0]
                self.gpu_label.setText(f"GPU: {gpu.Name.strip()}")
                ram = self._wmi_conn.Win32_ComputerSystem()[0]
                total_ram = int(ram.TotalPhysicalMemory) / (1024**3)
                self.ram_label.setText(f"RAM: {total_ram:.1f} GB")
            elif _PSUTIL_AVAILABLE:
                self.cpu_label.setText(f"CPU: {psutil.cpu_percent(interval=None)}%")
                self.gpu_label.setText("GPU: N/A (wmi ausente)")
                mem = psutil.virtual_memory()
                self.ram_label.setText(f"RAM: {mem.used/1024**3:.1f}/{mem.total/1024**3:.1f} GB")
            else:
                raise RuntimeError("Nenhum modulo de hardware disponivel")
            if _PSUTIL_AVAILABLE:
                self.cpu_uso_label.setText(f"CPU USO: {psutil.cpu_percent(interval=None)}%")
        except Exception as e:
            log(f"[HARDWARE] Refresh failed: {e}")
            self.cpu_label.setText("CPU: N/A")
            self.gpu_label.setText("GPU: N/A")
            self.cpu_uso_label.setText("CPU USO: --%")
            self.ram_label.setText("RAM: --")

    def _start_keybinds(self):
        from PyQt5.QtWidgets import QShortcut as _QShortcut
        _QShortcut(QKeySequence(Qt.Key_F5), self, self._reset_weapon_state)
        _QShortcut(QKeySequence(Qt.Key_F6), self, self._toggle_minimize)
        _QShortcut(QKeySequence(Qt.Key_F10), self, self._release_and_exit)

    def customEvent(self, event):
        pass

    def _reset_weapon_state(self):
        self.shot_label.setText("TIROS: 0")
        self.current_weapon = "[ SELECIONE ]"
        self.weapon_label.setText("ARMA: [ SELECIONE ]")
        log("CALIBRAGEM: reset de arma (F5)")

    def load_weapons(self, presets: dict):
        try:
            self.weapon_combo.currentTextChanged.disconnect(self._on_weapon_changed)
        except TypeError:
            pass
        self.weapon_combo.clear()
        self.weapon_combo.addItem("[ SELECIONE A ARMA ]")
        cats = {"AR": "Rifles de Assalto", "SMG": "SMGs", "DMR": "DMRs", "LMG": "Metralhadoras", "SG": "Escopetas"}
        for cat_code, cat_name in cats.items():
            guns = [n for n, p in presets.items() if p.get("category") == cat_code]
            if guns:
                self.weapon_combo.addItem(f"-- {cat_name} --")
                idx = self.weapon_combo.count() - 1
                self.weapon_combo.model().item(idx).setEnabled(False)
                for g in sorted(guns):
                    self.weapon_combo.addItem(f"  {g}")
        self.weapon_combo.currentTextChanged.connect(self._on_weapon_changed)

    def _on_weapon_changed(self, name):
        name = name.strip()
        if name.startswith("[") or name.startswith("--"):
            return
        self.current_weapon = name
        self.weapon_change_signal.emit(name)

    def _toggle(self):
        self.toggle_signal.emit(not self._on)

    def _toggle_turbo(self):
        self._turbo_on = not self._turbo_on
        self.turbo_btn.setText("TURBO: ON" if self._turbo_on else "TURBO: OFF")
        self.turbo_btn.setStyleSheet(
            "QPushButton{background:#1E1E1E;color:#00ff66;font-size:9px;font-weight:bold;border:1px solid #00ff66;border-radius:4px;padding:0 8px;}"
            "QPushButton:hover{background:rgba(0,255,102,0.15);}"
            "QPushButton:pressed{background:rgba(0,255,102,0.3);}"
            if self._turbo_on else
            "QPushButton{background:#1E1E1E;color:#ff9944;font-size:9px;font-weight:bold;border:1px solid #ff9944;border-radius:4px;padding:0 8px;}"
            "QPushButton:hover{background:rgba(255,153,68,0.15);}"
            "QPushButton:pressed{background:rgba(255,153,68,0.3);}")
        self.turbo_signal.emit(self._turbo_on)

    def _emit_value(self, key, delta):
        spin = self.param_vars.get(key)
        if spin is not None:
            spin.setValue(spin.value() + delta)

    def _emit_adjust(self, vertical=0.0, horizontal=0.0):
        self.param_change_signal.emit("adjust", {"vertical": vertical, "horizontal": horizontal})

    def update_license_time(self, expiry):
        if expiry == "LIFETIME":
            self._is_lifetime = True
            self._countdown_seconds = 86400
            self.license_label.setText("LIFE TIME: 4500d 23:59:59")
        else:
            self._is_lifetime = False
            try:
                from datetime import datetime
                dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                remaining = int((dt - datetime.now()).total_seconds())
                self._countdown_seconds = max(0, remaining)
            except Exception:
                self._countdown_seconds = 0
            self._update_display()

    def _tick(self):
        now = time.localtime()
        self.timer_label.setText(f"TIME: {now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}")
        if self._countdown_seconds <= 0:
            if self._is_lifetime:
                self._countdown_seconds = 86400
            else:
                return
        self._countdown_seconds -= 1
        self._update_display()

    def _update_display(self):
        s = self._countdown_seconds
        if self._is_lifetime:
            h = s // 3600
            m = (s % 3600) // 60
            sec = s % 60
            self.license_label.setText(f"LIFE TIME: 4500d {h:02d}:{m:02d}:{sec:02d}")
        else:
            days = s // 86400
            h = (s % 86400) // 3600
            m = (s % 3600) // 60
            sec = s % 60
            self.license_label.setText(f"LICENCA: {days}d {h:02d}:{m:02d}:{sec:02d}")

    def update_ai_status(self, weapon="NONE", shots=0, status="ACTIVE",
                         slot1=None, slot2=None, burst=0, fps=0, profiler=None):
        if slot1:
            self.slot1_label.setText(f"SLOT 1: [ {slot1.upper()} ]")
            self.slot1_label.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        else:
            self.slot1_label.setText("SLOT 1: Selecione o Slot 1")
            self.slot1_label.setStyleSheet("color: #666666; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        if slot2:
            self.slot2_label.setText(f"SLOT 2: [ {slot2.upper()} ]")
            self.slot2_label.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        else:
            self.slot2_label.setText("SLOT 2: Selecione o Slot 2")
            self.slot2_label.setStyleSheet("color: #666666; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        self.weapon_label.setText(f"ARMA: [ {weapon.upper() if weapon else 'SELECIONE'} ]")
        self.shot_label.setText(f"TIROS: {shots}")
        if fps:
            self.cap_label.setText(f"CAP: {fps}")
        if profiler:
            self.profiler_label.setText(
                f"LAT: C{profiler.get('capture',0):.1f}/D{profiler.get('detect',0):.1f}/R{profiler.get('recoil',0):.1f} ms"
            )

        text = "ATIVADO" if status == "ACTIVE" else "DESATIVADO"
        color = "#00ff66" if status == "ACTIVE" else "#ff3344"
        self.ia_status_label.setText(text)
        self.ia_status_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        self.status_label.setText(f"SISTEMA: {text}")
        self.status_label.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        led = getattr(self, "on_off_label", None)
        if led is not None:
            led.setStyleSheet(f"color: {color}; font-size: 22px; border: none; background: transparent;")

    def _release_and_exit(self):
        import ctypes
        ctypes.windll.user32.ClipCursor(None)
        sys.exit(0)

    def _toggle_minimize(self):
        if self.isMinimized():
            self.showNormal()
            self.raise_()
        else:
            self.showMinimized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()

    # ------------------------------------------------------------------
    # Crosshair overlay integration
    # ------------------------------------------------------------------
    def set_crosshair_overlay(self, overlay: "CrosshairOverlay | None"):
        self._crosshair_overlay = overlay
        self._update_crosshair_state()

    def _update_crosshair_state(self):
        overlay = getattr(self, "_crosshair_overlay", None)
        if overlay is None:
            return
        if getattr(self, "_on", False):
            overlay.show()
            overlay.raise_()
        else:
            overlay.hide()


    # Fim da classe TacticalHUD
