"""
Servidor de Validação de Licenças
Roda em paralelo com o bot para receber requisições HTTP dos clientes
"""

from flask import Flask, request, jsonify
import os
import sqlite3
from datetime import datetime, timedelta
import hashlib
try:
    import psycopg2
    import psycopg2.extras
except Exception:
    psycopg2 = None

app = Flask(__name__)

# Chave secreta (DEVE SER A MESMA!)
CHAVE_SECRETA = os.environ.get("LICENCA_SECRET", "CRIATIVA_2025_LICENCA_SEGURA_XYZ789_PRIVADA")

# Grace period (dias offline permitidos)
GRACE_PERIOD_DIAS = 30


def _is_postgres():
    return bool(os.environ.get("DATABASE_URL")) and (psycopg2 is not None)

def init_db():
    """Garante que a tabela de licenças exista (Postgres ou SQLite)."""
    if _is_postgres():
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute(
            """
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
            """
        )
        conn.commit()
        conn.close()
    else:
        db = sqlite3.connect('licencas.db')
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
        db.close()


# Garante que o banco esteja pronto ao iniciar o servidor
init_db()


def get_db():
    """Conecta ao banco de licenças (Postgres se disponível, senão SQLite)."""
    if _is_postgres():
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        return conn
    else:
        db = sqlite3.connect('licencas.db')
        db.row_factory = sqlite3.Row
        return db


def gerar_assinatura(codigo, hwid, data_expiracao):
    """Gera assinatura criptográfica"""
    dados = f"{codigo}|{hwid}|{data_expiracao}|{CHAVE_SECRETA}"
    return hashlib.sha256(dados.encode()).hexdigest()


@app.route('/api/ativar', methods=['POST'])
def ativar_licenca():
    """
    Ativa uma licença vinculando ao HWID do cliente
    """
    try:
        dados = request.get_json()
        codigo = dados.get('codigo', '').upper()
        hwid = dados.get('hwid', '')
        
        if not codigo or not hwid:
            return jsonify({
                'sucesso': False,
                'erro': 'Código e HWID são obrigatórios'
            }), 400
        
        db = get_db()
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) if _is_postgres() else db.cursor()
        
        # Busca a licença
        q_sel = 'SELECT * FROM licencas WHERE codigo = %s' if _is_postgres() else 'SELECT * FROM licencas WHERE codigo = ?'
        cursor.execute(q_sel, (codigo,))
        licenca = cursor.fetchone()
        
        if not licenca:
            return jsonify({
                'sucesso': False,
                'erro': 'Código de licença não encontrado'
            }), 404
        
        # Verifica se já está ativada
        if licenca['status'] == 'ativa':
            # Verifica se é o mesmo HWID
            if licenca['hwid'] != hwid:
                return jsonify({
                    'sucesso': False,
                    'erro': 'Esta licença já está ativada em outro computador',
                    'bloqueada': True
                }), 403
            
            # Mesmo HWID - permite (renovação/reinstalação)
            return jsonify({
                'sucesso': True,
                'mensagem': 'Licença já ativada neste computador',
                'cliente': licenca['cliente'],
                'data_expiracao': licenca['data_expiracao'],
                'dias_validade': licenca['dias_validade'],
                'assinatura': gerar_assinatura(codigo, hwid, licenca['data_expiracao'])
            })
        
        # Verifica se está revogada
        if licenca['status'] == 'revogada':
            return jsonify({
                'sucesso': False,
                'erro': 'Esta licença foi revogada. Entre em contato com o suporte.',
                'bloqueada': True
            }), 403
        
        # Ativa a licença
        data_ativacao = datetime.now().strftime('%Y-%m-%d')
        q_up = (
            "UPDATE licencas SET status = 'ativa', hwid = %s, data_ativacao = %s WHERE codigo = %s"
            if _is_postgres() else
            "UPDATE licencas SET status = 'ativa', hwid = ?, data_ativacao = ? WHERE codigo = ?"
        )
        cursor.execute(q_up, (hwid, data_ativacao, codigo))
        db.commit()
        db.close()
        
        print(f"✅ Licença ativada: {codigo} | HWID: {hwid[:16]}... | Cliente: {licenca['cliente']}")
        
        return jsonify({
            'sucesso': True,
            'mensagem': 'Licença ativada com sucesso!',
            'cliente': licenca['cliente'],
            'data_expiracao': licenca['data_expiracao'],
            'dias_validade': licenca['dias_validade'],
            'assinatura': gerar_assinatura(codigo, hwid, licenca['data_expiracao'])
        })
    
    except Exception as e:
        print(f"❌ Erro ao ativar licença: {e}")
        return jsonify({
            'sucesso': False,
            'erro': 'Erro interno do servidor'
        }), 500


