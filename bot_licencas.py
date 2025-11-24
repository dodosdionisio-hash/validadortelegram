"""
Bot do Telegram para Gerenciamento de Licenças
Execute este arquivo para iniciar o bot
"""

import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import hashlib
import random
import string
import requests

# ============================================
# CONFIGURAÇÕES - ALTERE AQUI
# ============================================

# Token do bot (obtenha com @BotFather no Telegram)
BOT_TOKEN = "8548346669:AAH2D3oEx-U61ViXTE_F0NF7tpr1QeWNaNk"

# ID do seu usuário no Telegram (para segurança)
# Para descobrir seu ID, use o bot @userinfobot
ADMIN_USER_ID = 1809485065

# Chave secreta (DEVE SER A MESMA do licenca_telegram.py)
CHAVE_SECRETA = "CRIATIVA_2025_LICENCA_SEGURA_XYZ789_PRIVADA"

# URL do servidor de validação no Render (health check)
RENDER_HEALTH_URL = "https://validadortelegram.onrender.com/health"

# ============================================
# BANCO DE DADOS
# ============================================

db = sqlite3.connect('licencas.db', check_same_thread=False)
db.row_factory = sqlite3.Row

# Criar tabela de licenças
db.execute('''
    CREATE TABLE IF NOT EXISTS licencas (
        codigo TEXT PRIMARY KEY,
        cliente TEXT NOT NULL,
        dias_validade INTEGER NOT NULL,
        data_criacao TEXT NOT NULL,
        data_expiracao TEXT NOT NULL,
        hwid TEXT,
        data_ativacao TEXT,
        status TEXT NOT NULL,
        observacoes TEXT
    )
''')
db.commit()

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def gerar_codigo():
    """Gera código único de licença no formato CRIAT-XXXX-XXXX-XXXX"""
    # Gera 3 blocos de 4 caracteres hexadecimais
    import random
    import string
    
    def gerar_bloco():
        """Gera um bloco de 4 caracteres alfanuméricos"""
        caracteres = string.ascii_uppercase + string.digits
        return ''.join(random.choice(caracteres) for _ in range(4))
    
    parte1 = gerar_bloco()
    parte2 = gerar_bloco()
    parte3 = gerar_bloco()
    return f"CRIAT-{parte1}-{parte2}-{parte3}"


def gerar_assinatura(codigo, hwid, data_expiracao):
    """Gera assinatura criptográfica (mesma lógica do cliente)"""
    dados = f"{codigo}|{hwid}|{data_expiracao}|{CHAVE_SECRETA}"
    return hashlib.sha256(dados.encode()).hexdigest()


def formatar_data(data_str):
    """Formata data para exibição"""
    try:
        dt = datetime.strptime(data_str, '%Y-%m-%d')
        return dt.strftime('%d/%m/%Y')
    except:
        return data_str


# ============================================
# BOT DO TELEGRAM
# ============================================

bot = telebot.TeleBot(BOT_TOKEN)


def verificar_admin(message):
    """Verifica se o usuário é o administrador"""
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "❌ Acesso negado. Este bot é exclusivo para administração.")
        return False
    return True


