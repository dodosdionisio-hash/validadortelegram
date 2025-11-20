@echo off
echo ========================================
echo  INSTALANDO DEPENDENCIAS
echo ========================================
echo.

echo [1/3] Atualizando pip...
python -m pip install --upgrade pip

echo.
echo [2/3] Instalando PyInstaller...
pip install pyinstaller

echo.
echo [3/3] Instalando dependencias do gerador...
pip install requests

echo.
echo ========================================
echo  INSTALACAO CONCLUIDA!
echo ========================================
echo.
echo Agora voce pode compilar o gerador executando:
echo   python build_gerador.py
echo.
pause
