import sys, os, time
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

print("=" * 70)
print("  RELATORIO COMPLETO - UNIFIED AI COMBAT")
print(f"  {time.strftime('%d/%m/%Y %H:%M:%S')}")
print("=" * 70)

results = []
def r(name, status, detail=""):
    results.append((name, status, detail))

# ============================================================
# 1. SINTAXE
# ============================================================
py_files = sorted([f for f in os.listdir('.') if f.endswith('.py') and os.path.isfile(f)])
skip_patterns = ('pyinstxtractor', 'delete_davi', 'list_files', 'setup_firebase',
                 'autoreload', 'storemagic', 'deduperreload')
files_ok = 0
files_err = []
for f in py_files:
    if any(s in f for s in skip_patterns): continue
    rcode = os.system(f'python -m py_compile "{f}"')
    if rcode == 0:
        files_ok += 1
    else:
        files_err.append(f)
status = "OK" if not files_err else f"PARCIAL ({len(files_err)} erro(s))"
detail = f"{files_ok}/{len(py_files)} arquivos"
if files_err:
    detail += f" | ERRO: {files_err}"
r(f"[1/6] Syntax check", status, detail)

# ============================================================
# 2. IMPORTS
# ============================================================
r(f"[2/6] Module imports", "---", "")

all_imports = [
    ("config", "config"),
    ("logger", "log"),
    ("screen_capture", "ScreenCapturer"),
    ("weapon_detector", "WeaponDetector"),
    ("aim_tracker", "AimTracker"),
    ("aim_calculation", "AimCalculator"),
    ("command_executor", "CommandExecutor"),
    ("CombatCore", "UnifiedCommandExecutor"),
    ("CombatSecurity", "CombatSecurity"),
    ("TacticalHUD", "TacticalHUD"),
    ("crosshair_overlay", "CrosshairOverlay"),
    ("object_detection", "ObjectDetector"),
    ("UnifiedObjectDetector", "UnifiedObjectDetector"),
    ("main", "MacroSystem"),
]
import_ok = 0
import_fail = 0
for mod_name, cls_name in all_imports:
    try:
        mod = __import__(mod_name, fromlist=[cls_name])
        cls = getattr(mod, cls_name)
        r(f"  {mod_name}.{cls_name}", "OK")
        import_ok += 1
    except Exception as e:
        r(f"  {mod_name}.{cls_name}", "ERRO", str(e)[:60])
        import_fail += 1

# ============================================================
# 3. INSTANTIATION (safe only - no GUI/display needed)
# ============================================================
r(f"[3/6] Instantiation", "---", "")

def safe_instantiate(name, import_path, class_name, constructor_args=None):
    try:
        mod = __import__(import_path, fromlist=[class_name])
        cls = getattr(mod, class_name)
        args = constructor_args or ()
        obj = cls(*args) if isinstance(args, tuple) else cls(**args)
        r(f"  {name}", "OK")
        return obj
    except Exception as e:
        r(f"  {name}", "ERRO", str(e)[:80])
        return None

# Safe (no GUI/display)
safe_instantiate("AimTracker()", "aim_tracker", "AimTracker")
safe_instantiate("AimCalculator()", "aim_calculation", "AimCalculator")
safe_instantiate("UnifiedCommandExecutor(enabled=True)", "CombatCore", "UnifiedCommandExecutor", (True,))
safe_instantiate("CombatSecurity()", "CombatSecurity", "CombatSecurity")

# TacticalHUD - class only (not instantiated, needs QApp)
try:
    import TacticalHUD as th_mod
    first_line = open("TacticalHUD.py", encoding="utf-8").readline()
    winsound_ok = "winsound" in first_line
    if winsound_ok:
        r("  TacticalHUD (winsound check)", "OK")
    else:
        r("  TacticalHUD (winsound check)", "ERRO", "winsound nao encontrado na linha 1")
except Exception as e:
    r("  TacticalHUD (winsound check)", "ERRO", str(e)[:60])

# CrosshairOverlay - skip (needs QApplication)
r("  CrosshairOverlay()", "SKIP", "Requer QApplication (PyQt5)")

# ObjectDetector
safe_instantiate("ObjectDetector(method='template')", "object_detection", "ObjectDetector", {"method": "template"})

