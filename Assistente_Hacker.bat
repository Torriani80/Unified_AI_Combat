@echo off
cls
echo Iniciando Assistente Aider...
cd /d "C:\Users\Bruno\Desktop\Unified_AI_Combat"
C:\Users\Bruno\AppData\Roaming\Python\Python312\Scripts\aider.exe --model ollama/qwen2.5-coder:7b --no-git --chat-history-file .aider.chat.history.md --input-history-file .aider.input.history
pause