@bot.message_handler(commands=['start', 'help', 'menu'])
def cmd_start(message):
    if not verificar_admin(message):
        return
    
    # Cria o teclado com botões
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Linha 1: Estatísticas
    btn_stats = types.KeyboardButton('📊 Estatísticas')
    btn_ativas = types.KeyboardButton('✅ Licenças Ativas')
    markup.row(btn_stats, btn_ativas)
    
    # Linha 2: Listagens
    btn_listar = types.KeyboardButton('📋 Listar Todas')
    btn_pendentes = types.KeyboardButton('⏳ Pendentes')
    markup.row(btn_listar, btn_pendentes)
    
    # Linha 3: Ações
    btn_gerar = types.KeyboardButton('➕ Gerar Licença')
    btn_buscar = types.KeyboardButton('🔍 Buscar')
    markup.row(btn_gerar, btn_buscar)
    
    # Linha 4: Controle
    btn_bloquear = types.KeyboardButton('🔒 Bloquear')
    btn_desbloquear = types.KeyboardButton('🔓 Desbloquear')
    markup.row(btn_bloquear, btn_desbloquear)
    
    # Linha 5: Mais ações
    btn_transferir = types.KeyboardButton('🔄 Transferir')
    btn_atualizacoes = types.KeyboardButton('📦 Atualizações')
    markup.row(btn_transferir, btn_atualizacoes)
    
    # Linha 6: Servidor / Ajuda
    btn_acordar = types.KeyboardButton('🌐 Acordar Servidor')
    btn_ajuda = types.KeyboardButton('❓ Ajuda')
    markup.row(btn_acordar, btn_ajuda)
    
    texto = """
🤖 *Bot de Gerenciamento de Licenças*

Bem-vindo! Use os botões abaixo para gerenciar suas licenças.

✅ Clique nos botões para executar ações
📱 Muito mais fácil que digitar comandos!
    """
    
    bot.send_message(message.chat.id, texto, parse_mode='Markdown', reply_markup=markup)