# UnifiedObjectDetector
safe_instantiate("UnifiedObjectDetector(method='template')", "UnifiedObjectDetector", "UnifiedObjectDetector", ("template",))

# MacroSystem
safe_instantiate("MacroSystem(test_mode=True)", "main", "MacroSystem", {"test_mode": True})

# ============================================================
# 4. FIX VERIFICATION
# ============================================================
r(f"[4/6] Fix verification", "---", "")

def check_file(name, path, check_fn):
    try:
        content = open(path, encoding="utf-8").read()
        if check_fn(content):
            r(f"  {name}", "OK")
        else:
            r(f"  {name}", "ERRO", "condicao nao satisfeita")
    except Exception as e:
        r(f"  {name}", "ERRO", str(e)[:60])

# UUID removal
if os.path.exists("weapon_templates/590543d8-c6b5-41bd-bbb5-1bf10ce8eef4.png"):
    r("  UUID removido (source)", "ERRO", "arquivo ainda existe")
else:
    r("  UUID removido (source)", "OK")

if os.path.exists("dist/TacticalSetup/_internal/weapon_templates/590543d8-c6b5-41bd-bbb5-1bf10ce8eef4.png"):
    r("  UUID removido (dist)", "ERRO", "arquivo ainda existe")
else:
    r("  UUID removido (dist)", "OK")

check_file("winsound import (linha 1)", "TacticalHUD.py", lambda c: "winsound" in c.split("\n")[0])
check_file("main: AimCalculator import", "main.py", lambda c: "from aim_calculation import AimCalculator" in c)
check_file("main: run() method", "main.py", lambda c: "def run(self)" in c)
check_file("CombatCore: self.shot_counter", "CombatCore.py", lambda c: "self.shot_counter" in c)
check_file("CombatCore: sem _log_shots local", "CombatCore.py", lambda c: "_log_shots = 0" not in c)
check_file("test_yolo: ObjectDetector", "test_yolo.py", lambda c: "from object_detection import ObjectDetector" in c)
check_file("UnifiedMain: CrosshairOverlay import", "UnifiedMain.py", lambda c: "from crosshair_overlay import CrosshairOverlay" in c)
check_file("UnifiedMain: CrosshairOverlay criado", "UnifiedMain.py", lambda c: "self.crosshair = CrosshairOverlay()" in c)
check_file("UnifiedMain: crosshair set no HUD", "UnifiedMain.py", lambda c: "self.hud.set_crosshair_overlay" in c)
check_file(".gitignore criado", ".gitignore", lambda c: True)
check_file("serviceAccountKey no .gitignore", ".gitignore", lambda c: "serviceAccountKey" in c)

# Password migration test
try:
    from CombatSecurity import _hash_password, CombatSecurity
    pw = "test123"
    hashed = _hash_password(pw)
    if hashed == _hash_password(pw):
        r("  _hash_password (SHA256)", "OK")
    else:
        r("  _hash_password (SHA256)", "ERRO", "hash mismatch")
    cs = CombatSecurity()
    # hash stored
    if cs._check_password(hashed, pw):
        r("  _check_password (hash stored)", "OK")
    else:
        r("  _check_password (hash stored)", "ERRO")
    # plaintext stored (migracao)
    if cs._check_password(pw, pw):
        r("  _check_password (plaintext stored)", "OK")
    else:
        r("  _check_password (plaintext stored)", "ERRO")
    # wrong password
    if not cs._check_password(hashed, "wrong"):
        r("  _check_password (wrong password)", "OK")
    else:
        r("  _check_password (wrong password)", "ERRO")
except Exception as e:
    r("  Password migration tests", "ERRO", str(e)[:80])

# RateLimiter test
try:
    from CombatSecurity import RateLimiter
    rl = RateLimiter(3, 1)
    ok = sum(1 for _ in range(4) if rl.allow())
    if ok == 3:
        r("  RateLimiter (3/4 allowed)", "OK")
    else:
        r("  RateLimiter (3/4 allowed)", "ERRO", f"allowed {ok}")
    time.sleep(1.1)
    if rl.allow():
        r("  RateLimiter (reset after delay)", "OK")
    else:
        r("  RateLimiter (reset after delay)", "ERRO")
