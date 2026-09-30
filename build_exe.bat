@echo off
chcp 65001 >nul
REM 一键打包 Windows 可执行文件（需要本机已安装 Python 3.9+ 和 Google Chrome）
cd /d %~dp0
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --onefile --name bhh-auto-sign --collect-all patchright --hidden-import sign --hidden-import login app.py
echo.
echo 打包完成：dist\bhh-auto-sign.exe
pause
