import sys
import socket
import threading
import time
from datetime import datetime

# Configuration par défaut
MASTER_IP = "127.0.0.1"
MASTER_PORT = 6000  # Port par défaut


class ChatClient:
    """Gestion de la connexion et communication avec le Master"""
    
    def __init__(self):
        self.username = None
        self.ip = "127.0.0.1"  # IP par défaut
        self.port = None
        self.public_key = None
        self.master_socket = None
        self.running = False
        self.gui_mode = False
        self.master_ip = MASTER_IP  # IP du Master
        self.master_port = MASTER_PORT  # Port du Master
        
    def register(self, username=None, ip=None, port=None, master_ip=None, master_port=None):
        """Inscription avec le Master"""
        if not username or not ip or not port:
            # Mode CLI - Demander les infos
            print("\n", "="*60)
            print("CLIENT REGISTRATION")
            print("="*60)
            
            self.username = input("Enter your username: ")
            
            # Demander l'IP du client
            while True:
                ip_input = input("Enter your IP address (default: 127.0.0.1): ").strip()
                if ip_input == "":
                    self.ip = "127.0.0.1"
                    break
                elif self.validate_ip(ip_input):
                    self.ip = ip_input
                    break
                else:
                    print("X Invalid IP address format. Please use IPv4 format (e.g., 127.0.0.1)")
            
            # Demander le port
            while True:
                try:
                    port_input = input("Enter your listening port (7001, 7002, ...): ")
                    self.port = int(port_input)
                    
                    # Vérifier si le port est disponible
                    try:
                        test_sock = socket.socket()
                        test_sock.bind((self.ip, self.port))
                        test_sock.close()
                        break
                    except OSError:
                        print(f"X Port {self.port} is already in use on {self.ip}. Please choose another.")
                        
                except ValueError:
                    print("X Please enter a valid number.")
            
            # Demander l'IP du Master
            while True:
                master_ip_input = input(f"Enter Master server IP (default: {MASTER_IP}): ").strip()
                if master_ip_input == "":
                    self.master_ip = MASTER_IP
                    break
                elif self.validate_ip(master_ip_input):
                    self.master_ip = master_ip_input
                    break
                else:
                    print("X Invalid IP address format. Please use IPv4 format (e.g., 127.0.0.1)")
            
            # Demander le PORT du Master
            while True:
                master_port_input = input(f"Enter Master server port (default: {MASTER_PORT}): ").strip()
                if master_port_input == "":
                    self.master_port = MASTER_PORT
                    break
                try:
                    port_num = int(master_port_input)
                    if 1 <= port_num <= 65535:
                        self.master_port = port_num
                        break
                    else:
                        print("X Port must be between 1 and 65535")
                except ValueError:
                    print("X Please enter a valid number")
        else:
            # Mode GUI - Utiliser les paramètres fournis
            self.username = username
            self.ip = ip
            self.port = port
            if master_ip:
                self.master_ip = master_ip
            if master_port:
                self.master_port = master_port
        
        if not self.gui_mode:
            print(f"\nConnecting to master at {self.master_ip}:{self.master_port}...")
        
        try:
            # Connexion au Master
            self.master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.master_socket.settimeout(10.0)
            self.master_socket.connect((self.master_ip, self.master_port))
            
            # Identifier en tant que Client
            self.master_socket.send(b"CLIENT")
            time.sleep(0.1)
            
            # Envoyer les données d'inscription
            reg_data = f"{self.username}::{self.ip}::{self.port}"
            self.master_socket.send(reg_data.encode())
            
            # Réponse du Master
            response = self.master_socket.recv(1024).decode()
            
            if response.startswith("OK:"):
                _, e_str, n_str = response.split(":")
                self.public_key = (int(e_str), int(n_str))
                self.master_socket.settimeout(None)
                
                if not self.gui_mode:
                    print(f"\nSuccessfully registered as '{self.username}'")
                    print(f"   IP: {self.ip}")
                    print(f"   Listening on port: {self.port}")
                    print(f"   Master server: {self.master_ip}:{self.master_port}")
                    print(f"   Public key: ({e_str[:10]}..., {n_str[:10]}...)")
                
                return True, "Connexion réussie"
            else:
                error_msg = f"X Registration failed: {response}"
                if not self.gui_mode:
                    print(f"\n{error_msg}")
                return False, error_msg
                
        except ConnectionRefusedError:
            error_msg = f"\nX Cannot connect to master server at {self.master_ip}:{self.master_port}.\n   Make sure master.py is running"
            if not self.gui_mode:
                print(error_msg)
            return False, "Impossible de se connecter au serveur Master"
        except socket.timeout:
            error_msg = f"\nX Connection timeout to {self.master_ip}:{self.master_port}.\n   Master server is not responding"
            if not self.gui_mode:
                print(error_msg)
            return False, "Délai de connexion dépassé"
        except Exception as e:
            error_msg = f"\nX Registration error: {type(e).__name__}: {e}"
            if not self.gui_mode:
                print(error_msg)
            return False, f"Erreur: {e}"
    
    def validate_ip(self, ip):
        """Valide une adresse IPv4"""
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False
    
    def get_online_users(self):
        """Liste des utilisateurs en ligne"""
        try:
            self.master_socket.send(b"LIST")
            response = self.master_socket.recv(1024).decode()
            
            if response.startswith("ONLINE:"):
                users = response[7:].split(",")
                # Filtrer les chaînes vides et soi-même
                return [u for u in users if u and u != self.username]
            return []
        except:
            return []
    
    def get_user_info(self, username):
        """Récupère les informations d'un utilisateur"""
        try:
            self.master_socket.send(f"GET:{username}".encode())
            response = self.master_socket.recv(1024).decode()
            
            if response.startswith("USER:"):
                parts = response[5:].split(":")
                if len(parts) >= 4:
                    return {
                        "ip": parts[0],
                        "port": int(parts[1]),
                        "public_key": (int(parts[2]), int(parts[3]))
                    }
            return None
        except:
            return None
    
    def request_path(self, target_user, nb_layers):
        """Demande d'un chemin de routage"""
        try:
            request = f"PATH:{self.username}:{nb_layers}:{target_user}"
            self.master_socket.send(request.encode())
            
            response = self.master_socket.recv(4096).decode()
            
            if response.startswith("ERROR"):
                if not self.gui_mode:
                    print(f"   X Path error: {response}")
                return None, None
            
            if "||" not in response:
                if not self.gui_mode:
                    print("   X Invalid response format")
                return None, None
            
            path_part, target_part = response.split("||", 1)
            
            routers = []
            for hop in path_part.split("|"):
                if hop:
                    ip, port, e, n = hop.split(";")
                    routers.append({
                        "ip": ip,
                        "port": int(port),
                        "pub_key": (int(e), int(n))
                    })
            
            target_ip, target_port = target_part.split(";")
            target_info = {"ip": target_ip, "port": int(target_port)}
            
            return routers, target_info
            
        except Exception as e:
            if not self.gui_mode:
                print(f"   X Path request error: {e}")
            return None, None
    
    def encrypt_message(self, message, pub_key):
        """Chiffrement RSA"""
        e, n = pub_key
        encrypted = []
        for char in message:
            try:
                encrypted.append(pow(ord(char), e, n))
            except:
                encrypted.append(ord(char) % n)
        return encrypted
    
    def build_onion(self, message, routers, target_info):
        """Construction du chiffrement oignon"""
        current = message
        
        for i in range(len(routers)-1, -1, -1):
            router = routers[i]
            
            if i == len(routers)-1:
                next_hop = f"{target_info['ip']};{target_info['port']}"
            else:
                next_router = routers[i+1]
                next_hop = f"{next_router['ip']};{next_router['port']}"
            
            layer = f"{next_hop}|{current}"
            encrypted = self.encrypt_message(layer, router['pub_key'])
            current = ",".join(str(x) for x in encrypted)
        
        return current
    
    def send_message(self, target_user, message, nb_layers=1):
        """Envoi d'un message"""
        if not self.gui_mode:
            print(f"\nPreparing message for '{target_user}'...")
            print(f"   Looking up '{target_user}'...")
        
        user_info = self.get_user_info(target_user)
        
        if not user_info:
            error_msg = f"Utilisateur '{target_user}' introuvable"
            if not self.gui_mode:
                print(f"   X {error_msg}")
            return False, error_msg
        
        # En mode CLI, demander le nombre de couches
        if not self.gui_mode:
            while True:
                try:
                    nb_layers_input = input(f"   Number of router layers: ")
                    nb_layers = int(nb_layers_input)
                    if nb_layers > 0:
                        break
                    print("   /!\\ Please enter a positive number")
                except ValueError:
                    print("   /!\\ Please enter a valid number")
        
        if not self.gui_mode:
            print(f"   Requesting path from master...")
        
        routers, target_info = self.request_path(target_user, nb_layers)
        
        if not routers:
            error_msg = "Impossible d'obtenir un chemin"
            if not self.gui_mode:
                print(f"   X {error_msg}")
            return False, error_msg
        
        if not self.gui_mode:
            print(f"   Path obtained: {len(routers)} routers")
            print(f"   Building onion encryption...")
        
        complete_message = f"{self.username}:{message}"
        onion = self.build_onion(complete_message, routers, target_info)
        
        first_router = routers[0]
        
        if not self.gui_mode:
            print(f"   Sending to first router: {first_router['ip']}:{first_router['port']}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((first_router["ip"], first_router["port"]))
            sock.send(onion.encode())
            sock.close()
            
            success_msg = f"Message sent successfully via {len(routers)} routers!"
            if not self.gui_mode:
                print(f"   {success_msg}")
            
            return True, success_msg
            
        except ConnectionRefusedError:
            error_msg = f"Router {first_router['ip']}:{first_router['port']} not available"
            if not self.gui_mode:
                print(f"   X {error_msg}")
            return False, error_msg
        except socket.timeout:
            error_msg = "Router connection timeout"
            if not self.gui_mode:
                print(f"   X {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Erreur d'envoi: {e}"
            if not self.gui_mode:
                print(f"   X {error_msg}")
            return False, error_msg
    
    def listen_for_messages(self, callback=None):
        """Écoute des messages entrants"""
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.ip, self.port))
            server.listen(5)
            
            if not self.gui_mode:
                print(f"\nMessage listener started on {self.ip}:{self.port}")
            
            while self.running:
                try:
                    conn, addr = server.accept()
                    data = conn.recv(8192).decode()
                    conn.close()
                    
                    if data:
                        if ":" in data:
                            sender, message = data.split(":", 1)
                            
                            if callback and self.gui_mode:
                                # Mode GUI - utiliser le callback
                                current_time = datetime.now().strftime("%H:%M")
                                callback(sender, message, current_time)
                            elif not self.gui_mode:
                                # Mode CLI - afficher directement
                                print(f"\n", "="*50)
                                print(f"NEW MESSAGE FROM {sender}")
                                print(f"{'='*50}")
                                print(f"{message}")
                                print(f"{'='*50}")
                                
                                # Réafficher le prompt
                                sys.stdout.write("\n>> ")
                                sys.stdout.flush()
                        else:
                            if not self.gui_mode:
                                print(f"\nReceived: {data}")
                        
                except:
                    if not self.running:
                        break
                    pass
                
        except Exception as e:
            if not self.gui_mode:
                print(f"\nX Listener error: {e}")
        finally:
            if 'server' in locals():
                server.close()
    
    def keep_alive(self, callback=None):
        """Maintien de la connexion"""
        while self.running:
            try:
                if self.master_socket:
                    self.master_socket.send(b"PING")
                    response = self.master_socket.recv(1024)
                    if response != b"PONG":
                        self.running = False
                        if callback and self.gui_mode:
                            callback()
                        elif not self.gui_mode:
                            print("\n/!\\ Lost connection to master")
            except:
                self.running = False
                if callback and self.gui_mode:
                    callback()
                elif not self.gui_mode:
                    print("\n/!\\ Master connection error")
            
            time.sleep(30)
    
    def start(self, message_callback=None, disconnect_callback=None):
        """Démarrer les threads"""
        self.running = True
        
        # Thread d'écoute
        listener_args = () if not self.gui_mode else (message_callback,)
        threading.Thread(
            target=self.listen_for_messages, 
            args=listener_args, 
            daemon=True
        ).start()
        
        # Thread keep-alive
        keepalive_args = () if not self.gui_mode else (disconnect_callback,)
        threading.Thread(
            target=self.keep_alive, 
            args=keepalive_args, 
            daemon=True
        ).start()
    
    def stop(self):
        """Arrêter proprement"""
        self.running = False
        if self.master_socket:
            try:
                self.master_socket.send(b"QUIT")
                self.master_socket.close()
            except:
                pass


