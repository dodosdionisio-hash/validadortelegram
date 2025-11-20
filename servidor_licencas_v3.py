"""
SERVIDOR DE VALIDAÇÃO DE LICENÇAS - V3.0
Sistema completo com proteção anti-clonagem e modo offline
Para deploy no Render.com
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import hashlib
import hmac

app = Flask(__name__)

# Configurações
DATABASE = 'licenses.db'
API_KEY = os.environ.get('API_KEY', 'sua-chave-secreta-aqui')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Alicia2705@#@')

# ============================================================================
# BANCO DE DADOS
# ============================================================================

def get_db():
    """Conecta ao banco de dados"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Inicializa o banco de dados"""
    db = get_db()
    
    # Tabela de licenças
    db.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            hwid TEXT NOT NULL,
            bound_hwid TEXT,
            plan TEXT NOT NULL DEFAULT 'standard',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_check TEXT,
            status TEXT DEFAULT 'active',
            unbind_count INTEGER DEFAULT 0,
            client_name TEXT
        )
    ''')
    
    # Tabela de logs de validação
    db.execute('''
        CREATE TABLE IF NOT EXISTS validation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            hwid TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            ip_address TEXT,
            result TEXT,
            detected_hwid TEXT,
            message TEXT
        )
    ''')
    
    # Tabela de mudanças de HWID (auditoria)
    db.execute('''
        CREATE TABLE IF NOT EXISTS hwid_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id INTEGER,
            old_hwid TEXT,
            new_hwid TEXT,
            changed_at TEXT NOT NULL,
            reason TEXT,
            admin_user TEXT
        )
    ''')
    
    db.commit()
    db.close()
    print("✅ Banco de dados inicializado")

# ============================================================================
# MIDDLEWARE DE AUTENTICAÇÃO
# ============================================================================

def require_api_key(f):
    """Decorator para exigir API Key"""
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != API_KEY:
            return jsonify({'error': 'API Key inválida'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def require_admin(f):
    """Decorator para exigir senha de admin"""
    def decorated_function(*args, **kwargs):
        password = request.headers.get('X-Admin-Password')
        if password != ADMIN_PASSWORD:
            return jsonify({'error': 'Senha de admin inválida'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def log_validation(license_key, hwid, result, detected_hwid, message, ip):
    """Registra log de validação"""
    db = get_db()
    db.execute('''
        INSERT INTO validation_logs 
        (license_key, hwid, checked_at, ip_address, result, detected_hwid, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (license_key, hwid, datetime.now().isoformat(), ip, result, detected_hwid, message))
    db.commit()
    db.close()

