# 🚀 GUIA DE IMPLEMENTAÇÃO - SISTEMA DE LICENCIAMENTO V3.0

## 📋 VISÃO GERAL

Sistema profissional de validação de licenças com:
- ✅ **Proteção Anti-Clonagem:** 1 licença = 1 PC
- ✅ **Modo Híbrido:** Online/Offline automático
- ✅ **Cache Criptografado:** Fernet (AES 128-bit) + HMAC
- ✅ **Grace Period:** 90 dias offline
- ✅ **Auditoria Completa:** Logs de todas as operações

---

## 🏗️ ARQUITETURA

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENTE (PDV)                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  license_validator.py                            │  │
│  │  - Gera HWID único                               │  │
│  │  - Valida online (timeout 5s)                    │  │
│  │  - Usa cache criptografado se offline           │  │
│  │  - Grace period 90 dias                          │  │
│  └──────────────────────────────────────────────────┘  │
│                         ↕                               │
│              (HTTPS - Timeout 5s)                       │
│                         ↕                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │  .license_cache (criptografado)                  │  │
│  │  - Fernet AES 128-bit                            │  │
│  │  - Assinatura HMAC SHA256                        │  │
│  │  - Timestamp de cache                            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         ↕
┌─────────────────────────────────────────────────────────┐
│              SERVIDOR (Render.com)                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │  servidor_licencas_v3.py                         │  │
│  │  - API REST (Flask)                              │  │
│  │  - Proteção anti-clonagem                        │  │
│  │  - Vinculação HWID                               │  │
│  │  - Bloqueio automático                           │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  licenses.db (SQLite)                            │  │
│  │  - Tabela licenses                               │  │
│  │  - Tabela validation_logs                        │  │
│  │  - Tabela hwid_changes                           │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         ↕
┌─────────────────────────────────────────────────────────┐
│              GERADOR (Seu PC)                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │  gerador_licencas_v3.py                          │  │
│  │  - Interface gráfica (Tkinter)                   │  │
│  │  - Gerar novas licenças                          │  │
│  │  - Desbloquear licenças                          │  │
│  │  - Desvincular HWID                              │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 PASSO 1: DEPLOY DO SERVIDOR NO RENDER

### **1.1. Preparar Arquivos**

Crie uma pasta separada para o servidor:

```bash
mkdir servidor_licencas
cd servidor_licencas
```

Copie os arquivos:
- `servidor_licencas_v3.py`
- `requirements.txt`

### **1.2. Criar `requirements.txt` para o servidor:**

```txt
Flask==3.0.0
Flask-Cors==4.0.0
gunicorn==21.2.0
```

### **1.3. Deploy no Render**

1. Acesse: https://render.com
2. Clique em "New +" → "Web Service"
3. Conecte seu repositório GitHub ou faça upload manual
4. Configurações:
   - **Name:** `validador-licencas-v3`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn servidor_licencas_v3:app`
   - **Instance Type:** `Free`

5. **Variáveis de Ambiente:**
   - `API_KEY`: `sua-chave-api-secreta-aqui-min-32-chars`
   - `ADMIN_PASSWORD`: `Alicia2705@#@`

6. Clique em "Create Web Service"

7. Aguarde o deploy (5-10 minutos)

8. Anote a URL: `https://validador-licencas-v3.onrender.com`

### **1.4. Testar o Servidor**

```bash
curl https://validador-licencas-v3.onrender.com/health
```

Deve retornar:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-20T..."
}
```

---

## 🔧 PASSO 2: CONFIGURAR O CLIENTE (PDV)

### **2.1. Instalar Dependências**

```bash
pip install cryptography requests
```

### **2.2. Integrar no Sistema**

Edite `Criativa/app.py` e adicione no início do arquivo:

```python
from license_validator import LicenseValidator

# Configuração do validador de licença
LICENSE_VALIDATOR = LicenseValidator(
    api_url='https://validador-licencas-v3.onrender.com',
    api_key='sua-chave-api-secreta-aqui-min-32-chars',
    secret_key='min-32-caracteres-aleatorios-complexos-para-seguranca'
)
```

### **2.3. Atualizar Middleware de Validação**

Substitua o middleware atual por:

```python
@app.before_request
def verificar_licenca_middleware():
    """Verifica a licença antes de cada requisição"""
    # Rotas públicas
    rotas_publicas = ['/login', '/static', '/assets', '/licenca_expirada', '/renovar_licenca']
    
    if any(request.path.startswith(rota) for rota in rotas_publicas):
        return None
    
    if not session.get('usuario_id'):
        return None
    
    # FECHAMENTO AUTOMÁTICO DE CAIXA (mantém o código existente)
    # ... código do fechamento automático ...
    
    # VALIDAÇÃO DE LICENÇA V3
    try:
        from database import obter_licenca
        licenca = obter_licenca()
        license_key = licenca.get('license_key', '')
        
        if not license_key or license_key.strip() == '':
            return redirect(url_for('licenca_expirada'))
        
        # Valida com o novo sistema
        is_valid, status = LICENSE_VALIDATOR.validate(license_key)
        
        if not is_valid:
            print(f"❌ Licença inválida: {status.get('message')}")
            return redirect(url_for('licenca_expirada'))
        
        # Licença válida!
        if status.get('status') == 'offline':
            print(f"⚠️  Modo offline: {status.get('days_remaining_offline')} dias restantes")
        
    except Exception as e:
        print(f'Erro ao verificar licença: {e}')
        return redirect(url_for('licenca_expirada'))
    
    return None
