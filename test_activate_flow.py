"""Teste fluxo completo: activate_license e check_license_by_hwid"""
import firebase_admin
from firebase_admin import credentials, db
from pathlib import Path

base = Path(__file__).parent
cred = credentials.Certificate(str(base / "serviceAccountKey.json"))
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
    })

HWID = "811F79A0-B669-480D-258B-08BFB86F491E"
NICK = "bruno"
KEY = "BB7C200D-D3F0-4E"

print("1. check_license_by_hwid")
data = db.reference('licenses').get()
found = None
if data:
    for k, v in data.items():
        if isinstance(v, dict) and v.get('hwid') == HWID:
            found = k
            break
print(f"   HWID match? {found}")

print("\n2. activate_license flow (simulado):")
ref = db.reference(f'licenses/{KEY}')
lic_data = ref.get()
print(f"   Lic data: {lic_data}")
if lic_data and isinstance(lic_data, dict):
    print(f"   used_by: '{lic_data.get('used_by')}' == nick '{NICK}'? {lic_data.get('used_by') == NICK}")
    if lic_data.get('used_by') == NICK:
        print("   >>> ATIVACAO VALIDA: used_by == nick <<<")
        print("   >>> Agora setando hwid...")
        ref.update({'hwid': HWID, 'activated_at': '2026-06-02 15:30:00'})
        verif = ref.get()
        print(f"   >>> Apos update: {verif}")
        if verif and verif.get('hwid') == HWID:
            print("   >>> HWID VINCULADO COM SUCESSO <<<")
        else:
            print("   >>> ERRO: HWID nao foi vinculado <<<")
    else:
        print("   >>> ERRO: used_by nao bate <<<")

print("\n3. Verifica denovo check_license_by_hwid:")
data = db.reference('licenses').get()
found = None
if data:
    for k, v in data.items():
        if isinstance(v, dict) and v.get('hwid') == HWID:
            found = k
            break
print(f"   HWID match? {found} (key: {found})")
