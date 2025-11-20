"""
Script para compilar o Gerador de Licenças em executável
"""

import os
import sys
import subprocess
import shutil

def print_header(msg):
    print("\n" + "="*60)
    print(f"  {msg}")
    print("="*60 + "\n")

def run_command(cmd, description):
    """Executa comando e mostra progresso"""
    print(f"⏳ {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} - OK")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro: {e}")
        print(f"   Output: {e.output}")
        return False

def main():
    print_header("COMPILADOR - GERADOR DE LICENÇAS V3.0")
    
    # Passo 1: Instalar PyInstaller
    if not run_command(
        "pip install pyinstaller",
        "Instalando PyInstaller"
    ):
        print("\n❌ Falha ao instalar PyInstaller")
        return
    
    # Passo 2: Limpar builds anteriores
    print("\n⏳ Limpando builds anteriores...")
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("Gerador de Licencas v3.0.spec"):
        os.remove("Gerador de Licencas v3.0.spec")
    print("✅ Limpeza concluída")
    
    # Passo 3: Compilar
    print_header("COMPILANDO EXECUTÁVEL")
    
    cmd = [
        "pyinstaller",
        "--onefile",              # Arquivo único
        "--windowed",             # Sem console
        "--name", "Gerador de Licencas v3.0",
        "--clean",                # Limpar cache
        "--noconfirm",            # Não pedir confirmação
        # Imports ocultos
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.simpledialog",
        "--hidden-import=requests",
        "--hidden-import=urllib3",
        # Excluir pacotes desnecessários
        "--exclude-module=matplotlib",
        "--exclude-module=numpy",
        "--exclude-module=pandas",
        "--exclude-module=scipy",
        "--exclude-module=PIL",
        # Arquivo fonte (versão melhorada)
        "gerador_licencas_v3_melhorado.py"
    ]
    
    if not run_command(" ".join(cmd), "Compilando executável"):
        print("\n❌ Falha na compilação")
        return
    
    # Passo 4: Verificar resultado
    exe_path = os.path.join("dist", "Gerador de Licencas v3.0.exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print_header("COMPILAÇÃO CONCLUÍDA COM SUCESSO!")
        print(f"📦 Executável criado:")
        print(f"   Caminho: {os.path.abspath(exe_path)}")
        print(f"   Tamanho: {size_mb:.2f} MB")
        print("\n✅ Pronto para distribuição!")
    else:
        print("\n❌ Executável não foi criado")
        return
    
    # Passo 5: Limpar arquivos temporários
    print("\n⏳ Limpando arquivos temporários...")
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("Gerador de Licencas v3.0.spec"):
        os.remove("Gerador de Licencas v3.0.spec")
    print("✅ Limpeza concluída")
    
    print_header("PROCESSO FINALIZADO")
    print("O executável está em: dist\\Gerador de Licencas v3.0.exe")
    print("\nVocê pode distribuir este arquivo para seus clientes.")

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