except Exception as e:
    r("  RateLimiter tests", "ERRO", str(e)[:80])

# ============================================================
# 5. BUILDS
# ============================================================
r(f"[5/6] Builds", "---", "")

if os.path.exists("dist/Unified_Combat_V1.exe"):
    size_mb = os.path.getsize("dist/Unified_Combat_V1.exe") / 1024 / 1024
    try:
        import cv2
        r("  cv2 (OpenCV) disponivel", "OK", cv2.__version__)
    except ImportError:
        r("  cv2 (OpenCV) disponivel", "ERRO", "cv2 nao importavel - vai crashar no runtime")
    r("  Unified_Combat_V1.exe", "OK", f"{size_mb:.1f} MB")
else:
    r("  Unified_Combat_V1.exe", "ERRO", "nao encontrado")

if os.path.exists("dist/AdminPanel/AdminPanel.exe"):
    size_mb = os.path.getsize("dist/AdminPanel/AdminPanel.exe") / 1024 / 1024
    r("  AdminPanel.exe", "OK", f"{size_mb:.1f} MB")
else:
    r("  AdminPanel.exe", "ERRO", "nao encontrado")

# ============================================================
# 6. ASSETS
# ============================================================
r(f"[6/6] Assets & config", "---", "")

if os.path.exists("yolov8n.onnx"):
    size_mb = os.path.getsize("yolov8n.onnx") / 1024 / 1024
    r("  yolov8n.onnx", "OK", f"{size_mb:.1f} MB")
else:
    r("  yolov8n.onnx", "AUSENTE", "YOLO desativado (fallback para template)")

if os.path.exists("recoil_patterns.json"):
    size_kb = os.path.getsize("recoil_patterns.json") / 1024
    r("  recoil_patterns.json", "OK", f"{size_kb:.1f} KB")
else:
    r("  recoil_patterns.json", "AUSENTE")

if os.path.exists("presets.json"):
    size_kb = os.path.getsize("presets.json") / 1024
    r("  presets.json", "OK", f"{size_kb:.1f} KB")
else:
    r("  presets.json", "AUSENTE")

if os.path.exists("config_pubg.json"):
    size_kb = os.path.getsize("config_pubg.json") / 1024
    r("  config_pubg.json", "OK", f"{size_kb:.1f} KB")
else:
    r("  config_pubg.json", "AUSENTE")

if os.path.exists("serviceAccountKey.json"):
    size_kb = os.path.getsize("serviceAccountKey.json") / 1024
    r("  serviceAccountKey.json", "OK", f"{size_kb:.1f} KB (ATENCAO: .gitignore aplicado)")
else:
    r("  serviceAccountKey.json", "AUSENTE", "Firebase desativado")

# ============================================================
# SUMMARY
# ============================================================
print("=" * 70)
ok_count = sum(1 for _, s, _ in results if s == "OK")
err_count = sum(1 for _, s, _ in results if s == "ERRO")
skip_count = sum(1 for _, s, _ in results if s == "SKIP")
ausente_count = sum(1 for _, s, _ in results if s in ("AUSENTE",))
other_count = sum(1 for _, s, _ in results if s == "---")

total_checks = len(results) - other_count  # exclude section headers

print(f"\n  RESUMO FINAL:")
print(f"  {'=' * 50}")
print(f"  Total de verificacoes: {total_checks}")
print(f"  PASSOU: {ok_count}")
print(f"  FALHOU: {err_count}")
print(f"  PULADO: {skip_count}")
print(f"  AUSENTE: {ausente_count}")
print()

if err_count == 0:
    print("  STATUS: 100% - TODOS OS TESTES PASSARAM")
else:
    print(f"  STATUS: {err_count} FALHA(S) ENCONTRADA(S)")

if skip_count > 0:
    print(f"  NOTA: {skip_count} teste(s) foram pulados por exigirem GUI (PyQt5 QApplication)")
if ausente_count > 0:
    print(f"  NOTA: {ausente_count} asset(s) estao ausentes (fallbacks serao usados)")

print(f"\n  Relatorio gerado em: {time.strftime('%d/%m/%Y %H:%M:%S')}")
print("=" * 70)