def run_cli():
    """Interface en ligne de commande"""
    print("\n" + "="*60)
    print("ONION CHAT CLIENT - MODE LIGNE DE COMMANDE")
    print("="*60)
    
    client = ChatClient()
    success, _ = client.register()
    
    if not success:
        print("\nX Registration failed. Exiting.")
        return
    
    # Démarrer les threads
    client.start()
    
    print("\n" + "="*60)
    print(f"WELCOME TO ONION CHAT, {client.username}!")
    print("="*60)
    print(f"Your connection: {client.ip}:{client.port}")
    print(f"Master server: {client.master_ip}:{client.master_port}")
    print("="*60)
    print("Available commands:")
    print("  /list          - Show online users")
    print("  /msg <user>    - Send message to user")
    print("  /quit          - Exit the chat")
    print("="*60)
    print("\nType your commands below:\n")
    
    while client.running:
        try:
            # Afficher le prompt
            sys.stdout.write(">> ")
            sys.stdout.flush()
            
            # Lire l'entrée
            cmd = input().strip()
            
            if cmd == "/quit":
                print("\nGoodbye!")
                client.stop()
                break
                
            elif cmd == "/list":
                users = client.get_online_users()
                if users:
                    print(f"\nOnline users ({len(users)}):")
                    for user in users:
                        print(f"  • {user}")
                else:
                    print("\nNo other users online")
                
            elif cmd.startswith("/msg "):
                parts = cmd.split(" ", 2)
                if len(parts) >= 2:
                    target = parts[1]
                    message = parts[2] if len(parts) > 2 else input("Message: ")
                    
                    if target == client.username:
                        print("\n/!\\ You can't message yourself!")
                    elif not message.strip():
                        print("\n/!\\ Message can't be empty")
                    else:
                        client.send_message(target, message)
                else:
                    print("\n/!\\ Usage: /msg <username> <message>")
                    
            elif cmd:
                print(f"\n/!\\ Unknown command: {cmd}")
                print("   Available: /list, /msg, /quit")
                
        except KeyboardInterrupt:
            print("\n\n/!\\ Interrupted. Type /quit to exit properly.")
        except Exception as e:
            print(f"\nX Error: {e}")
    
    print("\nClient stopped.")


