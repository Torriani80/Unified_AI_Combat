import os, struct

exe_path = r'C:\Users\Bruno\Desktop\W1364AT5ADET\3MLXONFR66.exe'
size = os.path.getsize(exe_path)
print(f'File size: {size} bytes ({size/1024/1024:.1f} MB)')

with open(exe_path, 'rb') as f:
    data = f.read()

# Common PyInstaller indicators
magics = [
    (b'PYINSTALLER', 'PyInstaller cookie (5+)'),
    (b'PyInstaller', 'PyInstaller (older)'),
    (b'PYZ\x00', 'PYZ archive magic'),
    (b'PKG\x00', 'PKG archive magic'),
    (b'MEI\x00', 'MEI cookie'),
    (b'MEN\x00\x00\x00', 'MEN cookie'),
    (b'upx\x00', 'UPX compressed'),
]

for magic, desc in magics:
    idx = 0
    count = 0
    first = None
    while True:
        idx = data.find(magic, idx)
        if idx < 0:
            break
        count += 1
        if first is None:
            first = idx
        idx += 1

    if count > 0:
        pct = first / size * 100 if first else 0
        print(f'{desc}: {count} vezes, primeira em offset {first} ({pct:.1f}%)')
    else:
        print(f'{desc}: nao encontrado')

# Python 3.12 .pyc magic
pyc_magic_312 = bytes([0x6f, 0x0d, 0x0d, 0x0a])
idx = data.find(pyc_magic_312)
count = 0
positions = []
while idx >= 0:
    count += 1
    positions.append(idx)
    idx = data.find(pyc_magic_312, idx + 1)
print(f'\nPython 3.12 .pyc magic: {count} ocorrencias')
if positions:
    print(f'Primeira em offset: {positions[0]} ({positions[0]/size*100:.1f}%)')
    for p in positions[:5]:
        print(f'  offset {p} -> {(p/size)*100:.1f}%')

# Look for module names
print('\nBuscando nomes de modulos...')
for marker in [b'config.py', b'__main__', b'main.py', b'object_detection', 
               b'aim_calculation', b'command_executor', b'screen_capture',
               b'test_data_generator', b'weapon_recognition', b'PubgAim',
               b'DropboxUpdate', b'main_window']:
    idx = data.find(marker)
    if idx >= 0:
        ctx = data[max(0,idx-10):idx+len(marker)+20]
        r = ''.join(chr(b) if 32 <= b < 127 else '.' for b in ctx)
        pct = idx / size * 100
        print(f'  "{marker.decode()}" em offset {idx} ({pct:.1f}%): {r}')
    else:
        print(f'  "{marker.decode()}": nao encontrado')

# Also search for shape PNG references
for marker in [b'shapem416', b'shapeakm', b'shapekar98k', b'weapons_configs']:
    idx = data.find(marker)
    if idx >= 0:
        print(f'  "{marker.decode()}" encontrado em offset {idx} ({idx/size*100:.1f}%)')

print('\nAnalise concluida.')
