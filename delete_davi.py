"""Deletar tudo relacionado ao Davi + mostrar estado final"""
import firebase_admin
from firebase_admin import credentials, db
from pathlib import Path

base = Path(__file__).parent
cred = credentials.Certificate(str(base / "serviceAccountKey.json"))
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
    })

print("=== ANTES ===")
lics = db.reference('licenses').get()
if lics:
    for k, v in lics.items():
        if isinstance(v, dict):
            print(f"  LICENSE {k}: used_by={v.get('used_by','?')}")

users = db.reference('users').get()
if users:
    for k in users:
        print(f"  USER {k}")

# Find license for Davi
davi_key = None
if lics:
    for k, v in lics.items():
        if isinstance(v, dict) and v.get('used_by','').lower() == 'davi':
            davi_key = k
            break

print(f"\n=== DELETANDO DAVI ===")
if davi_key:
    ref = db.reference(f'licenses/{davi_key}')
    ref.delete()
    print(f"License {davi_key} deleted")

ref = db.reference('users/Davi')
ref.delete()
print(f"User Davi deleted")

print("\n=== DEPOIS ===")
lics = db.reference('licenses').get()
if lics:
    for k, v in lics.items():
        if isinstance(v, dict):
            print(f"  LICENSE {k}: used_by={v.get('used_by','?')}")
else:
    print("  No licenses")

users = db.reference('users').get()
if users:
    for k in users:
        print(f"  USER {k}")
else:
    print("  No users")

print("\nPronto! Pode criar um novo usuario e testar o fluxo completo.")
