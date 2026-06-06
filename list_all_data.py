"""Listar todas as chaves no Firebase"""
import firebase_admin
from firebase_admin import credentials, db
from pathlib import Path

base = Path(__file__).parent
cred = credentials.Certificate(str(base / "serviceAccountKey.json"))
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
    })

print("=== TODAS AS LICENCAS ===")
data = db.reference('licenses').get()
if data:
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                print(f"\n  [{k}]")
                for kk, vv in v.items():
                    print(f"    {kk}: {repr(vv)}")
            else:
                print(f"  [{k}]: {repr(v)} (type={type(v).__name__})")
    else:
        print(f"  (data is {type(data).__name__}: {repr(data)})")
else:
    print("  (vazio / None)")

print("\n=== TODOS OS USUARIOS ===")
data = db.reference('users').get()
if data:
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                print(f"\n  [{k}]")
                for kk, vv in v.items():
                    print(f"    {kk}: {repr(vv)}")
            else:
                print(f"  [{k}]: {repr(v)}")
    else:
        print(f"  (data is {type(data).__name__})")
else:
    print("  (vazio / None)")