@bot.message_handler(commands=['gerar'])
def cmd_gerar(message):
    if not verificar_admin(message):
        return
    
    try:
        # Parse: /gerar Cliente Nome 365
        partes = message.text.split(maxsplit=2)
        if len(partes) < 3:
            bot.reply_to(message, "❌ Uso: /gerar NOME_CLIENTE DIAS\nExemplo: /gerar Loja do João 365")
            return
        
        # Extrai cliente e dias
        texto_resto = partes[2]
        partes_resto = texto_resto.rsplit(maxsplit=1)
        
        if len(partes_resto) != 2:
            bot.reply_to(message, "❌ Formato inválido. Use: /gerar NOME_CLIENTE DIAS")
            return
        
        cliente = partes_resto[0]
        dias = int(partes_resto[1])
        
        if dias < 1 or dias > 3650:
            bot.reply_to(message, "❌ Dias deve estar entre 1 e 3650 (10 anos)")
            return
        
        # Gera código único
        codigo = gerar_codigo()
        data_criacao = datetime.now().strftime('%Y-%m-%d')
        data_expiracao = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
        
        # Salva no banco
        db.execute('''
            INSERT INTO licencas (codigo, cliente, dias_validade, data_criacao, 
                                 data_expiracao, status, observacoes)
            VALUES (?, ?, ?, ?, ?, 'pendente', NULL)
        ''', (codigo, cliente, dias, data_criacao, data_expiracao))
        db.commit()
        
        resposta = f"""
✅ *Licença gerada com sucesso!*

📋 *Código:* `{codigo}`
👤 *Cliente:* {cliente}
⏰ *Validade:* {dias} dias
📅 *Expira em:* {formatar_data(data_expiracao)}
🔑 *Status:* Pendente de ativação

📤 *Envie este código para o cliente ativar.*
        """
        bot.reply_to(message, resposta, parse_mode='Markdown')
        
        print(f"✅ Licença gerada: {codigo} para {cliente} ({dias} dias)")
    
    except ValueError:
        bot.reply_to(message, "❌ Dias deve ser um número válido")
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['acordar'])
def cmd_acordar(message):
    """Comando para acordar/testar o servidor no Render chamando /health."""
    if not verificar_admin(message):
        return
    
    bot.reply_to(message, "⏳ Verificando servidor de licenças no Render...")
    
    try:
        resp = requests.get(RENDER_HEALTH_URL, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            texto = (
                "✅ Servidor online!\n\n"
                f"🌐 URL: {RENDER_HEALTH_URL}\n"
                f"📅 Timestamp: {data.get('timestamp', 'N/A')}"
            )
            bot.send_message(message.chat.id, texto)
        else:
            bot.send_message(
                message.chat.id,
                f"⚠️ Servidor respondeu com status {resp.status_code}. Tente novamente em alguns segundos."
            )
    except requests.exceptions.Timeout:
        bot.send_message(
            message.chat.id,
            "❌ Timeout ao contactar o servidor. Ele pode estar acordando ou offline."
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Erro ao contactar servidor: {e}")
        print(f"Erro ao gerar licença: {e}")


@bot.message_handler(commands=['listar'])
def cmd_listar(message):
    if not verificar_admin(message):
        return
    
    try:
        cursor = db.execute('''
            SELECT * FROM licencas 
            ORDER BY data_criacao DESC 
            LIMIT 20
        ''')
        licencas = cursor.fetchall()
        
        if not licencas:
            bot.reply_to(message, "📋 Nenhuma licença cadastrada")
            return
        
        resposta = "📋 *Últimas 20 licenças:*\n\n"
        
        for lic in licencas:
            emoji = {
                'ativa': '✅',
                'pendente': '⏳',
                'revogada': '❌',
                'expirada': '⚠️'
            }.get(lic['status'], '❓')
            
            resposta += f"{emoji} `{lic['codigo']}`\n"
            resposta += f"   👤 {lic['cliente']}\n"
            resposta += f"   📅 Expira: {formatar_data(lic['data_expiracao'])}\n"
            resposta += f"   🔑 {lic['status'].title()}\n"
            
            if lic['hwid']:
                resposta += f"   💻 HWID: `{lic['hwid'][:16]}...`\n"
            
            resposta += "\n"
        
        bot.reply_to(message, resposta, parse_mode='Markdown')
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['buscar'])
def cmd_buscar(message):
    if not verificar_admin(message):
        return
    
    try:
        partes = message.text.split()
        if len(partes) < 2:
            bot.reply_to(message, "❌ Uso: /buscar CODIGO")
            return
        
        codigo = partes[1].upper()
        
        cursor = db.execute('SELECT * FROM licencas WHERE codigo = ?', (codigo,))
        lic = cursor.fetchone()
        
        if not lic:
            bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
            return
        
        # Calcula dias restantes
        data_exp = datetime.strptime(lic['data_expiracao'], '%Y-%m-%d')
        dias_restantes = (data_exp - datetime.now()).days
        
        resposta = f"""
📋 *Detalhes da Licença*

🔑 *Código:* `{lic['codigo']}`
👤 *Cliente:* {lic['cliente']}
📅 *Criada em:* {formatar_data(lic['data_criacao'])}
⏰ *Validade:* {lic['dias_validade']} dias
📅 *Expira em:* {formatar_data(lic['data_expiracao'])}
⏳ *Dias restantes:* {dias_restantes}
🔑 *Status:* {lic['status'].title()}
        """
        
        if lic['hwid']:
            resposta += f"\n💻 *HWID:* `{lic['hwid']}`"
        
        if lic['data_ativacao']:
            resposta += f"\n✅ *Ativada em:* {formatar_data(lic['data_ativacao'])}"
        
        if lic['observacoes']:
            resposta += f"\n📝 *Obs:* {lic['observacoes']}"
        
        bot.reply_to(message, resposta, parse_mode='Markdown')
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['ativar'])
def cmd_ativar(message):
    if not verificar_admin(message):
        return
    
    try:
        partes = message.text.split()
        if len(partes) < 3:
            bot.reply_to(message, "❌ Uso: /ativar CODIGO HWID\nExemplo: /ativar CRIAT-A1B2-C3D4-E5F6 ABC123...")
            return
        
        codigo = partes[1].upper()
        hwid = partes[2]
        
        # Verifica se existe
        cursor = db.execute('SELECT cliente, dias_validade, data_expiracao FROM licencas WHERE codigo = ?', (codigo,))
        lic = cursor.fetchone()
        
        if not lic:
            bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
            return
        
        # Ativa
        data_ativacao = datetime.now().strftime('%Y-%m-%d')
        db.execute('''
            UPDATE licencas 
            SET status = 'ativa', 
                hwid = ?,
                data_ativacao = ?
            WHERE codigo = ?
        ''', (hwid, data_ativacao, codigo))
        db.commit()
        
        bot.reply_to(message, f"✅ Licença `{codigo}` de *{lic['cliente']}* ativada com sucesso!\n💻 HWID: `{hwid[:16]}...`", parse_mode='Markdown')
        print(f"✅ Licença ativada: {codigo}")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['bloquear'])
