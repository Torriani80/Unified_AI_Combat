import urllib.request, os

urls = [
    'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx',
    'https://github.com/ultralytics/ultralytics/releases/download/v8.2.0/yolov8n.onnx',
    'https://github.com/ultralytics/assets/releases/latest/download/yolov8n.onnx',
]

out = 'C:/ai-macro-shooting/yolov8n.onnx'

for url in urls:
    try:
        print(f'Tentando: {url[:60]}...')
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            with open(out, 'wb') as f:
                f.write(response.read())
        size = os.path.getsize(out)
        if size > 1000000:
            print(f'OK! {size/1024/1024:.1f} MB')
            break
        else:
            print(f'Arquivo pequeno: {size} bytes')
    except Exception as e:
        print(f'  Falhou: {str(e)[:60]}')
else:
    print('Todas falharam.')
