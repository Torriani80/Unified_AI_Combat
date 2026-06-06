import sys
import os
import threading
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QSplitter, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy, QScrollArea,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QPoint, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QPen, QBrush

from jarvis.config import config
from jarvis.orchestrator import JarvisOrchestrator
from jarvis.voice.listener import VoiceListener
from jarvis.voice.speaker import VoiceSpeaker
from jarvis.utils.logger import log


class VoiceThread(QThread):
    command_received = pyqtSignal(str)

    def __init__(self, wake_word="jarvis", language="pt-BR"):
        super().__init__()
        self.wake_word = wake_word
        self.language = language
        self._running = False

    def run(self):
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                while self._running:
                    try:
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=10)
                        try:
                            text = recognizer.recognize_google(audio, language=self.language)
                            text = text.lower().strip()
                            if text.startswith(self.wake_word):
                                cmd = text[len(self.wake_word):].strip()
                                if cmd:
                                    self.command_received.emit(cmd)
                        except:
                            pass
                    except:
                        pass
        except Exception as e:
            log.error("Voice thread error: " + str(e))

    def stop(self):
        self._running = False


class MessageBubble(QFrame):
    def __init__(self, text, is_user=True, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        if is_user:
            layout.addStretch()

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Segoe UI", 10))
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)

        if is_user:
            bubble.setStyleSheet(
                "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #B8860B,stop:1 #FFD700);"
                "color: #000000;"
                "border-radius: 12px;"
                "padding: 10px 14px;"
            )
        else:
            bubble.setStyleSheet(
                "background: #1E1E1E;"
                "color: #D4AF37;"
                "border: 1px solid #333;"
                "border-radius: 12px;"
                "padding: 10px 14px;"
            )

        layout.addWidget(bubble)

        if not is_user:
            layout.addStretch()


class WorkerSignals(QThread):
    append_message = pyqtSignal(str, str, bool)
    update_agents = pyqtSignal()
    set_input_enabled = pyqtSignal(bool)
    # Sinais não precisam ser QThread, apenas QObject
    pass

