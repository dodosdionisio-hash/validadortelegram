"""
GERADOR DE LICENÇAS V3.0 - MELHORADO
Interface gráfica para gerenciar licenças no servidor
Com melhor tratamento de erros e configuração
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import random
import string
from datetime import datetime
import json
import os

class ConfigDialog(tk.Toplevel):
    """Dialog para configurar URL e credenciais"""
    def __init__(self, parent, current_config):
        super().__init__(parent)
        self.title("Configurações do Servidor")
        self.geometry("500x300")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        
        # Frame principal
        main_frame = tk.Frame(self, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL da API
        tk.Label(main_frame, text="URL do Servidor:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.url_entry = tk.Entry(main_frame, font=("Segoe UI", 10), width=50)
        self.url_entry.pack(pady=(0, 15))
        self.url_entry.insert(0, current_config.get('api_url', ''))
        
        # API Key
        tk.Label(main_frame, text="API Key:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.api_key_entry = tk.Entry(main_frame, font=("Segoe UI", 10), width=50)
        self.api_key_entry.pack(pady=(0, 15))
        self.api_key_entry.insert(0, current_config.get('api_key', ''))
        
        # Admin Password
        tk.Label(main_frame, text="Senha Admin:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.password_entry = tk.Entry(main_frame, font=("Segoe UI", 10), width=50, show="*")
        self.password_entry.pack(pady=(0, 20))
        self.password_entry.insert(0, current_config.get('admin_password', ''))
        
        # Botões
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack()
        
        tk.Button(
            btn_frame,
            text="Salvar",
            command=self.save,
            bg="#16a34a",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=30,
            pady=10,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="Cancelar",
            command=self.destroy,
            bg="#6b7280",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=30,
            pady=10,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
    
    def save(self):
        """Salva configurações"""
        self.result = {
            'api_url': self.url_entry.get().strip(),
            'api_key': self.api_key_entry.get().strip(),
            'admin_password': self.password_entry.get().strip()
        }
        self.destroy()

class LicenseGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Licenças V3.0 - Sistema PDV")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        
        # Arquivo de configuração
        self.config_file = "gerador_config.json"
        
        # Carrega configurações
        self.load_config()
        
        self.setup_ui()
        
        # Tenta carregar licenças (mas não bloqueia se falhar)
        self.root.after(100, self.load_licenses_safe)
    
    def load_config(self):
        """Carrega configurações do arquivo"""
        default_config = {
            'api_url': 'https://validador-i16f.onrender.com',
            'api_key': 'sua-chave-api-aqui',
            'admin_password': 'Alicia2705@#@'
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.api_url = config.get('api_url', default_config['api_url'])
                    self.api_key = config.get('api_key', default_config['api_key'])
                    self.admin_password = config.get('admin_password', default_config['admin_password'])
            except:
                self.api_url = default_config['api_url']
                self.api_key = default_config['api_key']
                self.admin_password = default_config['admin_password']
        else:
            self.api_url = default_config['api_url']
            self.api_key = default_config['api_key']
            self.admin_password = default_config['admin_password']
    
    def save_config(self):
        """Salva configurações no arquivo"""
        config = {
            'api_url': self.api_url,
            'api_key': self.api_key,
            'admin_password': self.admin_password
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Erro ao salvar config: {e}")
    
    def setup_ui(self):
        """Configura a interface"""
        # Título
        title_frame = tk.Frame(self.root, bg="#2563eb", height=80)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        tk.Label(
            title_frame,
            text="🔑 Gerador de Licenças V3.0",
            font=("Segoe UI", 20, "bold"),
            bg="#2563eb",
            fg="white"
        ).pack(pady=20)
        
        # Frame principal
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Botões de ação
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Button(
            btn_frame,
            text="➕ Gerar Nova Licença",
            command=self.generate_license,
            bg="#16a34a",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=10,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="🔓 Desbloquear Licença",
            command=self.unblock_license,
            bg="#f59e0b",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=10,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="🔗 Desvincular HWID",
            command=self.unbind_license,
            bg="#8b5cf6",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=10,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="🔄 Atualizar Lista",
            command=self.load_licenses,
            bg="#3b82f6",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=10,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="⚙️ Configurações",
            command=self.open_config,
            bg="#6b7280",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=10,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)
        
        # Tabela de licenças
        table_frame = tk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview
        self.tree = ttk.Treeview(
            table_frame,
            columns=("Chave", "Cliente", "HWID", "Status", "Expira", "Último Check"),
            show="headings",
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.tree.yview)
        
        # Colunas
        self.tree.heading("Chave", text="Chave de Licença")
        self.tree.heading("Cliente", text="Cliente")
        self.tree.heading("HWID", text="HWID Vinculado")
        self.tree.heading("Status", text="Status")
        self.tree.heading("Expira", text="Expira em")
        self.tree.heading("Último Check", text="Último Check")
        
        self.tree.column("Chave", width=150)
        self.tree.column("Cliente", width=150)
        self.tree.column("HWID", width=150)
        self.tree.column("Status", width=120)
        self.tree.column("Expira", width=100)
        self.tree.column("Último Check", width=150)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_label = tk.Label(
            self.root,
            text=f"Servidor: {self.api_url}",
            bg="#f3f4f6",
            anchor=tk.W,
            padx=10,
            pady=5,
            font=("Segoe UI", 9)
        )
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM)
    
    def open_config(self):
        """Abre dialog de configurações"""
        dialog = ConfigDialog(self.root, {
            'api_url': self.api_url,
            'api_key': self.api_key,
            'admin_password': self.admin_password
        })
        self.root.wait_window(dialog)
        
        if dialog.result:
            self.api_url = dialog.result['api_url']
            self.api_key = dialog.result['api_key']
            self.admin_password = dialog.result['admin_password']
            self.save_config()
            self.status_label.config(text=f"Servidor: {self.api_url}")
            messagebox.showinfo("Sucesso", "Configurações salvas!")
    
    def generate_license(self):
        """Gera uma nova licença"""
        # Dialog para dados
        dialog = tk.Toplevel(self.root)
        dialog.title("Gerar Nova Licença")
        dialog.geometry("400x350")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Campos
        tk.Label(dialog, text="Nome do Cliente:", font=("Segoe UI", 10)).pack(pady=(20, 5))
        client_entry = tk.Entry(dialog, font=("Segoe UI", 10), width=40)
        client_entry.pack(pady=5)
        
        tk.Label(dialog, text="HWID do Cliente:", font=("Segoe UI", 10)).pack(pady=(10, 5))
        hwid_entry = tk.Entry(dialog, font=("Segoe UI", 10), width=40)
        hwid_entry.pack(pady=5)
        hwid_entry.insert(0, "XXXX-XXXX-XXXX-XXXX")
        
        tk.Label(dialog, text="Duração (dias):", font=("Segoe UI", 10)).pack(pady=(10, 5))
        duration_entry = tk.Entry(dialog, font=("Segoe UI", 10), width=40)
        duration_entry.pack(pady=5)
        duration_entry.insert(0, "365")
        
        tk.Label(dialog, text="Plano:", font=("Segoe UI", 10)).pack(pady=(10, 5))
        plan_var = tk.StringVar(value="standard")
        plan_combo = ttk.Combobox(dialog, textvariable=plan_var, values=["standard", "premium", "enterprise"], state="readonly", width=37)
        plan_combo.pack(pady=5)
        
        def create():
            client_name = client_entry.get().strip()
            hwid = hwid_entry.get().strip()
            duration = duration_entry.get().strip()
            plan = plan_var.get()
            
            if not client_name or not hwid:
                messagebox.showerror("Erro", "Preencha todos os campos!")
                return
            
            try:
                duration_days = int(duration)
            except:
                messagebox.showerror("Erro", "Duração inválida!")
                return
            
            # Gera chave aleatória
            license_key = self._generate_key()
            
            # Cria no servidor
            try:
                response = requests.post(
                    f"{self.api_url}/api/licenses/create",
                    json={
                        "license_key": license_key,
                        "hwid": hwid,
                        "client_name": client_name,
                        "duration_days": duration_days,
                        "plan": plan
                    },
                    headers={
                        "X-API-Key": self.api_key,
                        "X-Admin-Password": self.admin_password
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    messagebox.showinfo(
                        "Sucesso",
                        f"Licença criada com sucesso!\n\n"
                        f"Chave: {license_key}\n"
                        f"Cliente: {client_name}\n"
                        f"HWID: {hwid}\n"
                        f"Expira em: {data['expires_at'][:10]}"
                    )
                    dialog.destroy()
                    self.load_licenses()
                else:
                    error = response.json().get('error', 'Erro desconhecido')
                    messagebox.showerror("Erro", f"Falha ao criar licença:\n{error}")
            
            except requests.exceptions.Timeout:
                messagebox.showerror("Erro", "Timeout ao conectar com servidor.\nVerifique a URL nas configurações.")
            except requests.exceptions.ConnectionError:
                messagebox.showerror("Erro", "Não foi possível conectar ao servidor.\nVerifique:\n- URL está correta\n- Servidor está online\n- Conexão com internet")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao conectar com servidor:\n{str(e)}")
        
        tk.Button(
            dialog,
            text="Criar Licença",
            command=create,
            bg="#16a34a",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=10,
            cursor="hand2"
        ).pack(pady=20)
    
    def unblock_license(self):
        """Desbloqueia uma licença"""
        license_key = simpledialog.askstring("Desbloquear Licença", "Digite a chave da licença:")
        if not license_key:
            return
        
        try:
            response = requests.post(
                f"{self.api_url}/api/licenses/unblock/{license_key}",
                headers={
                    "X-API-Key": self.api_key,
                    "X-Admin-Password": self.admin_password
                },
                timeout=30
            )
            
            if response.status_code == 200:
                messagebox.showinfo("Sucesso", "Licença desbloqueada com sucesso!")
                self.load_licenses()
            else:
                error = response.json().get('error', 'Erro desconhecido')
                messagebox.showerror("Erro", f"Falha ao desbloquear:\n{error}")
        
        except requests.exceptions.Timeout:
            messagebox.showerror("Erro", "Timeout ao conectar com servidor.")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Erro", "Não foi possível conectar ao servidor.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao conectar com servidor:\n{str(e)}")
    
    def unbind_license(self):
        """Desvincula HWID de uma licença"""
        license_key = simpledialog.askstring("Desvincular HWID", "Digite a chave da licença:")
        if not license_key:
            return
        
        confirm = messagebox.askyesno(
            "Confirmar",
            "Isso permitirá que a licença seja usada em outro PC.\nDeseja continuar?"
        )
        if not confirm:
            return
        
        try:
            response = requests.post(
                f"{self.api_url}/api/licenses/unbind/{license_key}",
                headers={
                    "X-API-Key": self.api_key,
                    "X-Admin-Password": self.admin_password
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                messagebox.showinfo("Sucesso", f"HWID desvinculado!\n\nHWID anterior: {data.get('old_hwid')}")
                self.load_licenses()
            else:
                error = response.json().get('error', 'Erro desconhecido')
                messagebox.showerror("Erro", f"Falha ao desvincular:\n{error}")
        
        except requests.exceptions.Timeout:
            messagebox.showerror("Erro", "Timeout ao conectar com servidor.")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Erro", "Não foi possível conectar ao servidor.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao conectar com servidor:\n{str(e)}")
    
    def load_licenses_safe(self):
        """Carrega licenças sem bloquear a interface"""
        try:
            self.load_licenses()
        except:
            self.status_label.config(text=f"⚠️ Servidor offline - {self.api_url}")
    
    def load_licenses(self):
        """Carrega lista de licenças"""
        self.status_label.config(text="Carregando licenças...")
        self.root.update()
        
        try:
            response = requests.get(
                f"{self.api_url}/api/licenses",
                headers={
                    "X-API-Key": self.api_key,
                    "X-Admin-Password": self.admin_password
                },
                timeout=30
            )
            
            if response.status_code == 200:
                licenses = response.json()
                
                # Limpa tabela
                for item in self.tree.get_children():
                    self.tree.delete(item)
                
                # Preenche tabela
                for lic in licenses:
                    self.tree.insert("", "end", values=(
                        lic['license_key'],
                        lic.get('client_name', 'N/A'),
                        lic.get('bound_hwid', 'Não vinculado'),
                        lic['status'],
                        lic['expires_at'][:10] if lic.get('expires_at') else 'N/A',
                        lic.get('last_check', 'Nunca')[:19] if lic.get('last_check') else 'Nunca'
                    ))
                
                self.status_label.config(text=f"✅ {len(licenses)} licença(s) carregada(s) - {self.api_url}")
            else:
                self.status_label.config(text=f"❌ Erro ao carregar licenças - {self.api_url}")
        
        except requests.exceptions.Timeout:
            self.status_label.config(text=f"⚠️ Timeout - Servidor não responde - {self.api_url}")
            messagebox.showwarning(
                "Timeout",
                "Não foi possível conectar ao servidor.\n\n"
                "Verifique:\n"
                "1. URL está correta (Configurações)\n"
                "2. Servidor está online\n"
                "3. Conexão com internet"
            )
        except requests.exceptions.ConnectionError:
            self.status_label.config(text=f"⚠️ Servidor offline - {self.api_url}")
            messagebox.showwarning(
                "Servidor Offline",
                "Não foi possível conectar ao servidor.\n\n"
                "Verifique:\n"
                "1. URL nas Configurações\n"
                "2. Servidor está deployado no Render\n"
                "3. Conexão com internet"
            )
        except Exception as e:
            self.status_label.config(text=f"❌ Erro: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao conectar com servidor:\n{str(e)}")
    
    def _generate_key(self):
        """Gera chave aleatória"""
        chars = string.ascii_uppercase + string.digits
        parts = []
        for _ in range(4):
            part = ''.join(random.choice(chars) for _ in range(4))
            parts.append(part)
        return '-'.join(parts)


if __name__ == '__main__':
    root = tk.Tk()
    app = LicenseGeneratorGUI(root)
    root.mainloop()
