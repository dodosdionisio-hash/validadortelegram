"""
Script para fazer commit do Sistema de Licenciamento V3.0
"""

import subprocess
import os

def run_command(cmd, description):
    """Executa comando git"""
    print(f"\n⏳ {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} - OK")
        if result.stdout:
            print(f"   {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro: {e}")
        if e.stderr:
            print(f"   {e.stderr.strip()}")
        return False

def main():
    print("="*70)
    print("  GIT COMMIT - SISTEMA DE LICENCIAMENTO V3.0")
    print("="*70)
    
    # Verifica se é repositório git
    if not os.path.exists(".git"):
        print("\n❌ ERRO: Não é um repositório Git!")
        print("   Execute: git init")
        return
    
    # Lista de arquivos novos
    novos_arquivos = [
        "servidor_licencas_v3.py",
        "Criativa/license_validator.py",
        "gerador_licencas_v3.py",
        "gerador_licencas_v3_melhorado.py",
        "build_gerador.py",
        "build_gerador.bat",
        "gerador_licencas.spec",
        "instalar_dependencias.bat",
        "GUIA_IMPLEMENTACAO_V3.md",
        "SISTEMA_LICENCIAMENTO_V3_COMPLETO.md",
        "COMO_COMPILAR_GERADOR.md",
        "COMPILAR_GERADOR_RAPIDO.txt",
        "SOLUCAO_ERRO_TIMEOUT.md",
        "MENU_OTIMIZADO.md",
        "requirements.txt",
        "commit_licenciamento_v3.bat",
        "commit_licenciamento_v3.py"
    ]
    
    # Lista de arquivos modificados
    modificados = [
        "Criativa/app.py",
        "assets/css/dashboard.css",
        "assets/css/usuario_logado.css"
    ]
    
    # Adicionar arquivos
    print("\n" + "="*70)
    print("  ADICIONANDO ARQUIVOS")
    print("="*70)
    
    for arquivo in novos_arquivos + modificados:
        if os.path.exists(arquivo):
            run_command(f'git add "{arquivo}"', f"Adicionando {arquivo}")
        else:
            print(f"⚠️  Arquivo não encontrado: {arquivo}")
    
    # Criar commit
    print("\n" + "="*70)
    print("  CRIANDO COMMIT")
    print("="*70)
    
    commit_message = """feat: Sistema de Licenciamento V3.0 completo

- Implementado sistema profissional de validação de licenças
- Proteção anti-clonagem (1 licença = 1 PC)
- Modo híbrido online/offline com cache criptografado
- Grace period de 90 dias sem internet
- API REST completa para Render
- Gerador de licenças com interface gráfica
- Scripts de compilação para .exe
- Documentação completa
- Menu lateral otimizado (todos itens visíveis)
- Middleware de validação atualizado

Arquivos adicionados:
- servidor_licencas_v3.py
- Criativa/license_validator.py
- gerador_licencas_v3.py
- gerador_licencas_v3_melhorado.py
- build_gerador.py
- Documentação completa

Arquivos modificados:
- Criativa/app.py (middleware de licença)
- assets/css/dashboard.css (menu otimizado)
- requirements.txt (cryptography adicionado)"""
    
    if not run_command(f'git commit -m "{commit_message}"', "Criando commit"):
        print("\n⚠️  Nenhuma alteração para commitar ou erro no commit")
        return
    
    # Push para GitHub
    print("\n" + "="*70)
    print("  ENVIANDO PARA GITHUB")
    print("="*70)
    
    # Verifica branch atual
    result = subprocess.run("git branch --show-current", shell=True, capture_output=True, text=True)
    branch = result.stdout.strip() or "main"
    
    print(f"\n📤 Enviando para branch: {branch}")
    
    if run_command(f"git push origin {branch}", f"Push para origin/{branch}"):
        print("\n" + "="*70)
        print("  ✅ COMMIT CONCLUÍDO COM SUCESSO!")
        print("="*70)
        print("\n📦 Arquivos commitados:")
        print("   - Sistema de Licenciamento V3.0")
        print("   - Gerador de Licenças")
        print("   - Scripts de Build")
        print("   - Documentação Completa")
        print("   - Menu Otimizado")
        print("\n🎉 Tudo enviado para o GitHub!")
    else:
        print("\n❌ Erro ao fazer push")
        print("   Verifique:")
        print("   1. Você tem permissão no repositório")
        print("   2. Está autenticado no Git")
        print("   3. A branch existe no remoto")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Processo cancelado pelo usuário")
    except Exception as e:
        print(f"\n\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPressione ENTER para sair...")
