#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERVIDOR DE VALIDAÇÃO DE LICENÇAS ONLINE
=========================================

Este servidor fica online 24/7 e valida as licenças dos clientes em tempo real.

VANTAGENS:
- Controle centralizado
- Bloqueia/desbloqueia remotamente
- Cliente sempre consulta o servidor
- Estatísticas de uso
- Proteção total contra pirataria

COMO HOSPEDAR:
- Heroku (grátis)
- DigitalOcean ($5/mês)
- AWS, Google Cloud, Azure
- Qualquer VPS

REQUISITOS:
pip install flask flask-cors
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
import hashlib

app = Flask(__name__)
CORS(app)  # Permite requisições de qualquer origem

# Arquivo de banco de dados (em produção, use PostgreSQL/MySQL)
ARQUIVO_LICENCAS = 'licencas_online.json'

# Senha de administrador (MUDE ISSO!)
ADMIN_PASSWORD = 'SUA_SENHA_SECRETA_AQUI_123'


def carregar_licencas():
    """Carrega licenças do arquivo"""
    if not os.path.exists(ARQUIVO_LICENCAS):
        return []
    
    with open(ARQUIVO_LICENCAS, 'r', encoding='utf-8') as f:
        return json.load(f)


def salvar_licencas(licencas):
    """Salva licenças no arquivo"""
    with open(ARQUIVO_LICENCAS, 'w', encoding='utf-8') as f:
        json.dump(licencas, f, indent=2, ensure_ascii=False)


def verificar_senha_admin(senha):
    """Verifica senha de administrador"""
    return senha == ADMIN_PASSWORD


@app.route('/', methods=['GET'])
def home():
    """Página inicial"""
    return jsonify({
        'servidor': 'Servidor de Validação de Licenças',
        'versao': '1.0',
        'status': 'online',
        'endpoints': {
            'validar': 'POST /api/validar',
            'adicionar': 'POST /api/admin/adicionar',
            'bloquear': 'POST /api/admin/bloquear',
            'desbloquear': 'POST /api/admin/desbloquear',
            'listar': 'GET /api/admin/listar',
            'estatisticas': 'GET /api/admin/estatisticas'
        }
    })


