import os
import subprocess
import threading
import time


def run_bot():
    """Roda o bot de licenças (Telegram)."""
    # Usa o mesmo Python do ambiente
    print("[start_services] Iniciando bot_licencas.py...")
    # stdout/stderr vão para os logs do Render
    subprocess.call(["python", "bot_licencas.py"])


def run_server():
    """Roda o servidor de validação via gunicorn."""
    port = os.environ.get("PORT", "10000")
    print(f"[start_services] Iniciando servidor_validacao na porta {port}...")
    subprocess.call([
        "gunicorn",
        "servidor_validacao:app",
        "-b",
        f"0.0.0.0:{port}",
    ])


if __name__ == "__main__":
    print("=" * 60)
    print("INICIANDO SERVIÇOS: BOT TELEGRAM + SERVIDOR DE VALIDAÇÃO")
    print("=" * 60)

    # Sobe o bot em uma thread separada
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Sobe o servidor (processo principal)
    run_server()
