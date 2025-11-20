from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

# Importar blueprints de API
from api_dashboard import api_dashboard
from api_caixa import api_caixa

# Importar funções de HWID
from hwid import obter_hwid, validar_hwid_licenca

from database import (
    init_db,
    get_connection,
    autenticar,
    listar_clientes,
    criar_cliente,
    atualizar_cliente,
    deletar_cliente,
    listar_categorias,
    criar_categoria,
    atualizar_categoria,
    deletar_categoria,
    listar_produtos,
    obter_produto,
    criar_produto,
    atualizar_produto,
    deletar_produto,
    criar_venda,
    listar_vendas,
    obter_venda_com_itens,
    deletar_venda,
    listar_variantes,
    salvar_variantes,
    criar_orcamento,
    listar_orcamentos,
    obter_orcamento_com_itens,
    atualizar_status_orcamento,
    deletar_orcamento,
    listar_ordens_servico,
    obter_ordem_servico,
    atualizar_status_os,
    deletar_ordem_servico,
    listar_contas_pagar,
    obter_conta_pagar,
    criar_conta_pagar,
    atualizar_conta_pagar,
    deletar_conta_pagar,
    atualizar_status_conta_pagar,
    listar_vendas_pendentes,
    listar_vendas_pendentes_por_cliente,
    obter_cliente,
    obter_itens_venda,
    obter_configuracoes,
    salvar_configuracoes,
    listar_meios_pagamento,
    criar_meio_pagamento,
    excluir_meio_pagamento,
    listar_usuarios,
    obter_usuario,
    criar_usuario,
    atualizar_usuario,
    deletar_usuario,
    limpar_clientes,
    limpar_produtos,
    limpar_orcamentos,
    limpar_vendas,
    obter_licenca,
    salvar_licenca,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, '..', 'assets', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, '..', 'assets'),
    static_url_path='/assets',
    template_folder=os.path.join(BASE_DIR, 'templates'),
)

app.secret_key = os.urandom(24)

# Registrar blueprints de API
app.register_blueprint(api_dashboard)
app.register_blueprint(api_caixa)

# Middleware de verificação de licença e fechamento automático de caixa
@app.before_request
def verificar_licenca_middleware():
    """Verifica a licença e fecha caixa automaticamente à meia-noite"""
    # Rotas que não precisam de verificação de licença
    rotas_publicas = ['/login', '/static', '/assets', '/licenca_expirada', '/renovar_licenca', '/api/validar_licenca', '/api/salvar_licenca.php', '/api/bloquear_licenca_local']
    
    # Verifica se a rota atual está nas rotas públicas
    if any(request.path.startswith(rota) for rota in rotas_publicas):
        return None
    
    # Se não estiver logado, permite (vai para o login)
    if not session.get('usuario_id'):
        return None
    
    # FECHAMENTO AUTOMÁTICO DE CAIXA À MEIA-NOITE
    # Verifica se há caixa aberto de dia anterior
    try:
        from datetime import datetime
        conn = get_connection()
        cursor = conn.cursor()
        
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT id, data_abertura, valor_inicial 
            FROM caixas 
            WHERE data_fechamento IS NULL 
            AND data_abertura < ?
            ORDER BY data_abertura DESC 
            LIMIT 1
        """, (data_hoje,))
        
        caixa_anterior = cursor.fetchone()
        
        if caixa_anterior:
            # Fechar caixa automaticamente
            hora_fechamento = '23:59:59'
            data_fechamento = caixa_anterior[1]  # Data de abertura
            
            # Calcular valor final (soma das vendas + valor inicial)
            cursor.execute("""
                SELECT COALESCE(SUM(total), 0) 
                FROM vendas 
                WHERE DATE(data_venda) = ?
            """, (caixa_anterior[1],))
            
            total_vendas = cursor.fetchone()[0]
            valor_final = caixa_anterior[2] + total_vendas  # valor_inicial + vendas
            
            cursor.execute("""
                UPDATE caixas 
                SET data_fechamento = ?,
                    hora_fechamento = ?,
                    valor_final = ?,
                    status = 'fechado'
                WHERE id = ?
            """, (data_fechamento, hora_fechamento, valor_final, caixa_anterior[0]))
            
            conn.commit()
            print(f"🕐 Caixa ID {caixa_anterior[0]} de {caixa_anterior[1]} fechado automaticamente à meia-noite")
        
        conn.close()
    except Exception as e:
        print(f"Erro ao verificar fechamento automático de caixa: {e}")
    
    # Verifica se há licença válida
    try:
        licenca = obter_licenca()
        license_key = licenca.get('license_key', '')
        
        # Se não houver chave de licença
        if not license_key or license_key.strip() == '':
            return redirect(url_for('licenca_expirada'))
        
        # Valida formato básico
        partes = license_key.split('-')
        if len(partes) != 4 or not all(len(p) == 4 for p in partes):
            return redirect(url_for('licenca_expirada'))
        
        # Verifica se a licença está bloqueada localmente
        licenca_bloqueada = licenca.get('license_bloqueada', 'false')
        if licenca_bloqueada == 'true':
            return redirect(url_for('licenca_expirada'))
        
        # Verifica último status de validação online
        ultimo_status = licenca.get('ultimo_status_online', '')
        if ultimo_status == 'bloqueada' or ultimo_status == 'invalida':
            return redirect(url_for('licenca_expirada'))
            
    except Exception as e:
        print(f'Erro ao verificar licença: {e}')
        return redirect(url_for('licenca_expirada'))
    
    return None

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}


# Filtro personalizado para formatar datas no padrão brasileiro
@app.template_filter('data_br')
def formatar_data_br(data_str, com_hora=False):
    """
    Formata data para o padrão brasileiro DD/MM/YYYY
    Se com_hora=True, retorna DD/MM/YYYY HH:MM
    """
    if not data_str:
        return '-'
    
    try:
        # Tenta parsear a data em diferentes formatos
        if isinstance(data_str, str):
            # Formato: YYYY-MM-DD HH:MM:SS ou YYYY-MM-DD
            if ' ' in data_str:
                data = datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S')
            else:
                data = datetime.strptime(data_str, '%Y-%m-%d')
        else:
            data = data_str
        
        if com_hora:
            return data.strftime('%d/%m/%Y %H:%M')
        else:
            return data.strftime('%d/%m/%Y')
    except:
        return data_str


def formatar_moeda(valor):
    """Formata número como moeda brasileira: 1.234,56.

    Aceita int, float ou string. Em caso de erro, retorna 0,00.
    """
    try:
        if valor is None:
            v = 0.0
        elif isinstance(valor, str):
            # Remove símbolo de moeda e espaços, trata separadores pt-BR
            s = valor.strip()
            s = s.replace("R$", "").replace("r$", "").strip()
            # remove separador de milhar e troca vírgula decimal por ponto
            s = s.replace(".", "").replace(",", ".")
            v = float(s)
        else:
            v = float(valor)
    except Exception:
        v = 0.0

    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


app.jinja_env.filters["moeda"] = formatar_moeda


def conta_pagar_para_dict(conta):
    if not conta:
        return None
    if hasattr(conta, "keys"):
        return {chave: conta[chave] for chave in conta.keys()}
    return conta


def row_to_dict(row):
    if not row:
        return None
    if hasattr(row, "keys"):
        return {chave: row[chave] for chave in row.keys()}
    return row


def usuario_logado():
    return session.get('usuario_id') is not None


def usuario_e_admin():
    return (session.get('usuario_privilegio') or '').lower() == 'admin'


def _salvar_arquivo_upload(file_storage, prefix='arquivo'):
    if not file_storage or not file_storage.filename:
        raise ValueError('Arquivo inválido')

    _, ext = os.path.splitext(file_storage.filename)
    ext = ext.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError('Formato de arquivo não permitido')

    nome = f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex}{ext}"
    caminho = os.path.join(UPLOAD_DIR, secure_filename(nome))
    file_storage.save(caminho)
    return f"/assets/uploads/{nome}"


def _extrair_dados_conta_request():
    data = request.get_json(silent=True)
    if not data:
        # Converte ImmutableMultiDict em dict normal
        data = request.form.to_dict()

    descricao = (data.get('descricao') or '').strip()
    fornecedor = (data.get('fornecedor') or '').strip()
    categoria = (data.get('categoria') or '').strip()
    data_vencimento = (data.get('data_vencimento') or '').strip() or None
    observacoes = (data.get('observacoes') or '').strip()
    status = (data.get('status') or 'pendente').strip().lower()
    if status not in ['pendente', 'pago', 'vencido']:
        status = 'pendente'

    valor_raw = str(data.get('valor', '0')).strip()
    valor_raw = valor_raw.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
    try:
        valor = float(valor_raw or 0)
    except ValueError:
        raise ValueError('Valor inválido')

    if data_vencimento and status != 'pago':
        try:
            data_date = datetime.strptime(data_vencimento, '%Y-%m-%d')
            hoje = datetime.now().date()
            if data_date.date() < hoje:
                status = 'vencido'
        except ValueError:
            pass

    return {
        'descricao': descricao,
        'fornecedor': fornecedor,
        'categoria': categoria,
        'valor': valor,
        'data_vencimento': data_vencimento,
        'status': status,
        'observacoes': observacoes,
    }


def _calcular_valor_restante(venda):
    if not venda:
        return 0

    desconto = float(venda.get('desconto') or 0)
    valor_pago = float(venda.get('valor_pago') or 0)

    subtotal = venda.get('subtotal')
    if subtotal is None:
        subtotal = float(venda.get('valor_total') or 0) + desconto
    subtotal = float(subtotal or 0)

    base_cobranca = subtotal - desconto
    restante = base_cobranca - valor_pago

    return max(restante, 0)


def _normalizar_pagamento_venda(venda):
    if not venda:
        return venda

    valor_total = float(venda.get('valor_total') or 0)
    desconto = float(venda.get('desconto') or 0)
    valor_pago = float(venda.get('valor_pago') or 0)

    subtotal = venda.get('subtotal')
    if subtotal is None:
        subtotal = valor_total + desconto
    subtotal = float(subtotal or 0)
    tipo_pagamento = (venda.get('tipo_pagamento') or 'total').lower()

    venda['valor_total'] = valor_total
    venda['desconto'] = desconto
    venda['subtotal'] = subtotal
    venda['valor_pago'] = max(valor_pago, 0)
    venda['tipo_pagamento'] = tipo_pagamento

    data_venda = venda.get('data_venda') or ''
    if data_venda:
        venda['data_venda'] = data_venda.split(' ')[0]

    return venda


@app.route('/', methods=['GET'])
def home():
    if session.get('usuario_id'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    mensagem = None

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()

        usuario = autenticar(email, senha)
        if not usuario:
            mensagem = 'Email ou senha incorretos.'
        else:
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            session['usuario_email'] = usuario['email']
            session['usuario_privilegio'] = usuario['privilegio']
            return redirect(url_for('dashboard'))

    # Busca configurações da empresa para exibir no login
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT chave, valor FROM configuracoes")
    config_rows = cursor.fetchall()
    config = {row['chave']: row['valor'] for row in config_rows}
    conn.close()

    return render_template('login.html', mensagem=mensagem, config=config)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    
    from database import get_connection
    from datetime import datetime
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Estatísticas iniciais (hoje)
    stats = {
        'faturamento_bruto': 0,
        'lucro': 0,
        'valores_receber': 0,
        'contas_pagar': 0,
        'total_vendas': 0,
        'total_clientes': 0,
        'total_produtos': 0,
        'orcamentos_pendentes': 0
    }
    
    try:
        # Busca estatísticas básicas
        cursor.execute("SELECT COUNT(*) as total FROM vendas")
        result = cursor.fetchone()
        stats['total_vendas'] = result[0] if result else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM clientes")
        result = cursor.fetchone()
        stats['total_clientes'] = result[0] if result else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM produtos WHERE ativo = 1")
        result = cursor.fetchone()
        stats['total_produtos'] = result[0] if result else 0
        
        cursor.execute("SELECT COUNT(*) as total FROM orcamentos WHERE status = 'pendente'")
        result = cursor.fetchone()
        stats['orcamentos_pendentes'] = result[0] if result else 0
    except:
        pass
    
    # Status do caixa
    caixa_info = {
        'status': 'fechado',
        'status_texto': 'Caixa está fechado',
        'valor_inicial': 0,
        'vendas_dia': 0,
        'valor_esperado': 0,
        'suprimentos': 0,
        'sangrias': 0
    }
    
    try:
        data_hoje = datetime.now().date().strftime('%Y-%m-%d')
        
        # Busca QUALQUER caixa aberto (independente da data)
        cursor.execute("""
            SELECT * FROM caixas 
            WHERE data_fechamento IS NULL
            ORDER BY data_abertura DESC 
            LIMIT 1
        """)
        
        caixa_row = cursor.fetchone()
        
        if caixa_row:
            caixa = dict(caixa_row)
            caixa_info['status'] = 'aberto'
            caixa_info['data_abertura'] = caixa['data_abertura']
            caixa_info['hora_abertura'] = caixa['hora_abertura']
            caixa_info['caixa_id'] = caixa['id']
            
            # Verifica se é de hoje ou de dia anterior
            if caixa['data_abertura'] == data_hoje:
                caixa_info['status_texto'] = 'Caixa está aberto e operacional'
            else:
                caixa_info['status_texto'] = f'⚠️ Caixa aberto desde {caixa["data_abertura"]} - Será fechado automaticamente à meia-noite'
            
            caixa_info['valor_inicial'] = float(caixa['valor_inicial'])
            
            # Suprimentos
            cursor.execute("""
                SELECT COALESCE(SUM(valor), 0) as total 
                FROM suprimentos WHERE caixa_id = ?
            """, (caixa['id'],))
            caixa_info['suprimentos'] = float(cursor.fetchone()[0])
            
            # Sangrias
            cursor.execute("""
                SELECT COALESCE(SUM(valor), 0) as total 
                FROM sangrias WHERE caixa_id = ?
            """, (caixa['id'],))
            caixa_info['sangrias'] = float(cursor.fetchone()[0])
            
            # Vendas do dia (baseado no histórico de pagamentos)
            # Soma todos os pagamentos que entraram hoje
            cursor.execute("""
                SELECT COALESCE(SUM(valor_pago), 0) as total
                FROM pagamentos_vendas
                WHERE DATE(data_pagamento) = ?
            """, (data_hoje,))
            caixa_info['vendas_dia'] = float(cursor.fetchone()[0])
            
            caixa_info['valor_esperado'] = (caixa_info['valor_inicial'] + 
                                           caixa_info['suprimentos'] - 
                                           caixa_info['sangrias'] + 
                                           caixa_info['vendas_dia'])
    except Exception as e:
        print(f"Erro ao buscar caixa: {e}")
        pass
    finally:
        cursor.close()
        conn.close()

    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'
    data_hoje = datetime.now().strftime('%d/%m/%Y')

    contexto = {
        'stats': stats,
        'usuario_nome': usuario_nome,
        'usuario_email': usuario_email,
        'usuario_privilegio': usuario_privilegio,
        'usuario_inicial': usuario_inicial,
        'data_hoje': data_hoje,
        'caixa_status': caixa_info['status'],
        'caixa_status_texto': caixa_info['status_texto'],
        'caixa_valor_inicial': f"{caixa_info['valor_inicial']:.2f}".replace('.', ','),
        'caixa_vendas_dia': f"{caixa_info['vendas_dia']:.2f}".replace('.', ','),
        'caixa_valor_esperado': f"{caixa_info['valor_esperado']:.2f}".replace('.', ','),
        'caixa_suprimentos': f"{caixa_info['suprimentos']:.2f}".replace('.', ','),
        'caixa_sangrias': f"{caixa_info['sangrias']:.2f}".replace('.', ','),
    }

    return render_template('dashboard.html', **contexto)


@app.route('/clientes', methods=['GET'])
def clientes():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 6
    
    clientes_rows = listar_clientes()
    
    # Calcular total de páginas
    total_clientes = len(clientes_rows)
    total_pages = (total_clientes + per_page - 1) // per_page
    
    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    clientes_paginados = clientes_rows[start_idx:end_idx]

    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

    from datetime import datetime
    data_hoje = datetime.now().strftime('%d/%m/%Y')

    return render_template(
        'clientes.html',
        clientes=clientes_paginados,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial,
        data_hoje=data_hoje,
        page=page,
        total_pages=total_pages,
        total_clientes=total_clientes,
    )


@app.route('/clientes/novo', methods=['POST'])
def clientes_novo():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    import json

    dados = {
        'nome': request.form.get('nome', '').strip(),
        'email': request.form.get('email', '').strip() or None,
        'telefone': request.form.get('telefone', '').strip() or None,
        'documento': request.form.get('documento', '').strip() or None,
        'endereco': request.form.get('endereco', '').strip() or None,
    }

    if dados['nome']:
        criar_cliente(dados)

    return redirect(url_for('clientes'))


@app.route('/clientes/editar/<int:cliente_id>', methods=['POST'])
def clientes_editar(cliente_id):
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    dados = {
        'nome': request.form.get('nome', '').strip(),
        'email': request.form.get('email', '').strip() or None,
        'telefone': request.form.get('telefone', '').strip() or None,
        'documento': request.form.get('documento', '').strip() or None,
        'endereco': request.form.get('endereco', '').strip() or None,
    }

    if dados['nome']:
        atualizar_cliente(cliente_id, dados)

    return redirect(url_for('clientes'))


@app.route('/clientes/<int:cliente_id>/deletar', methods=['POST'])
def clientes_deletar(cliente_id):
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    deletar_cliente(cliente_id)
    return redirect(url_for('clientes'))


@app.route('/categorias', methods=['GET'])
def categorias():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 6
    
    categorias_rows = listar_categorias()
    
    total_categorias = len(categorias_rows)
    total_pages = (total_categorias + per_page - 1) // per_page
    
    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    categorias_paginadas = categorias_rows[start_idx:end_idx]

    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

    from datetime import datetime
    data_hoje = datetime.now().strftime('%d/%m/%Y')

    return render_template(
        'categorias.html',
        categorias=categorias_paginadas,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial,
        data_hoje=data_hoje,
        page=page,
        total_pages=total_pages,
        total_categorias=total_categorias,
    )


@app.route('/categorias/novo', methods=['POST'])
def categorias_novo():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    dados = {
        'nome': request.form.get('nome', '').strip(),
        'descricao': request.form.get('descricao', '').strip() or None,
    }

    if dados['nome']:
        criar_categoria(dados)

    return redirect(url_for('categorias'))


@app.route('/categorias/editar/<int:categoria_id>', methods=['POST'])
def categorias_editar(categoria_id):
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    dados = {
        'nome': request.form.get('nome', '').strip(),
        'descricao': request.form.get('descricao', '').strip() or None,
    }

    if dados['nome']:
        atualizar_categoria(categoria_id, dados)

    return redirect(url_for('categorias'))


@app.route('/categorias/<int:categoria_id>/deletar', methods=['POST'])
def categorias_deletar(categoria_id):
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    deletar_categoria(categoria_id)
    return redirect(url_for('categorias'))


@app.route('/produtos', methods=['GET'])
def produtos():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 6
    
    produtos_rows = listar_produtos()
    categorias_rows = listar_categorias()
    
    total_produtos = len(produtos_rows)
    total_pages = (total_produtos + per_page - 1) // per_page
    
    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    produtos_paginados = produtos_rows[start_idx:end_idx]

    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

    from datetime import datetime
    data_hoje = datetime.now().strftime('%d/%m/%Y')

    return render_template(
        'produtos.html',
        produtos=produtos_paginados,
        categorias=categorias_rows,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial,
        data_hoje=data_hoje,
        page=page,
        total_pages=total_pages,
        total_produtos=total_produtos,
    )


@app.route('/pos/autorizar', methods=['GET'])
def pos_autorizar():
    """Gera token de autorização para acessar o POS desbloqueado"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    
    import secrets
    # Gerar token único
    token = secrets.token_urlsafe(32)
    session['pos_token'] = token
    
    # Redirecionar para o POS com o token
    return redirect(url_for('pos', direto=1, token=token))


