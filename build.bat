@echo off
echo ============================================
echo   Building J.A.R.V.I.S  Standalone App
echo ============================================
echo.

C:\Python313\python.exe -m PyInstaller ^
    --name "Jarvis" ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --icon "assets\jarvis_icon.ico" ^
    --add-data "config.py;." ^
    --add-data "voice_cache;voice_cache" ^
    --hidden-import "pyttsx3.drivers" ^
    --hidden-import "pyttsx3.drivers.sapi5" ^
    --hidden-import "edge_tts" ^
    --hidden-import "pygame" ^
    --hidden-import "customtkinter" ^
    --hidden-import "speech_recognition" ^
    --hidden-import "sounddevice" ^
    --hidden-import "numpy" ^
    --hidden-import "pystray" ^
    --hidden-import "pystray._win32" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL.Image" ^
    --hidden-import "PIL.ImageDraw" ^
    --hidden-import "PIL.ImageFont" ^
    --collect-all "customtkinter" ^
    --collect-all "edge_tts" ^
    jarvis_app.py

echo.
if exist "dist\Jarvis.exe" (
    echo ============================================
    echo   BUILD SUCCESSFUL!
    echo   Your app is at: dist\Jarvis.exe
    echo ============================================
) else (
    echo   BUILD FAILED - check errors above
)
pause
