# STATUS - Unified AI Combat

## Build Atual
- `dist\Unified_Combat_V1.exe` - 187 MB (onefile, noconsole)
- Build otimizado sem torch, tensorflow, transformers, scipy, sklearn, matplotlib

## Correcoes Aplicadas (05/06/2026)

### 1. `CombatCore.py` - Log excessivo de recoil
- **Antes**: Logava a cada tiro individualmente
- **Depois**: Loga apenas nos primeiros 5 tiros, depois a cada 30 tiros

### 2. `CombatSecurity.py` - Path resolution simplificado
- **Antes**: Usava `getattr(self, "bundled_path", runtime_path)` confuso
- **Depois**: Verifica APPDATA primeiro, depois fallback para diretorio do projeto

### 3. `weapon_detector.py` + `config_pubg.json` - Coordenadas hardcoded
- **Antes**: Regioes de attachment fixas em 1920x1080
- **Depois**: Escala automaticamente proporcional a resolucao da tela

### 4. `build.bat` - Build otimizado
- **Antes**: Incluia torch, tensorflow, transformers, etc. (desnecessarios)
- **Depois**: Exclui 15+ pacotes pesados, gerando .exe mais rapido e enxuto

## Bugs Anteriores (ja corrigidos)
- `config_pubg.json` nunca carregado (adicionado `load_from_json`)
- Metodo `_val()` duplicado removido
- `Detection.area` property adicionada
- YOLO letterbox scaling corrigido
- `get_center_of_screen` adicionado ao UnifiedObjectDetector

## Para Executar
```powershell
.\dist\Unified_Combat_V1.exe
```