```

---

## 🎮 PASSO 3: CONFIGURAR O GERADOR

### **3.1. Editar Configurações**

Abra `gerador_licencas_v3.py` e edite:

```python
# Linha 16-18
self.api_url = "https://validador-licencas-v3.onrender.com"
self.api_key = "sua-chave-api-secreta-aqui-min-32-chars"
self.admin_password = "Alicia2705@#@"
```

### **3.2. Executar o Gerador**

```bash
python gerador_licencas_v3.py
```

---

## 🧪 PASSO 4: TESTAR O SISTEMA

### **Teste 1: Gerar Licença**

1. Abra o gerador
2. Clique em "Gerar Nova Licença"
3. Preencha:
   - **Cliente:** Gráfica Teste
   - **HWID:** `1234-5678-9ABC-DEF0` (teste)
   - **Duração:** 365 dias
   - **Plano:** standard
4. Clique em "Criar Licença"
5. Anote a chave gerada: `XXXX-XXXX-XXXX-XXXX`

### **Teste 2: Validar no Cliente**

```bash
cd Criativa
python license_validator.py
```

Digite a chave quando solicitado.

Deve retornar:
```
✅ LICENÇA VÁLIDA!
   Mensagem: Licença válida
   Status: active
   Expira em: 2026-11-20
```

### **Teste 3: Modo Offline**

1. Desconecte a internet
2. Execute novamente: `python license_validator.py`
3. Deve usar o cache:
```
✅ LICENÇA VÁLIDA!
   Mensagem: Licença válida (modo offline - 90 dias restantes)
   Status: offline
```

### **Teste 4: Proteção Anti-Clonagem**

1. Copie o sistema para outro PC (ou simule com HWID diferente)
2. Tente validar a mesma licença
3. Deve bloquear:
```
❌ LICENÇA INVÁLIDA!
   Mensagem: Licença bloqueada: detectado uso em múltiplos PCs
   Status: blocked_multiple_pc
```

---

## 🔒 SEGURANÇA

### **Chaves Secretas**

Gere chaves aleatórias fortes:

```python
import secrets
print("API_KEY:", secrets.token_urlsafe(32))
print("SECRET_KEY:", secrets.token_urlsafe(32))
```

### **Proteções Implementadas**

1. ✅ **Cache Criptografado:** Fernet AES 128-bit
2. ✅ **Assinatura HMAC:** SHA256 para integridade
3. ✅ **HWID Binding:** Vinculação ao hardware
4. ✅ **Bloqueio Automático:** Detecta uso múltiplo
5. ✅ **Timeout:** 5 segundos para não travar
6. ✅ **Grace Period:** 90 dias offline
7. ✅ **Auditoria:** Logs completos

---

## 📊 CENÁRIOS DE USO

### **Cenário 1: Cliente Normal**

```
Dia 1: Ativa licença → Valida online → Cache salvo
Dia 2: Usa sistema → Valida online (1h) → Atualiza cache
Dia 3: Sem internet → Usa cache → Modo offline (89 dias restantes)
Dia 4: Internet volta → Valida online → Renova grace period
```

### **Cenário 2: Tentativa de Pirataria**

```
PC 1: Usa licença → HWID vinculado: ABC123
PC 2: Tenta usar mesma licença → HWID diferente: XYZ789
Servidor: Detecta HWID != ABC123 → BLOQUEIA licença
PC 1: Próxima validação → Bloqueado
PC 2: Bloqueado
```

### **Cenário 3: Troca Legítima de PC**

```
Cliente: Comprou PC novo
Admin: Abre gerador → Desvincular HWID
Servidor: bound_hwid = NULL
Cliente: Usa no PC novo → HWID vinculado ao novo PC
```

---

## 🛠️ MANUTENÇÃO

### **Ver Logs do Servidor**

No Render:
1. Dashboard → Seu serviço
2. Aba "Logs"
3. Veja validações em tempo real

### **Backup do Banco**

```bash
# No servidor Render (via SSH ou download)
sqlite3 licenses.db .dump > backup.sql
```

### **Limpar Cache do Cliente**

```python
from license_validator import LicenseValidator

validator = LicenseValidator(api_url, api_key, secret_key)
validator.clear_cache()
```

---

## 📈 MONITORAMENTO

### **Endpoints Úteis**

```bash
# Health check
curl https://seu-servidor.onrender.com/health

# Listar licenças (requer admin)
curl -H "X-API-Key: sua-chave" \
     -H "X-Admin-Password: senha" \
     https://seu-servidor.onrender.com/api/licenses

# Ver licença específica
curl -H "X-API-Key: sua-chave" \
     -H "X-Admin-Password: senha" \
     https://seu-servidor.onrender.com/api/licenses/XXXX-XXXX-XXXX-XXXX
```

---

## ✅ CHECKLIST FINAL

- [ ] Servidor deployado no Render
- [ ] Variáveis de ambiente configuradas
- [ ] Health check funcionando
- [ ] Gerador de licenças configurado
- [ ] Cliente (PDV) integrado
- [ ] Teste de validação online OK
- [ ] Teste de modo offline OK
- [ ] Teste de proteção anti-clonagem OK
- [ ] Backup do banco configurado
- [ ] Documentação atualizada

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ Deploy do servidor
2. ✅ Gerar primeira licença
3. ✅ Testar validação
4. ✅ Integrar no sistema PDV
5. ✅ Distribuir para clientes

---

**Sistema pronto para produção!** 🚀✅🔒
