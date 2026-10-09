@echo off
cd /d %USERPROFILE%\crypto-agency
call venv\Scripts\activate.bat
python monitor.py
pause
