$host.UI.RawUI.WindowTitle = "ASSISTENTE IA LOCAL (Aider)"
$host.UI.RawUI.BackgroundColor = "Black"
$host.UI.RawUI.ForegroundColor = "Green"
Clear-Host

$art = @"

  ▄▄▄▄   ██▓▓█████▄ ▓█████  ██▀███  
 ▓█████▄▓██▒▒██▀ ██▌▓█   ▀ ▓██ ▒ ██▒
 ▒██▒ ▄██▒██▒░██   █▌▒███   ▓██ ░▄█ ▒
 ▒██░█▀  ░██░░▓█▄   ▌▒▓█  ▄ ▒██▀▀█▄  
 ░▓█▀▀█▄ ░██░░▒████▓ ░▒████▒░██▓ ▒██▒
  ▒▒▓ ▒█▒░▓  ▒▒▓  ▒ ░░ ▒░ ░░ ▒▓ ░▒▓░
  ░▒▓ ░ ░ ▒ ░░ ▒  ▒  ░ ░  ░  ░▒ ░ ▒░
  ░░▒ ░ ░ ▒ ░░ ░  ░    ░     ░░   ░ 
   ░    ░    ░        ░  ░   ░     
"@

Write-Host $art -ForegroundColor Green
Write-Host "`n"
Write-Host "  ==================================================" -ForegroundColor DarkGray
Write-Host "       AIDER - ASSISTENTE DE CODIGO LOCAL" -ForegroundColor Yellow
Write-Host "       Modelo: Qwen 2.5 Coder 7B (100% local)" -ForegroundColor Cyan
Write-Host "  ==================================================" -ForegroundColor DarkGray

Write-Host "`n  Inicializando Aider..." -ForegroundColor Yellow

# Caminho completo do Aider (já que não está no PATH)
$aiderPath = "C:\Users\Bruno\AppData\Roaming\Python\Python312\Scripts\aider.exe"

& $aiderPath --model ollama/qwen2.5-coder:7b --no-git
