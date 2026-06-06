"""Teste direto de escrita no Firebase (sem PyInstaller)"""
import firebase_admin
from firebase_admin import credentials, db
from pathlib import Path
from datetime import datetime

base = Path(__file__).parent
path = str(base / "serviceAccountKey.json")
print(f"Credential path: {path}")
print(f"File exists: {Path(path).exists()}")

try:
    cred = credentials.Certificate(path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
    })
    print("Firebase initialized OK")
except Exception as e:
    print(f"Firebase init ERROR: {e}")
    import traceback; traceback.print_exc()
    exit(1)

# Test: write a test node
test_key = f"TESTE-{datetime.now().strftime('%H%M%S')}"
print(f"\nWriting to /licenses/{test_key} ...")
try:
    ref = db.reference(f'licenses/{test_key}')
    ref.set({
        "expiry": "LIFETIME",
        "used_by": "teste",
        "hwid": None,
        "status": "ativa",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    print("Write OK - no exception")
except Exception as e:
    print(f"Write ERROR: {e}")
    import traceback; traceback.print_exc()

# Read back
print(f"\nReading /licenses/{test_key} ...")
try:
    data = db.reference(f'licenses/{test_key}').get()
    print(f"Read result: {data}")
except Exception as e:
    print(f"Read ERROR: {e}")

# Delete
print(f"\nDeleting /licenses/{test_key} ...")
try:
    # Try multiple methods
    ref = db.reference(f'licenses/{test_key}')
    
    # Method 1: delete()
    ref.delete()
    data = ref.get()
    print(f"After delete() -> get(): {data}")
    
    # Method 2: set(None) 
    ref.set(None)
    data = ref.get()
    print(f"After set(None) -> get(): {data}")
    
    # Method 3: set({}) 
    ref.set({})
    data = ref.get()
    print(f"After set({{}}) -> get(): {data}")
except Exception as e:
    print(f"Delete ERROR: {e}")
    import traceback; traceback.print_exc()

# Read all licenses
print("\nAll licenses:")
all_lics = db.reference('licenses').get()
if all_lics:
    for k, v in all_lics.items():
        print(f"  {k}: {type(v).__name__} = {v}")
else:
    print("  (none)")

print("\nDone!")
