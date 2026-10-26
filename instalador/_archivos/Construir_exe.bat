@echo off
rem Arma dist\AutoMix-Setup.exe (el instalador liviano). Necesita internet para bajar PyInstaller.
cd /d "%~dp0"
set PYX=python
where py >nul 2>nul && (py -3.13 -c "import sys" >nul 2>nul && set PYX=py -3.13 || (py -3.14 -c "import sys" >nul 2>nul && set PYX=py -3.14))
echo Usando: %PYX%
%PYX% -m pip install --upgrade pyinstaller || goto :error
%PYX% -m PyInstaller --onefile --noconsole --clean --name AutoMix-Setup AutoMixInstalador.py || goto :error
echo.
echo Listo: %~dp0dist\AutoMix-Setup.exe
pause
exit /b 0
:error
echo.
echo Algo fallo. Mira el mensaje de arriba.
pause
exit /b 1