@app.route('/pos', methods=['GET'])
def pos():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    clientes_rows = listar_clientes()
    produtos_rows = listar_produtos()

    # Flags para mostrar notificações
    venda_sucesso = request.args.get('venda_sucesso') == '1'
    venda_suspensa = request.args.get('venda_suspensa') == '1'
    
    # Verificar se o usuário tem autorização para acessar o POS desbloqueado
    # A autorização é dada por um token único que só é gerado quando clica nos botões
    token_url = request.args.get('token')
    token_sessao = session.get('pos_token')
    
    direto_param = request.args.get('direto') == '1'
    
    # Só desbloqueia se vier com direto=1 E o token da URL bater com o da sessão
    if direto_param and token_url and token_url == token_sessao:
        direto = True
        # Consumir o token (uso único)
        session.pop('pos_token', None)
    else:
        # Qualquer outro caso: mostrar modal e bloquear
        direto = False
        session.pop('pos_token', None)

    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

    from datetime import datetime
    data_hoje = datetime.now().strftime('%d/%m/%Y')
    
    # Verifica se há caixa aberto
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, data_abertura, valor_inicial 
        FROM caixas 
        WHERE data_fechamento IS NULL 
        ORDER BY data_abertura DESC 
        LIMIT 1
    """)
    caixa_aberto = cursor.fetchone()
    conn.close()
    
    print(f"🔍 Verificação de caixa:")
    print(f"   Caixa aberto: {caixa_aberto}")
    print(f"   Direto antes: {direto}")
    
    # Se não houver caixa aberto, bloqueia o POS
    if not caixa_aberto:
        direto = False
        print(f"   ❌ Nenhum caixa aberto - bloqueando POS")
    else:
        print(f"   ✅ Caixa ID {caixa_aberto[0]} está aberto")
    
    print(f"   Direto depois: {direto}")

    return render_template(
        'pos.html',
        clientes=clientes_rows,
        produtos=produtos_rows,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial,
        data_hoje=data_hoje,
        venda_sucesso=venda_sucesso,
        venda_suspensa=venda_suspensa,
        direto=direto,
        caixa_aberto=caixa_aberto,
    )


@app.route('/pos/finalizar', methods=['POST'])
def pos_finalizar():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    def to_float(value, default=0.0):
        """Converte string de valor monetário brasileiro para float.

        Aceita formatos como '1234', '1.234,56', '1234,56', '1234.56'.
        """
        try:
            if value is None:
                return default
            if isinstance(value, str):
                s = value.strip()
                s = s.replace('R$', '').replace('r$', '').strip()
                # se tiver vírgula, trata como pt-BR: remove pontos de milhar e troca vírgula por ponto
                if ',' in s:
                    s = s.replace('.', '').replace(',', '.')
                return float(s)
            return float(value)
        except Exception:
            return default

    cliente_id = request.form.get('cliente_id') or None
    produto_ids = request.form.getlist('produto_id[]')
    quantidades = request.form.getlist('quantidade[]')
    precos = request.form.getlist('preco_unitario[]')
    variantes_descricoes = request.form.getlist('variantes_descricao[]')

    subtotal = 0.0
    itens = []

    for idx, (pid, qnt, pr) in enumerate(zip(produto_ids, quantidades, precos)):
        if not pid:
            continue
        quantidade = to_float(qnt or 0)
        preco_unitario = to_float(pr or 0)
        if quantidade <= 0 or preco_unitario < 0:
            continue
        total = quantidade * preco_unitario
        subtotal += total
        descricao_var = None
        if variantes_descricoes and idx < len(variantes_descricoes):
            descricao_var = (variantes_descricoes[idx] or '').strip() or None

        itens.append(
            {
                'produto_id': int(pid),
                'quantidade': quantidade,
                'preco_unitario': preco_unitario,
                'total': total,
                'variantes_descricao': descricao_var,
            }
        )

    if itens:
        desconto = to_float(request.form.get('desconto', 0) or 0)
        total_final = to_float(request.form.get('total_final', subtotal) or subtotal)
        forma_pagamento = request.form.get('forma_pagamento') or None
        valor_recebido = to_float(request.form.get('valor_recebido', 0) or 0)
        troco = to_float(request.form.get('troco', 0) or 0)

        descricao_venda = request.form.get('descricao_venda') or None
        data_entrega = request.form.get('data_entrega') or None

        cabecalho = {
            'cliente_id': int(cliente_id) if cliente_id else None,
            'subtotal': subtotal,
            'desconto': desconto,
            'total': total_final,
            'forma_pagamento': forma_pagamento,
            'valor_recebido': valor_recebido,
            'troco': troco,
            'descricao_venda': descricao_venda,
            'data_entrega': data_entrega,
        }
        criar_venda(cabecalho, itens)

    return redirect(url_for('pos', venda_sucesso='1'))


@app.route('/pos/suspender', methods=['POST'])
def pos_suspender():
    """Suspende uma venda (salva como pendente sem forma de pagamento)"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    def to_float(value, default=0.0):
        try:
            if value is None:
                return default
            if isinstance(value, str):
                s = value.strip()
                s = s.replace('R$', '').replace('r$', '').strip()
                if ',' in s:
                    s = s.replace('.', '').replace(',', '.')
                return float(s)
            return float(value)
        except Exception:
            return default

    cliente_id = request.form.get('cliente_id') or None
    produto_ids = request.form.getlist('produto_id[]')
    quantidades = request.form.getlist('quantidade[]')
    precos = request.form.getlist('preco_unitario[]')
    variantes_descricoes = request.form.getlist('variantes_descricao[]')

    subtotal = 0.0
    itens = []

    for idx, (pid, qnt, pr) in enumerate(zip(produto_ids, quantidades, precos)):
        if not pid:
            continue
        quantidade = to_float(qnt or 0)
        preco_unitario = to_float(pr or 0)
        if quantidade <= 0 or preco_unitario < 0:
            continue
        total = quantidade * preco_unitario
        subtotal += total
        descricao_var = None
        if variantes_descricoes and idx < len(variantes_descricoes):
            descricao_var = (variantes_descricoes[idx] or '').strip() or None

        itens.append(
            {
                'produto_id': int(pid),
                'quantidade': quantidade,
                'preco_unitario': preco_unitario,
                'total': total,
                'variantes_descricao': descricao_var,
            }
        )

    if itens:
        desconto = to_float(request.form.get('desconto', 0) or 0)
        total_final = to_float(request.form.get('total_final', subtotal) or subtotal)
        descricao_venda = request.form.get('descricao_venda') or None
        data_entrega = request.form.get('data_entrega') or None

        # Venda suspensa: sem forma de pagamento, valor recebido = 0
        cabecalho = {
            'cliente_id': int(cliente_id) if cliente_id else None,
            'subtotal': subtotal,
            'desconto': desconto,
            'total': total_final,
            'forma_pagamento': None,  # Venda pendente
            'valor_recebido': 0,
            'troco': 0,
            'descricao_venda': descricao_venda,
            'data_entrega': data_entrega,
        }
        criar_venda(cabecalho, itens)

    return redirect(url_for('pos', venda_suspensa='1'))