class JarvisGUI(QMainWindow):
    # Definindo sinais para comunicação segura entre threads
    sig_append_message = pyqtSignal(str, str, bool)
    sig_update_agents = pyqtSignal()
    sig_set_input_enabled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.jarvis = None
        self.voice_thread = None
        self.voice_enabled = config.voice.enabled
        self._drag_pos = QPoint()
        
        # Conectando sinais aos métodos da interface
        self.sig_append_message.connect(self._append_message)
        self.sig_update_agents.connect(self._update_agents)
        self.sig_set_input_enabled.connect(self._set_input_enabled)
        
        self._init_ui()
        self._init_jarvis()

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

        # Widget central para conter tudo
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        outer = QVBoxLayout(central_widget)
        outer.setContentsMargins(20, 20, 20, 20)

        self.container = QFrame()
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            QFrame#MainContainer {
                background-color: #0A0A0A;
                border: 2px solid #D4AF37;
                border-radius: 18px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(212, 175, 55, 150))
        shadow.setOffset(0, 0)
        self.container.setGraphicsEffect(shadow)

        outer.addWidget(self.container)

        main_layout = QHBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)

        self.content = self._create_content()
        main_layout.addWidget(self.content, 1)

    def _create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet(
            "QFrame {"
            "background: #0D0D0D;"
            "border-right: 1px solid #222;"
            "border-top-left-radius: 18px;"
            "border-bottom-left-radius: 18px;"
            "}"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        header = QHBoxLayout()
        icon = QLabel("J")
        icon.setFont(QFont("Segoe UI", 24))
        header.addWidget(icon)

        title = QLabel("JARVIS")
        title.setStyleSheet("color: #D4AF37; font-size: 22px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        prov_layout = QVBoxLayout()
        prov_label = QLabel("PROVIDER")
        prov_label.setStyleSheet("color: #666; font-size: 10px; font-weight: bold;")
        prov_layout.addWidget(prov_label)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["ollama", "gemini", "groq", "claude"])
        self.provider_combo.setCurrentText(config.brain.provider)
        self.provider_combo.setStyleSheet(
            "QComboBox {"
            "background: #1E1E1E;"
            "color: #D4AF37;"
            "border: 1px solid #333;"
            "border-radius: 6px;"
            "padding: 8px 12px;"
            "font-size: 12px;"
            "}"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView {"
            "background: #1E1E1E; color: #D4AF37;"
            "selection-background-color: #D4AF37; selection-color: #000;"
            "}"
        )
        self.provider_combo.currentTextChanged.connect(self._on_provider_change)
        prov_layout.addWidget(self.provider_combo)
        layout.addLayout(prov_layout)

        self.conclave_btn = QPushButton("Conclave: ON" if config.conclave.enabled else "Conclave: OFF")
        self.conclave_btn.setCheckable(True)
        self.conclave_btn.setChecked(config.conclave.enabled)
        self.conclave_btn.setStyleSheet(
            "QPushButton {"
            "background: #1E1E1E;"
            "color: #D4AF37;"
            "border: 1px solid #333;"
            "border-radius: 6px;"
            "padding: 8px;"
            "font-size: 11px;"
            "}"
            "QPushButton:checked { background: rgba(212,175,55,0.2); border-color: #D4AF37; }"
        )
        self.conclave_btn.clicked.connect(self._on_conclave_toggle)
        layout.addWidget(self.conclave_btn)

        self.voice_btn = QPushButton("Voz: ON" if self.voice_enabled else "Voz: OFF")
        self.voice_btn.setCheckable(True)
        self.voice_btn.setChecked(self.voice_enabled)
        self.voice_btn.setStyleSheet(
            "QPushButton {"
            "background: #1E1E1E;"
            "color: #D4AF37;"
            "border: 1px solid #333;"
            "border-radius: 6px;"
            "padding: 8px;"
            "font-size: 11px;"
            "}"
            "QPushButton:checked { background: rgba(212,175,55,0.2); border-color: #D4AF37; }"
        )
        self.voice_btn.clicked.connect(self._on_voice_toggle)
        layout.addWidget(self.voice_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #222; border: none; max-height: 1px;")
        layout.addWidget(sep)

        agents_label = QLabel("AGENTES (17)")
        agents_label.setStyleSheet("color: #666; font-size: 10px; font-weight: bold;")
        layout.addWidget(agents_label)

        self.agent_list = QListWidget()
        self.agent_list.setStyleSheet(
            "QListWidget {"
            "background: transparent;"
            "border: none;"
            "color: #B0B0B0;"
            "font-size: 11px;"
            "}"
            "QListWidget::item {"
            "padding: 6px 8px;"
            "border-radius: 4px;"
            "}"
            "QListWidget::item:hover { background: rgba(212,175,55,0.1); }"
            "QListWidget::item:selected { background: rgba(212,175,55,0.2); color: #FFD700; }"
        )
        layout.addWidget(self.agent_list)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background: #222; border: none; max-height: 1px;")
        layout.addWidget(sep2)

        self.proj_btn = QPushButton("Abrir Pasta de Projetos")
        self.proj_btn.setStyleSheet(
            "QPushButton {"
            "background: #1E1E1E;"
            "color: #D4AF37;"
            "border: 1px solid #D4AF37;"
            "border-radius: 6px;"
            "padding: 10px;"
            "font-size: 11px;"
            "}"
            "QPushButton:hover { background: rgba(212,175,55,0.15); }"
        )
        self.proj_btn.clicked.connect(self._open_projects)
        layout.addWidget(self.proj_btn)

        layout.addStretch()

        controls = QHBoxLayout()
        controls.setSpacing(8)
        for txt, color in [("-", "#D4AF37"), ("X", "#FF4444")]:
            b = QPushButton(txt)
            b.setFixedSize(28, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { background: transparent; color: #888; font-size: 14px; font-weight: bold;"
                "border: 1px solid rgba(212,175,55,0.3); border-radius: 14px; }"
                "QPushButton:hover { color: " + color + "; border-color: " + color + "; }"
            )
            if txt == "-":
                b.clicked.connect(self.showMinimized)
            else:
                b.clicked.connect(self.close)
            controls.addWidget(b)
        layout.addLayout(controls)

        return sidebar

    def _create_content(self):
        content = QFrame()
        content.setStyleSheet(
            "QFrame {"
            "background: #0A0A0A;"
            "border-top-right-radius: 18px;"
            "border-bottom-right-radius: 18px;"
            "}"
        )

        layout = QVBoxLayout(content)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: #121212; width: 8px; border: none; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: #333; border-radius: 4px; min-height: 40px; }"
            "QScrollBar::handle:vertical:hover { background: #D4AF37; }"
        )

        self.chat_widget = QWidget()
        self.chat_widget.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(0, 0, 10, 0)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_widget)
        layout.addWidget(self.chat_scroll, 1)

        input_frame = QFrame()
        input_frame.setFixedHeight(70)
        input_frame.setStyleSheet(
            "QFrame {"
            "background: #121212;"
            "border: 1px solid #222;"
            "border-radius: 12px;"
            "}"
        )

        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(15, 8, 15, 8)
        input_layout.setSpacing(10)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Digite sua mensagem ou diga 'Jarvis...' ...")
        self.input_field.setFont(QFont("Segoe UI", 12))
        self.input_field.setStyleSheet(
            "QLineEdit {"
            "background: #0A0A0A;"
            "color: #FFFFFF;"
            "border: 1px solid #333;"
            "border-radius: 8px;"
            "padding: 10px 15px;"
            "font-size: 13px;"
            "}"
            "QLineEdit:focus { border-color: #D4AF37; }"
        )
        self.input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_field)

        self.send_btn = QPushButton("Enviar")
        self.send_btn.setFixedSize(100, 44)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(
            "QPushButton {"
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #B8860B,stop:1 #FFD700);"
            "color: #000000;"
            "font-size: 13px;"
            "font-weight: bold;"
            "border: none;"
            "border-radius: 8px;"
            "}"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #D4A017,stop:1 #FFE44D); }"
        )
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(input_frame)

        return content

    def _init_jarvis(self):
        self.sig_append_message.emit("Sistema", "Inicializando JARVIS...", False)

        def init_async():
            try:
                self.jarvis = JarvisOrchestrator()
                self.sig_update_agents.emit()
                self.sig_append_message.emit("Sistema", f"JARVIS pronto! Provider: {config.brain.provider.upper()}", False)
                self.sig_set_input_enabled.emit(True)
            except Exception as e:
                self.sig_append_message.emit("Erro", f"Falha ao iniciar: {e}", False)

        threading.Thread(target=init_async, daemon=True).start()

    def _send_message(self):
        text = self.input_field.text().strip()
        if not text or not self.jarvis:
            return
        self.input_field.clear()
        self.sig_append_message.emit("Você", text, True)
        self.sig_set_input_enabled.emit(False)

        def process():
            try:
                response = self.jarvis.execute_voice_command(text)
                resp = response.replace('\n', '<br>')
                self.sig_append_message.emit("JARVIS", resp, False)
                if self.voice_enabled and config.voice.enabled:
                    self.jarvis.speak(response[:500])
            except Exception as e:
                self.sig_append_message.emit("Erro", str(e), False)
            finally:
                self.sig_set_input_enabled.emit(True)

        threading.Thread(target=process, daemon=True).start()

    def _on_voice_command(self, cmd):
        self.sig_append_message.emit("Você (voz)", cmd, True)
        self.sig_set_input_enabled.emit(False)

        def process():
            try:
                response = self.jarvis.execute_voice_command(cmd)
                resp = response.replace('\n', '<br>')
                self.sig_append_message.emit("JARVIS", resp, False)
                if self.voice_enabled:
                    self.jarvis.speak(response[:500])
            except Exception as e:
                self.sig_append_message.emit("Erro", str(e), False)
            finally:
                self.sig_set_input_enabled.emit(True)

        threading.Thread(target=process, daemon=True).start()

    def _set_input_enabled(self, enabled):
        self.input_field.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)

    def _on_provider_change(self, provider):
        config.brain.provider = provider
        from jarvis.brains.claude_brain import ClaudeBrain
        if self.jarvis:
            self.jarvis.brain = ClaudeBrain()
            self._append_message("Sistema", "Provider trocado para: " + provider.upper(), is_user=False)

    def _on_conclave_toggle(self, checked):
        config.conclave.enabled = checked
        self.conclave_btn.setText("Conclave: ON" if checked else "Conclave: OFF")

    def _on_voice_toggle(self, checked):
        self.voice_enabled = checked
        self.voice_btn.setText("Voz: ON" if checked else "Voz: OFF")
        if checked and not self.voice_thread:
            self.voice_thread = VoiceThread(
                wake_word=config.voice.wake_word,
                language=config.voice.language,
            )
            self.voice_thread.command_received.connect(self._on_voice_command)
            self.voice_thread.start()
        elif not checked and self.voice_thread:
            self.voice_thread.stop()
            self.voice_thread = None

    def _on_voice_command(self, cmd):
        self._append_message("Voce (voz)", cmd, is_user=True)
        self._set_input_enabled(False)

        def process():
            try:
                response = self.jarvis.execute_voice_command(cmd)
                resp = response.replace("\n", "<br>")
                self._append_message("JARVIS", resp, is_user=False)
                if self.voice_enabled:
                    self.jarvis.speak(response[:500])
            except Exception as e:
                self._append_message("Erro", str(e), is_user=False)
            finally:
                self._set_input_enabled(True)

        threading.Thread(target=process, daemon=True).start()

    def _open_projects(self):
        path = config.data_dir
        if os.path.exists(path):
            if sys.platform == "win32":
                os.startfile(path)
            else:
                os.system("xdg-open '" + path + "'")
        else:
            QMessageBox.information(self, "Projetos", "Pasta de projetos ainda nao criada.")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def closeEvent(self, event):
        if self.voice_thread:
            self.voice_thread.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0A0A0A"))
    palette.setColor(QPalette.WindowText, QColor("#FFFFFF"))
    palette.setColor(QPalette.Base, QColor("#121212"))
    palette.setColor(QPalette.AlternateBase, QColor("#1E1E1E"))
    palette.setColor(QPalette.Text, QColor("#FFFFFF"))
    palette.setColor(QPalette.Button, QColor("#1E1E1E"))
    palette.setColor(QPalette.ButtonText, QColor("#D4AF37"))
    palette.setColor(QPalette.Highlight, QColor("#D4AF37"))
    palette.setColor(QPalette.HighlightedText, QColor("#000000"))
    app.setPalette(palette)

    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = JarvisGUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()