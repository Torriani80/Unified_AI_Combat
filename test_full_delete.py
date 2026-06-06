"""Check Firebase state + test delete on a temp key"""
import firebase_admin
from firebase_admin import credentials, db
from pathlib import Path
from datetime import datetime
import uuid

base = Path(__file__).parent
cred = credentials.Certificate(str(base / "serviceAccountKey.json"))
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
    })

print("=== CURRENT STATE ===")
lics = db.reference('licenses').get()
if lics and isinstance(lics, dict):
    for k, v in lics.items():
        if isinstance(v, dict):
            print(f"  LICENSE {k}: hwid='{v.get('hwid','')}' used_by={v.get('used_by','?')}")
        else:
            print(f"  LICENSE {k}: {type(v).__name__}")
else:
    print("  No licenses")

users = db.reference('users').get()
if users and isinstance(users, dict):
    for k, v in users.items():
        if isinstance(v, dict):
            print(f"  USER {k}: status={v.get('status','?')}")
else:
    print("  No users")

print("\n=== TEST: WRITE + DELETE a temp key ===")
test_key = "TEST-" + str(uuid.uuid4()).upper()[:8]
ref = db.reference(f'licenses/{test_key}')
ref.set({
    "expiry": "LIFETIME", "used_by": "test",
    "hwid": "", "status": "ativa",
    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
})
print(f"Created temp key: {test_key}")

# Read back
data = ref.get()
print(f"Read: {data is not None}")

# Delete
ref.delete()
data = ref.get()
print(f"After delete: {data}")

# Verify it's gone from full scan
lics = db.reference('licenses').get()
found = test_key in lics if lics else False
print(f"Key exists in full scan: {found}")
print("DELETE WORKED!" if not found else "DELETE FAILED!")

print("\n=== DELETANDO LICENCA EXISTENTE BB7C200D ===")
ref = db.reference('licenses/BB7C200D-D3F0-4E')
ref.delete()
data = ref.get()
print(f"Apos delete BB7C200D: {data}")

lics = db.reference('licenses').get()
print(f"Licenses restantes: {len(lics) if lics else 0}")
if lics:
    for k in lics:
        print(f"  {k}")
