import firebase_admin
from firebase_admin import credentials, db
from pathlib import Path

base = Path(__file__).parent
cred_path = str(base / "serviceAccountKey.json")

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'
})

print("[SETUP] Criando estrutura de teste...\n")

# Cria uma licença de teste (simula o que o App de Controle do admin faria)
db.reference('licenses/KEY-TESTE-001').set({
    'used_by': None,
    'hwid': None,
    'status': 'ativa',
    'created_at': '2026-06-02 12:00:00'
})
print("[SETUP] Licenca de teste criada: /licenses/KEY-TESTE-001")
print("       status: ativa, hwid: null (disponivel para vincular)\n")

print("=== TESTE RAPIDO ===")
print("1. Execute o .exe")
print("2. Digite USER: Teste  |  PASSWORD: 123  |  KEY: KEY-TESTE-001")
print("3. Clique em ATIVAR")
print("4. O sistema vai vincular a key ao HWID do seu PC")
print("5. Feche e abra de novo - vai logar automaticamente!\n")

print("[SETUP] Para simular o fluxo completo de registro+aprovacao:")
print("1. No .exe clique em REGISTRAR com USER + PASSWORD")
print("2. Depois execute este comando no terminal:")
print("   python -c \"")
print("import firebase_admin")
print("from firebase_admin import credentials, db")
print("cred = credentials.Certificate('serviceAccountKey.json')")
print("firebase_admin.initialize_app(cred, {'databaseURL': 'https://macro-5c92d-default-rtdb.firebaseio.com'})")
print("db.reference('users/SEU_NICK').update({'status': 'aprovado'})")
print("db.reference('licenses/KEY-SEU-NICK').set({'used_by': 'SEU_NICK', 'hwid': None, 'status': 'ativa'})")
print("print('Aprovado!')")
print("   \"")