def cmd_bloquear(message):
    if not verificar_admin(message):
        return
    
    try:
        partes = message.text.split(maxsplit=2)
        if len(partes) < 2:
            bot.reply_to(message, "❌ Uso: /bloquear CODIGO [MOTIVO]\nExemplo: /bloquear CRIAT-A1B2-C3D4-E5F6 Uso indevido")
            return
        
        codigo = partes[1].upper()
        motivo = partes[2] if len(partes) > 2 else "Bloqueada pelo administrador"
        
        # Verifica se existe
        cursor = db.execute('SELECT cliente, status FROM licencas WHERE codigo = ?', (codigo,))
        lic = cursor.fetchone()
        
        if not lic:
            bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
            return
        
        # Bloqueia
        db.execute('''
            UPDATE licencas 
            SET status = 'revogada', 
                observacoes = ?
            WHERE codigo = ?
        ''', (f"Bloqueada em {datetime.now().strftime('%d/%m/%Y %H:%M')}: {motivo}", codigo))
        db.commit()
        
        bot.reply_to(message, f"🔒 Licença `{codigo}` de *{lic['cliente']}* bloqueada!\n📝 Motivo: {motivo}", parse_mode='Markdown')
        print(f"🔒 Licença bloqueada: {codigo} - {motivo}")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['desbloquear'])
def cmd_desbloquear(message):
    if not verificar_admin(message):
        return
    
    try:
        partes = message.text.split()
        if len(partes) < 2:
            bot.reply_to(message, "❌ Uso: /desbloquear CODIGO")
            return
        
        codigo = partes[1].upper()
        
        # Verifica se existe
        cursor = db.execute('SELECT cliente, status, hwid FROM licencas WHERE codigo = ?', (codigo,))
        lic = cursor.fetchone()
        
        if not lic:
            bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
            return
        
        if lic['status'] != 'revogada':
            bot.reply_to(message, f"⚠️ Licença `{codigo}` não está bloqueada (status: {lic['status']})", parse_mode='Markdown')
            return
        
        # Desbloqueia
        novo_status = 'ativa' if lic['hwid'] else 'pendente'
        db.execute('''
            UPDATE licencas 
            SET status = ?,
                observacoes = 'Desbloqueada em ' || datetime('now', 'localtime')
            WHERE codigo = ?
        ''', (novo_status, codigo))
        db.commit()
        
        bot.reply_to(message, f"🔓 Licença `{codigo}` de *{lic['cliente']}* desbloqueada!\n🔑 Status: {novo_status}", parse_mode='Markdown')
        print(f"🔓 Licença desbloqueada: {codigo}")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['transferir'])
def cmd_transferir(message):
    if not verificar_admin(message):
        return
    
    try:
        partes = message.text.split()
        if len(partes) < 2:
            bot.reply_to(message, "❌ Uso: /transferir CODIGO\nIsso resetará o HWID para permitir ativação em outro PC")
            return
        
        codigo = partes[1].upper()
        
        # Verifica se existe
        cursor = db.execute('SELECT cliente, status FROM licencas WHERE codigo = ?', (codigo,))
        lic = cursor.fetchone()
        
        if not lic:
            bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
            return
        
        # Reseta HWID e marca como pendente
        db.execute('''
            UPDATE licencas 
            SET status = 'pendente',
                hwid = NULL,
                data_ativacao = NULL,
                observacoes = 'Transferência autorizada em ' || datetime('now', 'localtime')
            WHERE codigo = ?
        ''', (codigo,))
        db.commit()
        
        bot.reply_to(message, f"🔄 Licença `{codigo}` de *{lic['cliente']}* liberada para transferência!\n\n✅ O cliente pode ativar em outro computador agora.", parse_mode='Markdown')
        print(f"🔄 Licença transferida: {codigo}")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['revogar'])
