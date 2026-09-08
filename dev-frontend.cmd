@echo off
REM Native Windows frontend başlatıcı — WSL kullanmaz.
REM İlk kurulum: apps\frontend\node_modules yoksa "cd apps\frontend && npm install" çalıştırın.
cd /d "%~dp0apps\frontend"
npm run dev