@app.route('/vendas', methods=['GET'])
def vendas():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    try:
        # Paginação e filtro
        page = request.args.get('page', 1, type=int)
        filtro_status = request.args.get('status', 'todas')
        per_page = 6
        
        vendas_rows = listar_vendas()
        
        # Aplicar filtro de status
        if filtro_status == 'pago':
            vendas_rows = [v for v in vendas_rows if v['valor_recebido'] >= v['total'] and v['total'] > 0]
        elif filtro_status == 'pendente':
            vendas_rows = [v for v in vendas_rows if v['valor_recebido'] < v['total'] or v['total'] == 0]
        
        # Calcular total de páginas após filtro
        total_vendas = len(vendas_rows)
        total_pages = (total_vendas + per_page - 1) // per_page  # Arredonda para cima
        
        # Garantir que page está no range válido
        if page < 1:
            page = 1
        if page > total_pages and total_pages > 0:
            page = total_pages
        
        # Pegar apenas os itens da página atual
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        vendas_paginadas = vendas_rows[start_idx:end_idx]
        
        # Buscar produtos para o select de adicionar itens
        produtos_rows = listar_produtos()
        
        # Converter Row para dict para permitir serialização JSON
        produtos_list = [dict(p) for p in produtos_rows]

        usuario_nome = session.get('usuario_nome', 'Usuário')
        usuario_email = session.get('usuario_email', '')
        usuario_privilegio = session.get('usuario_privilegio', 'admin')
        usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

        from datetime import datetime
        data_hoje = datetime.now().strftime('%d/%m/%Y')

        return render_template(
            'vendas.html',
            vendas=vendas_paginadas,
            produtos=produtos_list,
            usuario_nome=usuario_nome,
            usuario_email=usuario_email,
            usuario_privilegio=usuario_privilegio,
            usuario_inicial=usuario_inicial,
            data_hoje=data_hoje,
            page=page,
            total_pages=total_pages,
            total_vendas=total_vendas,
            filtro_status=filtro_status,
        )
    except Exception as e:
        print(f"Erro na rota /vendas: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro: {str(e)}", 500


@app.route('/vendas/<int:venda_id>/cupom', methods=['GET'])
def venda_cupom(venda_id):
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    cabecalho, itens = obter_venda_com_itens(venda_id)
    if not cabecalho:
        return redirect(url_for('vendas'))

    # Converte Row para dict para garantir acesso correto no template
    itens_dict = [dict(item) for item in itens]

    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

    return render_template(
        'venda_cupom.html',
        venda=cabecalho,
        itens=itens_dict,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial,
    )


@app.route('/api/vendas/<int:venda_id>', methods=['GET'])
def api_obter_venda(venda_id):
    """Retorna dados de uma venda em JSON para o modal de edição."""
    if not session.get('usuario_id'):
        return jsonify({'error': 'não autenticado'}), 401

    cabecalho, itens = obter_venda_com_itens(venda_id)
    if not cabecalho:
        return jsonify({'error': 'Venda não encontrada'}), 404

    venda = {
        'id': cabecalho['id'],
        'numero': cabecalho['numero'],
        'cliente_nome': cabecalho['cliente_nome'],
        'subtotal': cabecalho['subtotal'],
        'desconto': cabecalho['desconto'],
        'total': cabecalho['total'],
        'forma_pagamento': cabecalho['forma_pagamento'],
        'valor_recebido': cabecalho['valor_recebido'],
        'troco': cabecalho['troco'],
    }

    return jsonify(venda)


@app.route('/api/vendas/<int:venda_id>/completa', methods=['GET'])
def api_obter_venda_completa(venda_id):
    """Retorna dados completos de uma venda incluindo itens."""
    if not session.get('usuario_id'):
        return jsonify({'error': 'não autenticado'}), 401

    try:
        cabecalho, itens = obter_venda_com_itens(venda_id)
        if not cabecalho:
            return jsonify({'error': 'Venda não encontrada'}), 404

        # Converter Row para dict para acesso seguro
        cabecalho_dict = dict(cabecalho)

        venda = {
            'id': cabecalho_dict.get('id'),
            'numero': cabecalho_dict.get('numero'),
            'cliente_nome': cabecalho_dict.get('cliente_nome'),
            'subtotal': cabecalho_dict.get('subtotal', 0),
            'desconto': cabecalho_dict.get('desconto', 0),
            'total': cabecalho_dict.get('total', 0),
            'forma_pagamento': cabecalho_dict.get('forma_pagamento'),
            'valor_recebido': cabecalho_dict.get('valor_recebido', 0),
            'troco': cabecalho_dict.get('troco', 0),
            'descricao_venda': cabecalho_dict.get('descricao_venda'),
            'data_entrega': cabecalho_dict.get('data_entrega'),
        }

        itens_list = [dict(item) for item in itens]

        return jsonify({'venda': venda, 'itens': itens_list})
    except Exception as e:
        print(f"Erro ao buscar venda completa: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@app.route('/vendas/<int:venda_id>/editar', methods=['POST'])
def vendas_editar(venda_id):
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    def to_float(value, default=0.0):
        try:
            if value is None:
                return default
            if isinstance(value, str):
                s = value.strip()
                s = s.replace('R$', '').replace('r$', '').strip()
                if ',' in s:
                    s = s.replace('.', '').replace(',', '.')
                return float(s)
            return float(value)
        except Exception:
            return default

    forma_pagamento = request.form.get('forma_pagamento') or None
    valor_recebido = to_float(request.form.get('valor_recebido', 0) or 0)
    descricao_venda = request.form.get('descricao_venda') or None
    data_entrega = request.form.get('data_entrega') or None
    
    # Pegar itens editados
    item_ids = request.form.getlist('item_id[]')
    produto_ids = request.form.getlist('produto_id[]')
    quantidades = request.form.getlist('quantidade[]')
    precos = request.form.getlist('preco_unitario[]')
    variantes_descricoes = request.form.getlist('variantes_descricao[]')

    from database import get_connection
    conn = get_connection()
    cur = conn.cursor()

    # Atualizar ou deletar itens existentes
    if item_ids and quantidades and precos:
        # Primeiro, deletar todos os itens da venda
        cur.execute("DELETE FROM itens_venda WHERE venda_id = ?", (venda_id,))
        
        # Recalcular subtotal e total
        subtotal = 0.0
        for idx, (pid, qtd, preco) in enumerate(zip(produto_ids, quantidades, precos)):
            quantidade = to_float(qtd)
            preco_unitario = to_float(preco)
            total_item = quantidade * preco_unitario
            subtotal += total_item
            
            # Pegar variante correspondente
            variante_desc = None
            if variantes_descricoes and idx < len(variantes_descricoes):
                variante_desc = (variantes_descricoes[idx] or '').strip() or None
            
            # Inserir item atualizado
            cur.execute(
                """
                INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario, total, variantes_descricao)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (venda_id, int(pid), quantidade, preco_unitario, total_item, variante_desc)
            )
        
        # Atualizar venda com novos totais
        total_final = subtotal  # Sem desconto por enquanto
        cur.execute(
            """
            UPDATE vendas
            SET subtotal = ?, total = ?, forma_pagamento = ?, valor_recebido = ?, descricao_venda = ?, data_entrega = ?
            WHERE id = ?
            """,
            (subtotal, total_final, forma_pagamento, valor_recebido, descricao_venda, data_entrega, venda_id),
        )
    else:
        # Se não houver itens, apenas atualizar forma de pagamento
        cur.execute(
            """
            UPDATE vendas
            SET forma_pagamento = ?, valor_recebido = ?, descricao_venda = ?, data_entrega = ?
            WHERE id = ?
            """,
            (forma_pagamento, valor_recebido, descricao_venda, data_entrega, venda_id),
        )

    conn.commit()
    conn.close()

    return redirect(url_for('vendas'))


@app.route('/vendas/<int:venda_id>/deletar', methods=['POST'])
def vendas_deletar(venda_id):
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    deletar_venda(venda_id)
    return redirect(url_for('vendas'))


@app.route('/vendas/<int:venda_id>/concluir-pagamento', methods=['POST'])
def vendas_concluir_pagamento(venda_id):
    """Conclui o pagamento de uma venda, pagando o valor restante"""
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401
    
    try:
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Busca a venda
        cursor.execute('SELECT total, valor_recebido FROM vendas WHERE id = ?', (venda_id,))
        venda = cursor.fetchone()
        
        if not venda:
            return jsonify({'erro': 'Venda não encontrada'}), 404
        
        total = venda['total']
        valor_recebido = venda['valor_recebido'] or 0
        
        # Calcula o valor restante
        valor_restante = total - valor_recebido
        
        if valor_restante <= 0:
            return jsonify({'erro': 'Venda já está paga'}), 400
        
        # Atualiza o valor recebido para o total (marca como pago)
        cursor.execute('''
            UPDATE vendas 
            SET valor_recebido = total 
            WHERE id = ?
        ''', (venda_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'sucesso': True,
            'mensagem': 'Pagamento concluído com sucesso',
            'valor_pago': valor_restante
        }), 200
        
    except Exception as e:
        print(f"Erro ao concluir pagamento: {e}")
        return jsonify({'erro': str(e)}), 500


@app.route('/produtos/novo', methods=['POST'])
def produtos_novo():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    def to_float(value, default=0.0):
        try:
            return float(value.replace(',', '.')) if isinstance(value, str) else float(value)
        except Exception:
            return default

    import json

    dados = {
        'nome': request.form.get('nome', '').strip(),
        'descricao': request.form.get('descricao', '').strip() or None,
        'categoria_id': request.form.get('categoria_id') or None,
        'custo': to_float(request.form.get('custo', 0) or 0),
        'preco': to_float(request.form.get('preco', 0) or 0),
        'estoque': to_float(request.form.get('estoque', 0) or 0),
        'unidade': request.form.get('unidade', 'un').strip() or 'un',
        'eh_servico': request.form.get('eh_servico') == 'on',
        'vendido_por_m2': request.form.get('vendido_por_m2') == 'on',
        'ativo': request.form.get('ativo') != 'off',
        'codigo_barras': request.form.get('codigo_barras', '').strip() or None,
    }

    variacoes_json = request.form.get('variacoes_json', '[]')
    try:
        variacoes = json.loads(variacoes_json) if variacoes_json else []
    except Exception:
        variacoes = []

    if dados['nome']:
        produto_id = criar_produto(dados)
        salvar_variantes(produto_id, variacoes)

    return redirect(url_for('produtos'))


@app.route('/produtos/editar/<int:produto_id>', methods=['POST'])
def produtos_editar(produto_id):
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    def to_float(value, default=0.0):
        try:
            return float(value.replace(',', '.')) if isinstance(value, str) else float(value)
        except Exception:
            return default

    import json

    dados = {
        'nome': request.form.get('nome', '').strip(),
        'descricao': request.form.get('descricao', '').strip() or None,
        'categoria_id': request.form.get('categoria_id') or None,
        'custo': to_float(request.form.get('custo', 0) or 0),
        'preco': to_float(request.form.get('preco', 0) or 0),
        'estoque': to_float(request.form.get('estoque', 0) or 0),
        'unidade': request.form.get('unidade', 'un').strip() or 'un',
        'eh_servico': request.form.get('eh_servico') == 'on',
        'vendido_por_m2': request.form.get('vendido_por_m2') == 'on',
        'ativo': request.form.get('ativo') != 'off',
        'codigo_barras': request.form.get('codigo_barras', '').strip() or None,
    }

    variacoes_json = request.form.get('variacoes_json', '[]')
    try:
        variacoes = json.loads(variacoes_json) if variacoes_json else []
    except Exception:
        variacoes = []

    if dados['nome']:
        atualizar_produto(produto_id, dados)
        salvar_variantes(produto_id, variacoes)

    return redirect(url_for('produtos'))


@app.route('/produtos/<int:produto_id>/deletar', methods=['POST'])
def produtos_deletar(produto_id):
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    deletar_produto(produto_id)
    return redirect(url_for('produtos'))


@app.route('/api/produtos/<int:produto_id>', methods=['GET'])
def api_obter_produto(produto_id):
    """Retorna dados de um produto + variacoes em JSON para o modal de edição."""
    if not session.get('usuario_id'):
        return jsonify({'error': 'não autenticado'}), 401

    row = obter_produto(produto_id)
    if not row:
        return jsonify({'error': 'Produto não encontrado'}), 404

    variacoes_rows = listar_variantes(produto_id)
    variacoes = [
        {
            'id': v['id'],
            'nome': v['nome'],
            'preco': v['preco'],
        }
        for v in variacoes_rows
    ]

    produto = {
        'id': row['id'],
        'nome': row['nome'],
        'descricao': row['descricao'],
        'categoria_id': row['categoria_id'],
        'custo': row['custo'],
        'preco': row['preco'],
        'estoque': row['estoque'],
        'unidade': row['unidade'],
        'eh_servico': bool(row['eh_servico']),
        'vendido_por_m2': bool(row['vendido_por_m2']),
        'ativo': bool(row['ativo']),
        'codigo_barras': row['codigo_barras'],
        'variacoes': variacoes,
    }

    return jsonify(produto)


@app.route('/api/pos/variantes/<int:produto_id>', methods=['GET'])
def api_pos_variantes(produto_id):
    """Retorna as variantes cadastradas para um produto em formato JSON."""
    if not session.get('usuario_id'):
        return jsonify({'error': 'não autenticado'}), 401

    rows = listar_variantes(produto_id)
    variacoes = [
        {
            'id': row['id'],
            'nome': row['nome'],
            'preco': row['preco'],
        }
        for row in rows
    ]
    return jsonify(variacoes)


@app.route('/debug/ultima-venda')
def debug_ultima_venda():
    """DEBUG: Mostra os dados brutos da última venda para verificar variantes_descricao."""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    
    from database import get_connection
    conn = get_connection()
    cur = conn.cursor()
    
    # Pega a última venda
    cur.execute("SELECT id, numero FROM vendas ORDER BY id DESC LIMIT 1")
    venda = cur.fetchone()
    
    if not venda:
        conn.close()
        return "<h1>Nenhuma venda encontrada</h1>"
    
    venda_id = venda['id']
    
    # Pega os itens dessa venda
    cur.execute("""
        SELECT 
            iv.id,
            iv.produto_id,
            p.nome AS produto_nome,
            iv.quantidade,
            iv.preco_unitario,
            iv.total,
            iv.variantes_descricao
        FROM itens_venda iv
        LEFT JOIN produtos p ON iv.produto_id = p.id
        WHERE iv.venda_id = ?
    """, (venda_id,))
    
    itens = cur.fetchall()
    conn.close()
    
    html = f"<h1>DEBUG - Última Venda (ID: {venda_id}, Nº: {venda['numero']})</h1>"
    html += "<table border='1' cellpadding='5'><tr><th>Item ID</th><th>Produto</th><th>Qtd</th><th>Preço Unit</th><th>Total</th><th>variantes_descricao</th></tr>"
    
    for item in itens:
        var_desc = item['variantes_descricao'] or '(VAZIO)'
        html += f"<tr><td>{item['id']}</td><td>{item['produto_nome']}</td><td>{item['quantidade']}</td><td>{item['preco_unitario']}</td><td>{item['total']}</td><td><strong>{var_desc}</strong></td></tr>"
    
    html += "</table>"
    html += "<br><a href='/vendas'>Voltar para Vendas</a>"
    
    return html


# ============================================
# ROTAS DE ORÇAMENTOS
# ============================================

@app.route('/orcamentos/autorizar-novo', methods=['GET'])
def orcamentos_autorizar_novo():
    """Autoriza criação de orçamento e redireciona"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    
    # Gerar token de autorização
    session['criar_orcamento_autorizado'] = True
    
    return redirect(url_for('orcamentos_novo'))


@app.route('/orcamentos/novo', methods=['GET'])
def orcamentos_novo():
    """Página para criar novo orçamento (similar ao POS)"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    # Verificar se tem autorização (token gerado ao clicar no botão do POS)
    autorizado = session.pop('criar_orcamento_autorizado', False)
    
    if not autorizado:
        # Se não tem autorização, redireciona para o POS
        return redirect(url_for('pos'))

    clientes_rows = listar_clientes()
    produtos_rows = listar_produtos()

    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

    from datetime import datetime
    data_hoje = datetime.now().strftime('%d/%m/%Y')

    return render_template(
        'orcamentos.html',
        clientes=clientes_rows,
        produtos=produtos_rows,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial,
        data_hoje=data_hoje,
    )


@app.route('/orcamentos/finalizar', methods=['POST'])
def orcamentos_finalizar():
    """Finaliza e salva o orçamento"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    def to_float(value, default=0.0):
        try:
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            value_str = str(value).replace(',', '.')
            return float(value_str) if value_str else default
        except (ValueError, TypeError):
            return default

    # Capturar dados do formulário
    cliente_id = request.form.get('cliente_id')
    if cliente_id:
        cliente_id = int(cliente_id) if cliente_id.isdigit() else None

    subtotal = to_float(request.form.get('subtotal', 0))
    desconto = to_float(request.form.get('desconto', 0))
    total = to_float(request.form.get('total', 0))
    validade_dias = int(request.form.get('validade_dias', 15))
    descricao = request.form.get('descricao_orcamento', '')

    # Itens
    produto_ids = request.form.getlist('produto_id[]')
    quantidades = request.form.getlist('quantidade[]')
    precos_unitarios = request.form.getlist('preco_unitario[]')
    totais_itens = request.form.getlist('total_item[]')
    variantes_descricoes = request.form.getlist('variantes_descricao[]')

    itens = []
    for i in range(len(produto_ids)):
        itens.append({
            'produto_id': int(produto_ids[i]),
            'quantidade': to_float(quantidades[i]),
            'preco_unitario': to_float(precos_unitarios[i]),
            'total': to_float(totais_itens[i]),
            'variantes_descricao': variantes_descricoes[i] if i < len(variantes_descricoes) else ''
        })

    cabecalho = {
        'cliente_id': cliente_id,
        'subtotal': subtotal,
        'desconto': desconto,
        'total': total,
        'validade_dias': validade_dias,
        'descricao': descricao
    }

    orcamento_id, numero = criar_orcamento(cabecalho, itens)

    return redirect(url_for('orcamentos_lista', orcamento_criado=1))


@app.route('/orcamentos', methods=['GET'])
def orcamentos_lista():
    """Lista todos os orçamentos"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 6
    
    orcamentos_rows = listar_orcamentos()
    
    # Calcular total de páginas
    total_orcamentos = len(orcamentos_rows)
    total_pages = (total_orcamentos + per_page - 1) // per_page
    
    # Garantir que page está no range válido
    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    # Pegar apenas os itens da página atual
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    orcamentos_paginados = orcamentos_rows[start_idx:end_idx]

    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

    orcamento_criado = request.args.get('orcamento_criado') == '1'

    return render_template(
        'orcamentos_lista.html',
        orcamentos=orcamentos_paginados,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial,
        orcamento_criado=orcamento_criado,
        page=page,
        total_pages=total_pages,
        total_orcamentos=total_orcamentos,
    )


@app.route('/orcamentos/<int:orcamento_id>')
def visualizar_orcamento(orcamento_id):
    """Visualiza detalhes de um orçamento"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    # Buscar orçamento completo
    cabecalho, itens = obter_orcamento_com_itens(orcamento_id)
    
    if not cabecalho:
        flash('Orçamento não encontrado', 'error')
        return redirect(url_for('listar_orcamentos'))
    
    # Converter para dict
    orcamento = dict(cabecalho)
    itens_list = [dict(item) for item in itens]
    
    # Busca configurações da empresa
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT chave, valor FROM configuracoes")
    config_rows = cursor.fetchall()
    config = {row['chave']: row['valor'] for row in config_rows}
    conn.close()
    
    # Dados do usuário
    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'usuario')
    usuario_inicial = usuario_nome[0].upper() if usuario_nome else 'U'
    
    return render_template(
        'orcamento_detalhes.html',
        orcamento=orcamento,
        itens=itens_list,
        config=config,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial
    )


@app.route('/orcamentos/<int:orcamento_id>/converter', methods=['POST'])
def converter_orcamento_em_venda(orcamento_id):
    """Converte um orçamento em venda"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    # Buscar orçamento completo
    cabecalho, itens = obter_orcamento_com_itens(orcamento_id)
    
    if not cabecalho:
        return jsonify({'erro': 'Orçamento não encontrado'}), 404
    
    # Converter Row para dict
    cabecalho_dict = dict(cabecalho)
    itens_list = [dict(item) for item in itens]
    
    # Pegar dados do formulário
    data_entrega = request.form.get('data_entrega', '')
    forma_pagamento = request.form.get('forma_pagamento', 'A definir')
    valor_recebido = float(request.form.get('valor_recebido', 0))
    
    total = cabecalho_dict.get('total', 0)
    troco = max(0, valor_recebido - total)
    
    # Preparar dados da venda
    venda_cabecalho = {
        'cliente_id': cabecalho_dict.get('cliente_id'),
        'subtotal': cabecalho_dict.get('subtotal', 0),
        'desconto': cabecalho_dict.get('desconto', 0),
        'total': total,
        'forma_pagamento': forma_pagamento,
        'valor_recebido': valor_recebido,
        'troco': troco,
        'descricao_venda': cabecalho_dict.get('descricao', ''),
        'data_entrega': data_entrega
    }
    
    # Preparar itens da venda
    venda_itens = []
    for item in itens_list:
        venda_itens.append({
            'produto_id': item.get('produto_id'),
            'quantidade': item.get('quantidade'),
            'preco_unitario': item.get('preco_unitario'),
            'total': item.get('total'),
            'variantes_descricao': item.get('variantes_descricao', '')
        })
    
    # Criar venda
    venda_id, numero_venda = criar_venda(venda_cabecalho, venda_itens)
    
    # Atualizar status do orçamento para "convertido"
    atualizar_status_orcamento(orcamento_id, 'convertido')
    
    return redirect(url_for('vendas', venda_criada=1))


@app.route('/orcamentos/<int:orcamento_id>/excluir', methods=['POST'])
def excluir_orcamento(orcamento_id):
    """Exclui um orçamento"""
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autorizado'}), 401
    
    try:
        deletar_orcamento(orcamento_id)
        return jsonify({'sucesso': True}), 200
    except Exception as e:
        print(f"Erro ao excluir orçamento: {e}")
        return jsonify({'erro': 'Erro ao excluir orçamento'}), 500


# ============================================
# ORDENS DE SERVIÇO
# ============================================


@app.route('/ordens-servico', methods=['GET'])
def ordens_servico():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    try:
        page = request.args.get('page', 1, type=int)
        per_page = 6

        ordens_rows = listar_ordens_servico()
        total_ordens = len(ordens_rows)
        total_pages = (total_ordens + per_page - 1) // per_page

        if page < 1:
            page = 1
        if total_pages > 0 and page > total_pages:
            page = total_pages

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        ordens_paginadas = [row_to_dict(row) for row in ordens_rows[start_idx:end_idx]]

        usuario_nome = session.get('usuario_nome', 'Usuário')
        usuario_email = session.get('usuario_email', '')
        usuario_privilegio = session.get('usuario_privilegio', 'admin')
        usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

        return render_template(
            'ordens_servico.html',
            ordens=ordens_paginadas,
            total_ordens=total_ordens,
            page=page,
            total_pages=total_pages,
            usuario_nome=usuario_nome,
            usuario_email=usuario_email,
            usuario_privilegio=usuario_privilegio,
            usuario_inicial=usuario_inicial,
        )
    except Exception as e:
        print(f"Erro na rota /ordens-servico: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro: {str(e)}", 500


@app.route('/ordens-servico/<int:os_id>/status', methods=['POST'])
def ordens_servico_status(os_id):
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401

    body = request.get_json(silent=True) or {}
    novo_status = (body.get('status') or '').strip().upper()
    status_validos = {
        'PEDIDO RECEBIDO',
        'EM PRODUÇÃO',
        'PRONTO PRA ENTREGA',
        'ENTREGUE'
    }

    if novo_status not in status_validos:
        return jsonify({'erro': 'Status inválido'}), 400

    ordem = obter_ordem_servico(os_id)
    if not ordem:
        return jsonify({'erro': 'Ordem de serviço não encontrada'}), 404

    ordem_dict = row_to_dict(ordem)
    status_atual = (ordem_dict.get('status') or '').upper()
    if status_atual == 'ENTREGUE' and novo_status != 'ENTREGUE':
        return jsonify({'erro': 'Ordem já entregue não pode ser alterada'}), 400

    try:
        atualizar_status_os(os_id, novo_status)
        return jsonify({'sucesso': True, 'status': novo_status}), 200
    except Exception as e:
        print(f"Erro ao atualizar status da OS: {e}")
        return jsonify({'erro': 'Erro ao atualizar status'}), 500


@app.route('/ordens-servico/<int:os_id>/excluir', methods=['POST'])
def ordens_servico_excluir(os_id):
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401

    ordem = obter_ordem_servico(os_id)
    if not ordem:
        return jsonify({'erro': 'Ordem de serviço não encontrada'}), 404

    try:
        deletar_ordem_servico(os_id)
        return jsonify({'sucesso': True}), 200
    except Exception as e:
        print(f"Erro ao excluir OS: {e}")
        return jsonify({'erro': 'Erro ao excluir ordem de serviço'}), 500


# ============================================
# ROTAS DE ESTOQUE
# ============================================

@app.route('/estoque', methods=['GET'])
def estoque():
    """Página de controle de estoque"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    
    try:
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        produtos_rows = listar_produtos()
        categorias_rows = listar_categorias()
        
        # Calcular total de páginas
        total_produtos = len(produtos_rows)
        total_pages = (total_produtos + per_page - 1) // per_page
        
        # Garantir que page está no range válido
        if page < 1:
            page = 1
        if page > total_pages and total_pages > 0:
            page = total_pages
        
        # Pegar apenas os itens da página atual
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        produtos_paginados = produtos_rows[start_idx:end_idx]
        
        usuario_nome = session.get('usuario_nome', 'Usuário')
        usuario_email = session.get('usuario_email', '')
        usuario_privilegio = session.get('usuario_privilegio', 'admin')
        usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'
        
        return render_template(
            'estoque.html',
            produtos=produtos_paginados,
            categorias=categorias_rows,
            usuario_nome=usuario_nome,
            usuario_email=usuario_email,
            usuario_privilegio=usuario_privilegio,
            usuario_inicial=usuario_inicial,
            page=page,
            total_pages=total_pages,
            total_produtos=total_produtos
        )
    except Exception as e:
        print(f"Erro na rota /estoque: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro: {str(e)}", 500


@app.route('/estoque/<int:produto_id>/ajustar', methods=['POST'])
def estoque_ajustar(produto_id):
    """Ajusta o estoque de um produto"""
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401
    
    try:
        data = request.get_json()
        tipo = data.get('tipo')  # 'entrada' ou 'saida'
        quantidade = float(data.get('quantidade', 0))
        motivo = data.get('motivo', '')
        
        if quantidade <= 0:
            return jsonify({'erro': 'Quantidade deve ser maior que zero'}), 400
        
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Buscar produto atual
        cursor.execute('SELECT nome, estoque, controlar_estoque, eh_servico, vendido_por_m2 FROM produtos WHERE id = ?', (produto_id,))
        produto = cursor.fetchone()
        
        if not produto:
            return jsonify({'erro': 'Produto não encontrado'}), 404
        
        # Verificar se é serviço ou vendido por m²
        if produto['eh_servico'] or produto['vendido_por_m2']:
            return jsonify({'erro': 'Este produto não permite controle de estoque'}), 400
        
        estoque_atual = produto['estoque'] or 0
        
        # Calcular novo estoque
        if tipo == 'entrada':
            novo_estoque = estoque_atual + quantidade
        elif tipo == 'saida':
            if quantidade > estoque_atual:
                return jsonify({'erro': 'Quantidade maior que estoque disponível'}), 400
            novo_estoque = estoque_atual - quantidade
        else:
            return jsonify({'erro': 'Tipo inválido'}), 400
        
        # Atualizar estoque E ativar controle de estoque automaticamente
        cursor.execute('UPDATE produtos SET estoque = ?, controlar_estoque = 1 WHERE id = ?', (novo_estoque, produto_id))
        
        # Registrar movimentação (se houver tabela de histórico)
        # TODO: Criar tabela de histórico de estoque se necessário
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'sucesso': True,
            'estoque_anterior': estoque_atual,
            'estoque_novo': novo_estoque,
            'quantidade': quantidade,
            'tipo': tipo
        }), 200
        
    except Exception as e:
        print(f"Erro ao ajustar estoque: {e}")
        return jsonify({'erro': str(e)}), 500


# ============================================
# ROTAS DE ETIQUETAS
# ============================================

@app.route('/etiquetas', methods=['GET'])
def etiquetas():
    """Página de geração de etiquetas"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    
    try:
        produtos_rows = listar_produtos()
        categorias_rows = listar_categorias()
        
        # Busca configurações da empresa
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT chave, valor FROM configuracoes")
        config_rows = cursor.fetchall()
        config = {row['chave']: row['valor'] for row in config_rows}
        conn.close()
        
        usuario_nome = session.get('usuario_nome', 'Usuário')
        usuario_email = session.get('usuario_email', '')
        usuario_privilegio = session.get('usuario_privilegio', 'admin')
        usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'
        
        return render_template(
            'etiquetas.html',
            produtos=produtos_rows,
            categorias=categorias_rows,
            config=config,
            usuario_nome=usuario_nome,
            usuario_email=usuario_email,
            usuario_privilegio=usuario_privilegio,
            usuario_inicial=usuario_inicial
        )
    except Exception as e:
        print(f"Erro na rota /etiquetas: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro: {str(e)}", 500


# ============================================
# RELATÓRIOS
# ============================================

@app.route('/relatorios', methods=['GET'])
def relatorios():
    """Página de geração de relatórios"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    
    try:
        # Busca configurações da empresa
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT chave, valor FROM configuracoes")
        config_rows = cursor.fetchall()
        config = {row['chave']: row['valor'] for row in config_rows}
        conn.close()
        
        usuario_nome = session.get('usuario_nome', 'Usuário')
        usuario_email = session.get('usuario_email', '')
        usuario_privilegio = session.get('usuario_privilegio', 'admin')
        usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'
        
        return render_template(
            'relatorios.html',
            config=config,
            usuario_nome=usuario_nome,
            usuario_email=usuario_email,
            usuario_privilegio=usuario_privilegio,
            usuario_inicial=usuario_inicial
        )
    except Exception as e:
        print(f"Erro na rota /relatorios: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro: {str(e)}", 500


@app.route('/api/relatorios/<tipo>', methods=['GET'])
def api_relatorio(tipo):
    """API para gerar dados de relatórios"""
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Busca configurações da empresa
        cursor.execute("SELECT chave, valor FROM configuracoes")
        config_rows = cursor.fetchall()
        config = {row['chave']: row['valor'] for row in config_rows}
        
        data_geracao = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        resultado = {
            'tipo': tipo,
            'data_geracao': data_geracao,
            'empresa': {
                'nome': config.get('empresa_nome', 'Empresa'),
                'cnpj': config.get('empresa_cnpj', ''),
                'telefone': config.get('empresa_telefone', ''),
                'endereco': config.get('empresa_endereco', '')
            },
            'dados': []
        }
        
        if tipo == 'produtos':
            # Verifica se a coluna estoque_minimo existe
            cursor.execute("PRAGMA table_info(produtos)")
            colunas = [col[1] for col in cursor.fetchall()]
            
            if 'estoque_minimo' in colunas:
                cursor.execute("""
                    SELECT p.id, p.nome, p.codigo_barras, p.preco, p.estoque, 
                           p.estoque_minimo, c.nome as categoria
                    FROM produtos p
                    LEFT JOIN categorias c ON p.categoria_id = c.id
                    ORDER BY p.nome
                """)
            else:
                cursor.execute("""
                    SELECT p.id, p.nome, p.codigo_barras, p.preco, p.estoque, 
                           c.nome as categoria
                    FROM produtos p
                    LEFT JOIN categorias c ON p.categoria_id = c.id
                    ORDER BY p.nome
                """)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Lista de Produtos'
            
        elif tipo == 'produtos_categoria':
            cursor.execute("""
                SELECT c.nome as categoria, COUNT(p.id) as total_produtos,
                       SUM(p.estoque) as total_estoque,
                       AVG(p.preco) as preco_medio
                FROM categorias c
                LEFT JOIN produtos p ON c.id = p.categoria_id
                GROUP BY c.id, c.nome
                ORDER BY c.nome
            """)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Produtos por Categoria'
            
        elif tipo == 'estoque_baixo':
            # Verifica se a coluna estoque_minimo existe
            cursor.execute("PRAGMA table_info(produtos)")
            colunas = [col[1] for col in cursor.fetchall()]
            
            if 'estoque_minimo' in colunas:
                cursor.execute("""
                    SELECT p.id, p.nome, p.codigo_barras, p.estoque, 
                           p.estoque_minimo, c.nome as categoria
                    FROM produtos p
                    LEFT JOIN categorias c ON p.categoria_id = c.id
                    WHERE p.estoque <= p.estoque_minimo
                    ORDER BY p.estoque ASC
                """)
            else:
                # Se não existe estoque_minimo, considera produtos com estoque <= 5
                cursor.execute("""
                    SELECT p.id, p.nome, p.codigo_barras, p.estoque, 
                           5 as estoque_minimo, c.nome as categoria
                    FROM produtos p
                    LEFT JOIN categorias c ON p.categoria_id = c.id
                    WHERE p.estoque <= 5
                    ORDER BY p.estoque ASC
                """)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Produtos com Estoque Baixo'
            
        elif tipo == 'produtos_mais_vendidos':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT p.id, p.nome, p.codigo_barras, 
                       SUM(iv.quantidade) as total_vendido,
                       SUM(iv.total) as valor_total,
                       COUNT(DISTINCT iv.venda_id) as num_vendas
                FROM produtos p
                INNER JOIN itens_venda iv ON p.id = iv.produto_id
                INNER JOIN vendas v ON iv.venda_id = v.id
            """
            
            if data_inicio and data_fim:
                query += " WHERE DATE(v.created_at) BETWEEN ? AND ?"
                cursor.execute(query + """
                    GROUP BY p.id, p.nome, p.codigo_barras
                    ORDER BY total_vendido DESC
                    LIMIT 50
                """, (data_inicio, data_fim))
            else:
                cursor.execute(query + """
                    GROUP BY p.id, p.nome, p.codigo_barras
                    ORDER BY total_vendido DESC
                    LIMIT 50
                """)
            
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Produtos Mais Vendidos'
            
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'vendas':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT v.id, v.created_at as data_venda, v.total, v.forma_pagamento,
                       v.desconto, v.subtotal, c.nome as cliente
                FROM vendas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
            """
            params = []
            
            if data_inicio and data_fim:
                query += " WHERE DATE(v.created_at) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " ORDER BY v.created_at DESC"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Relatório de Vendas'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'caixa':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT id, data_abertura, data_fechamento, saldo_inicial,
                       saldo_final, total_vendas, total_entradas, total_saidas,
                       usuario_abertura, usuario_fechamento, status
                FROM caixa
            """
            params = []
            
            if data_inicio and data_fim:
                query += " WHERE DATE(data_abertura) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " ORDER BY data_abertura DESC"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Relatório de Caixa'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'clientes_mais_compram':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT c.id, c.nome, c.documento, c.telefone,
                       COUNT(v.id) as total_compras,
                       SUM(v.total) as valor_total,
                       AVG(v.total) as ticket_medio
                FROM clientes c
                INNER JOIN vendas v ON c.id = v.cliente_id
            """
            
            if data_inicio and data_fim:
                query += " WHERE DATE(v.created_at) BETWEEN ? AND ?"
                cursor.execute(query + """
                    GROUP BY c.id, c.nome, c.documento, c.telefone
                    ORDER BY valor_total DESC
                    LIMIT 50
                """, (data_inicio, data_fim))
            else:
                cursor.execute(query + """
                    GROUP BY c.id, c.nome, c.documento, c.telefone
                    ORDER BY valor_total DESC
                    LIMIT 50
                """)
            
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Clientes que Mais Compram'
            
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'meios_pagamento':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT forma_pagamento, 
                       COUNT(*) as quantidade,
                       SUM(total) as total
                FROM vendas
                WHERE forma_pagamento IS NOT NULL
            """
            params = []
            
            if data_inicio and data_fim:
                query += " AND DATE(data_venda) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " GROUP BY forma_pagamento ORDER BY total DESC"
            
            cursor.execute(query, params)
            dados = [dict(row) for row in cursor.fetchall()]
            
            # Calcula percentual
            total_geral = sum(d['total'] for d in dados)
            if total_geral > 0:
                for d in dados:
                    d['percentual'] = (d['total'] / total_geral) * 100
            else:
                for d in dados:
                    d['percentual'] = 0
            
            resultado['dados'] = dados
            resultado['titulo'] = 'Meios de Pagamento Mais Utilizados'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'orcamentos':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT o.id, o.data_orcamento, o.total, o.status,
                       o.desconto, o.subtotal, c.nome as cliente
                FROM orcamentos o
                LEFT JOIN clientes c ON o.cliente_id = c.id
            """
            params = []
            
            if data_inicio and data_fim:
                query += " WHERE DATE(o.data_orcamento) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " ORDER BY o.data_orcamento DESC"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Relatório de Orçamentos'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'ordens_servico':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT os.id, os.data_abertura, os.data_previsao, os.data_conclusao,
                       os.valor_total, os.status, c.nome as cliente, os.descricao
                FROM ordens_servico os
                LEFT JOIN clientes c ON os.cliente_id = c.id
            """
            params = []
            
            if data_inicio and data_fim:
                query += " WHERE DATE(os.data_abertura) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " ORDER BY os.data_abertura DESC"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Relatório de Ordens de Serviço'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
        
        elif tipo == 'contas_pagar':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT id, descricao, valor, data_vencimento, data_pagamento,
                       status, categoria, fornecedor
                FROM contas_pagar
            """
            params = []
            
            if data_inicio and data_fim:
                query += " WHERE DATE(data_vencimento) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " ORDER BY data_vencimento DESC"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Relatório de Contas a Pagar'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
        
        elif tipo == 'clientes':
            cursor.execute("""
                SELECT id, nome, cpf_cnpj, telefone, email, endereco,
                       (SELECT COUNT(*) FROM vendas WHERE cliente_id = clientes.id) as total_compras,
                       (SELECT SUM(total) FROM vendas WHERE cliente_id = clientes.id) as valor_total
                FROM clientes
                ORDER BY nome
            """)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Lista de Clientes'
            
        elif tipo == 'categorias':
            cursor.execute("""
                SELECT c.id, c.nome, c.descricao,
                       COUNT(p.id) as total_produtos,
                       SUM(p.estoque) as total_estoque
                FROM categorias c
                LEFT JOIN produtos p ON c.id = p.categoria_id
                GROUP BY c.id, c.nome, c.descricao
                ORDER BY c.nome
            """)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Lista de Categorias'
            
        elif tipo == 'inadimplentes':
            cursor.execute("""
                SELECT c.id, c.nome, c.cpf_cnpj, c.telefone,
                       COUNT(v.id) as vendas_pendentes,
                       SUM(v.total) as valor_pendente
                FROM clientes c
                INNER JOIN vendas v ON c.id = v.cliente_id
                WHERE v.forma_pagamento IS NULL OR v.valor_recebido < v.total
                GROUP BY c.id, c.nome, c.cpf_cnpj, c.telefone
                ORDER BY valor_pendente DESC
            """)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Clientes Inadimplentes'
            
        elif tipo == 'produtos_sem_venda':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT p.id, p.nome, p.codigo_barras, p.preco, p.estoque,
                       c.nome as categoria
                FROM produtos p
                LEFT JOIN categorias c ON p.categoria_id = c.id
                WHERE p.id NOT IN (
                    SELECT DISTINCT iv.produto_id
                    FROM itens_venda iv
                    INNER JOIN vendas v ON iv.venda_id = v.id
            """
            params = []
            
            if data_inicio and data_fim:
                query += " WHERE DATE(v.created_at) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += ") ORDER BY p.nome"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Produtos Sem Venda'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'ticket_medio':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT DATE(data_venda) as data,
                       COUNT(*) as total_vendas,
                       SUM(total) as valor_total,
                       AVG(total) as ticket_medio,
                       MIN(total) as menor_venda,
                       MAX(total) as maior_venda
                FROM vendas
                WHERE forma_pagamento IS NOT NULL
            """
            params = []
            
            if data_inicio and data_fim:
                query += " AND DATE(data_venda) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " GROUP BY DATE(data_venda) ORDER BY data DESC"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Análise de Ticket Médio'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'descontos':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT v.id, v.created_at as data_venda, v.subtotal, v.desconto, v.total,
                       c.nome as cliente,
                       ROUND((v.desconto / v.subtotal) * 100, 2) as percentual_desconto
                FROM vendas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.desconto > 0
            """
            params = []
            
            if data_inicio and data_fim:
                query += " AND DATE(v.created_at) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " ORDER BY v.desconto DESC"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Relatório de Descontos'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'vendas_produto':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT p.nome as produto, p.codigo_barras,
                       SUM(iv.quantidade) as quantidade_vendida,
                       SUM(iv.total) as valor_total,
                       AVG(iv.preco_unitario) as preco_medio,
                       COUNT(DISTINCT iv.venda_id) as num_vendas
                FROM itens_venda iv
                INNER JOIN produtos p ON iv.produto_id = p.id
                INNER JOIN vendas v ON iv.venda_id = v.id
                WHERE 1=1
            """
            params = []
            
            if data_inicio and data_fim:
                query += " AND DATE(v.created_at) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " GROUP BY p.id, p.nome, p.codigo_barras ORDER BY quantidade_vendida DESC"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Vendas por Produto'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
            
        elif tipo == 'vendas_categoria':
            data_inicio = request.args.get('data_inicio')
            data_fim = request.args.get('data_fim')
            
            query = """
                SELECT c.nome as categoria,
                       COUNT(DISTINCT v.id) as total_vendas,
                       SUM(iv.quantidade) as quantidade_vendida,
                       SUM(iv.total) as valor_total
                FROM categorias c
                INNER JOIN produtos p ON c.id = p.categoria_id
                INNER JOIN itens_venda iv ON p.id = iv.produto_id
                INNER JOIN vendas v ON iv.venda_id = v.id
                WHERE 1=1
            """
            params = []
            
            if data_inicio and data_fim:
                query += " AND DATE(v.created_at) BETWEEN ? AND ?"
                params = [data_inicio, data_fim]
            
            query += " GROUP BY c.id, c.nome ORDER BY valor_total DESC"
            
            cursor.execute(query, params)
            resultado['dados'] = [dict(row) for row in cursor.fetchall()]
            resultado['titulo'] = 'Vendas por Categoria'
            if data_inicio and data_fim:
                resultado['periodo'] = f"{data_inicio} a {data_fim}"
        
        else:
            conn.close()
            return jsonify({'erro': 'Tipo de relatório inválido'}), 400
        
        conn.close()
        return jsonify(resultado)
        
    except Exception as e:
        print(f"Erro ao gerar relatório {tipo}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@app.route('/api/relatorios/caixa', methods=['GET'])
def api_relatorio_caixa():
    """API específica para histórico de caixa"""
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401
    
    try:
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        print(f"Buscando histórico de caixa: {data_inicio} até {data_fim}")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                id,
                data_abertura,
                hora_abertura,
                data_fechamento,
                hora_fechamento,
                valor_inicial,
                valor_final,
                status
            FROM caixas
        """
        
        params = []
        if data_inicio and data_fim:
            query += " WHERE DATE(data_abertura) BETWEEN ? AND ?"
            params = [data_inicio, data_fim]
        
        query += " ORDER BY data_abertura DESC, hora_abertura DESC"
        
        cursor.execute(query, params)
        caixas = cursor.fetchall()
        
        print(f"Encontrados {len(caixas)} registros de caixa")
        
        # Calcula valor esperado para cada caixa
        dados = []
        for caixa in caixas:
            caixa_dict = dict(caixa)
            caixa_id = caixa_dict['id']
            
            # Busca suprimentos
            cursor.execute("""
                SELECT COALESCE(SUM(valor), 0) as total
                FROM suprimentos
                WHERE caixa_id = ?
            """, (caixa_id,))
            total_suprimentos = cursor.fetchone()['total']
            
            # Busca sangrias
            cursor.execute("""
                SELECT COALESCE(SUM(valor), 0) as total
                FROM sangrias
                WHERE caixa_id = ?
            """, (caixa_id,))
            total_sangrias = cursor.fetchone()['total']
            
            # Busca vendas do dia (pela data de abertura do caixa)
            cursor.execute("""
                SELECT COALESCE(SUM(total), 0) as total
                FROM vendas
                WHERE DATE(created_at) = ?
            """, (caixa_dict['data_abertura'],))
            vendas_dia = cursor.fetchone()['total']
            
            # Calcula valor esperado
            valor_inicial = caixa_dict.get('valor_inicial', 0) or 0
            valor_esperado = valor_inicial + total_suprimentos - total_sangrias + vendas_dia
            
            caixa_dict['valor_esperado'] = valor_esperado
            caixa_dict['total_suprimentos'] = total_suprimentos
            caixa_dict['total_sangrias'] = total_sangrias
            caixa_dict['vendas_dia'] = vendas_dia
            
            dados.append(caixa_dict)
        
        conn.close()
        
        return jsonify({
            'sucesso': True,
            'dados': dados
        })
        
    except Exception as e:
        print(f"Erro ao buscar histórico de caixa: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


# ============================================
# CONTAS A PAGAR
# ============================================


@app.route('/contas-pagar', methods=['GET'])
def contas_pagar():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    try:
        contas_rows = listar_contas_pagar()
        contas = [conta_pagar_para_dict(row) for row in contas_rows]

        total_pendente = sum(c['valor'] for c in contas if (c['status'] or '').lower() in ['pendente', 'vencido'])
        total_pago = sum(c['valor'] for c in contas if (c['status'] or '').lower() == 'pago')
        total_vencido = sum(c['valor'] for c in contas if (c['status'] or '').lower() == 'vencido')

        usuario_nome = session.get('usuario_nome', 'Usuário')
        usuario_email = session.get('usuario_email', '')
        usuario_privilegio = session.get('usuario_privilegio', 'admin')
        usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

        return render_template(
            'contas_pagar.html',
            contas=contas,
            total_pendente=total_pendente,
            total_pago=total_pago,
            total_vencido=total_vencido,
            usuario_nome=usuario_nome,
            usuario_email=usuario_email,
            usuario_privilegio=usuario_privilegio,
            usuario_inicial=usuario_inicial,
        )
    except Exception as e:
        print(f"Erro na rota /contas-pagar: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro: {str(e)}", 500


@app.route('/contas-pagar', methods=['POST'])
def contas_pagar_criar():
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401

    try:
        dados = _extrair_dados_conta_request()
        if not dados['descricao']:
            return jsonify({'erro': 'Descrição é obrigatória'}), 400
        if dados['valor'] <= 0:
            return jsonify({'erro': 'Valor deve ser maior que zero'}), 400

        conta_id = criar_conta_pagar(dados)
        conta = conta_pagar_para_dict(obter_conta_pagar(conta_id))
        return jsonify({'sucesso': True, 'conta': conta}), 201
    except ValueError as e:
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        print(f"Erro ao criar conta: {e}")
        return jsonify({'erro': 'Erro interno ao criar conta'}), 500


@app.route('/contas-pagar/<int:conta_id>', methods=['PUT', 'PATCH'])
def contas_pagar_atualizar(conta_id):
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401

    try:
        if not obter_conta_pagar(conta_id):
            return jsonify({'erro': 'Conta não encontrada'}), 404

        dados = _extrair_dados_conta_request()
        if not dados['descricao']:
            return jsonify({'erro': 'Descrição é obrigatória'}), 400
        if dados['valor'] <= 0:
            return jsonify({'erro': 'Valor deve ser maior que zero'}), 400

        atualizar_conta_pagar(conta_id, dados)
        conta = conta_pagar_para_dict(obter_conta_pagar(conta_id))
        return jsonify({'sucesso': True, 'conta': conta}), 200
    except ValueError as e:
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        print(f"Erro ao atualizar conta: {e}")
        return jsonify({'erro': 'Erro interno ao atualizar conta'}), 500


@app.route('/contas-pagar/<int:conta_id>', methods=['DELETE'])
def contas_pagar_deletar(conta_id):
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401

    try:
        if not obter_conta_pagar(conta_id):
            return jsonify({'erro': 'Conta não encontrada'}), 404

        deletar_conta_pagar(conta_id)
        return jsonify({'sucesso': True}), 200
    except Exception as e:
        print(f"Erro ao excluir conta: {e}")
        return jsonify({'erro': 'Erro interno ao excluir conta'}), 500


@app.route('/contas-pagar/<int:conta_id>/status', methods=['POST'])
def contas_pagar_status(conta_id):
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401

    try:
        body = request.get_json(silent=True) or {}
        novo_status = (body.get('status') or '').lower()
        if novo_status not in ['pendente', 'pago', 'vencido']:
            return jsonify({'erro': 'Status inválido'}), 400

        if not obter_conta_pagar(conta_id):
            return jsonify({'erro': 'Conta não encontrada'}), 404

        atualizar_status_conta_pagar(conta_id, novo_status)
        conta = conta_pagar_para_dict(obter_conta_pagar(conta_id))
        return jsonify({'sucesso': True, 'conta': conta}), 200
    except Exception as e:
        print(f"Erro ao atualizar status da conta: {e}")
        return jsonify({'erro': 'Erro interno ao atualizar status'}), 500


# ============================================
# VALORES A RECEBER
# ============================================


@app.route('/valores-receber', methods=['GET'])
def valores_receber():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    try:
        vendas_rows = listar_vendas_pendentes()
        clientes_map = {}
        total_receber = 0.0
        total_vendas = 0

        for row in vendas_rows:
            venda = _normalizar_pagamento_venda(row_to_dict(row))
            valor_restante = _calcular_valor_restante(venda)
            if valor_restante <= 0:
                continue

            cliente_id = venda.get('cliente_id')
            cliente_nome = venda.get('cliente_nome') or 'Cliente não informado'
            cliente_key = cliente_id if cliente_id else f"sem-cliente-{venda['id']}"

            if cliente_key not in clientes_map:
                clientes_map[cliente_key] = {
                    'id': cliente_id,
                    'nome': cliente_nome,
                    'total_pendente': 0.0,
                    'qtde_vendas': 0,
                    'vendas': []
                }

            entry = clientes_map[cliente_key]
            entry['total_pendente'] += valor_restante
            entry['qtde_vendas'] += 1
            entry['vendas'].append({
                'id': venda['id'],
                'numero': venda.get('numero'),
                'data_venda': venda.get('data_venda'),
                'valor_restante': valor_restante,
                'subtotal': float(venda.get('subtotal') or venda.get('valor_total') or 0),
                'valor_total': float(venda.get('valor_total') or 0),
                'desconto': float(venda.get('desconto') or 0),
                'valor_pago': float(venda.get('valor_pago') or 0),
                'descricao_venda': venda.get('descricao_venda') or ''
            })

            total_receber += valor_restante
            total_vendas += 1

        clientes_valores = list(clientes_map.values())
        clientes_valores.sort(key=lambda c: c['total_pendente'], reverse=True)
        total_clientes = len(clientes_valores)

        usuario_nome = session.get('usuario_nome', 'Usuário')
        usuario_email = session.get('usuario_email', '')
        usuario_privilegio = session.get('usuario_privilegio', 'admin')
        usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

        return render_template(
            'valores_receber.html',
            clientes=clientes_valores,
            total_receber=total_receber,
            total_clientes=total_clientes,
            total_vendas=total_vendas,
            usuario_nome=usuario_nome,
            usuario_email=usuario_email,
            usuario_privilegio=usuario_privilegio,
            usuario_inicial=usuario_inicial,
        )
    except Exception as e:
        print(f"Erro na rota /valores-receber: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro: {str(e)}", 500


@app.route('/valores-receber/<int:cliente_id>/detalhes', methods=['GET'])
def valores_receber_detalhes(cliente_id):
    if not session.get('usuario_id'):
        return jsonify({'erro': 'Não autenticado'}), 401

    try:
        cliente_row = obter_cliente(cliente_id)
        if not cliente_row:
            return jsonify({'erro': 'Cliente não encontrado'}), 404

        cliente = row_to_dict(cliente_row)
        vendas_rows = listar_vendas_pendentes_por_cliente(cliente_id)
        vendas = []
        total_pendente = 0.0

        for row in vendas_rows:
            venda = row_to_dict(row)
            valor_restante = _calcular_valor_restante(venda)
            if valor_restante <= 0:
                continue

            itens_rows = obter_itens_venda(venda['id'])
            itens = []
            for item_row in itens_rows:
                item = row_to_dict(item_row)
                itens.append({
                    'produto_nome': item.get('produto_nome') or '',
                    'quantidade': float(item.get('quantidade') or 0),
                    'preco_unitario': float(item.get('preco_unitario') or 0),
                    'subtotal': float(item.get('total') or 0),
                    'area': float(item.get('area')) if item.get('area') not in (None, '') else None,
                    'largura': float(item.get('largura')) if item.get('largura') not in (None, '') else None,
                    'altura': float(item.get('altura')) if item.get('altura') not in (None, '') else None,
                    'vendido_por_m2': bool(item.get('vendido_por_m2')),
                    'unidade': item.get('unidade'),
                    'variantes_descricao': item.get('variantes_descricao') or '',
                    'variacao_nome': item.get('variantes_descricao') or ''
                })

            vendas.append({
                'id': venda['id'],
                'numero': venda.get('numero'),
                'data_venda': venda.get('data_venda'),
                'subtotal': float(venda.get('subtotal') or venda.get('valor_total') or 0),
                'valor_total': float(venda.get('valor_total') or 0),
                'desconto': float(venda.get('desconto') or 0),
                'valor_pago': float(venda.get('valor_pago') or 0),
                'valor_restante': valor_restante,
                'tipo_pagamento': venda.get('tipo_pagamento'),
                'descricao_venda': venda.get('descricao_venda') or '',
                'observacoes': venda.get('observacoes') or '',
                'itens': itens
            })

            total_pendente += valor_restante

        return jsonify({
            'success': True,
            'cliente': cliente,
            'vendas': vendas,
            'total_pendente': total_pendente,
            'qtde_vendas': len(vendas)
        }), 200
    except Exception as e:
        print(f"Erro ao obter detalhes de valores a receber: {e}")
        return jsonify({'erro': 'Erro interno ao buscar valores'}), 500


# ============================================
# CONFIGURAÇÕES DO SISTEMA
# ============================================


@app.route('/configuracoes', methods=['GET'])
def configuracoes():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))

    configuracoes_dict = obter_configuracoes()
    meios_pagamento = listar_meios_pagamento()
    usuarios_list = listar_usuarios() if usuario_e_admin() else []
    licenca = obter_licenca()

    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'

    return render_template(
        'configuracoes.html',
        configuracoes=configuracoes_dict,
        meios_pagamento=meios_pagamento,
        usuarios=usuarios_list,
        licenca=licenca,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial,
        eh_admin=usuario_e_admin(),
    )


@app.route('/renovar_licenca', methods=['GET'])
def renovar_licenca():
    """Página especial para renovar licença mesmo quando bloqueada"""
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    
    # Permite acesso mesmo com licença bloqueada
    licenca = obter_licenca()
    
    # Adiciona o HWID atual do computador
    hwid_atual = obter_hwid()
    licenca['hwid_atual'] = hwid_atual
    
    usuario_nome = session.get('usuario_nome', 'Usuário')
    usuario_email = session.get('usuario_email', '')
    usuario_privilegio = session.get('usuario_privilegio', 'admin')
    usuario_inicial = usuario_nome[:1].upper() if usuario_nome else 'U'
    
    return render_template(
        'renovar_licenca.html',
        licenca=licenca,
        usuario_nome=usuario_nome,
        usuario_email=usuario_email,
        usuario_privilegio=usuario_privilegio,
        usuario_inicial=usuario_inicial,
        eh_admin=usuario_e_admin(),
    )


def _requer_autenticacao_json():
    if not session.get('usuario_id'):
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    return None


def _requer_admin_json():
    if not session.get('usuario_id'):
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    if not usuario_e_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    return None


@app.route('/api/buscar_configuracoes.php', methods=['GET'])
def api_buscar_configuracoes():
    auth = _requer_autenticacao_json()
    if auth:
        return auth
    return jsonify({'success': True, 'configuracoes': obter_configuracoes()})


@app.route('/api/configuracoes', methods=['GET'])
def api_configuracoes():
    """Rota alternativa para buscar configurações (sem autenticação para uso em impressões)"""
    return jsonify({'success': True, 'configuracoes': obter_configuracoes()})


@app.route('/api/salvar_configuracoes.php', methods=['POST'])
def api_salvar_configuracoes():
    auth = _requer_autenticacao_json()
    if auth:
        return auth

    dados = request.get_json(silent=True) or {}
    if not isinstance(dados, dict):
        return jsonify({'success': False, 'error': 'Payload inválido'}), 400

    try:
        salvar_configuracoes(dados)
        return jsonify({'success': True})
    except Exception as exc:
        print(f'Erro ao salvar configurações: {exc}')
        return jsonify({'success': False, 'error': 'Erro ao salvar configurações'}), 500


@app.route('/api/salvar_licenca.php', methods=['POST'])
def api_salvar_licenca():
    """Salva a chave de licença (permite acesso mesmo com licença bloqueada)"""
    if not session.get('usuario_id'):
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    
    dados = request.get_json(silent=True) or {}
    chave_licenca = dados.get('chave_licenca', '').strip().upper()
    
    if not chave_licenca:
        return jsonify({'success': False, 'error': 'Chave de licença não informada'}), 400
    
    # Valida formato básico
    partes = chave_licenca.split('-')
    if len(partes) != 4 or not all(len(p) == 4 for p in partes):
        return jsonify({'success': False, 'error': 'Formato inválido. Use: XXXX-XXXX-XXXX-XXXX'}), 400
    
    try:
        # Obtém o HWID atual do computador
        hwid_atual = obter_hwid()
        
        # Salva a nova licença
        salvar_licenca(chave_licenca)
        
        # LIMPA TODOS OS STATUS ANTIGOS E RESETA BLOQUEIOS
        from datetime import datetime
        salvar_configuracoes({
            'hwid': hwid_atual,
            'tentativas_outro_pc': '0',
            'license_bloqueada': 'false',
            'ultimo_status_online': '',  # LIMPA status antigo
            'licenca_bloqueada_servidor': 'false',
            'ultima_validacao_online': '',  # LIMPA última validação
            'ultima_mensagem_online': '',  # LIMPA mensagem antiga
        })
        
        print(f"✅ Licença salva: {chave_licenca}")
        print(f"✅ HWID registrado: {hwid_atual}")
        print(f"✅ Todos os bloqueios resetados")
        
        return jsonify({
            'success': True,
            'mensagem': 'Licença atualizada com sucesso!'
        })
    except Exception as e:
        print(f'Erro ao salvar licença: {e}')
        return jsonify({
            'success': False,
            'error': 'Erro ao salvar licença. Tente novamente.'
        }), 500


@app.route('/api/bloquear_licenca_local', methods=['POST'])
def api_bloquear_licenca_local():
    """Bloqueia a licença localmente (para uso do gerador)"""
    try:
        # Bloqueia a licença no banco de dados local
        salvar_configuracoes({
            'license_bloqueada': 'true',
            'ultimo_status_online': 'invalida',
            'ultima_mensagem_online': 'Licença bloqueada pelo administrador'
        })
        
        print(f"🔒 Licença bloqueada localmente!")
        
        return jsonify({
            'success': True,
            'mensagem': 'Licença bloqueada com sucesso!'
        })
    except Exception as e:
        print(f'Erro ao bloquear licença: {e}')
        return jsonify({
            'success': False,
            'error': 'Erro ao bloquear licença.'
        }), 500


@app.route('/api/validar_licenca', methods=['GET'])
def api_validar_licenca():
    """Valida a licença do sistema com verificação de HWID (híbrido online/offline)"""
    try:
        import requests
        from datetime import timedelta
        
        licenca = obter_licenca()
        license_key = licenca.get('license_key', '')
        
        # Se não houver chave de licença, considera inválida
        if not license_key or license_key.strip() == '':
            return jsonify({
                'valida': False,
                'mensagem': 'Nenhuma chave de licença cadastrada. Entre em contato com o suporte.'
            })
        
        # Valida formato básico
        partes = license_key.split('-')
        if len(partes) != 4 or not all(len(p) == 4 for p in partes):
            return jsonify({
                'valida': False,
                'mensagem': 'Formato de licença inválido. Entre em contato com o suporte.'
            })
        
        # VALIDAÇÃO ONLINE (se configurado E se houver histórico de validação)
        servidor_validacao = licenca.get('servidor_validacao', '')
        ultimo_status = licenca.get('ultimo_status_online', '')
        
        # Só tenta validação online se tiver servidor configurado E já tiver validado antes
        if servidor_validacao and servidor_validacao.strip() and ultimo_status:
            # Tenta validar com servidor online
            try:
                hwid_atual = obter_hwid()
                
                response = requests.post(
                    f"{servidor_validacao}/api/validar",
                    json={
                        'chave': license_key,
                        'hwid': hwid_atual
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # SALVA O STATUS DA ÚLTIMA VALIDAÇÃO ONLINE
                    salvar_configuracoes({
                        'ultima_validacao_online': datetime.now().isoformat(),
                        'ultimo_status_online': 'valida' if data.get('valida') else 'invalida',
                        'ultima_mensagem_online': data.get('mensagem', ''),
                        'licenca_bloqueada_servidor': 'true' if data.get('bloqueada') else 'false'
                    })
                    
                    print(f"✅ Validação online bem-sucedida: {data.get('mensagem')}")
                    return jsonify(data)
                    
            except requests.exceptions.Timeout:
                print("⚠️ Timeout ao conectar com servidor de validação")
            except requests.exceptions.ConnectionError:
                print("⚠️ Erro de conexão com servidor de validação")
            except Exception as e:
                print(f"⚠️ Erro ao validar online: {e}")
            
            # SERVIDOR OFFLINE - USA VALIDAÇÃO LOCAL (HWID)
            print("📡 Servidor offline - usando validação local por HWID")
            
            licenca_bloqueada = licenca.get('licenca_bloqueada_servidor', 'false')
            ultimo_status = licenca.get('ultimo_status_online', '')
            ultima_validacao = licenca.get('ultima_validacao_online', '')
            
            # Se licença estava BLOQUEADA no servidor, mantém bloqueada
            if licenca_bloqueada == 'true':
                print("❌ Licença bloqueada pelo servidor (último status)")
                return jsonify({
                    'valida': False,
                    'mensagem': 'Licença bloqueada pelo servidor. Entre em contato com o suporte.',
                    'servidor_offline': True,
                    'bloqueada': True
                })
            
            # Se última validação foi INVÁLIDA, mantém inválida
            if ultimo_status == 'invalida':
                print("❌ Última validação online foi inválida")
                mensagem_original = licenca.get('ultima_mensagem_online', 'Licença inválida')
                return jsonify({
                    'valida': False,
                    'mensagem': f'{mensagem_original} (Servidor offline)',
                    'servidor_offline': True
                })
            
            # Se última validação foi VÁLIDA, permite uso offline
            if ultimo_status == 'valida':
                # Verifica há quanto tempo foi a última validação
                if ultima_validacao:
                    try:
                        dt_ultima = datetime.fromisoformat(ultima_validacao)
                        dias_offline = (datetime.now() - dt_ultima).days
                        
                        # Permite uso offline por até 90 dias
                        if dias_offline > 90:
                            print(f"⚠️ Servidor offline há {dias_offline} dias (limite: 90)")
                            return jsonify({
                                'valida': False,
                                'mensagem': f'Servidor offline há {dias_offline} dias. Conecte à internet para validar.',
                                'servidor_offline': True
                            })
                        
                        print(f"✅ Modo offline: {dias_offline} dias desde última validação (limite: 90)")
                    except:
                        pass
                
                # Permite uso offline com última validação válida
                print("✅ Licença válida - modo offline ativado")
                # Continua para validação de HWID local
            
            # Se nunca validou online, continua para validação local de HWID
            # Não bloqueia mais por falta de validação online inicial
        
        # VALIDAÇÃO DE HWID (Hardware ID)
        hwid_armazenado = licenca.get('hwid', '')
        print(f"🔍 HWID armazenado: {hwid_armazenado}")
        
        resultado_hwid = validar_hwid_licenca(license_key, hwid_armazenado)
        print(f"🔍 Resultado validação HWID: {resultado_hwid}")
        
        # Se é a primeira ativação, salva o HWID
        if resultado_hwid.get('primeira_ativacao'):
            salvar_configuracoes({'hwid': resultado_hwid['hwid_atual']})
            print(f"✅ HWID registrado: {resultado_hwid['hwid_atual']}")
        
        # Se o HWID não é válido, bloqueia
        if not resultado_hwid['valido']:
            # Incrementa contador de tentativas
            tentativas = int(licenca.get('tentativas_outro_pc', 0)) + 1
            salvar_configuracoes({'tentativas_outro_pc': str(tentativas)})
            
            # Se passou de 3 tentativas, bloqueia permanentemente
            if tentativas >= 3:
                salvar_configuracoes({'license_bloqueada': 'true'})
                return jsonify({
                    'valida': False,
                    'mensagem': 'LICENÇA BLOQUEADA! Detectado uso em computador não autorizado. Entre em contato com o suporte.'
                })
            
            return jsonify({
                'valida': False,
                'mensagem': f'{resultado_hwid["mensagem"]}. Tentativa {tentativas}/3. Após 3 tentativas a licença será bloqueada permanentemente.'
            })
        
        # Verifica se a licença foi bloqueada
        if licenca.get('license_bloqueada') == 'true':
            return jsonify({
                'valida': False,
                'mensagem': 'Licença bloqueada por uso em múltiplos computadores. Entre em contato com o suporte.'
            })
        
        # Validação bem-sucedida
        return jsonify({
            'valida': True,
            'mensagem': 'Licença válida',
            'hwid': resultado_hwid['hwid_atual'],
            'dados': {
                'cliente': licenca.get('cliente_nome', ''),
                'email': licenca.get('cliente_email', '')
            }
        })
        
    except Exception as e:
        print(f'Erro ao validar licença: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'valida': False,
            'mensagem': 'Erro ao validar licença. Tente novamente.'
        }), 500


@app.route('/api/obter_hwid', methods=['GET'])
def api_obter_hwid():
    """Retorna o HWID do computador atual"""
    try:
        hwid_atual = obter_hwid()
        
        return jsonify({
            'success': True,
            'hwid': hwid_atual
        })
    except Exception as e:
        print(f'Erro ao obter HWID: {e}')
        return jsonify({
            'success': False,
            'erro': str(e)
        }), 500


@app.route('/licenca_expirada', methods=['GET'])
def licenca_expirada():
    """Página de licença expirada"""
    return render_template('licenca_expirada.html')


@app.route('/api/upload_logo.php', methods=['POST'])
def api_upload_logo():
    auth = _requer_autenticacao_json()
    if auth:
        return auth

    file = (
        request.files.get('empresa_logo') or
        request.files.get('logo') or
        request.files.get('sistema_logo') or
        request.files.get('favicon') or
        request.files.get('arquivo')
    )

    if not file:
        return jsonify({'success': False, 'error': 'Arquivo não enviado'}), 400

    tipo = request.form.get('tipo', 'logo')
    prefixo = 'logo-empresa' if 'empresa' in tipo else 'logo-sistema'

    try:
        url = _salvar_arquivo_upload(file, prefix=prefixo)
        return jsonify({'success': True, 'url': url})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        print(f'Erro ao fazer upload: {exc}')
        return jsonify({'success': False, 'error': 'Erro ao enviar arquivo'}), 500


@app.route('/api/listar_meios_pagamento.php', methods=['GET'])
def api_listar_meios_pagamento():
    auth = _requer_autenticacao_json()
    if auth:
        return auth
    meios = [row_to_dict(row) for row in listar_meios_pagamento()]
    return jsonify({'success': True, 'meios': meios})


@app.route('/api/criar_meio_pagamento.php', methods=['POST'])
def api_criar_meio_pagamento():
    auth = _requer_autenticacao_json()
    if auth:
        return auth

    corpo = request.get_json(silent=True) or {}
    nome = (corpo.get('nome') or '').strip()
    if not nome:
        return jsonify({'success': False, 'error': 'Nome é obrigatório'}), 400

    try:
        meio_id = criar_meio_pagamento(nome, corpo.get('ativo', 1), corpo.get('ordem', 0))
        return jsonify({'success': True, 'id': meio_id})
    except Exception as exc:
        print(f'Erro ao criar meio de pagamento: {exc}')
        return jsonify({'success': False, 'error': 'Erro ao criar meio de pagamento'}), 500


@app.route('/api/excluir_meio_pagamento.php', methods=['POST', 'DELETE'])
def api_excluir_meio_pagamento():
    auth = _requer_autenticacao_json()
    if auth:
        return auth

    payload = request.get_json(silent=True) or {}
    meio_id = request.args.get('id') or payload.get('id')
    if not meio_id:
        return jsonify({'success': False, 'error': 'ID não informado'}), 400

    try:
        excluir_meio_pagamento(int(meio_id))
        return jsonify({'success': True, 'message': 'Meio de pagamento excluído com sucesso'})
    except Exception as exc:
        print(f'Erro ao excluir meio de pagamento: {exc}')
        return jsonify({'success': False, 'error': 'Erro ao excluir meio de pagamento'}), 500


def _executar_limpeza(nome_acao, funcao):
    try:
        funcao()
        return jsonify({'success': True, 'message': f'{nome_acao} concluída com sucesso'})
    except Exception as exc:
        print(f'Erro ao limpar {nome_acao}: {exc}')
        return jsonify({'success': False, 'error': f'Erro ao limpar {nome_acao}'}), 500


@app.route('/api/limpar_clientes.php', methods=['POST'])
def api_limpar_clientes():
    auth = _requer_admin_json()
    if auth:
        return auth
    return _executar_limpeza('clientes', limpar_clientes)


@app.route('/api/limpar_produtos.php', methods=['POST'])
def api_limpar_produtos():
    auth = _requer_admin_json()
    if auth:
        return auth
    return _executar_limpeza('produtos', limpar_produtos)


@app.route('/api/limpar_orcamentos.php', methods=['POST'])
def api_limpar_orcamentos():
    auth = _requer_admin_json()
    if auth:
        return auth
    return _executar_limpeza('orcamentos', limpar_orcamentos)


@app.route('/api/limpar_vendas.php', methods=['POST'])
def api_limpar_vendas():
    auth = _requer_admin_json()
    if auth:
        return auth
    return _executar_limpeza('vendas', limpar_vendas)


@app.route('/api/zerar_sistema', methods=['POST'])
def api_zerar_sistema():
    """Zera todos os dados do sistema mantendo apenas usuários e configurações"""
    auth = _requer_admin_json()
    if auth:
        return auth
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Lista de tabelas para limpar (na ordem correta devido às foreign keys)
        tabelas_limpar = [
            'pagamentos_vendas',
            'itens_venda',
            'vendas',
            'itens_orcamento',
            'orcamentos',
            'ordens_servico',
            'contas_pagar',
            'suprimentos',
            'sangrias',
            'caixas',
            'produto_variacoes',
            'produtos',
            'categorias',
            'clientes',
        ]
        
        total_removidos = 0
        
        # Limpa cada tabela
        for tabela in tabelas_limpar:
            cursor.execute(f"DELETE FROM {tabela}")
            total_removidos += cursor.rowcount
        
        # Reseta os auto-incrementos
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ({})".format(
            ','.join(['?' for _ in tabelas_limpar])
        ), tabelas_limpar)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Sistema zerado com sucesso! {total_removidos} registros removidos.',
            'total_removidos': total_removidos
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/criar_backup', methods=['GET'])
def api_criar_backup():
    """Cria um backup completo do banco de dados em formato JSON"""
    auth = _requer_admin_json()
    if auth:
        return auth
    
    try:
        import json
        from datetime import datetime
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Lista de tabelas para fazer backup
        tabelas = [
            'clientes',
            'categorias',
            'produtos',
            'produto_variacoes',
            'caixas',
            'sangrias',
            'suprimentos',
            'contas_pagar',
            'ordens_servico',
            'orcamentos',
            'itens_orcamento',
            'vendas',
            'itens_venda',
            'pagamentos_vendas',
        ]
        
        backup_data = {
            'versao': '1.0',
            'data_backup': datetime.now().isoformat(),
            'sistema': 'Sistema de Gestão - Gráfica Criativa',
            'tabelas': {}
        }
        
        # Exporta dados de cada tabela
        for tabela in tabelas:
            cursor.execute(f"SELECT * FROM {tabela}")
            colunas = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            backup_data['tabelas'][tabela] = {
                'colunas': colunas,
                'dados': [dict(zip(colunas, row)) for row in rows]
            }
        
        conn.close()
        
        # Converte para JSON
        json_data = json.dumps(backup_data, ensure_ascii=False, indent=2)
        
        # Retorna como arquivo para download
        from flask import Response
        return Response(
            json_data,
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename=backup_sistema_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            }
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/restaurar_backup', methods=['POST'])
def api_restaurar_backup():
    """Restaura o banco de dados a partir de um arquivo de backup JSON"""
    auth = _requer_admin_json()
    if auth:
        return auth
    
    try:
        import json
        
        # Verifica se o arquivo foi enviado
        if 'backup' not in request.files:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
        
        arquivo = request.files['backup']
        
        if arquivo.filename == '':
            return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
        
        # Lê e valida o JSON
        try:
            backup_data = json.load(arquivo)
        except json.JSONDecodeError:
            return jsonify({'success': False, 'error': 'Arquivo JSON inválido'}), 400
        
        # Valida estrutura do backup
        if 'tabelas' not in backup_data or 'versao' not in backup_data:
            return jsonify({'success': False, 'error': 'Estrutura de backup inválida'}), 400
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Lista de tabelas na ordem correta para limpeza (foreign keys)
        tabelas_limpar = [
            'pagamentos_vendas',
            'itens_venda',
            'vendas',
            'itens_orcamento',
            'orcamentos',
            'ordens_servico',
            'contas_pagar',
            'suprimentos',
            'sangrias',
            'caixas',
            'produto_variacoes',
            'produtos',
            'categorias',
            'clientes',
        ]
        
        # Limpa tabelas existentes
        for tabela in tabelas_limpar:
            cursor.execute(f"DELETE FROM {tabela}")
        
        # Reseta auto-incrementos
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ({})".format(
            ','.join(['?' for _ in tabelas_limpar])
        ), tabelas_limpar)
        
        total_restaurados = 0
        
        # Restaura dados na ordem inversa (para respeitar foreign keys)
        for tabela in reversed(tabelas_limpar):
            if tabela in backup_data['tabelas']:
                dados_tabela = backup_data['tabelas'][tabela]
                
                for registro in dados_tabela['dados']:
                    colunas = list(registro.keys())
                    valores = list(registro.values())
                    placeholders = ','.join(['?' for _ in colunas])
                    colunas_str = ','.join(colunas)
                    
                    cursor.execute(
                        f"INSERT INTO {tabela} ({colunas_str}) VALUES ({placeholders})",
                        valores
                    )
                    total_restaurados += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Backup restaurado com sucesso!',
            'total_restaurados': total_restaurados
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/buscar_usuario.php', methods=['GET'])
def api_buscar_usuario():
    auth = _requer_admin_json()
    if auth:
        return auth

    usuario_id = request.args.get('id')
    if not usuario_id:
        return jsonify({'success': False, 'error': 'ID não informado'}), 400

    usuario = obter_usuario(int(usuario_id))
    if not usuario:
        return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404

    return jsonify({'success': True, 'usuario': row_to_dict(usuario)})


@app.route('/api/criar_usuario.php', methods=['POST'])
def api_criar_usuario():
    auth = _requer_admin_json()
    if auth:
        return auth

    dados = request.get_json(silent=True) or {}
    try:
        usuario_id = criar_usuario(dados)
        return jsonify({'success': True, 'id': usuario_id})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        print(f'Erro ao criar usuário: {exc}')
        return jsonify({'success': False, 'error': 'Erro ao criar usuário'}), 500


@app.route('/api/editar_usuario.php', methods=['POST'])
def api_editar_usuario():
    auth = _requer_admin_json()
    if auth:
        return auth

    dados = request.get_json(silent=True) or {}
    usuario_id = dados.get('id')
    if not usuario_id:
        return jsonify({'success': False, 'error': 'ID do usuário é obrigatório'}), 400

    try:
        atualizar_usuario(int(usuario_id), dados)
        return jsonify({'success': True})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        print(f'Erro ao atualizar usuário: {exc}')
        return jsonify({'success': False, 'error': 'Erro ao atualizar usuário'}), 500


@app.route('/api/excluir_usuario.php', methods=['POST'])
def api_excluir_usuario():
    auth = _requer_admin_json()
    if auth:
        return auth

    dados = request.get_json(silent=True) or {}
    usuario_id = dados.get('id')
    if not usuario_id:
        return jsonify({'success': False, 'error': 'ID do usuário é obrigatório'}), 400

    try:
        deletar_usuario(int(usuario_id))
        return jsonify({'success': True})
    except Exception as exc:
        print(f'Erro ao excluir usuário: {exc}')
        return jsonify({'success': False, 'error': 'Erro ao excluir usuário'}), 500


@app.route('/api/alterar_licenca.php', methods=['POST'])
def api_alterar_licenca():
    auth = _requer_admin_json()
    if auth:
        return auth

    dados = request.get_json(silent=True) or {}
    chave = (dados.get('license_key') or '').strip()
    if not chave:
        return jsonify({'success': False, 'error': 'Chave de licença é obrigatória'}), 400

    try:
        salvar_licenca(chave)
        return jsonify({'success': True, 'message': 'Licença atualizada com sucesso'})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        print(f'Erro ao salvar licença: {exc}')
        return jsonify({'success': False, 'error': 'Erro ao atualizar licença'}), 500


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
