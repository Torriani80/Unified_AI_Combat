"""Teste: resetar HWID de uma chave especifica"""
import firebase_admin
from firebase_admin import credentials, db
from pathlib import Path
import sys

base = Path(__file__).parent
path = str(base / "serviceAccountKey.json")

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
        })
        print("Firebase OK")
except Exception as e:
    print(f"Init ERROR: {e}")
    sys.exit(1)

KEY = "811F79A0-B669-480D-258B-08BFB86F491E"

# 1. Read current state
print(f"\n=== ANTES ===")
ref = db.reference(f'licenses/{KEY}')
data = ref.get()
print(f"Dados atuais: {data}")

# 2. Reset HWID
print(f"\n=== RESETANDO HWID ===")
try:
    # Method: update with empty string
    ref.update({'hwid': ''})
    print("update({'hwid': ''}) executed")
except Exception as e:
    print(f"update ERROR: {e}")

# 3. Verify
print(f"\n=== DEPOIS ===")
data = ref.get()
print(f"Dados apos reset: {data}")
if data:
    hwid = data.get('hwid', '---KEY NOT FOUND---')
    print(f"hwid = '{hwid}'")
    if hwid == '':
        print(">>> RESET BEM SUCEDIDO <<<")
    elif hwid is None:
        print(">>> hwid = None (pode ser problema) <<<")
    else:
        print(f">>> hwid = {repr(hwid)} <<<")
else:
    print(">>> KEY NAO ENCONTRADA <<<")

# 4. Also try delete() approach
print(f"\n=== TENTANDO DELETE() DIRETO ===")
try:
    ref2 = db.reference(f'licenses/{KEY}/hwid')
    ref2.delete()
    data = ref.get()
    print(f"Dados apos delete hwid: {data}")
except Exception as e:
    print(f"delete hwid ERROR: {e}")

print(f"\n=== VERIFICACAO FINAL ===")
data = ref.get()
print(f"Dados finais: {data}")