def log_hwid_change(license_id, old_hwid, new_hwid, reason, admin_user='system'):
    """Registra mudança de HWID"""
    db = get_db()
    db.execute('''
        INSERT INTO hwid_changes 
        (license_id, old_hwid, new_hwid, changed_at, reason, admin_user)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (license_id, old_hwid, new_hwid, datetime.now().isoformat(), reason, admin_user))
    db.commit()
    db.close()

# ============================================================================
# ENDPOINTS DA API
# ============================================================================

@app.route('/')
def index():
    """Página inicial"""
    return jsonify({
        'service': 'License Validation API v3.0',
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'features': [
            'Proteção anti-clonagem',
            'Modo offline (30 dias)',
            'Cache criptografado',
            'Auditoria completa'
        ]
    })

@app.route('/health')
def health():
    """Health check"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/validate', methods=['POST'])
@require_api_key
def validate_license():
    """
    Valida uma licença
    
    Request:
    {
        "license_key": "XXXX-XXXX-XXXX-XXXX",
        "hwid": "XXXX-XXXX-XXXX-XXXX"
    }
    
    Response:
    {
        "valid": true/false,
        "message": "...",
        "expires_at": "...",
        "plan": "...",
        "bound_hwid": "...",
        "days_remaining": 30
    }
    """
    data = request.get_json()
    license_key = data.get('license_key', '').strip()
    hwid_request = data.get('hwid', '').strip()
    ip_address = request.remote_addr
    
    if not license_key or not hwid_request:
        return jsonify({
            'valid': False,
            'message': 'Chave de licença e HWID são obrigatórios'
        }), 400
    
    db = get_db()
    license_row = db.execute(
        'SELECT * FROM licenses WHERE license_key = ?',
        (license_key,)
    ).fetchone()
    
    # Licença não encontrada
    if not license_row:
        log_validation(license_key, hwid_request, 'not_found', hwid_request, 'Licença não encontrada', ip_address)
        db.close()
        return jsonify({
            'valid': False,
            'message': 'Licença não encontrada'
        }), 404
    
    license_dict = dict(license_row)
    license_id = license_dict['id']
    bound_hwid = license_dict['bound_hwid']
    status = license_dict['status']
    expires_at_str = license_dict['expires_at']
    
    # PROTEÇÃO ANTI-CLONAGEM
    if bound_hwid is None:
        # Primeira vez usando - vincular ao HWID atual
        db.execute(
            'UPDATE licenses SET bound_hwid = ?, last_check = ? WHERE id = ?',
            (hwid_request, datetime.now().isoformat(), license_id)
        )
        db.commit()
        log_hwid_change(license_id, None, hwid_request, 'first_bind')
        bound_hwid = hwid_request
        print(f"🔗 Licença {license_key} vinculada ao HWID {hwid_request}")
    
    elif bound_hwid != hwid_request:
        # TENTATIVA DE USO EM PC DIFERENTE - BLOQUEAR!
        db.execute(
            'UPDATE licenses SET status = ? WHERE id = ?',
            ('blocked_multiple_pc', license_id)
        )
        db.commit()
        log_validation(license_key, hwid_request, 'blocked_multiple_pc', hwid_request, 
                      f'Tentativa de uso em PC diferente. Original: {bound_hwid}', ip_address)
        log_hwid_change(license_id, bound_hwid, hwid_request, 'blocked_attempt')
        db.close()
        
        print(f"🚨 BLOQUEIO: Licença {license_key} tentou usar em PC diferente!")
        print(f"   HWID Original: {bound_hwid}")
        print(f"   HWID Tentativa: {hwid_request}")
        
        return jsonify({
            'valid': False,
            'message': 'Licença bloqueada: detectado uso em múltiplos PCs. Entre em contato com o suporte.',
            'status': 'blocked_multiple_pc'
        }), 403
    
    # Verifica se está bloqueada
    if status == 'blocked_multiple_pc':
        log_validation(license_key, hwid_request, 'blocked', hwid_request, 'Licença bloqueada por uso múltiplo', ip_address)
        db.close()
        return jsonify({
            'valid': False,
            'message': 'Licença bloqueada por uso em múltiplos PCs. Entre em contato com o suporte.',
            'status': 'blocked_multiple_pc'
        }), 403
    
    if status == 'revoked':
        log_validation(license_key, hwid_request, 'revoked', hwid_request, 'Licença revogada', ip_address)
        db.close()
        return jsonify({
            'valid': False,
            'message': 'Licença revogada',
            'status': 'revoked'
        }), 403
    
    # Verifica expiração
    expires_at = datetime.fromisoformat(expires_at_str)
    now = datetime.now()
    
    if now > expires_at:
        db.execute(
            'UPDATE licenses SET status = ? WHERE id = ?',
            ('expired', license_id)
        )
        db.commit()
        log_validation(license_key, hwid_request, 'expired', hwid_request, 'Licença expirada', ip_address)
        db.close()
        return jsonify({
            'valid': False,
            'message': 'Licença expirada',
            'status': 'expired',
            'expired_at': expires_at_str
        }), 403
    
    # Atualiza último check
    db.execute(
        'UPDATE licenses SET last_check = ? WHERE id = ?',
        (now.isoformat(), license_id)
    )
    db.commit()
    
    # Calcula dias restantes
    days_remaining = (expires_at - now).days
    
    log_validation(license_key, hwid_request, 'success', hwid_request, 'Validação bem-sucedida', ip_address)
    db.close()
    
    return jsonify({
        'valid': True,
        'message': 'Licença válida',
        'expires_at': expires_at_str,
        'plan': license_dict['plan'],
        'bound_hwid': bound_hwid,
        'days_remaining': days_remaining,
        'status': 'active'
    })

@app.route('/api/licenses/create', methods=['POST'])
@require_admin
def create_license():
    """
    Cria uma nova licença
    
    Request:
    {
        "license_key": "XXXX-XXXX-XXXX-XXXX",
        "hwid": "XXXX-XXXX-XXXX-XXXX",
        "client_name": "Nome do Cliente",
        "duration_days": 365,
        "plan": "premium"
    }
    """
    data = request.get_json()
    license_key = data.get('license_key', '').strip()
    hwid = data.get('hwid', '').strip()
    client_name = data.get('client_name', '')
    duration_days = data.get('duration_days', 365)
    plan = data.get('plan', 'standard')
    
    if not license_key or not hwid:
        return jsonify({'error': 'license_key e hwid são obrigatórios'}), 400
    
    now = datetime.now()
    expires_at = now + timedelta(days=duration_days)
    
    db = get_db()
    try:
        db.execute('''
            INSERT INTO licenses 
            (license_key, hwid, plan, created_at, expires_at, status, client_name)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
        ''', (license_key, hwid, plan, now.isoformat(), expires_at.isoformat(), client_name))
        db.commit()
        license_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.close()
        
        return jsonify({
            'success': True,
            'license_id': license_id,
            'license_key': license_key,
            'hwid': hwid,
            'client_name': client_name,
            'expires_at': expires_at.isoformat(),
            'plan': plan
        })
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({'error': 'Licença já existe'}), 409

@app.route('/api/licenses/unbind/<license_key>', methods=['POST'])
@require_admin
def unbind_license(license_key):
    """Desvincula licença de um PC (para permitir troca de computador)"""
    db = get_db()
    license_row = db.execute(
        'SELECT * FROM licenses WHERE license_key = ?',
        (license_key,)
    ).fetchone()
    
    if not license_row:
        db.close()
        return jsonify({'error': 'Licença não encontrada'}), 404
    
    license_dict = dict(license_row)
    old_hwid = license_dict['bound_hwid']
    
    db.execute('''
        UPDATE licenses 
        SET bound_hwid = NULL, unbind_count = unbind_count + 1
        WHERE license_key = ?
    ''', (license_key,))
    db.commit()
    
    log_hwid_change(license_dict['id'], old_hwid, None, 'admin_unbind', 'admin')
    db.close()
    
    return jsonify({
        'success': True,
        'message': 'Licença desvinculada. Próximo uso vinculará ao novo PC.',
        'old_hwid': old_hwid
    })

@app.route('/api/licenses/unblock/<license_key>', methods=['POST'])
@require_admin
def unblock_license(license_key):
    """Desbloqueia licença que foi bloqueada por uso múltiplo"""
    db = get_db()
    db.execute('''
        UPDATE licenses 
        SET status = 'active'
        WHERE license_key = ? AND status = 'blocked_multiple_pc'
    ''', (license_key,))
    db.commit()
    
    if db.total_changes == 0:
        db.close()
        return jsonify({'error': 'Licença não encontrada ou não está bloqueada'}), 404
    
    db.close()
    return jsonify({
        'success': True,
        'message': 'Licença desbloqueada'
    })

@app.route('/api/licenses/<license_key>', methods=['GET'])
@require_admin
def get_license(license_key):
    """Consulta informações de uma licença"""
    db = get_db()
    license_row = db.execute(
        'SELECT * FROM licenses WHERE license_key = ?',
        (license_key,)
    ).fetchone()
    
    if not license_row:
        db.close()
        return jsonify({'error': 'Licença não encontrada'}), 404
    
    license_dict = dict(license_row)
    db.close()
    
    return jsonify(license_dict)

@app.route('/api/licenses', methods=['GET'])
@require_admin
def list_licenses():
    """Lista todas as licenças"""
    status_filter = request.args.get('status')
    
    db = get_db()
    if status_filter:
        rows = db.execute(
            'SELECT * FROM licenses WHERE status = ? ORDER BY created_at DESC',
            (status_filter,)
        ).fetchall()
    else:
        rows = db.execute(
            'SELECT * FROM licenses ORDER BY created_at DESC'
        ).fetchall()
    
    licenses = [dict(row) for row in rows]
    db.close()
    
    return jsonify(licenses)

@app.route('/api/licenses/<license_key>', methods=['DELETE'])
@require_admin
def revoke_license(license_key):
    """Revoga uma licença"""
    db = get_db()
    db.execute('''
        UPDATE licenses 
        SET status = 'revoked'
        WHERE license_key = ?
    ''', (license_key,))
    db.commit()
    
    if db.total_changes == 0:
        db.close()
        return jsonify({'error': 'Licença não encontrada'}), 404
    
    db.close()
    return jsonify({
        'success': True,
        'message': 'Licença revogada'
    })

# ============================================================================
# INICIALIZAÇÃO
# ============================================================================

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
