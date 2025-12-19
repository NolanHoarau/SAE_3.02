import socket
import threading
import time
import sys

MASTER_IP = "127.0.0.1"
MASTER_PORT = 6000

class Client:
    def __init__(self):
        self.username = None
        self.port = None
        self.public_key = None
        self.master_socket = None
        self.running = False
        
    def register(self):
        """Inscription avec le Master"""
        print("\n", "="*60)
        print("CLIENT REGISTRATION")
        print("="*60)
        
        # Choix du nom
        self.username = input("Enter your username: ")
        
        # Choix du port (7000 pour mieux se distinguer du master et des routeurs)
        while True:
            try:
                self.port = int(input("Enter your listening port (7001, 7002, ...): "))
                
                # Verifier si le port est disponible
                try:
                    test_sock = socket.socket()
                    test_sock.bind(("127.0.0.1", self.port))
                    test_sock.close()
                    break
                except OSError:
                    print(f"X Port {self.port} is already in use. Please choose another.")
                    
            except ValueError:
                print("X Please enter a valid number.")
        
        print(f"\nConnecting to master at {MASTER_IP}:{MASTER_PORT}...")
        
        try:
            # Connexion au Master
            self.master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.master_socket.settimeout(10.0)
            self.master_socket.connect((MASTER_IP, MASTER_PORT))
            
            # Identifier en tant que Client
            self.master_socket.send(b"CLIENT")
            time.sleep(0.1)  # Small delay
            
            # Envoie des donnees d'inscription
            reg_data = f"{self.username}::127.0.0.1::{self.port}"
            self.master_socket.send(reg_data.encode())
            
            # Reponse du Master
            response = self.master_socket.recv(1024).decode()
            
            if response.startswith("OK:"):
                # Extraire la cle publique
                _, e_str, n_str = response.split(":")
                self.public_key = (int(e_str), int(n_str))
                
                print(f"\nSuccessfully registered as '{self.username}'")
                print(f"   Listening on port: {self.port}")
                print(f"   Public key: ({e_str[:10]}..., {n_str[:10]}...)")
                
                # Supprimer le delai d'attente
                self.master_socket.settimeout(None)
                return True
            else:
                print(f"\nX Registration failed: {response}")
                return False
                
        except ConnectionRefusedError:
            print("\nX Cannot connect to master server.")
            print("   Make sure master.py is running on port 6000")
            return False
        except socket.timeout:
            print("\nX Connection timeout.")
            print("   Master server is not responding")
            return False
        except Exception as e:
            print(f"\nX Registration error: {type(e).__name__}: {e}")
            return False
    
    def get_online_users(self):
        """Liste des utilisateurs en ligne"""
        try:
            self.master_socket.send(b"LIST")
            response = self.master_socket.recv(1024).decode()
            
            if response.startswith("ONLINE:"):
                users = response[7:].split(",")
                # Filtre les chaines vides et self
                return [u for u in users if u and u != self.username]
            return []
        except:
            return []
    
    def get_user_info(self, username):
        """Recois les infromations d'un utilisateur"""
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
        """Demande d'un chemin de routage au Master"""
        try:
            # Envoie d'une requete pour le chemin
            request = f"PATH:{self.username}:{nb_layers}:{target_user}"
            self.master_socket.send(request.encode())
            
            # Reponse
            response = self.master_socket.recv(4096).decode()
            
            if response.startswith("ERROR"):
                print(f"   X Path error: {response}")
                return None, None
            
            if "||" not in response:
                print("   X Invalid response format")
                return None, None
            
            # Separer les reponses
            path_part, target_part = response.split("||", 1)
            
            # Separer le chemin
            routers = []
            for hop in path_part.split("|"):
                if hop:
                    ip, port, e, n = hop.split(";")
                    routers.append({
                        "ip": ip,
                        "port": int(port),
                        "pub_key": (int(e), int(n))
                    })
            
            # Separer les informations de la cible
            target_ip, target_port = target_part.split(";")
            target_info = {
                "ip": target_ip,
                "port": int(target_port)
            }
            
            return routers, target_info
            
        except Exception as e:
            print(f"   X Path request error: {e}")
            return None, None
    
    def encrypt_message(self, message, pub_key):
        """Chiffrement du message avec RSA"""
        e, n = pub_key
        encrypted = []
        for char in message:
            try:
                encrypted.append(pow(ord(char), e, n))
            except:
                # Solution pour des nombres trop grands
                encrypted.append(ord(char) % n)
        return encrypted
    
    def build_onion(self, message, routers, target_info):
        """Construction du chiffrement oignon du message"""
        # Commencer avec le message final
        current = message
        
        # Ajout de couches du dernier au premier routeur
        for i in range(len(routers)-1, -1, -1):
            router = routers[i]
            
            # Definir le prochain saut
            if i == len(routers)-1:
                # Last router sends to target
                next_hop = f"{target_info['ip']};{target_info['port']}"
            else:
                # Routeur envoie au prochain
                next_router = routers[i+1]
                next_hop = f"{next_router['ip']};{next_router['port']}"
            
            # Creation couches: next_hop|encrypted_data
            layer = f"{next_hop}|{current}"
            
            # Chiffrement avec la cle publique du routeur
            encrypted = self.encrypt_message(layer, router['pub_key'])
            current = ",".join(str(x) for x in encrypted)
        
        return current
    
    def send_message(self, target_user, message):
        """Envoie d'un message a un autre utilisateur"""
        print(f"\nPreparing message for '{target_user}'...")
        
        # Recevoir les infos du destinataire
        print(f"   Looking up '{target_user}'...")
        user_info = self.get_user_info(target_user)
        
        if not user_info:
            print(f"   X User '{target_user}' not found or offline")
            return
        
        # Demander pour le nombre de couches de chiffrement (nombre de routeurs)
        while True:
            try:
                nb_layers = int(input(f"   Number of router layers (1-3 recommended): "))
                if 1 <= nb_layers <= 5:
                    break
                print("   /!\\ Please enter a number between 1 and 5")
            except ValueError:
                print("   /!\\ Please enter a valid number")
        
        # Recevoir le chemin de routage
        print(f"   Requesting path from master...")
        routers, target_info = self.request_path(target_user, nb_layers)
        
        if not routers:
            return
        
        print(f"   Path obtained: {len(routers)} routers")
        
        # Construction du message avec nos infos
        complete_message = f"{self.username}:{message}"
        
        # Construction de l'oignon
        print(f"   Building onion encryption...")
        onion = self.build_onion(complete_message, routers, target_info)
        
        # Envoie au premier routeur
        first_router = routers[0]
        print(f"   Sending to first router: {first_router['ip']}:{first_router['port']}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((first_router["ip"], first_router["port"]))
            sock.send(onion.encode())
            sock.close()
            print(f"   Message sent successfully via {len(routers)} routers!")
            
        except ConnectionRefusedError:
            print(f"   X Router {first_router['ip']}:{first_router['port']} not available")
        except socket.timeout:
            print(f"   X Router connection timeout")
        except Exception as e:
            print(f"   X Send error: {e}")
    
    def listen_for_messages(self):
        """Ecoute pour les messages entrant sur notre port"""
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", self.port))
            server.listen(5)
            
            print(f"\nMessage listener started on port {self.port}")
            
            while self.running:
                try:
                    conn, addr = server.accept()
                    
                    # Recois le message
                    data = conn.recv(8192).decode()
                    conn.close()
                    
                    if data:
                        # Affichage du message
                        if ":" in data:
                            sender, message = data.split(":", 1)
                            print(f"\n", "="*50)
                            print(f"NEW MESSAGE FROM {sender}")
                            print(f"{'='*50}")
                            print(f"{message}")
                            print(f"{'='*50}")
                        else:
                            print(f"\nReceived: {data}")
                        
                        # Affichage de la console
                        sys.stdout.write("\n>> ")
                        sys.stdout.flush()
                        
                except:
                    pass
                
        except Exception as e:
            print(f"\nX Listener error: {e}")
        finally:
            if 'server' in locals():
                server.close()
    
    def keep_alive(self):
        """Envoie de pings constemment au Master pour garder la connexion"""
        while self.running:
            try:
                if self.master_socket:
                    self.master_socket.send(b"PING")
                    response = self.master_socket.recv(1024)
                    if response != b"PONG":
                        print("\n/!\\ Lost connection to master")
                        self.running = False
            except:
                print("\n/!\\ Master connection error")
                self.running = False
            
            time.sleep(30)  # Ping toutes les 30 secondes
    
    def chat_interface(self):
        """Interface messagerie"""
        self.running = True
        
        # Lancement du thread pour l'ecoute des messages entrant
        listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
        listener_thread.start()
        
        # Lancement du thread pour garder la connexion
        ping_thread = threading.Thread(target=self.keep_alive, daemon=True)
        ping_thread.start()
        
        print("\n" + "="*60)
        print(f"WELCOME TO ONION CHAT, {self.username}!")
        print("="*60)
        print("Available commands:")
        print("  /list          - Show online users")
        print("  /msg <user>    - Send message to user")
        print("  /quit          - Exit the chat")
        print("="*60)
        print("\nType your commands below:\n")
        
        while self.running:
            try:
                # Show prompt
                sys.stdout.write(">> ")
                sys.stdout.flush()
                
                # Get input
                cmd = input().strip()
                
                if cmd == "/quit":
                    print("\nGoodbye!")
                    self.running = False
                    if self.master_socket:
                        self.master_socket.send(b"QUIT")
                        self.master_socket.close()
                    break
                    
                elif cmd == "/list":
                    users = self.get_online_users()
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
                        
                        if target == self.username:
                            print("\n/!\\ You can't message yourself!")
                        elif not message.strip():
                            print("\n/!\\ Message can't be empty")
                        else:
                            self.send_message(target, message)
                    else:
                        print("\n/!\\ Usage: /msg <username> <message>")
                        
                elif cmd:
                    print(f"\n/!\\ Unknown command: {cmd}")
                    print("   Available: /list, /msg, /quit")
                    
            except KeyboardInterrupt:
                print("\n\n/!\\ Interrupted. Type /quit to exit properly.")
            except Exception as e:
                print(f"\nX Error: {e}")
    
    def run(self):
        """Fonction main"""
        if not self.register():
            print("\nX Registration failed. Exiting.")
            return
        
        self.chat_interface()
        print("\nClient stopped.")

def run_gui():
    """Lance l'interface graphique"""
    try:
        # Import et lancement de l'interface graphique
        from client_gui import main as gui_main
        print("\n" + "="*60)
        print("LANCEMENT DE L'INTERFACE GRAPHIQUE")
        print("="*60)
        gui_main()
    except ImportError as e:
        print(f"\nX Erreur: Impossible d'importer l'interface graphique")
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
            client = Client()
            client.run()
            # Après fermeture du client CLI, revenir au menu
            continue
        elif choice == "3":
            print("\nAu revoir!")
            break
        else:
            print("\n/!\\ Choix invalide. Veuillez choisir 1, 2 ou 3.")

if __name__ == "__main__":
    main()
