import json
import subprocess
import os
import sys
import hashlib
import time
from datetime import datetime
from typing import Tuple, Optional
from pathlib import Path
from collections import deque
import firebase_admin
from firebase_admin import credentials, db

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

class RateLimiter:
    def __init__(self, max_calls=5, per_seconds=2):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._calls = deque()

    def allow(self) -> bool:
        now = time.time()
        while self._calls and now - self._calls[0] >= self.per_seconds:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            return False
        self._calls.append(now)
        return True

class CombatSecurity:
    def __init__(self, service_account_path="serviceAccountKey.json"):
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys._MEIPASS)
            appdata = Path(os.environ.get('APPDATA', Path.home())) / "Unified_AI_Combat"
            appdata.mkdir(parents=True, exist_ok=True)
        else:
            base_dir = Path(__file__).parent
            appdata = base_dir

        self.service_account_path = Path(os.environ.get("APPDATA")) / "Unified_AI_Combat" / service_account_path
        if not self.service_account_path.exists():
            self.service_account_path = base_dir / service_account_path
        self.session_path = appdata / "session.json"
        self._rate_limiter = RateLimiter()
        self._init_firebase()

    def _init_firebase(self):
        try:
            if not firebase_admin._apps:
                env_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
                if env_json:
                    import json as _json
                    cred = credentials.Certificate(_json.loads(env_json))
                elif self.service_account_path.exists():
                    path = str(self.service_account_path)
                    print(f"[FIREBASE] Carregando credenciais de: {path}")
                    cred = credentials.Certificate(path)
                else:
                    raise FileNotFoundError(
                        "Credencial Firebase nao encontrada. Defina FIREBASE_SERVICE_ACCOUNT_JSON "
                        "ou coloque serviceAccountKey.json no diretorio."
                    )
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
                })
                print("[FIREBASE] Inicializado com sucesso")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[FIREBASE] Erro: {e}")
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(e), "Erro Firebase", 0x10)

    def get_hwid(self) -> str:
        try:
            uuid = subprocess.check_output(['wmic', 'csproduct', 'get', 'uuid']).decode().split('\n')[1].strip()
            return uuid
        except:
            return "UNKNOWN_HWID_12345"

    def _check_password(self, stored: str, input_password: str) -> bool:
        if stored == _hash_password(input_password):
            return True
        if stored == input_password:
            return True
        return False

    def register_user(self, nick: str, password: str) -> Tuple[bool, str]:
        if not self._rate_limiter.allow():
            return False, "Muitas tentativas. Aguarde."
        try:
            hwid = self.get_hwid()
            ref = db.reference(f'users/{nick}')
            ref.set({
                'password': _hash_password(password),
                'hwid': hwid,
                'status': 'pendente',
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return True, "Cadastro enviado! Aguarde a aprovacao do administrador."
        except Exception as e:
            if "404" in str(e):
                return False, "Erro: Banco de dados nao encontrado."
            return False, f"Erro ao registrar: {e}"

    def check_user_status(self, nick: str, password: str) -> Tuple[str, Optional[str]]:
        if not self._rate_limiter.allow():
            return 'error', "Muitas tentativas. Aguarde."
        try:
            ref = db.reference(f'users/{nick}')
            data = ref.get()
            if not data:
                return 'not_found', None
            stored_pw = data.get('password', '')
            if not self._check_password(stored_pw, password):
                return 'not_found', None
            if stored_pw == password:
                db.reference(f'users/{nick}/password').set(_hash_password(password))

            status = data.get('status')
            if status == 'pendente':
                return 'pending', "Cadastro pendente. Aguarde a aprovacao."

            if status == 'aprovado':
                licenses = db.reference('licenses').get()
                if licenses:
                    for key, lic in licenses.items():
                        if isinstance(lic, dict) and lic.get('used_by') == nick:
                            return 'approved', "Conta aprovada! Ative sua licenca."
                return 'approved', "Conta aprovada! Entre em contato com o admin para receber sua chave."

            return 'not_found', None
        except Exception as e:
            if "404" in str(e):
                return 'not_found', None
            return 'error', f"Erro: {e}"

    def activate_license(self, nick: str, password: str, key: str) -> Tuple[bool, str]:
        if not self._rate_limiter.allow():
            return False, "Muitas tentativas. Aguarde."
        try:
            user_ref = db.reference(f'users/{nick}')
            user_data = user_ref.get()
            if not user_data or not self._check_password(user_data.get('password', ''), password):
                return False, "Usuario ou senha incorretos."
            if user_data.get('password') == password:
                user_ref.child('password').set(_hash_password(password))

            lic_ref = db.reference(f'licenses/{key}')
            lic = lic_ref.get()

            if not lic:
                return False, "Chave invalida."

            if not isinstance(lic, dict):
                return False, "Chave invalida."

            if lic.get('status') != 'ativa':
                return False, "Chave ja utilizada ou desativada."

            designated = lic.get('used_by')
            if designated and designated != nick:
                return False, "Esta chave nao pertence a este usuario."

            current_hwid = self.get_hwid()
            existing_hwid = lic.get('hwid')

            if existing_hwid and existing_hwid != current_hwid:
                return False, "Chave ja vinculada a outro computador."

            lic_ref.update({
                'hwid': current_hwid,
                'activated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            return True, "Licenca ativada com sucesso!"
        except Exception as e:
            if "404" in str(e):
                return False, "Chave invalida."
            return False, f"Erro: {e}"

    def check_license_by_hwid(self) -> Tuple[bool, Optional[dict]]:
        try:
            current_hwid = self.get_hwid()
            licenses = db.reference('licenses').get()
            if licenses:
                for key, data in licenses.items():
                    if isinstance(data, dict) and data.get('hwid') == current_hwid:
                        return True, data
            return False, None
        except:
            return False, None

    def save_session(self, nick, password, key, remember=True):
        if remember:
            with open(self.session_path, "w") as f:
                json.dump({"nick": nick, "password": _hash_password(password), "key": key, "remember": True}, f)
        elif self.session_path.exists():
            self.session_path.unlink()

    def get_session(self):
        if os.path.exists(self.session_path):
            try:
                with open(self.session_path, "r") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def get_expiry(self, nick):
        try:
            licenses = db.reference('licenses').get()
            if licenses:
                for key, data in licenses.items():
                    if isinstance(data, dict) and data.get('used_by') == nick:
                        exp = data.get('expiry', 'LIFETIME')
                        if exp == 'LIFETIME':
                            return 'LIFETIME'
                        try:
                            dt = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S")
                            return dt.strftime("%d/%m/%Y")
                        except:
                            return exp
            return "No License"
        except:
            return "Error"