@app.route('/api/validar', methods=['POST'])
def validar_licenca():
    """
    Endpoint público - Cliente consulta para validar licença
    
    POST /api/validar
    Body: {
        "chave": "XXXX-XXXX-XXXX-XXXX",
        "hwid": "XXXX-XXXX-XXXX-XXXX"
    }
    
    Response: {
        "valida": true/false,
        "mensagem": "...",
        "bloqueada": true/false
    }
    """
    try:
        dados = request.get_json()
        chave = dados.get('chave', '').strip()
        hwid = dados.get('hwid', '').strip()
        
        if not chave or not hwid:
            return jsonify({
                'valida': False,
                'mensagem': 'Chave e HWID são obrigatórios'
            }), 400
        
        # Carrega licenças
        licencas = carregar_licencas()
        
        # Busca a licença
        licenca = None
        for lic in licencas:
            if lic['chave'] == chave:
                licenca = lic
                break
        
        if not licenca:
            return jsonify({
                'valida': False,
                'mensagem': 'Licença não encontrada'
            })
        
        # Verifica se está bloqueada
        if licenca.get('bloqueada', False):
            return jsonify({
                'valida': False,
                'mensagem': 'Licença bloqueada. Entre em contato com o suporte.',
                'bloqueada': True
            })
        
        # Verifica se está revogada
        if licenca.get('status') == 'revogada':
            return jsonify({
                'valida': False,
                'mensagem': 'Licença revogada. Entre em contato com o suporte.'
            })
        
        # Verifica validade
        data_validade = datetime.strptime(licenca['data_validade'], '%Y-%m-%d')
        if datetime.now() > data_validade:
            return jsonify({
                'valida': False,
                'mensagem': 'Licença expirada. Renove sua assinatura.'
            })
        
        # VERIFICA HWID
        if licenca['hwid'] != hwid:
            # Tentativa de uso em outro PC!
            licenca['tentativas_outro_pc'] = licenca.get('tentativas_outro_pc', 0) + 1
            licenca['ultimo_hwid_tentado'] = hwid
            licenca['ultima_tentativa'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Se tentar 3 vezes, bloqueia
            if licenca['tentativas_outro_pc'] >= 3:
                licenca['bloqueada'] = True
                licenca['status'] = 'bloqueada'
                salvar_licencas(licencas)
                
                return jsonify({
                    'valida': False,
                    'mensagem': 'LICENÇA BLOQUEADA! Detectado uso em computador não autorizado.',
                    'bloqueada': True
                })
            
            salvar_licencas(licencas)
            
            return jsonify({
                'valida': False,
                'mensagem': f'Esta licença está vinculada a outro computador. Tentativa {licenca["tentativas_outro_pc"]}/3.'
            })
        
        # Atualiza último acesso
        licenca['ultimo_acesso'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        licenca['total_acessos'] = licenca.get('total_acessos', 0) + 1
        salvar_licencas(licencas)
        
        # Licença válida!
        return jsonify({
            'valida': True,
            'mensagem': 'Licença válida',
            'bloqueada': False,
            'dados': {
                'cliente': licenca['cliente_nome'],
                'validade': licenca['data_validade']
            }
        })
        
    except Exception as e:
        print(f'Erro ao validar licença: {e}')
        return jsonify({
            'valida': False,
            'mensagem': 'Erro ao validar licença'
        }), 500


@app.route('/api/admin/adicionar', methods=['POST'])
def admin_adicionar_licenca():
    """
    Endpoint admin - Adiciona nova licença
    
    POST /api/admin/adicionar
    Headers: X-Admin-Password: SUA_SENHA
    Body: {
        "chave": "XXXX-XXXX-XXXX-XXXX",
        "cliente_nome": "João Silva",
        "cliente_email": "joao@email.com",
        "hwid": "XXXX-XXXX-XXXX-XXXX",
        "data_validade": "2125-11-19",
        "dias_validade": 36500
    }
    """
    senha = request.headers.get('X-Admin-Password', '')
    
    if not verificar_senha_admin(senha):
        return jsonify({'erro': 'Não autorizado'}), 401
    
    try:
        dados = request.get_json()
        
        licenca = {
            'chave': dados['chave'],
            'cliente_nome': dados['cliente_nome'],
            'cliente_email': dados['cliente_email'],
            'hwid': dados['hwid'],
            'data_geracao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_validade': dados['data_validade'],
            'dias_validade': dados.get('dias_validade', 36500),
            'status': 'ativa',
            'bloqueada': False,
            'tentativas_outro_pc': 0,
            'total_acessos': 0
        }
        
        licencas = carregar_licencas()
        licencas.append(licenca)
        salvar_licencas(licencas)
        
        return jsonify({
            'sucesso': True,
            'mensagem': 'Licença adicionada com sucesso',
            'licenca': licenca
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/api/admin/bloquear', methods=['POST'])
def admin_bloquear_licenca():
    """
    Endpoint admin - Bloqueia uma licença
    
    POST /api/admin/bloquear
    Headers: X-Admin-Password: SUA_SENHA
    Body: {
        "chave": "XXXX-XXXX-XXXX-XXXX"
    }
    """
    senha = request.headers.get('X-Admin-Password', '')
    
    if not verificar_senha_admin(senha):
        return jsonify({'erro': 'Não autorizado'}), 401
    
    try:
        dados = request.get_json()
        chave = dados.get('chave', '').strip()
        
        licencas = carregar_licencas()
        
        encontrada = False
        for lic in licencas:
            if lic['chave'] == chave:
                lic['bloqueada'] = True
                lic['status'] = 'bloqueada'
                encontrada = True
                break
        
        if encontrada:
            salvar_licencas(licencas)
            return jsonify({
                'sucesso': True,
                'mensagem': f'Licença {chave} bloqueada com sucesso'
            })
        else:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Licença não encontrada'
            }), 404
            
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/api/admin/desbloquear', methods=['POST'])
def admin_desbloquear_licenca():
    """
    Endpoint admin - Desbloqueia uma licença
    
    POST /api/admin/desbloquear
    Headers: X-Admin-Password: SUA_SENHA
    Body: {
        "chave": "XXXX-XXXX-XXXX-XXXX"
    }
    """
    senha = request.headers.get('X-Admin-Password', '')
    
    if not verificar_senha_admin(senha):
        return jsonify({'erro': 'Não autorizado'}), 401
    
    try:
        dados = request.get_json()
        chave = dados.get('chave', '').strip()
        
        licencas = carregar_licencas()
        
        encontrada = False
        for lic in licencas:
            if lic['chave'] == chave:
                lic['bloqueada'] = False
                lic['status'] = 'ativa'
                lic['tentativas_outro_pc'] = 0
                encontrada = True
                break
        
        if encontrada:
            salvar_licencas(licencas)
            return jsonify({
                'sucesso': True,
                'mensagem': f'Licença {chave} desbloqueada com sucesso'
            })
        else:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Licença não encontrada'
            }), 404
            
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/api/admin/listar', methods=['GET'])
def admin_listar_licencas():
    """
    Endpoint admin - Lista todas as licenças
    
    GET /api/admin/listar
    Headers: X-Admin-Password: SUA_SENHA
    """
    senha = request.headers.get('X-Admin-Password', '')
    
    if not verificar_senha_admin(senha):
        return jsonify({'erro': 'Não autorizado'}), 401
    
    licencas = carregar_licencas()
    
    return jsonify({
        'total': len(licencas),
        'licencas': licencas
    })