@app.route('/api/validar', methods=['POST'])
def validar_licenca():
    """
    Valida uma licença já ativada (verificação periódica)
    """
    try:
        dados = request.get_json()
        codigo = dados.get('codigo', '').upper()
        hwid = dados.get('hwid', '')
        
        if not codigo or not hwid:
            return jsonify({
                'valida': False,
                'erro': 'Código e HWID são obrigatórios'
            }), 400
        
        db = get_db()
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) if _is_postgres() else db.cursor()
        
        # Busca a licença
        q_sel = 'SELECT * FROM licencas WHERE codigo = %s' if _is_postgres() else 'SELECT * FROM licencas WHERE codigo = ?'
        cursor.execute(q_sel, (codigo,))
        licenca = cursor.fetchone()
        
        if not licenca:
            return jsonify({
                'valida': False,
                'erro': 'Licença não encontrada',
                'bloqueada': False
            }), 404
        
        # Verifica se está revogada
        if licenca['status'] == 'revogada':
            return jsonify({
                'valida': False,
                'erro': 'Licença revogada',
                'bloqueada': True
            }), 403
        
        # Verifica HWID
        if licenca['hwid'] != hwid:
            db.close()
            return jsonify({
                'valida': False,
                'erro': 'HWID diferente do autorizado',
                'bloqueada': False
            }), 403
        
        # Verifica expiração
        data_exp = datetime.strptime(licenca['data_expiracao'], '%Y-%m-%d')
        if datetime.now() > data_exp:
            return jsonify({
                'valida': False,
                'erro': 'Licença expirada',
                'data_expiracao': licenca['data_expiracao']
            }), 403
        
        db.close()
        
        # Licença válida!
        dias_restantes = (data_exp - datetime.now()).days
        
        return jsonify({
            'valida': True,
            'mensagem': 'Licença válida',
            'cliente': licenca['cliente'],
            'data_expiracao': licenca['data_expiracao'],
            'dias_restantes': dias_restantes,
            'assinatura': gerar_assinatura(codigo, hwid, licenca['data_expiracao'])
        })
    
    except Exception as e:
        print(f"❌ Erro ao validar licença: {e}")
        return jsonify({
            'valida': False,
            'erro': 'Erro interno do servidor'
        }), 500


@app.route('/api/status', methods=['GET'])
def status():
    """Status do servidor"""
    try:
        db = get_db()
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) if _is_postgres() else db.cursor()
        
        total = cursor.execute('SELECT COUNT(*) FROM licencas').fetchone()[0]
        ativas = cursor.execute("SELECT COUNT(*) FROM licencas WHERE status = 'ativa'").fetchone()[0]
        pendentes = cursor.execute("SELECT COUNT(*) FROM licencas WHERE status = 'pendente'").fetchone()[0]
        
        db.close()
        
        return jsonify({
            'online': True,
            'total_licencas': total,
            'ativas': ativas,
            'pendentes': pendentes,
            'grace_period_dias': GRACE_PERIOD_DIAS
        })
    except Exception as e:
        return jsonify({
            'online': True,
            'erro': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """Endpoint de health check para uso no Render e no bot/cliente."""
    try:
        return jsonify({
            'status': 'online',
            'timestamp': datetime.now().isoformat(),
            'endpoints': {
                'ativar': 'POST /api/ativar',
                'validar': 'POST /api/validar',
                'status': 'GET /api/status'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': str(e)
        }), 500


if __name__ == '__main__':
    print("="*60)
    print("🌐 SERVIDOR DE VALIDAÇÃO INICIADO")
    print("="*60)
    print("📡 Porta: 5001")
    print(f"⏰ Grace Period: {GRACE_PERIOD_DIAS} dias")
    print("="*60)
    print("\n✅ Servidor rodando...\n")
    
    app.run(host='0.0.0.0', port=5001, debug=False)