def cmd_revogar(message):
    if not verificar_admin(message):
        return
    
    try:
        partes = message.text.split()
        if len(partes) < 2:
            bot.reply_to(message, "❌ Uso: /revogar CODIGO")
            return
        
        codigo = partes[1].upper()
        
        # Verifica se existe
        cursor = db.execute('SELECT cliente FROM licencas WHERE codigo = ?', (codigo,))
        lic = cursor.fetchone()
        
        if not lic:
            bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
            return
        
        # Revoga
        db.execute('''
            UPDATE licencas 
            SET status = 'revogada', 
                observacoes = 'Revogada permanentemente em ' || datetime('now', 'localtime')
            WHERE codigo = ?
        ''', (codigo,))
        db.commit()
        
        bot.reply_to(message, f"❌ Licença `{codigo}` de *{lic['cliente']}* REVOGADA PERMANENTEMENTE!", parse_mode='Markdown')
        print(f"🔒 Licença revogada: {codigo}")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    if not verificar_admin(message):
        return
    
    try:
        # Total de licenças
        total = db.execute('SELECT COUNT(*) FROM licencas').fetchone()[0]
        
        # Por status
        ativas = db.execute("SELECT COUNT(*) FROM licencas WHERE status = 'ativa'").fetchone()[0]
        pendentes = db.execute("SELECT COUNT(*) FROM licencas WHERE status = 'pendente'").fetchone()[0]
        revogadas = db.execute("SELECT COUNT(*) FROM licencas WHERE status = 'revogada'").fetchone()[0]
        
        # Expirando em 30 dias
        data_limite = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        expirando = db.execute('''
            SELECT COUNT(*) FROM licencas 
            WHERE status = 'ativa' 
            AND data_expiracao <= ?
        ''', (data_limite,)).fetchone()[0]
        
        resposta = f"""
📊 *Estatísticas de Licenças*

📋 *Total:* {total}
✅ *Ativas:* {ativas}
⏳ *Pendentes:* {pendentes}
❌ *Revogadas:* {revogadas}
⚠️ *Expirando em 30 dias:* {expirando}
        """
        
        bot.reply_to(message, resposta, parse_mode='Markdown')
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['ativas'])
def cmd_ativas(message):
    if not verificar_admin(message):
        return
    
    try:
        cursor = db.execute('''
            SELECT * FROM licencas 
            WHERE status = 'ativa'
            ORDER BY data_ativacao DESC
        ''')
        licencas = cursor.fetchall()
        
        if not licencas:
            bot.reply_to(message, "📋 Nenhuma licença ativa")
            return
        
        resposta = f"✅ *Licenças Ativas ({len(licencas)}):*\n\n"
        
        for lic in licencas:
            data_exp = datetime.strptime(lic['data_expiracao'], '%Y-%m-%d')
            dias_restantes = (data_exp - datetime.now()).days
            
            emoji = "⚠️" if dias_restantes < 30 else "✅"
            
            resposta += f"{emoji} `{lic['codigo']}`\n"
            resposta += f"   👤 {lic['cliente']}\n"
            resposta += f"   📅 Expira: {formatar_data(lic['data_expiracao'])} ({dias_restantes}d)\n"
            
            if lic['data_ativacao']:
                resposta += f"   ✅ Ativada: {formatar_data(lic['data_ativacao'])}\n"
            
            if lic['hwid']:
                resposta += f"   💻 HWID: `{lic['hwid'][:20]}...`\n"
            
            resposta += "\n"
        
        bot.reply_to(message, resposta, parse_mode='Markdown')
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


# ============================================
# HANDLERS DE BOTÕES
# ============================================

@bot.message_handler(func=lambda message: message.text == '📊 Estatísticas')
def btn_stats(message):
    cmd_stats(message)

@bot.message_handler(func=lambda message: message.text == '✅ Licenças Ativas')
def btn_ativas(message):
    cmd_ativas(message)

@bot.message_handler(func=lambda message: message.text == '📋 Listar Todas')
def btn_listar(message):
    cmd_listar(message)