# ============================================================================
# PARTIE INTERFACE GRAPHIQUE (PyQt6)
# ============================================================================

def run_gui():
    """Lancer l'interface graphique"""
    try:
        from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                   QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                                   QTextEdit, QComboBox, QMessageBox, QDialog)
        from PyQt6.QtCore import Qt, pyqtSignal, QObject
        from PyQt6.QtGui import QFont, QTextCursor
        
        # Import supplémentaire pour la vérification du port
        import socket
        
        print("\n" + "="*60)
        print("LANCEMENT DE L'INTERFACE GRAPHIQUE")
        print("="*60)
        
        class MessageSignals(QObject):
            """Signaux pour la communication entre threads"""
            message_received = pyqtSignal(str, str, str)  # sender, message, time
            connection_lost = pyqtSignal()
            error_occurred = pyqtSignal(str)
        
        class LoginWindow(QDialog):
            """Fenêtre de connexion"""
            
            def __init__(self):
                super().__init__()
                self.username = None
                self.ip = None
                self.port = None
                self.master_ip = None
                self.master_port = None
                self.init_ui()
                
            def init_ui(self):
                self.setWindowTitle("Onion Chat - Connexion")
                self.setFixedSize(400, 450)
                self.setStyleSheet("""
                    QDialog {
                        background-color: #1e1e2e;
                    }
                    QLabel {
                        color: #cdd6f4;
                        font-size: 13px;
                    }
                    QLineEdit {
                        background-color: #313244;
                        border: 2px solid #45475a;
                        border-radius: 8px;
                        padding: 10px;
                        color: #cdd6f4;
                        font-size: 13px;
                    }
                    QLineEdit:focus {
                        border: 2px solid #89b4fa;
                    }
                    QPushButton {
                        background-color: #89b4fa;
                        color: #1e1e2e;
                        border: none;
                        border-radius: 8px;
                        padding: 12px;
                        font-weight: bold;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #74c7ec;
                    }
                    QPushButton:pressed {
                        background-color: #89dceb;
                    }
                """)
                
                layout = QVBoxLayout()
                layout.setSpacing(10)
                layout.setContentsMargins(30, 30, 30, 30)
                
                # Titre
                title = QLabel("Connexion à Onion Chat")
                title.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa;")
                title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(title)
                
                layout.addSpacing(10)
                
                # Nom d'utilisateur
                username_label = QLabel("Nom d'utilisateur :")
                layout.addWidget(username_label)
                
                self.username_input = QLineEdit()
                self.username_input.setPlaceholderText("Entrez votre nom")
                self.username_input.setMinimumHeight(35)
                layout.addWidget(self.username_input)
                
                # IP du client
                ip_label = QLabel("Votre adresse IP :")
                layout.addWidget(ip_label)
                
                self.ip_input = QLineEdit()
                self.ip_input.setPlaceholderText("127.0.0.1")
                self.ip_input.setMinimumHeight(35)
                layout.addWidget(self.ip_input)
                
                # Port
                port_label = QLabel("Port d'écoute :")
                layout.addWidget(port_label)
                
                self.port_input = QLineEdit()
                self.port_input.setPlaceholderText("7001, 7002, 7003...")
                self.port_input.setMinimumHeight(35)
                layout.addWidget(self.port_input)
                
                # IP du Master
                master_ip_label = QLabel("Adresse IP du serveur Master :")
                layout.addWidget(master_ip_label)
                
                self.master_ip_input = QLineEdit()
                self.master_ip_input.setPlaceholderText(f"{MASTER_IP}")
                self.master_ip_input.setMinimumHeight(35)
                layout.addWidget(self.master_ip_input)
                
                # Port du Master
                master_port_label = QLabel("Port du serveur Master :")
                layout.addWidget(master_port_label)
                
                self.master_port_input = QLineEdit()
                self.master_port_input.setPlaceholderText(f"{MASTER_PORT}")
                self.master_port_input.setMinimumHeight(35)
                layout.addWidget(self.master_port_input)
                
                layout.addSpacing(10)
                
                # Bouton de connexion
                connect_btn = QPushButton("Se connecter")
                connect_btn.setMinimumHeight(45)
                connect_btn.clicked.connect(self.validate_and_connect)
                layout.addWidget(connect_btn)
                
                self.setLayout(layout)
                
                # Enter pour valider
                self.username_input.returnPressed.connect(self.validate_and_connect)
                self.ip_input.returnPressed.connect(self.validate_and_connect)
                self.port_input.returnPressed.connect(self.validate_and_connect)
                self.master_ip_input.returnPressed.connect(self.validate_and_connect)
                self.master_port_input.returnPressed.connect(self.validate_and_connect)
                
            def validate_ip(self, ip):
                """Valide une adresse IPv4"""
                try:
                    socket.inet_aton(ip)
                    return True
                except socket.error:
                    return False
                
            def validate_and_connect(self):
                username = self.username_input.text().strip()
                ip = self.ip_input.text().strip()
                port_text = self.port_input.text().strip()
                master_ip = self.master_ip_input.text().strip()
                master_port_text = self.master_port_input.text().strip()
                
                if not username:
                    QMessageBox.warning(self, "Erreur", "Veuillez entrer un nom d'utilisateur")
                    return
                
                # IP du client (optionnelle, défaut: 127.0.0.1)
                if ip == "":
                    ip = "127.0.0.1"
                elif not self.validate_ip(ip):
                    QMessageBox.warning(self, "Erreur", "Adresse IP invalide")
                    return
                    
                if not port_text:
                    QMessageBox.warning(self, "Erreur", "Veuillez entrer un port")
                    return
                    
                try:
                    port = int(port_text)
                    if port < 1024 or port > 65535:
                        QMessageBox.warning(self, "Erreur", "Le port doit être entre 1024 et 65535")
                        return
                    
                    # VÉRIFICATION SI LE PORT EST DISPONIBLE
                    try:
                        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        test_sock.bind((ip, port))
                        test_sock.close()
                    except OSError:
                        QMessageBox.warning(self, "Port occupé", 
                                          f"Le port {port} sur {ip} est déjà utilisé.\n"
                                          f"Veuillez choisir un autre port (7001, 7002, 7003...).")
                        return
                        
                except ValueError:
                    QMessageBox.warning(self, "Erreur", "Le port doit être un nombre")
                    return
                
                # IP du Master (optionnelle, défaut: MASTER_IP)
                if master_ip == "":
                    master_ip = MASTER_IP
                elif not self.validate_ip(master_ip):
                    QMessageBox.warning(self, "Erreur", "Adresse IP du Master invalide")
                    return
                
                # Port du Master (optionnel, défaut: MASTER_PORT)
                if master_port_text == "":
                    master_port = MASTER_PORT
                else:
                    try:
                        master_port = int(master_port_text)
                        if not (1 <= master_port <= 65535):
                            QMessageBox.warning(self, "Erreur", "Le port du Master doit être entre 1 et 65535")
                            return
                    except ValueError:
                        QMessageBox.warning(self, "Erreur", "Le port du Master doit être un nombre")
                        return
                        
                self.username = username
                self.ip = ip
                self.port = port
                self.master_ip = master_ip
                self.master_port = master_port
                self.accept()
        
        class ChatWindow(QMainWindow):
            """Fenêtre principale de chat"""
            
            def __init__(self, client):
                super().__init__()
                self.client = client
                self.current_recipient = None
                
                # Configurer le client pour le mode GUI
                self.client.gui_mode = True
                
                # Créer les signaux
                self.signals = MessageSignals()
                self.signals.message_received.connect(self.on_message_received)
                self.signals.connection_lost.connect(self.on_connection_lost)
                self.signals.error_occurred.connect(self.on_error)
                
                self.init_ui()
                self.update_user_list()
                
            def init_ui(self):
                self.setWindowTitle(f"Onion Chat - {self.client.username} ({self.client.ip}:{self.client.port})")
                self.setGeometry(100, 100, 800, 600)
                self.setStyleSheet("""
                    QMainWindow {
                        background-color: #1e1e2e;
                    }
                    QLabel {
                        color: #cdd6f4;
                    }
                    QTextEdit {
                        background-color: #313244;
                        border: 2px solid #45475a;
                        border-radius: 10px;
                        padding: 10px;
                        color: #cdd6f4;
                        font-size: 13px;
                    }
                    QLineEdit {
                        background-color: #313244;
                        border: 2px solid #45475a;
                        border-radius: 8px;
                        padding: 10px;
                        color: #cdd6f4;
                        font-size: 13px;
                    }
                    QLineEdit:focus {
                        border: 2px solid #89b4fa;
                    }
                    QComboBox {
                        background-color: #313244;
                        border: 2px solid #45475a;
                        border-radius: 8px;
                        padding: 8px;
                        color: #cdd6f4;
                        font-size: 13px;
                    }
                    QComboBox:hover {
                        border: 2px solid #89b4fa;
                    }
                    QComboBox::drop-down {
                        border: none;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-left: 5px solid transparent;
                        border-right: 5px solid transparent;
                        border-top: 5px solid #cdd6f4;
                        margin-right: 10px;
                    }
                    QPushButton {
                        background-color: #89b4fa;
                        color: #1e1e2e;
                        border: none;
                        border-radius: 8px;
                        padding: 10px;
                        font-weight: bold;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #74c7ec;
                    }
                    QPushButton:pressed {
                        background-color: #89dceb;
                    }
                """)
                
                # Widget central
                central_widget = QWidget()
                self.setCentralWidget(central_widget)
                main_layout = QVBoxLayout(central_widget)
                main_layout.setSpacing(10)
                main_layout.setContentsMargins(15, 15, 15, 15)
                
                # En-tête
                header_layout = QHBoxLayout()
                
                # Informations de connexion
                connection_info = QLabel(f"● Connecté | Client: {self.client.ip}:{self.client.port} | Master: {self.client.master_ip}:{self.client.master_port}")
                connection_info.setStyleSheet("color: #a6e3a1; font-size: 12px;")
                header_layout.addWidget(connection_info)
                
                header_layout.addStretch()
                
                # Bouton de déconnexion
                disconnect_btn = QPushButton("X Déconnexion")
                disconnect_btn.setFixedWidth(150)
                disconnect_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f38ba8;
                        color: #1e1e2e;
                    }
                    QPushButton:hover {
                        background-color: #eba0ac;
                    }
                """)
                disconnect_btn.clicked.connect(self.disconnect)
                header_layout.addWidget(disconnect_btn)
                
                main_layout.addLayout(header_layout)
                
                # Sélection du destinataire
                recipient_layout = QHBoxLayout()
                
                recipient_label = QLabel("Destinataire :")
                recipient_label.setStyleSheet("font-weight: bold; font-size: 14px;")
                recipient_layout.addWidget(recipient_label)
                
                self.recipient_combo = QComboBox()
                self.recipient_combo.setMinimumHeight(40)
                self.recipient_combo.currentTextChanged.connect(self.on_recipient_changed)
                recipient_layout.addWidget(self.recipient_combo, 1)
                
                refresh_btn = QPushButton("refresh")
                refresh_btn.setFixedWidth(70)
                refresh_btn.clicked.connect(self.update_user_list)
                recipient_layout.addWidget(refresh_btn)
                
                main_layout.addLayout(recipient_layout)
                
                # Zone de chat
                self.chat_display = QTextEdit()
                self.chat_display.setReadOnly(True)
                self.chat_display.setFont(QFont("Monospace", 11))
                main_layout.addWidget(self.chat_display, 1)
                
                # Zone d'envoi
                send_layout = QHBoxLayout()
                
                # Nombre de couches
                layers_label = QLabel("Couches:")
                send_layout.addWidget(layers_label)
                
                self.layers_input = QLineEdit("1")
                self.layers_input.setFixedWidth(70)
                send_layout.addWidget(self.layers_input)
                
                # Champ de message
                self.message_input = QLineEdit()
                self.message_input.setPlaceholderText("Tapez votre message...")
                self.message_input.setMinimumHeight(45)
                self.message_input.returnPressed.connect(self.send_message)
                send_layout.addWidget(self.message_input, 1)
                
                # Bouton d'envoi
                send_btn = QPushButton("➤")
                send_btn.setFixedSize(50, 45)
                send_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #a6e3a1;
                        font-size: 20px;
                    }
                    QPushButton:hover {
                        background-color: #b4e4b4;
                    }
                """)
                send_btn.clicked.connect(self.send_message)
                send_layout.addWidget(send_btn)
                
                main_layout.addLayout(send_layout)
                
            def update_user_list(self):
                """Met à jour la liste des utilisateurs"""
                users = self.client.get_online_users()
                current = self.recipient_combo.currentText()
                
                self.recipient_combo.clear()
                self.recipient_combo.addItem("-- Sélectionner un utilisateur --")
                
                for user in users:
                    self.recipient_combo.addItem(user)
                    
                # Restaurer la sélection si possible
                if current:
                    index = self.recipient_combo.findText(current)
                    if index >= 0:
                        self.recipient_combo.setCurrentIndex(index)
        
            def on_recipient_changed(self, recipient):
                """Changement de destinataire"""
                if recipient and recipient != "-- Sélectionner un utilisateur --":
                    self.current_recipient = recipient
                    self.chat_display.clear()
                    self.chat_display.append(f"<div style='text-align: center; color: #89b4fa; font-weight: bold;'>")
                    self.chat_display.append(f"═══ Conversation avec {recipient} ═══")
                else:
                    self.current_recipient = None
        
            def send_message(self):
                """Envoyer un message"""
                if not self.current_recipient:
                    QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un destinataire")
                    return
                    
                message = self.message_input.text().strip()
                if not message:
                    return
                    
                try:
                    nb_layers = int(self.layers_input.text())
                    if nb_layers <= 0:
                        QMessageBox.warning(self, "Erreur", "Le nombre de couches doit être positif")
                        return
                except ValueError:
                    QMessageBox.warning(self, "Erreur", "Nombre de couches invalide")
                    return
                    
                # Envoi du message
                success, status = self.client.send_message(self.current_recipient, message, nb_layers)
                
                if success:
                    # Afficher le message envoyé
                    current_time = datetime.now().strftime("%H:%M")
                    self.display_message(self.client.username, message, current_time, sent=True)
                    self.message_input.clear()
                else:
                    QMessageBox.critical(self, "Erreur d'envoi", status)
        
            def display_message(self, sender, message, time, sent=False):
                """Afficher un message dans le chat"""
                if sent:
                    color = "#a6e3a1"  # Vert pour les messages envoyés
                    align = "right"
                    label = "Vous"
                    margin_style = "margin-left: 30%; margin-right: 5px;"
                else:
                    color = "#89b4fa"  # Bleu pour les messages reçus
                    align = "left"
                    label = sender
                    margin_style = "margin-right: 30%; margin-left: 5px;"
                
                html = f"""
                <div style='text-align: {align};'>
                    <div style='color: {color}; font-weight: bold; margin-bottom: 3px;'>{label} • {time}</div>
                    <div style='background-color: #45475a; padding: 10px; border-radius: 10px; 
                                text-align: left; {margin_style}'>
                        {message}
                    </div>
                </div>
                <br>
                """
                
                self.chat_display.append(html)
                self.chat_display.moveCursor(QTextCursor.MoveOperation.End)    
           
            def on_message_received(self, sender, message, time):
                """Message reçu"""
                if self.current_recipient and sender == self.current_recipient:
                    self.display_message(sender, message, time, sent=False)
                elif not self.current_recipient:
                    # Si aucun destinataire n'est sélectionné, afficher une notification
                    QMessageBox.information(self, "Nouveau message", 
                                          f"Message reçu de {sender}:\n{message}")
        
            def on_connection_lost(self):
                """Connexion perdue"""
                QMessageBox.warning(self, "Connexion perdue", "La connexion au serveur a été perdue")
                self.close()
            
            def on_error(self, error_msg):
                """Erreur"""
                QMessageBox.critical(self, "Erreur", error_msg)
            
            def disconnect(self):
                """Se déconnecter"""
                reply = QMessageBox.question(self, "Déconnexion", 
                                           "Voulez-vous vraiment vous déconnecter ?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.client.stop()
                    self.close()
            
            def closeEvent(self, event):
                """Fermeture de la fenêtre"""
                self.client.stop()
                event.accept()
        
        # Point d'entrée de l'interface graphique
        app = QApplication(sys.argv)
        
        # Fenêtre de connexion
        login = LoginWindow()
        if login.exec() != QDialog.DialogCode.Accepted:
            return
        
        # Créer le client et se connecter
        client = ChatClient()
        client.gui_mode = True  # Mode GUI activé
        success, message = client.register(login.username, login.ip, login.port, 
                                          login.master_ip, login.master_port)
        
        if not success:
            QMessageBox.critical(None, "Erreur de connexion", message)
            return
        
        # Démarrer le client avec les callbacks
        def message_callback(sender, message, time):
            chat_window.signals.message_received.emit(sender, message, time)
        
        def disconnect_callback():
            chat_window.signals.connection_lost.emit()
        
        client.start(message_callback, disconnect_callback)
        
        # Afficher la fenêtre de chat
        chat_window = ChatWindow(client)
        chat_window.show()
        
        sys.exit(app.exec())
        
    except ImportError as e:
        print(f"\nX Erreur: Impossible d'importer PyQt6")
        print(f"   Vérifiez que PyQt6 est installé: pip install PyQt6")
        print(f"   Détail: {e}")
        return False
    except Exception as e:
        print(f"\nX Erreur lors du lancement de l'interface graphique: {e}")
        return False
    return True


def main():
    """Fonction principale qui demande le mode d'interface"""
    print("\n" + "="*60)
    print("ONION CHAT CLIENT")
    print("="*60)
    
    while True:
        print("\nChoisissez le mode d'interface:")
        print("  1. Interface graphique (GUI)")
        print("  2. Interface en ligne de commande (CLI)")
        print("  3. Quitter")
        
        choice = input("\nVotre choix (1-3): ").strip()
        
        if choice == "1":
            # Lancer l'interface graphique
            run_gui()
            # Après fermeture de l'interface graphique, revenir au menu
            continue
        elif choice == "2":
            # Lancer l'interface en ligne de commande
            run_cli()
            # Après fermeture du client CLI, revenir au menu
            continue
        elif choice == "3":
            print("\nAu revoir!")
            break
        else:
            print("\n/!\\ Choix invalide. Veuillez choisir 1, 2 ou 3.")


if __name__ == "__main__":
    main()
