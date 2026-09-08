@echo off
REM Native Windows backend başlatıcı — WSL kullanmaz.
REM İlk kurulum: apps\backend\.venv-win yoksa "cd apps\backend && uv sync" çalıştırın
REM (UV_PROJECT_ENVIRONMENT=.venv-win ortam değişkeniyle, bkz. README.md).
cd /d "%~dp0apps\backend"
.venv-win\Scripts\python.exe -m uvicorn src.main:app --port 8000