@bot.message_handler(func=lambda message: message.text == '⏳ Pendentes')
def btn_pendentes(message):
    if not verificar_admin(message):
        return
    try:
        cursor = db.execute("SELECT * FROM licencas WHERE status = 'pendente' ORDER BY data_criacao DESC")
        licencas = cursor.fetchall()
        
        if not licencas:
            bot.reply_to(message, "📋 Nenhuma licença pendente")
            return
        
        resposta = f"⏳ *Licenças Pendentes ({len(licencas)}):*\n\n"
        
        for lic in licencas:
            resposta += f"📋 `{lic['codigo']}`\n"
            resposta += f"   👤 {lic['cliente']}\n"
            resposta += f"   📅 Criada: {formatar_data(lic['data_criacao'])}\n"
            resposta += f"   ⏰ Expira: {formatar_data(lic['data_expiracao'])}\n\n"
        
        bot.reply_to(message, resposta, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")

@bot.message_handler(func=lambda message: message.text == '➕ Gerar Licença')
def btn_gerar(message):
    if not verificar_admin(message):
        return
    bot.reply_to(message, "📝 Digite: *Nome do Cliente* e *Dias*\n\nExemplo:\n`Loja do João 365`", parse_mode='Markdown')
    bot.register_next_step_handler(message, processar_gerar_licenca)

def processar_gerar_licenca(message):
    if not verificar_admin(message):
        return
    try:
        partes = message.text.rsplit(maxsplit=1)
        if len(partes) != 2:
            bot.reply_to(message, "❌ Formato inválido. Digite: NOME_CLIENTE DIAS")
            return
        
        cliente = partes[0]
        dias = int(partes[1])
        
        if dias < 1 or dias > 3650:
            bot.reply_to(message, "❌ Dias deve estar entre 1 e 3650")
            return
        
        codigo = gerar_codigo()
        data_criacao = datetime.now().strftime('%Y-%m-%d')
        data_expiracao = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
        
        db.execute('''
            INSERT INTO licencas (codigo, cliente, dias_validade, data_criacao, 
                                 data_expiracao, status, observacoes)
            VALUES (?, ?, ?, ?, ?, 'pendente', NULL)
        ''', (codigo, cliente, dias, data_criacao, data_expiracao))
        db.commit()
        
        resposta = f"""
✅ *Licença gerada com sucesso!*

📋 *Código:* `{codigo}`
👤 *Cliente:* {cliente}
⏰ *Validade:* {dias} dias
📅 *Expira em:* {formatar_data(data_expiracao)}

📤 *Envie este código para o cliente ativar.*
        """
        bot.reply_to(message, resposta, parse_mode='Markdown')
        print(f"✅ Licença gerada: {codigo} para {cliente} ({dias} dias)")
    except ValueError:
        bot.reply_to(message, "❌ Dias deve ser um número válido")
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")

@bot.message_handler(func=lambda message: message.text == '🔍 Buscar')
def btn_buscar(message):
    if not verificar_admin(message):
        return
    bot.reply_to(message, "🔍 Digite o *código da licença*:\n\nExemplo: `CRIAT-A1B2-C3D4-E5F6`", parse_mode='Markdown')
    bot.register_next_step_handler(message, processar_buscar)

def processar_buscar(message):
    if not verificar_admin(message):
        return
    codigo = message.text.strip().upper()
    
    cursor = db.execute('SELECT * FROM licencas WHERE codigo = ?', (codigo,))
    lic = cursor.fetchone()
    
    if not lic:
        bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
        return
    
    emoji_status = {
        'ativa': '✅',
        'pendente': '⏳',
        'revogada': '❌'
    }.get(lic['status'], '❓')
    
    resposta = f"""
{emoji_status} *Licença: {lic['codigo']}*

👤 *Cliente:* {lic['cliente']}
🔑 *Status:* {lic['status'].upper()}
📅 *Criada:* {formatar_data(lic['data_criacao'])}
📅 *Expira:* {formatar_data(lic['data_expiracao'])}
⏰ *Validade:* {lic['dias_validade']} dias
    """
    
    if lic['data_ativacao']:
        resposta += f"\n✅ *Ativada:* {formatar_data(lic['data_ativacao'])}"
    
    if lic['hwid']:
        resposta += f"\n💻 *HWID:* `{lic['hwid'][:30]}...`"
    
    if lic['observacoes']:
        resposta += f"\n📝 *Obs:* {lic['observacoes']}"
    
    bot.reply_to(message, resposta, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🔒 Bloquear')
def btn_bloquear(message):
    if not verificar_admin(message):
        return
    bot.reply_to(message, "🔒 Digite o *código* e o *motivo* (opcional):\n\nExemplo:\n`CRIAT-A1B2-C3D4-E5F6 Uso indevido`", parse_mode='Markdown')
    bot.register_next_step_handler(message, processar_bloquear)

def processar_bloquear(message):
    if not verificar_admin(message):
        return
    try:
        partes = message.text.split(maxsplit=1)
        codigo = partes[0].upper()
        motivo = partes[1] if len(partes) > 1 else "Bloqueada pelo administrador"
        
        cursor = db.execute('SELECT cliente FROM licencas WHERE codigo = ?', (codigo,))
        lic = cursor.fetchone()
        
        if not lic:
            bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
            return
        
        db.execute('''
            UPDATE licencas 
            SET status = 'revogada', 
                observacoes = ?
            WHERE codigo = ?
        ''', (f"Bloqueada em {datetime.now().strftime('%d/%m/%Y %H:%M')}: {motivo}", codigo))
        db.commit()
        
        bot.reply_to(message, f"🔒 Licença `{codigo}` de *{lic['cliente']}* bloqueada!\n📝 Motivo: {motivo}", parse_mode='Markdown')
        print(f"🔒 Licença bloqueada: {codigo} - {motivo}")
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")

@bot.message_handler(func=lambda message: message.text == '🔓 Desbloquear')
def btn_desbloquear(message):
    if not verificar_admin(message):
        return
    bot.reply_to(message, "🔓 Digite o *código da licença*:\n\nExemplo: `CRIAT-A1B2-C3D4-E5F6`", parse_mode='Markdown')
    bot.register_next_step_handler(message, processar_desbloquear)

def processar_desbloquear(message):
    if not verificar_admin(message):
        return
    codigo = message.text.strip().upper()
    
    cursor = db.execute('SELECT cliente, status, hwid FROM licencas WHERE codigo = ?', (codigo,))
    lic = cursor.fetchone()
    
    if not lic:
        bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
        return
    
    if lic['status'] != 'revogada':
        bot.reply_to(message, f"⚠️ Licença não está bloqueada (status: {lic['status']})", parse_mode='Markdown')
        return
    
    novo_status = 'ativa' if lic['hwid'] else 'pendente'
    db.execute('''
        UPDATE licencas 
        SET status = ?,
            observacoes = 'Desbloqueada em ' || datetime('now', 'localtime')
        WHERE codigo = ?
    ''', (novo_status, codigo))
    db.commit()
    
    bot.reply_to(message, f"🔓 Licença `{codigo}` de *{lic['cliente']}* desbloqueada!\n🔑 Status: {novo_status}", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🔄 Transferir')
def btn_transferir(message):
    if not verificar_admin(message):
        return
    bot.reply_to(message, "🔄 Digite o *código da licença* para transferir:\n\nExemplo: `CRIAT-A1B2-C3D4-E5F6`", parse_mode='Markdown')
    bot.register_next_step_handler(message, processar_transferir)

def processar_transferir(message):
    if not verificar_admin(message):
        return
    codigo = message.text.strip().upper()
    
    cursor = db.execute('SELECT cliente FROM licencas WHERE codigo = ?', (codigo,))
    lic = cursor.fetchone()
    
    if not lic:
        bot.reply_to(message, f"❌ Licença `{codigo}` não encontrada", parse_mode='Markdown')
        return
    
    db.execute('''
        UPDATE licencas 
        SET status = 'pendente',
            hwid = NULL,
            data_ativacao = NULL,
            observacoes = 'Transferência autorizada em ' || datetime('now', 'localtime')
        WHERE codigo = ?
    ''', (codigo,))
    db.commit()
    
    bot.reply_to(message, f"🔄 Licença `{codigo}` de *{lic['cliente']}* liberada para transferência!\n\n✅ O cliente pode ativar em outro computador agora.", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '📦 Atualizações')
def btn_atualizacoes(message):
    if not verificar_admin(message):
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_publicar = types.InlineKeyboardButton('📤 Publicar Atualização', callback_data='atualizar_publicar')
    btn_status = types.InlineKeyboardButton('📊 Status Servidor', callback_data='atualizar_status')
    markup.add(btn_publicar, btn_status)
    
    bot.reply_to(message, "📦 *Gerenciamento de Atualizações*\n\nEscolha uma opção:", parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'atualizar_publicar')
def callback_publicar(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📦 Digite: *Versão* *Changelog*\n\nExemplo:\n`1.1.0 Correção de bugs`", parse_mode='Markdown')
    bot.register_next_step_handler(call.message, processar_publicar_atualizacao)

@bot.callback_query_handler(func=lambda call: call.data == 'atualizar_status')
def callback_status(call):
    bot.answer_callback_query(call.id)
    cmd_status_atualizacoes(call.message)

@bot.message_handler(func=lambda message: message.text == '❓ Ajuda')
def btn_ajuda(message):
    cmd_start(message)


# ============================================
# COMANDOS DE ATUALIZAÇÃO
# ============================================

@bot.message_handler(commands=['publicar_atualizacao'])
def cmd_publicar_atualizacao(message):
    if not verificar_admin(message):
        return
    
    bot.reply_to(message, "📦 Digite: *Versão* *Changelog* (opcional)\n\nExemplo:\n`1.1.0 Correção de bugs e melhorias`", parse_mode='Markdown')
    bot.register_next_step_handler(message, processar_publicar_atualizacao)

def processar_publicar_atualizacao(message):
    if not verificar_admin(message):
        return
    
    try:
        import requests
        
        partes = message.text.split(maxsplit=1)
        versao = partes[0]
        changelog = partes[1] if len(partes) > 1 else "Atualização do sistema"
        
        # Publica no servidor
        response = requests.post(
            'http://localhost:5002/api/publicar_atualizacao',
            json={
                'versao': versao,
                'changelog': changelog,
                'obrigatoria': False,
                'tamanho_mb': 5
            },
            timeout=10
        )
        
        if response.status_code == 200:
            bot.reply_to(message, f"✅ Atualização *v{versao}* publicada!\n\n📝 Changelog:\n{changelog}\n\n⚠️ Os clientes serão notificados na próxima verificação.", parse_mode='Markdown')
            print(f"✅ Atualização publicada: v{versao}")
        else:
            bot.reply_to(message, "❌ Erro ao publicar atualização")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {str(e)}")


@bot.message_handler(commands=['status_atualizacoes'])
def cmd_status_atualizacoes(message):
    if not verificar_admin(message):
        return
    
    try:
        import requests
        
        response = requests.get('http://localhost:5002/api/status', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            resposta = f"""
🌐 *Status do Servidor de Atualizações*

✅ *Online*
📌 *Versão Atual:* {data.get('versao_atual', 'N/A')}
📦 *Total de Versões:* {data.get('total_versoes', 0)}

*Versões Disponíveis:*
{chr(10).join(['• ' + v for v in data.get('versoes_disponiveis', [])])}
            """
            
            bot.reply_to(message, resposta, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Servidor offline")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Servidor offline: {str(e)}")


# ============================================
# INICIALIZAÇÃO
# ============================================

if __name__ == '__main__':
    print("="*60)
    print("🤖 BOT DE LICENÇAS INICIADO")
    print("="*60)
    print(f"📱 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"👤 Admin ID: {ADMIN_USER_ID}")
    print(f"💾 Banco de dados: licencas.db")
    print("="*60)
    print("\n✅ Bot rodando... (Ctrl+C para parar)\n")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n\n🛑 Bot encerrado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
