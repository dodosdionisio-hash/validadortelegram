"""
Servidor de Validação de Licenças
Roda em paralelo com o bot para receber requisições HTTP dos clientes
"""

from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)

# Chave secreta (DEVE SER A MESMA!)
CHAVE_SECRETA = "CRIATIVA_2025_LICENCA_SEGURA_XYZ789_PRIVADA"

# Grace period (dias offline permitidos)
GRACE_PERIOD_DIAS = 30


def get_db():
    """Conecta ao banco de licenças do bot"""
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
        cursor = db.cursor()
        
        # Busca a licença
        cursor.execute('SELECT * FROM licencas WHERE codigo = ?', (codigo,))
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
        cursor.execute('''
            UPDATE licencas 
            SET status = 'ativa',
                hwid = ?,
                data_ativacao = ?
            WHERE codigo = ?
        ''', (hwid, data_ativacao, codigo))
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
        cursor = db.cursor()
        
        # Busca a licença
        cursor.execute('SELECT * FROM licencas WHERE codigo = ?', (codigo,))
        licenca = cursor.fetchone()
        
        if not licenca:
            return jsonify({
                'valida': False,
                'erro': 'Licença não encontrada',
                'bloqueada': True
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
            # HWID diferente - BLOQUEIA!
            cursor.execute('''
                UPDATE licencas 
                SET status = 'revogada',
                    observacoes = 'Bloqueada automaticamente: tentativa de uso em outro PC em ' || datetime('now', 'localtime')
                WHERE codigo = ?
            ''', (codigo,))
            db.commit()
            db.close()
            
            print(f"🔒 LICENÇA BLOQUEADA: {codigo} | HWID esperado: {licenca['hwid'][:16]}... | HWID recebido: {hwid[:16]}...")
            
            return jsonify({
                'valida': False,
                'erro': 'Licença bloqueada: detectado uso em computador não autorizado',
                'bloqueada': True
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
        cursor = db.cursor()
        
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