@app.route('/api/admin/estatisticas', methods=['GET'])
def admin_estatisticas():
    """
    Endpoint admin - Estatísticas gerais
    
    GET /api/admin/estatisticas
    Headers: X-Admin-Password: SUA_SENHA
    """
    senha = request.headers.get('X-Admin-Password', '')
    
    if not verificar_senha_admin(senha):
        return jsonify({'erro': 'Não autorizado'}), 401
    
    licencas = carregar_licencas()
    
    total = len(licencas)
    ativas = sum(1 for l in licencas if l['status'] == 'ativa' and not l.get('bloqueada'))
    bloqueadas = sum(1 for l in licencas if l.get('bloqueada'))
    revogadas = sum(1 for l in licencas if l['status'] == 'revogada')
    total_acessos = sum(l.get('total_acessos', 0) for l in licencas)
    
    return jsonify({
        'total_licencas': total,
        'ativas': ativas,
        'bloqueadas': bloqueadas,
        'revogadas': revogadas,
        'total_acessos': total_acessos
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🌐 SERVIDOR DE VALIDAÇÃO DE LICENÇAS ONLINE")
    print("=" * 60)
    print("\nEndpoints Públicos:")
    print("  POST /api/validar - Validar licença (cliente)")
    print("\nEndpoints Admin (requer senha):")
    print("  POST /api/admin/adicionar - Adicionar licença")
    print("  POST /api/admin/bloquear - Bloquear licença")
    print("  POST /api/admin/desbloquear - Desbloquear licença")
    print("  GET /api/admin/listar - Listar todas")
    print("  GET /api/admin/estatisticas - Estatísticas")
    print("\n⚠️  IMPORTANTE: Mude a senha em ADMIN_PASSWORD!")
    print("=" * 60)
    
    # Em produção, use Gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:5000 servidor_licencas_online:app
    
    app.run(host='0.0.0.0', port=5000, debug=False)
