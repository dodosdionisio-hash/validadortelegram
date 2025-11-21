"""
SERVIDOR DE VALIDAÇÃO DE LICENÇAS - V3.0
Sistema completo com proteção anti-clonagem e modo offline
Suporte híbrido: PostgreSQL (Render) ou SQLite (local)
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import os
import hashlib
import hmac

app = Flask(__name__)

# Configurações
DATABASE_URL = os.environ.get('DATABASE_URL', '')
API_KEY = os.environ.get('API_KEY', 'sua-chave-secreta-aqui')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Alicia2705@#@')

# Detecta qual banco usar
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith('postgres'))

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    print("🐘 Usando PostgreSQL")
else:
    import sqlite3
    print("📁 Usando SQLite")

# ============================================================================
# BANCO DE DADOS - CAMADA DE ABSTRAÇÃO
# ============================================================================

def get_db():
    """Conecta ao banco de dados (PostgreSQL ou SQLite)"""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        db = sqlite3.connect('licenses.db')
        db.row_factory = sqlite3.Row
        return db

def dict_from_row(row):
    """Converte row em dict (compatível com ambos os bancos)"""
    if USE_POSTGRES:
        return dict(row)
    else:
        return dict(row)

def execute_query(conn, query, params=None):
    """Executa query compatível com ambos os bancos"""
    if USE_POSTGRES:
        # PostgreSQL usa %s
        query = query.replace('?', '%s')
        cur = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        return cur
    else:
        # SQLite usa ?
        if params:
            return conn.execute(query, params)
        else:
            return conn.execute(query)

# Monkey patch para db.execute funcionar com ambos
class DBWrapper:
    def __init__(self, conn):
        self.conn = conn
        self._cursor = None
        
    def execute(self, query, params=None):
        self._cursor = execute_query(self.conn, query, params)
        return self
    
    def fetchone(self):
        return self._cursor.fetchone() if self._cursor else None
    
    def fetchall(self):
        return self._cursor.fetchall() if self._cursor else []
    
    def commit(self):
        self.conn.commit()
    
    def close(self):
        if USE_POSTGRES and self._cursor:
            self._cursor.close()
        self.conn.close()
    
    @property
    def total_changes(self):
        if USE_POSTGRES:
            return self._cursor.rowcount if self._cursor else 0
        else:
            return self.conn.total_changes

def get_db_wrapped():
    """Retorna conexão com wrapper compatível"""
    return DBWrapper(get_db())

def init_db():
    """Inicializa o banco de dados"""
    conn = get_db()
    
    if USE_POSTGRES:
        cur = conn.cursor()
        
        # Tabela de licenças (PostgreSQL)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS licenses (
                id SERIAL PRIMARY KEY,
                license_key VARCHAR(255) UNIQUE NOT NULL,
                hwid VARCHAR(255) NOT NULL,
                bound_hwid VARCHAR(255),
                plan VARCHAR(50) NOT NULL DEFAULT 'standard',
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                last_check TIMESTAMP,
                status VARCHAR(20) DEFAULT 'active',
                unbind_count INTEGER DEFAULT 0,
                client_name VARCHAR(255)
            )
        ''')
        
        # Tabela de logs de validação (PostgreSQL)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS validation_logs (
                id SERIAL PRIMARY KEY,
                license_key VARCHAR(255) NOT NULL,
                hwid VARCHAR(255) NOT NULL,
                checked_at TIMESTAMP NOT NULL,
                ip_address VARCHAR(50),
                result VARCHAR(20),
                detected_hwid VARCHAR(255),
                message TEXT
            )
        ''')
        
        # Tabela de mudanças de HWID (PostgreSQL)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS hwid_changes (
                id SERIAL PRIMARY KEY,
                license_id INTEGER,
                old_hwid VARCHAR(255),
                new_hwid VARCHAR(255),
                changed_at TIMESTAMP NOT NULL,
                reason TEXT,
                admin_user VARCHAR(100)
            )
        ''')
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Banco PostgreSQL inicializado")
    
    else:
        # SQLite
        conn.execute('''
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
        
        conn.execute('''
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
        
        conn.execute('''
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
        
        conn.commit()
        conn.close()
        print("✅ Banco SQLite inicializado")
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
    """Decorator para exigir API Key e senha de admin"""
    def decorated_function(*args, **kwargs):
        # Verifica API Key
        api_key = request.headers.get('X-API-Key')
        if api_key != API_KEY:
            return jsonify({'error': 'API Key inválida'}), 401
        
        # Verifica senha admin
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
    db = get_db_wrapped()
    db.execute('''
        INSERT INTO validation_logs 
        (license_key, hwid, checked_at, ip_address, result, detected_hwid, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (license_key, hwid, datetime.now().isoformat(), ip, result, detected_hwid, message))
    db.commit()
    db.close()

def log_hwid_change(license_id, old_hwid, new_hwid, reason, admin_user='system'):
    """Registra mudança de HWID"""
    db = get_db_wrapped()
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
    
    db = get_db_wrapped()
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
    # Converte para string se necessário (PostgreSQL pode retornar datetime)
    if isinstance(expires_at_str, str):
        expires_at = datetime.fromisoformat(expires_at_str)
    else:
        expires_at = expires_at_str  # Já é datetime
    
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
    
    db = get_db_wrapped()
    try:
        db.execute('''
            INSERT INTO licenses 
            (license_key, hwid, plan, created_at, expires_at, status, client_name)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
        ''', (license_key, hwid, plan, now.isoformat(), expires_at.isoformat(), client_name))
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'license_key': license_key,
            'client_name': client_name,
            'created_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'plan': plan
        })
    except Exception as e:
        db.close()
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return jsonify({'error': 'Licença já existe'}), 409
        return jsonify({'error': str(e)}), 500

@app.route('/api/licenses/unbind/<license_key>', methods=['POST'])
@require_admin
def unbind_license(license_key):
    """Desvincula licença de um PC (para permitir troca de computador)"""
    db = get_db_wrapped()
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
    db = get_db_wrapped()
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
    db = get_db_wrapped()
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
    
    conn = get_db()
    
    if status_filter:
        cur = execute_query(conn,
            'SELECT * FROM licenses WHERE status = ? ORDER BY created_at DESC',
            (status_filter,)
        )
    else:
        cur = execute_query(conn,
            'SELECT * FROM licenses ORDER BY created_at DESC'
        )
    
    rows = cur.fetchall()
    licenses = [dict(row) for row in rows]
    
    if USE_POSTGRES:
        cur.close()
    conn.close()
    
    return jsonify(licenses)

@app.route('/api/licenses/<license_key>', methods=['DELETE'])
@require_admin
def revoke_license(license_key):
    """Revoga uma licença"""
    conn = get_db()
    cur = execute_query(conn, '''
        UPDATE licenses 
        SET status = 'revoked'
        WHERE license_key = ?
    ''', (license_key,))
    conn.commit()
    
    if USE_POSTGRES:
        affected = cur.rowcount
        cur.close()
    else:
        affected = conn.total_changes
    
    conn.close()
    
    if affected == 0:
        return jsonify({'error': 'Licença não encontrada'}), 404
    
    return jsonify({
        'success': True,
        'message': 'Licença revogada'
    })

# ============================================================================
# INICIALIZAÇÃO
# ============================================================================

# Inicializa o banco ao importar (necessário para Gunicorn)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
