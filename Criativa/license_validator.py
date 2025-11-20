"""
VALIDADOR DE LICENÇA - CLIENTE PDV
Sistema híbrido online/offline com cache criptografado
Proteção anti-clonagem e grace period de 30 dias
"""

import os
import json
import hashlib
import hmac
import subprocess
import requests
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import base64

class LicenseValidator:
    """Validador de licença com modo híbrido online/offline"""
    
    # Configurações
    ONLINE_CHECK_INTERVAL = 3600  # 1 hora em segundos
    GRACE_PERIOD_DAYS = 90        # 90 dias offline permitidos
    REQUEST_TIMEOUT = 5           # 5 segundos timeout
    
    def __init__(self, api_url, api_key, secret_key):
        """
        Inicializa o validador
        
        Args:
            api_url: URL da API de validação (ex: https://seu-servidor.onrender.com)
            api_key: Chave de API para autenticação
            secret_key: Chave secreta para criptografia do cache (min 32 chars)
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.secret_key = secret_key
        
        # Gera chave de criptografia a partir da secret_key
        key_material = hashlib.sha256(secret_key.encode()).digest()
        self.cipher_key = base64.urlsafe_b64encode(key_material)
        self.cipher = Fernet(self.cipher_key)
        
        # Caminho do cache
        self.cache_file = os.path.join(
            os.path.dirname(__file__),
            '.license_cache'
        )
    
    def get_hwid(self):
        """
        Gera HWID único do hardware
        
        Returns:
            str: HWID no formato XXXX-XXXX-XXXX-XXXX
        """
        try:
            # Windows: usa UUID da máquina
            if os.name == 'nt':
                output = subprocess.check_output(
                    'wmic csproduct get uuid',
                    shell=True,
                    stderr=subprocess.DEVNULL
                )
                uuid = output.decode().split('\n')[1].strip()
            else:
                # Linux/Mac: usa machine-id
                with open('/etc/machine-id', 'r') as f:
                    uuid = f.read().strip()
            
            # Gera hash do UUID
            hwid = hashlib.md5(uuid.encode()).hexdigest()[:16].upper()
            
            # Formata como XXXX-XXXX-XXXX-XXXX
            hwid_formatted = '-'.join([hwid[i:i+4] for i in range(0, 16, 4)])
            
            return hwid_formatted
        
        except Exception as e:
            print(f"Erro ao gerar HWID: {e}")
            # Fallback: usa nome da máquina
            import platform
            machine_name = platform.node()
            hwid = hashlib.md5(machine_name.encode()).hexdigest()[:16].upper()
            return '-'.join([hwid[i:i+4] for i in range(0, 16, 4)])
    
    def validate(self, license_key):
        """
        Valida a licença (método principal)
        
        Args:
            license_key: Chave da licença no formato XXXX-XXXX-XXXX-XXXX
        
        Returns:
            tuple: (bool, dict) - (válida?, informações)
        """
        hwid = self.get_hwid()
        
        # Carrega cache local
        cache = self._load_cache()
        
        # Decide se deve validar online
        should_check_online = self._should_check_online(cache)
        
        if should_check_online:
            # Tenta validação online
            online_result = self._check_online(license_key, hwid)
            
            if online_result['success']:
                # Validação online bem-sucedida
                self._save_cache(license_key, online_result['data'])
                return (online_result['data']['valid'], online_result['data'])
            else:
                # Falha online - usa cache se disponível
                print(f"⚠️  Validação online falhou: {online_result.get('error', 'Timeout')}")
                print(f"   Usando cache local (modo offline)")
        
        # Usa cache local
        if cache:
            return self._validate_from_cache(cache, license_key, hwid)
        else:
            # Sem cache e sem conexão online
            return (False, {
                'valid': False,
                'message': 'Não foi possível validar a licença. Verifique sua conexão com a internet.',
                'status': 'no_cache_no_connection'
            })
    
    def _should_check_online(self, cache):
        """Decide se deve tentar validação online"""
        if not cache:
            return True  # Sem cache, obrigatório validar online
        
        cached_at = cache.get('cached_at', 0)
        now = datetime.now().timestamp()
        elapsed = now - cached_at
        
        # Verifica se passou do intervalo de check online
        return elapsed > self.ONLINE_CHECK_INTERVAL
    
    def _check_online(self, license_key, hwid):
        """
        Tenta validação online
        
        Returns:
            dict: {'success': bool, 'data': dict} ou {'success': False, 'error': str}
        """
        try:
            response = requests.post(
                f'{self.api_url}/api/validate',
                json={'license_key': license_key, 'hwid': hwid},
                headers={'X-API-Key': self.api_key},
                timeout=self.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                return {'success': True, 'data': data}
            else:
                error_data = response.json()
                return {'success': True, 'data': error_data}  # Retorna erro mas com sucesso na requisição
        
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Timeout'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Sem conexão'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _validate_from_cache(self, cache, license_key, hwid):
        """Valida usando cache local"""
        license_data = cache.get('license', {})
        cached_at = cache.get('cached_at', 0)
        
        # Verifica se a licença no cache é a mesma
        if license_data.get('license_key') != license_key:
            return (False, {
                'valid': False,
                'message': 'Licença diferente da armazenada em cache',
                'status': 'cache_mismatch'
            })
        
        # Verifica HWID
        if license_data.get('bound_hwid') and license_data.get('bound_hwid') != hwid:
            return (False, {
                'valid': False,
                'message': 'HWID não corresponde ao vinculado',
                'status': 'hwid_mismatch'
            })
        
        # Verifica grace period
        now = datetime.now().timestamp()
        days_offline = (now - cached_at) / 86400  # 86400 segundos = 1 dia
        
        if days_offline > self.GRACE_PERIOD_DAYS:
            return (False, {
                'valid': False,
                'message': f'Período offline expirado ({int(days_offline)} dias). Conecte à internet para validar.',
                'status': 'grace_period_expired',
                'days_offline': int(days_offline)
            })
        
        # Verifica se está bloqueada
        if license_data.get('status') in ['blocked_multiple_pc', 'revoked', 'expired']:
            return (False, {
                'valid': False,
                'message': license_data.get('message', 'Licença bloqueada ou expirada'),
                'status': license_data.get('status')
            })
        
        # Cache válido!
        days_remaining_offline = self.GRACE_PERIOD_DAYS - int(days_offline)
        
        return (True, {
            'valid': True,
            'message': f'Licença válida (modo offline - {days_remaining_offline} dias restantes)',
            'status': 'offline',
            'days_offline': int(days_offline),
            'days_remaining_offline': days_remaining_offline,
            'expires_at': license_data.get('expires_at'),
            'plan': license_data.get('plan'),
            'bound_hwid': license_data.get('bound_hwid')
        })
    
    def _load_cache(self):
        """Carrega e valida cache local"""
        if not os.path.exists(self.cache_file):
            return None
        
        try:
            with open(self.cache_file, 'rb') as f:
                encrypted_data = f.read()
            
            # Descriptografa
            decrypted_data = self.cipher.decrypt(encrypted_data)
            cache = json.loads(decrypted_data.decode())
            
            # Verifica assinatura HMAC
            stored_signature = cache.get('signature', '')
            cache_data = cache.get('data', {})
            
            calculated_signature = self._generate_signature(cache_data)
            
            if not hmac.compare_digest(stored_signature, calculated_signature):
                print("⚠️  Cache adulterado! Assinatura inválida.")
                return None
            
            return cache_data
        
        except Exception as e:
            print(f"Erro ao carregar cache: {e}")
            return None
    
    def _save_cache(self, license_key, data):
        """Salva cache criptografado"""
        try:
            cache_data = {
                'license': {
                    'license_key': license_key,
                    'valid': data.get('valid'),
                    'bound_hwid': data.get('bound_hwid'),
                    'plan': data.get('plan'),
                    'expires_at': data.get('expires_at'),
                    'status': data.get('status'),
                    'message': data.get('message')
                },
                'cached_at': datetime.now().timestamp()
            }
            
            # Gera assinatura HMAC
            signature = self._generate_signature(cache_data)
            
            cache = {
                'data': cache_data,
                'signature': signature
            }
            
            # Criptografa
            cache_json = json.dumps(cache).encode()
            encrypted_data = self.cipher.encrypt(cache_json)
            
            # Salva arquivo
            with open(self.cache_file, 'wb') as f:
                f.write(encrypted_data)
            
            print(f"✅ Cache salvo: {self.cache_file}")
        
        except Exception as e:
            print(f"Erro ao salvar cache: {e}")
    
    def _generate_signature(self, data):
        """Gera assinatura HMAC dos dados"""
        data_json = json.dumps(data, sort_keys=True).encode()
        signature = hmac.new(
            self.secret_key.encode(),
            data_json,
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def clear_cache(self):
        """Limpa o cache local"""
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
            print("✅ Cache limpo")


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

if __name__ == '__main__':
    # Configuração
    API_URL = 'https://validador-i16f.onrender.com'
    API_KEY = 'sua-chave-api-aqui'
    SECRET_KEY = 'min-32-caracteres-aleatorios-complexos-para-seguranca'
    
    # Cria validador
    validator = LicenseValidator(API_URL, API_KEY, SECRET_KEY)
    
    # Obtém HWID
    hwid = validator.get_hwid()
    print(f"HWID deste PC: {hwid}")
    
    # Valida licença
    license_key = input("Digite a chave de licença: ").strip()
    
    is_valid, status = validator.validate(license_key)
    
    print("\n" + "="*60)
    if is_valid:
        print("✅ LICENÇA VÁLIDA!")
        print(f"   Mensagem: {status.get('message')}")
        print(f"   Status: {status.get('status')}")
        if status.get('expires_at'):
            print(f"   Expira em: {status.get('expires_at')}")
        if status.get('days_remaining_offline'):
            print(f"   Dias offline restantes: {status.get('days_remaining_offline')}")
    else:
        print("❌ LICENÇA INVÁLIDA!")
        print(f"   Mensagem: {status.get('message')}")
        print(f"   Status: {status.get('status')}")
    print("="*60)
