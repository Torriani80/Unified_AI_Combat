import sys, os, uuid
from datetime import datetime, timedelta
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, db
from PyQt5 import QtCore, QtWidgets, QtGui

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
    EXE_DIR = BASE_DIR
DEBUG_LOG = EXE_DIR / "admin_debug.log"

def debug(msg):
    with open(DEBUG_LOG, "a") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")

def format_expiry(expiry_str):
    if not expiry_str or expiry_str == "LIFETIME":
        return "LIFETIME"
    try:
        dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d/%m/%Y")
    except:
        return expiry_str


class StatusBadge(QtWidgets.QLabel):
    def __init__(self, text, color="#D4AF37"):
        super().__init__(text)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedHeight(22)
        self.setMinimumWidth(80)
        self.setStyleSheet(f"background:transparent;color:{color};border:1px solid {color};border-radius:10px;padding:0 10px;font-size:10px;font-weight:bold;")


class AdminPremiumPanel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        icon_path = str(Path(__file__).parent / "assets" / "logo.png")
        if Path(icon_path).exists():
            self.setWindowIcon(QtGui.QIcon(icon_path))

        # 1. REMOVE MOLDURA E ATIVA TRANSPARÊNCIA TOTAL
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.resize(1280, 960)

        # 2. LAYOUT EXTERNO (O 'VIDRO' INVISÍVEL)
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(0)

        # 3. O CARD PREMIUM (O ÚNICO ELEMENTO VISÍVEL)
        self.container = QtWidgets.QFrame()
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            #MainContainer {
                background-color: #0A0A0A;
                border: 2px solid #D4AF37;
                border-radius: 25px;
            }
        """)

        # Glow dourado
        glow = QtWidgets.QGraphicsDropShadowEffect()
        glow.setBlurRadius(50)
        glow.setColor(QtGui.QColor(212, 175, 55, 200))
        glow.setOffset(0, 0)
        self.container.setGraphicsEffect(glow)

        self.main_layout.addWidget(self.container)

        # 4. LAYOUT INTERNO DO CARD
        self.content_layout = QtWidgets.QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(30, 30, 30, 30)
        self.content_layout.setSpacing(16)

        self._init_firebase()
        self._build_content()
        self._refresh()

        # 5. ARRASTAR
        self.oldPos = self.pos()

    def _init_firebase(self):
        try:
            if not firebase_admin._apps:
                path = str(BASE_DIR / "serviceAccountKey.json")
                if not os.path.exists(path) and getattr(sys, 'frozen', False):
                    path = str(Path(sys.executable).parent / "serviceAccountKey.json")
                cred = credentials.Certificate(path)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
                })
                debug("Firebase init OK")
        except Exception as e:
            import traceback; traceback.print_exc()
            debug(f"Firebase init ERRO: {e}")

    def _gold_btn(self):
        return ("QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #B8860B,stop:0.4 #D4AF37,stop:0.7 #FFE44D,stop:1 #B8860B);"
                "color:#000000;font-size:12px;font-weight:bold;border:none;"
                "border-radius:8px;padding:6px 18px;}"
                "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #D4A017,stop:0.4 #FFE44D,stop:0.7 #FFF3A0,stop:1 #D4A017);}")

    def _dark_btn(self, color):
        return (f"QPushButton{{background:#1E1E1E;color:{color};font-size:11px;font-weight:bold;"
                f"border:1px solid {color};border-radius:8px;padding:5px 16px;}}"
                f"QPushButton:hover{{background:rgba({','.join(str(int(color[i:i+2],16)) for i in (1,3,5))},0.15);}}")

    def _style_table(self, table, zebra=False):
        css = ("QTableWidget{background-color:#121212;color:#FFFFFF;border:none;"
               "gridline-color:#2A2A2D;font-size:11px;}"
               "QTableWidget::item{padding:4px 6px;}"
               "QHeaderView::section{background-color:#B8860B;color:#000000;"
               "font-weight:bold;font-size:11px;border:none;padding:5px 6px;}"
               "QTableWidget::item:selected{background-color:rgba(212,175,55,0.3);color:#FFFFFF;}")
        if zebra:
            css += "QTableWidget{alternate-background-color:#151515;}"
        table.setStyleSheet(css)
        table.setAlternatingRowColors(zebra)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setHighlightSections(False)
        table.setShowGrid(False)

    def _build_content(self):
        # Header: botoes minimizar/fechar no canto + titulo
        top = QtWidgets.QHBoxLayout()
        top.addStretch()
        for txt, hov in [("_", "#D4AF37"), ("X", "#FF4444")]:
            b = QtWidgets.QPushButton(txt)
            b.setFixedSize(28, 28)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton{{background:transparent;color:#808080;font-size:14px;font-weight:bold;border:1px solid rgba(212,175,55,0.3);border-radius:14px;}}QPushButton:hover{{color:{hov};border-color:{hov};}}")
            b.clicked.connect(self.showMinimized if txt == "_" else self.close)
            top.addWidget(b)
        self.content_layout.addLayout(top)

        # Logo
        logo_lbl = QtWidgets.QLabel()
        logo_lbl.setAlignment(QtCore.Qt.AlignCenter)
        logo_path = str(Path(__file__).parent / "assets" / "logo.png")
        if Path(logo_path).exists():
            pix = QtGui.QPixmap(logo_path)
            logo_lbl.setPixmap(pix.scaled(100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            logo_lbl.setStyleSheet("border: none; background: transparent;")
        self.content_layout.addWidget(logo_lbl)

        # Titulo
        title = QtWidgets.QLabel("PAINEL ADMIN - GESTAO DE LICENCAS")
        title.setStyleSheet("color: #D4AF37; font-size: 22px; font-weight: bold; border: none; background: transparent;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        self.content_layout.addWidget(title)

        sub = QtWidgets.QLabel("Firebase Realtime Database")
        sub.setStyleSheet("color: #808080; font-size: 10px; border: none; background: transparent;")
        sub.setAlignment(QtCore.Qt.AlignCenter)
        self.content_layout.addWidget(sub)

        # ═══ CARD 1: PENDENTES ═══
        c1 = QtWidgets.QFrame()
        c1.setStyleSheet("QFrame{background-color:#121212;border:1px solid #D4AF37;border-radius:14px;}")
        c1l = QtWidgets.QVBoxLayout(c1)
        c1l.setContentsMargins(14, 10, 14, 10)

        h1 = QtWidgets.QLabel("USUARIOS PENDENTES")
        h1.setStyleSheet("color:#D4AF37;font-size:13px;font-weight:bold;border:none;background:transparent;")
        c1l.addWidget(h1)

        self.pend_table = QtWidgets.QTableWidget()
        self.pend_table.setColumnCount(4)
        self.pend_table.setHorizontalHeaderLabels(["NICK", "SENHA", "HWID", "DATA"])
        self.pend_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._style_table(self.pend_table)
        self.pend_table.horizontalHeader().setStretchLastSection(True)
        self.pend_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        c1l.addWidget(self.pend_table)

        ar = QtWidgets.QHBoxLayout()
        dl = QtWidgets.QLabel("Duracao:")
        dl.setStyleSheet("color:#B0B0B0;font-size:11px;border:none;background:transparent;")
        ar.addWidget(dl)
        self.dur_combo = QtWidgets.QComboBox()
        self.dur_combo.addItems(["LIFETIME", "30", "7", "3", "1"])
        self.dur_combo.setCurrentText("LIFETIME")
        self.dur_combo.setFixedWidth(100)
        self.dur_combo.setStyleSheet("QComboBox{background:#1E1E1E;color:#FFFFFF;border:1px solid #D4AF37;border-radius:6px;padding:4px 8px;font-size:11px;}QComboBox::drop-down{border:none;width:20px;}QComboBox::down-arrow{image:none;border-left:5px solid transparent;border-right:5px solid transparent;border-top:6px solid #D4AF37;}QComboBox QAbstractItemView{background:#1E1E1E;color:#FFFFFF;selection-background-color:#D4AF37;selection-color:#000000;border:1px solid #D4AF37;}")
        ar.addWidget(self.dur_combo)
        ar.addStretch()
        self.btn_approve = QtWidgets.QPushButton("APROVAR")
        self.btn_approve.setFixedHeight(30)
        self.btn_approve.setStyleSheet(self._gold_btn())
        self.btn_approve.clicked.connect(self._approve_user)
        ar.addWidget(self.btn_approve)
        c1l.addLayout(ar)
        self.content_layout.addWidget(c1)

        # ═══ CARD 2: GERAR CHAVE ═══
        c2 = QtWidgets.QFrame()
        c2.setStyleSheet("QFrame{background-color:#121212;border:1px solid #D4AF37;border-radius:14px;}")
        c2l = QtWidgets.QVBoxLayout(c2)
        c2l.setContentsMargins(14, 10, 14, 10)

        h2 = QtWidgets.QLabel("GERAR NOVA CHAVE")
        h2.setStyleSheet("color:#D4AF37;font-size:13px;font-weight:bold;border:none;background:transparent;")
        c2l.addWidget(h2)

        nl = QtWidgets.QLabel("Nome do Cliente:")
        nl.setStyleSheet("color:#B0B0B0;font-size:11px;border:none;background:transparent;")
        c2l.addWidget(nl)
        self.cust_input = QtWidgets.QLineEdit()
        self.cust_input.setPlaceholderText("Nome do cliente")
        self.cust_input.setStyleSheet("QLineEdit{background:#1E1E1E;color:#FFFFFF;border:1px solid #D4AF37;border-radius:8px;padding:6px 14px;font-size:12px;}QLineEdit:focus{border:1px solid #FFE44D;}QLineEdit::placeholder{color:#555555;}")
        c2l.addWidget(self.cust_input)

        gr = QtWidgets.QHBoxLayout()
        self.gen_dur = QtWidgets.QComboBox()
        self.gen_dur.addItems(["1", "3", "30", "LIFETIME"])
        self.gen_dur.setCurrentText("30")
        self.gen_dur.setFixedWidth(100)
        self.gen_dur.setStyleSheet(self.dur_combo.styleSheet())
        gr.addWidget(self.gen_dur)
        gr.addStretch()
        self.btn_gen = QtWidgets.QPushButton("GERAR")
        self.btn_gen.setFixedHeight(30)
        self.btn_gen.setStyleSheet(self._gold_btn())
        self.btn_gen.clicked.connect(self._generate)
        gr.addWidget(self.btn_gen)
        c2l.addLayout(gr)

        self.key_res = QtWidgets.QLineEdit()
        self.key_res.setReadOnly(True)
        self.key_res.setPlaceholderText("Chave gerada aparecera aqui")
        self.key_res.setStyleSheet("QLineEdit{background:#1E1E1E;color:#D4AF37;border:1px solid #D4AF37;border-radius:8px;padding:6px 14px;font-size:13px;font-weight:bold;}")
        c2l.addWidget(self.key_res)
        self.content_layout.addWidget(c2)

        # ═══ CARD 3: LICENCAS ═══
        c3 = QtWidgets.QFrame()
        c3.setStyleSheet("QFrame{background-color:#121212;border:1px solid #D4AF37;border-radius:14px;}")
        c3l = QtWidgets.QVBoxLayout(c3)
        c3l.setContentsMargins(14, 10, 14, 10)

        h3 = QtWidgets.QLabel("TABELA DE LICENCAS")
        h3.setStyleSheet("color:#D4AF37;font-size:13px;font-weight:bold;border:none;background:transparent;")
        c3l.addWidget(h3)

        self.lic_table = QtWidgets.QTableWidget()
        self.lic_table.setColumnCount(6)
        self.lic_table.setHorizontalHeaderLabels(["CHAVE", "DESIGNADA", "USUARIO", "EXPIRACAO", "HWID", "STATUS"])
        self.lic_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._style_table(self.lic_table, zebra=True)
        self.lic_table.horizontalHeader().setStretchLastSection(False)
        self.lic_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.lic_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.lic_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.lic_table.customContextMenuRequested.connect(self._ctx_menu)
        c3l.addWidget(self.lic_table)

        ar2 = QtWidgets.QHBoxLayout()
        for txt, col in [("RESETAR HWID", "#D4AF37"), ("DELETAR CHAVE", "#FF4444")]:
            b = QtWidgets.QPushButton(txt)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setFixedHeight(28)
            b.setStyleSheet(self._dark_btn(col))
            b.clicked.connect(self._reset_hwid if "RESET" in txt else self._delete_key)
            ar2.addWidget(b)
        ar2.addStretch()
        self.btn_refresh = QtWidgets.QPushButton("ATUALIZAR")
        self.btn_refresh.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_refresh.setFixedHeight(28)
        self.btn_refresh.setStyleSheet(self._gold_btn())
        self.btn_refresh.clicked.connect(self._refresh)
        ar2.addWidget(self.btn_refresh)
        c3l.addLayout(ar2)
        self.content_layout.addWidget(c3, 1)

        # Status
        self.status = QtWidgets.QLabel("")
        self.status.setAlignment(QtCore.Qt.AlignCenter)
        self.status.setFixedHeight(18)
        self.status.setStyleSheet("color:#B0B0B0;font-size:9px;border:none;background:transparent;")
        self.content_layout.addWidget(self.status)

        # Timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(10000)

    def _log(self, msg, color="#B0B0B0"):
        debug(msg)
        self.status.setText(msg)
        self.status.setStyleSheet(f"color:{color};font-size:9px;border:none;background:transparent;")
        QtCore.QTimer.singleShot(5000, lambda: self.status.setText(""))

    def _load_lics(self):
        lics = {}
        try:
            data = db.reference('licenses').get()
            if data:
                for k, v in data.items():
                    if isinstance(v, dict):
                        lics[k] = v
        except Exception as e:
            debug(f"_load_lics ERRO: {e}")
        return lics

    def _get_pending_users(self):
        users = []
        try:
            data = db.reference('users').get()
            if data:
                for nick, info in data.items():
                    if isinstance(info, dict) and info.get('status') == 'pendente':
                        users.append((nick, info))
        except Exception as e:
            debug(f"_get_pending_users ERRO: {e}")
        return users

    def _refresh(self):
        try:
            self.pend_table.setRowCount(0)
            for i, (nick, info) in enumerate(self._get_pending_users()):
                self.pend_table.insertRow(i)
                for j, v in enumerate([nick, "*******", info.get("hwid","?"), info.get("created_at","?")]):
                    it = QtWidgets.QTableWidgetItem(str(v))
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
                    self.pend_table.setItem(i, j, it)

            self.lic_table.setRowCount(0)
            row = 0
            for key, v in self._load_lics().items():
                if not isinstance(v, dict):
                    continue
                expiry = v.get("expiry", "LIFETIME")
                status = "ATIVO"
                if expiry != "LIFETIME":
                    try:
                        if datetime.now() > datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S"):
                            status = "EXPIRADO"
                    except:
                        pass
                if not v.get("used_by"):
                    status = "NAO UTILIZADO"
                self.lic_table.insertRow(row)
                for j, v2 in enumerate([key, v.get("designated_to","---"), v.get("used_by") or "---",
                                        format_expiry(expiry), v.get("hwid") or "---", ""]):
                    it = QtWidgets.QTableWidgetItem(str(v2))
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
                    self.lic_table.setItem(row, j, it)
                bc = {"ATIVO":"#D4AF37","EXPIRADO":"#FF4444","NAO UTILIZADO":"#666666"}.get(status,"#D4AF37")
                self.lic_table.setCellWidget(row, 5, StatusBadge(status, bc))
                row += 1
        except Exception as e:
            import traceback; traceback.print_exc()
            self._log(f"ERRO no refresh: {e}", "#FF4444")

    def _approve_user(self):
        rows = self.pend_table.selectedIndexes()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "!", "Selecione um usuario pendente.")
            return
        nick = self.pend_table.item(rows[0].row(), 0).text()
        key = str(uuid.uuid4()).upper()[:16]
        dur = self.dur_combo.currentText()
        expiry = "LIFETIME"
        if dur != "LIFETIME":
            expiry = (datetime.now() + timedelta(days=int(dur))).strftime("%Y-%m-%d %H:%M:%S")
        try:
            db.reference(f'licenses/{key}').set({"expiry": expiry, "used_by": nick, "hwid": None, "designated_to": nick, "status": "ativa", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            db.reference(f'users/{nick}').update({'status': 'aprovado'})
            self.key_res.setText(key)
            self._log(f"{nick} aprovado! Chave: {key}", "#D4AF37")
            self._refresh()
            QtWidgets.QMessageBox.information(self, "Sucesso", f"Usuario '{nick}' aprovado!\nChave: {key}")
        except Exception as e:
            import traceback; traceback.print_exc()
            self._log(f"ERRO ao aprovar: {e}", "#FF4444")
            QtWidgets.QMessageBox.critical(self, "ERRO", str(e))

    def _generate(self):
        key = str(uuid.uuid4()).upper()[:16]
        dur = self.gen_dur.currentText()
        cust = self.cust_input.text().strip() or "Unknown"
        expiry = "LIFETIME"
        if dur != "LIFETIME":
            expiry = (datetime.now() + timedelta(days=int(dur))).strftime("%Y-%m-%d %H:%M:%S")
        try:
            db.reference(f'licenses/{key}').set({"expiry": expiry, "used_by": None, "hwid": None, "designated_to": cust, "status": "ativa", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            self.key_res.setText(key)
            self._log(f"Chave gerada para {cust}", "#D4AF37")
            self._refresh()
        except Exception as e:
            import traceback; traceback.print_exc()
            self._log(f"ERRO ao gerar chave: {e}", "#FF4444")

    def _reset_hwid(self):
        rows = self.lic_table.selectedIndexes()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "!", "Selecione uma chave.")
            return
        key = self.lic_table.item(rows[0].row(), 0).text()
        try:
            db.reference(f'licenses/{key}').update({'hwid': ''})
            self._log(f"HWID resetado: {key}", "#D4AF37")
            self._refresh()
            QtWidgets.QMessageBox.information(self, "Sucesso", "HWID Resetado!")
        except Exception as e:
            import traceback; traceback.print_exc()
            self._log(f"ERRO ao resetar HWID: {e}", "#FF4444")
            QtWidgets.QMessageBox.critical(self, "ERRO", str(e))

    def _delete_key(self):
        rows = self.lic_table.selectedIndexes()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "!", "Selecione uma chave.")
            return
        key = self.lic_table.item(rows[0].row(), 0).text()
        try:
            ref = db.reference(f'licenses/{key}')
            lic_data = ref.get()
            nick = lic_data.get('used_by') if isinstance(lic_data, dict) else None
            ref.delete()
            if nick:
                db.reference(f'users/{nick}').delete()
            self._log(f"Deletado: {key}", "#D4AF37")
            self._refresh()
            QtWidgets.QMessageBox.information(self, "Sucesso", f"Chave + usuario '{nick}' deletados!")
        except Exception as e:
            import traceback; traceback.print_exc()
            self._log(f"ERRO ao deletar: {e}", "#FF4444")
            QtWidgets.QMessageBox.critical(self, "ERRO", str(e))

    def _ctx_menu(self, pos):
        item = self.lic_table.itemAt(pos)
        if not item:
            return
        key = self.lic_table.item(item.row(), 0).text()
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu{background:#1C1C1E;color:#D4AF37;border:1px solid #D4AF37;border-radius:8px;padding:4px;}QMenu::item{padding:6px 20px;border-radius:4px;}QMenu::item:selected{background:#D4AF37;color:#000000;}")
        act = menu.addAction("Copiar chave")
        if menu.exec_(self.lic_table.viewport().mapToGlobal(pos)) == act:
            QtWidgets.QApplication.clipboard().setText(key)
            self._log(f"Chave copiada: {key}", "#D4AF37")

    def keyPressEvent(self, event):
        if event.matches(QtGui.QKeySequence.Copy):
            rows = self.lic_table.selectedIndexes()
            if rows:
                key = self.lic_table.item(rows[0].row(), 0).text()
                QtWidgets.QApplication.clipboard().setText(key)
                self._log(f"Chave copiada: {key}", "#D4AF37")
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QtCore.QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = AdminPremiumPanel()
    window.show()
    sys.exit(app.exec_())
