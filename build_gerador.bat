@echo off
echo ========================================
echo  COMPILANDO GERADOR DE LICENCAS
echo ========================================
echo.

REM Instalar PyInstaller se necessario
echo [1/4] Verificando PyInstaller...
pip install pyinstaller --quiet

echo.
echo [2/4] Limpando builds anteriores...
if exist "dist\Gerador de Licencas.exe" del "dist\Gerador de Licencas.exe"
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo [3/4] Compilando executavel...
pyinstaller --onefile ^
    --windowed ^
    --name "Gerador de Licencas" ^
    --icon=NONE ^
    --add-data "gerador_licencas_v3.py;." ^
    --hidden-import=tkinter ^
    --hidden-import=requests ^
    gerador_licencas_v3.py

echo.
echo [4/4] Limpando arquivos temporarios...
if exist "Gerador de Licencas.spec" del "Gerador de Licencas.spec"
if exist "build" rmdir /s /q "build"

echo.
echo ========================================
echo  COMPILACAO CONCLUIDA!
echo ========================================
echo.
echo Executavel criado em: dist\Gerador de Licencas.exe
echo.
pause
