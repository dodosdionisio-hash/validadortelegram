@echo off
echo ========================================
echo  GIT COMMIT - SISTEMA DE LICENCIAMENTO V3.0
echo ========================================
echo.

REM Verificar se esta em um repositorio git
if not exist ".git" (
    echo ERRO: Nao e um repositorio Git!
    echo Execute: git init
    pause
    exit /b 1
)

echo [1/4] Adicionando arquivos novos...
git add servidor_licencas_v3.py
git add Criativa/license_validator.py
git add gerador_licencas_v3.py
git add gerador_licencas_v3_melhorado.py
git add build_gerador.py
git add build_gerador.bat
git add gerador_licencas.spec
git add instalar_dependencias.bat
git add GUIA_IMPLEMENTACAO_V3.md
git add SISTEMA_LICENCIAMENTO_V3_COMPLETO.md
git add COMO_COMPILAR_GERADOR.md
git add COMPILAR_GERADOR_RAPIDO.txt
git add SOLUCAO_ERRO_TIMEOUT.md
git add MENU_OTIMIZADO.md
git add requirements.txt

echo.
echo [2/4] Adicionando arquivos modificados...
git add Criativa/app.py
git add assets/css/dashboard.css
git add assets/css/usuario_logado.css

echo.
echo [3/4] Criando commit...
git commit -m "feat: Sistema de Licenciamento V3.0 completo

- Implementado sistema profissional de validacao de licencas
- Protecao anti-clonagem (1 licenca = 1 PC)
- Modo hibrido online/offline com cache criptografado
- Grace period de 90 dias sem internet
- API REST completa para Render
- Gerador de licencas com interface grafica
- Scripts de compilacao para .exe
- Documentacao completa
- Menu lateral otimizado (todos itens visiveis)
- Middleware de validacao atualizado"

echo.
echo [4/4] Enviando para GitHub...
git push origin main

echo.
echo ========================================
echo  COMMIT CONCLUIDO!
echo ========================================
echo.
echo Arquivos commitados:
echo - Sistema de Licenciamento V3.0
echo - Gerador de Licencas
echo - Scripts de Build
echo - Documentacao Completa
echo - Menu Otimizado
echo.
pause
