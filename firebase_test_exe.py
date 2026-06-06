import json, os, sys, uuid
from pathlib import Path
from datetime import datetime

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
    EXE_DIR = BASE_DIR

results = []

def log(msg):
    results.append(str(msg))

try:
    import firebase_admin
    from firebase_admin import credentials, db

    path = str(BASE_DIR / "serviceAccountKey.json")
    if not os.path.exists(path) and getattr(sys, 'frozen', False):
        path = str(Path(sys.executable).parent / "serviceAccountKey.json")
    log(f"Cred path: {path}")
    log(f"File exists: {os.path.exists(path)}")

    if not firebase_admin._apps:
        cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
        })
        log("Firebase init OK")

    # READ all licenses
    lics = db.reference('licenses').get()
    log(f"Licencas lidas: {len(lics) if lics else 0}")
    if lics:
        for k, v in lics.items():
            if isinstance(v, dict):
                log(f"  {k}: hwid={v.get('hwid','?')} used_by={v.get('used_by','?')}")

    # WRITE test key
    test_key = "TESTE-" + str(uuid.uuid4()).upper()[:8]
    ref = db.reference(f'licenses/{test_key}')
    ref.set({
        "expiry": "LIFETIME", "used_by": "teste",
        "hwid": "", "status": "ativa",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    log(f"WRITE: OK ({test_key})")

    data = ref.get()
    log(f"READ after write: {data is not None}")

    # UPDATE hwid
    ref.update({'hwid': 'TEST-HWID-123'})
    data = ref.get()
    log(f"UPDATE: OK - hwid = '{data.get('hwid', 'N/A')}'")

    # DELETE
    ref.delete()
    data = ref.get()
    log(f"DELETE: OK - data after delete is None: {data is None}")

except Exception as e:
    import traceback
    log(f"ERRO: {e}")
    log(traceback.format_exc())

with open(EXE_DIR / "firebase_test_result.txt", "w") as f:
    f.write("\n".join(results))
