@echo off
rem Borra lo que instalo el instalador (la carpeta %LOCALAPPDATA%\AutoMix y los accesos directos). No toca tu carpeta de desarrollo.
echo Se va a borrar: %LOCALAPPDATA%\AutoMix y los accesos directos de AutoMix (Escritorio y menu Inicio).
choice /m "Continuar"
if errorlevel 2 exit /b 0
rmdir /s /q "%LOCALAPPDATA%\AutoMix"
del "%USERPROFILE%\Desktop\AutoMix.lnk" 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\AutoMix.lnk" 2>nul
echo Listo.
pause
