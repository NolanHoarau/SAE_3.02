#!/usr/bin/env python3
"""
Master Server pour Onion Routing
Mode shell ou interface graphique selon le choix au démarrage
Utilise PyQt6 pour le mode graphique
"""

import sys
import socket
import threading
import random
import math
import mariadb
import time
from datetime import datetime

# Import PyQt6 uniquement si disponible
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QLabel, QTextEdit, QTableWidget, QTableWidgetItem, QTabWidget,
        QHeaderView, QMessageBox
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
    from PyQt6.QtGui import QFont, QColor
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("[WARNING] PyQt6 non disponible - Mode GUI désactivé")

# Configuration de la base de données
DB_CONFIG = {
    'host': 'localhost',
    'database': 'routage_oignon',
    'user': 'routage_user',
    'password': 'wxcvbn%!',
    'port': 3306
}

# ---------- SIGNAUX (pour mode GUI) ----------
if PYQT_AVAILABLE:
    class MasterSignals(QObject):
        """Signaux pour la communication entre threads"""
        log_message = pyqtSignal(str)  # Pour les logs
        router_connected = pyqtSignal(dict)  # Nouveau routeur
        client_connected = pyqtSignal(str, dict)  # Nouveau client
        client_disconnected = pyqtSignal(str)  # Client déconnecté
        router_disconnected = pyqtSignal(int)  # Routeur déconnecté

# ---------- RSA ----------
def generate_keys():
    """Générer clé RSA publique/privée"""
    p = 0
    q = 0
    while not is_prime(p):
        p = random.randint(11, 50)
    while not is_prime(q) or q == p:
        q = random.randint(11, 50)
    
    n = p * q
    phi = (p - 1) * (q - 1)
    e = 3
    while math.gcd(e, phi) != 1:
        e += 2
    d = pow(e, -1, phi)
    return (e, n), (d, n)

def is_prime(n):
    """Vérifier si un nombre est premier"""
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

# ---------- CONNEXION BDD ----------
def get_db():
    """Se connecter à la base de données"""
    try:
        conn = mariadb.connect(**DB_CONFIG)
        return conn
    except mariadb.Error as e:
        print(f"[MASTER] X Database Error: {e}")
        return None

def clear_database_tables():
    """Nettoyer toutes les tables dans la base de données au lancement"""
    db = get_db()
    if db:
        cur = db.cursor()
        try:
            cur.execute("SHOW TABLES")
            tables = cur.fetchall()
            if tables:
                print(f"[MASTER] Clearing {len(tables)} tables...")
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                for table in tables:
                    table_name = table[0]
                    cur.execute(f"TRUNCATE TABLE {table_name}")
                    print(f"[MASTER] Cleared table: {table_name}")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
                db.commit()
                print(f"[MASTER] All tables cleared successfully")
            else:
                print(f"[MASTER] No tables found in database")
        except mariadb.Error as e:
            print(f"[MASTER] X Error clearing tables: {e}")
            db.rollback()
        finally:
            db.close()
    else:
        print("[MASTER] /!\\ Could not connect to database for cleanup")

# ---------- MASTER SERVER ----------
class MasterServer:
    """Gestion du serveur Master"""
    
    def __init__(self, gui_mode=False):
        self.routers = []
        self.users = {}
        self.online_users = {}
        self.server = None
        self.running = False
        self.port = None
        self.gui_mode = gui_mode
        
        if gui_mode and PYQT_AVAILABLE:
            self.signals = MasterSignals()
        else:
            self.signals = None
        
    def log(self, message):
        """Envoyer un log via signal (GUI) ou print (shell)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        
        if self.gui_mode and self.signals:
            self.signals.log_message.emit(formatted_msg)
        else:
            print(formatted_msg)
        
    def handle_router(self, conn):
        """Gérer l'enregistrement des routeurs"""
        try:
            data = conn.recv(1024).decode().strip()
            self.log(f"Router registration: {data}")
            
            if ";" in data:
                ip, port = data.split(";")
                port = int(port)
                
                # Génération de clés RSA
                pub, priv = generate_keys()
                e, n = pub
                d, _ = priv
                
                # Sauvegarde en BDD
                db = get_db()
                if db:
                    cur = db.cursor()
                    cur.execute(
                        "INSERT INTO routers (ip, port, e, n, d) VALUES (?, ?, ?, ?, ?)",
                        (ip, port, e, n, d)
                    )
                    router_id = cur.lastrowid
                    db.commit()
                    db.close()
                    
                    # Ajout dans la liste
                    router_info = {
                        "id": router_id,
                        "ip": ip,
                        "port": port,
                        "e": e,
                        "n": n,
                        "d": d,
                        "active": True
                    }
                    self.routers.append(router_info)
                    
                    # Envoyer clé privée au routeur
                    response = f"{d};{n}"
                    conn.send(response.encode())
                    
                    self.log(f"Router {ip}:{port} registered (ID: {router_id})")
                    
                    if self.gui_mode and self.signals:
                        self.signals.router_connected.emit(router_info)
                else:
                    conn.send(b"ERROR:DB_CONNECTION")
            else:
                conn.send(b"ERROR:INVALID_FORMAT")
        except Exception as e:
            self.log(f"X Router handler error: {e}")
            conn.send(b"ERROR:INTERNAL")
        finally:
            conn.close()
            
    def handle_client(self, conn):
        """Gérer la connexion et l'enregistrement du Client"""
        username = None
        try:
            conn.settimeout(10.0)
            data = conn.recv(1024).decode().strip()
            self.log(f"Client registration: {data}")
            
            if "::" in data:
                parts = data.split("::")
                if len(parts) >= 3:
                    username = parts[0]
                    ip = parts[1]
                    port = int(parts[2])
                    
                    # Génération des clés RSA
                    pub, _ = generate_keys()
                    e, n = pub
                    
                    # Sauvegarder en BDD
                    db = get_db()
                    if not db:
                        conn.send(b"ERROR:DB_CONNECTION")
                        conn.close()
                        return
                    
                    cur = db.cursor()
                    cur.execute("SELECT username FROM users WHERE username = ?", (username,))
                    if cur.fetchone():
                        cur.execute("""
                            UPDATE users SET
                            ip=?, port=?, public_key_e=?, public_key_n=?, is_online=TRUE,
                            last_seen=NOW()
                            WHERE username=?
                        """, (ip, port, e, n, username))
                    else:
                        cur.execute("""
                            INSERT INTO users
                            (username, ip, port, public_key_e, public_key_n, is_online)
                            VALUES (?, ?, ?, ?, ?, TRUE)
                        """, (username, ip, port, e, n))
                    db.commit()
                    db.close()
                    
                    # Stocker en mémoire
                    self.users[username] = {
                        "ip": ip,
                        "port": port,
                        "public_key": (e, n),
                        "socket": conn,
                        "active": True
                    }
                    self.online_users[username] = True
                    
                    # Envoyer succès
                    response = f"OK:{e}:{n}"
                    conn.send(response.encode())
                    
                    self.log(f"User '{username}' registered at {ip}:{port}")
                    
                    if self.gui_mode and self.signals:
                        self.signals.client_connected.emit(username, self.users[username])
                    
                    # Supprimer le timeout
                    conn.settimeout(None)
                    
                    # Boucle de commandes
                    try:
                        while True:
                            cmd_data = conn.recv(1024).decode().strip()
                            if not cmd_data:
                                self.log(f"Client '{username}' disconnected")
                                break
                                
                            if cmd_data == "QUIT":
                                self.log(f"Client '{username}' quit")
                                break
                            elif cmd_data == "LIST":
                                user_list = list(self.users.keys())
                                response = f"ONLINE:{','.join(user_list)}"
                                conn.send(response.encode())
                                self.log(f"Sent user list to '{username}'")
                            elif cmd_data.startswith("GET:"):
                                target = cmd_data[4:]
                                if target in self.users:
                                    info = self.users[target]
                                    e, n = info["public_key"]
                                    response = f"USER:{info['ip']}:{info['port']}:{e}:{n}"
                                else:
                                    response = "NOT_FOUND"
                                conn.send(response.encode())
                            elif cmd_data.startswith("PATH:"):
                                _, sender, layers_str, target = cmd_data.split(":", 3)
                                layers = int(layers_str)
                                
                                if target not in self.users:
                                    conn.send(b"ERROR:TARGET_NOT_FOUND")
                                    continue
                                    
                                if layers > len(self.routers):
                                    layers = len(self.routers)
                                if layers <= 0:
                                    conn.send(b"ERROR:NO_ROUTERS_AVAILABLE")
                                    continue
                                    
                                path_routers = random.sample(self.routers, layers)
                                target_info = self.users[target]
                                
                                path_str = "|".join([
                                    f"{r['ip']};{r['port']};{r['e']};{r['n']}"
                                    for r in path_routers
                                ])
                                target_str = f"{target_info['ip']};{target_info['port']}"
                                response = f"{path_str}||{target_str}"
                                conn.send(response.encode())
                                
                                self.log(f"Path created: {sender} -> {target} ({layers} hops)")
                            elif cmd_data == "PING":
                                conn.send(b"PONG")
                            else:
                                conn.send(b"ERROR:UNKNOWN_COMMAND")
                    except ConnectionResetError:
                        self.log(f"Client '{username}' connection reset")
                    except Exception as e:
                        self.log(f"X Command error for '{username}': {type(e).__name__}")
                else:
                    conn.send(b"ERROR:INVALID_DATA")
            else:
                conn.send(b"ERROR:INVALID_FORMAT")
        except socket.timeout:
            self.log("Registration timeout for client")
        except Exception as e:
            self.log(f"X Client handler error: {type(e).__name__}: {e}")
        finally:
            if username and username in self.users:
                del self.users[username]
                if self.gui_mode and self.signals:
                    self.signals.client_disconnected.emit(username)
            if username and username in self.online_users:
                del self.online_users[username]
            if username:
                db = get_db()
                if db:
                    cur = db.cursor()
                    cur.execute("UPDATE users SET is_online = FALSE WHERE username = ?", (username,))
                    db.commit()
                    db.close()
                self.log(f"Cleaned up client '{username}'")
            conn.close()
            
    def start(self):
        """Démarrer le serveur Master"""
        self.running = True
        clear_database_tables()
        
        ports_to_try = [6000, 6001, 6002, 7000]
        for port in ports_to_try:
            try:
                self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server.bind(("127.0.0.1", port))
                self.server.listen(10)
                self.port = port
                self.log(f"Server started on 127.0.0.1:{port}")
                self.log(f"Available routers: {len(self.routers)}")
                self.log(f"Online users: {len(self.users)}")
                self.log("Waiting for connections...")
                print("-" * 60)
                break
            except OSError as e:
                if port == ports_to_try[-1]:
                    self.log("X Could not bind to any port")
                    self.log(f"Error: {e}")
                    print("[MASTER] Try: sudo kill $(sudo lsof -t -i:6000-7000)")
                    return False
                self.log(f"/!\\ Port {port} busy, trying next...")
                continue
        
        # Thread pour accepter les connexions
        threading.Thread(target=self._accept_connections, daemon=True).start()
        return True
        
    def _accept_connections(self):
        """Boucle d'acceptation des connexions"""
        while self.running:
            try:
                conn, addr = self.server.accept()
                self.log(f"New connection from {addr}")
                
                conn.settimeout(5.0)
                try:
                    typ_data = conn.recv(10).decode().strip()
                    self.log(f"Connection type: {typ_data}")
                    
                    if typ_data == "ROUTER":
                        self.log(f"New router from {addr}")
                        threading.Thread(target=self.handle_router, args=(conn,), daemon=True).start()
                    elif typ_data == "CLIENT":
                        self.log(f"New client from {addr}")
                        threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
                    else:
                        self.log(f"? Unknown type: {typ_data}")
                        conn.send(b"ERROR:UNKNOWN_TYPE")
                        conn.close()
                except socket.timeout:
                    self.log(f"Connection timeout from {addr}")
                    conn.close()
            except Exception as e:
                if self.running:
                    self.log(f"X Accept error: {type(e).__name__}: {e}")
                    
    def stop(self):
        """Arrêter le serveur"""
        self.running = False
        if self.server:
            self.server.close()
        self.log("Server stopped")

# ---------- INTERFACE GRAPHIQUE ----------
if PYQT_AVAILABLE:
    class MasterWindow(QMainWindow):
        """Fenêtre principale du Master"""
        
        def __init__(self, master_server):
            super().__init__()
            self.master = master_server
            
            # Connecter les signaux
            self.master.signals.log_message.connect(self.add_log)
            self.master.signals.router_connected.connect(self.add_router)
            self.master.signals.client_connected.connect(self.add_client)
            self.master.signals.client_disconnected.connect(self.remove_client)
            
            self.init_ui()
            
            # Timer pour rafraîchir l'affichage
            self.timer = QTimer()
            self.timer.timeout.connect(self.refresh_status)
            self.timer.start(2000)  # Toutes les 2 secondes
            
        def init_ui(self):
            self.setWindowTitle("🧅 Onion Routing - Master Server")
            self.setGeometry(100, 100, 1200, 700)
            
            # Style identique au client
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1e1e2e;
                }
                QLabel {
                    color: #cdd6f4;
                    font-size: 13px;
                }
                QTextEdit {
                    background-color: #313244;
                    border: 2px solid #45475a;
                    border-radius: 10px;
                    padding: 10px;
                    color: #cdd6f4;
                    font-size: 12px;
                }
                QTableWidget {
                    background-color: #313244;
                    border: 2px solid #45475a;
                    border-radius: 10px;
                    color: #cdd6f4;
                    gridline-color: #45475a;
                }
                QTableWidget::item {
                    padding: 5px;
                }
                QHeaderView::section {
                    background-color: #45475a;
                    color: #cdd6f4;
                    padding: 8px;
                    border: none;
                    font-weight: bold;
                }
                QTabWidget::pane {
                    border: 2px solid #45475a;
                    border-radius: 10px;
                    background-color: #313244;
                }
                QTabBar::tab {
                    background-color: #313244;
                    color: #cdd6f4;
                    padding: 10px 20px;
                    margin-right: 2px;
                    border: 2px solid #45475a;
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                }
                QTabBar::tab:selected {
                    background-color: #89b4fa;
                    color: #1e1e2e;
                    font-weight: bold;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #45475a;
                }
            """)
            
            # Widget central
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setSpacing(15)
            main_layout.setContentsMargins(15, 15, 15, 15)
            
            # En-tête
            header = QLabel("🧅 ONION ROUTING - MASTER SERVER")
            header.setStyleSheet("font-size: 20px; font-weight: bold; color: #89b4fa;")
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(header)
            
            # Onglets
            self.tabs = QTabWidget()
            main_layout.addWidget(self.tabs)
            
            # Onglet Logs
            self.logs_tab = QWidget()
            self.init_logs_tab()
            self.tabs.addTab(self.logs_tab, "📋 Logs")
            
            # Onglet Connexions
            self.connections_tab = QWidget()
            self.init_connections_tab()
            self.tabs.addTab(self.connections_tab, "🔗 Connexions")
            
        def init_logs_tab(self):
            """Initialiser l'onglet Logs"""
            layout = QVBoxLayout(self.logs_tab)
            layout.setContentsMargins(10, 10, 10, 10)
            
            # Zone de logs
            self.log_display = QTextEdit()
            self.log_display.setReadOnly(True)
            self.log_display.setFont(QFont("Monospace", 10))
            layout.addWidget(self.log_display)
            
        def init_connections_tab(self):
            """Initialiser l'onglet Connexions"""
            layout = QVBoxLayout(self.connections_tab)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(15)
            
            # Info Master
            master_group = QWidget()
            master_layout = QHBoxLayout(master_group)
            master_layout.setContentsMargins(10, 10, 10, 10)
            
            master_label = QLabel("Master:")
            master_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            master_layout.addWidget(master_label)
            
            self.master_info = QLabel("127.0.0.1:6000")
            self.master_info.setStyleSheet("font-size: 14px; color: #89b4fa;")
            master_layout.addWidget(self.master_info)
            
            self.master_status = QLabel("●")
            self.master_status.setStyleSheet("color: #a6e3a1; font-size: 20px;")
            master_layout.addWidget(self.master_status)
            
            master_layout.addStretch()
            layout.addWidget(master_group)
            
            # Layout horizontal pour les deux tables côte à côte
            tables_layout = QHBoxLayout()
            tables_layout.setSpacing(15)
            
            # ========== COLONNE ROUTEURS (GAUCHE) ==========
            routers_container = QWidget()
            routers_layout = QVBoxLayout(routers_container)
            routers_layout.setContentsMargins(0, 0, 0, 0)
            routers_layout.setSpacing(10)
            
            routers_label = QLabel("Routeurs")
            routers_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #89b4fa;")
            routers_layout.addWidget(routers_label)
            
            self.routers_table = QTableWidget()
            self.routers_table.setColumnCount(3)
            self.routers_table.setHorizontalHeaderLabels(["ID", "IP / Port", "État"])
            
            # Élargir la colonne IP/Port pour les routeurs
            self.routers_table.setColumnWidth(0, 50)   # ID
            self.routers_table.setColumnWidth(1, 200)  # IP/Port (élargi)
            self.routers_table.horizontalHeader().setStretchLastSection(True)  # État prend le reste
            
            self.routers_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            routers_layout.addWidget(self.routers_table)
            
            tables_layout.addWidget(routers_container)
            
            # ========== COLONNE CLIENTS (DROITE) ==========
            clients_container = QWidget()
            clients_layout = QVBoxLayout(clients_container)
            clients_layout.setContentsMargins(0, 0, 0, 0)
            clients_layout.setSpacing(10)
            
            clients_label = QLabel("Clients")
            clients_label.setStyleSheet("font-weight: bold; font-size: 15px; color: #89b4fa;")
            clients_layout.addWidget(clients_label)
            
            self.clients_table = QTableWidget()
            self.clients_table.setColumnCount(4)
            self.clients_table.setHorizontalHeaderLabels(["ID", "Nom", "IP / Port", "État"])
            
            # Élargir la colonne IP/Port pour les clients
            self.clients_table.setColumnWidth(0, 50)   # ID
            self.clients_table.setColumnWidth(1, 120)  # Nom
            self.clients_table.setColumnWidth(2, 200)  # IP/Port (élargi)
            self.clients_table.horizontalHeader().setStretchLastSection(True)  # État prend le reste
            
            self.clients_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            clients_layout.addWidget(self.clients_table)
            
            tables_layout.addWidget(clients_container)
            
            # Ajouter le layout horizontal au layout principal
            layout.addLayout(tables_layout)
            
            # Légende
            legend = QLabel("● Actif")
            legend.setStyleSheet("color: #a6e3a1; font-size: 12px;")
            layout.addWidget(legend)
            
        def add_log(self, message):
            """Ajouter un message dans les logs"""
            self.log_display.append(message)
            self.log_display.verticalScrollBar().setValue(
                self.log_display.verticalScrollBar().maximum()
            )
            
        def add_router(self, router_info):
            """Ajouter un routeur dans la table"""
            row = self.routers_table.rowCount()
            self.routers_table.insertRow(row)
            
            self.routers_table.setItem(row, 0, QTableWidgetItem(str(router_info['id'])))
            self.routers_table.setItem(row, 1, QTableWidgetItem(f"{router_info['ip']}:{router_info['port']}"))
            
            status_item = QTableWidgetItem("●")
            status_item.setForeground(QColor("#a6e3a1"))
            self.routers_table.setItem(row, 2, status_item)
            
        def add_client(self, username, client_info):
            """Ajouter un client dans la table"""
            row = self.clients_table.rowCount()
            self.clients_table.insertRow(row)
            
            self.clients_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.clients_table.setItem(row, 1, QTableWidgetItem(username))
            self.clients_table.setItem(row, 2, QTableWidgetItem(f"{client_info['ip']}:{client_info['port']}"))
            
            status_item = QTableWidgetItem("●")
            status_item.setForeground(QColor("#a6e3a1"))
            self.clients_table.setItem(row, 3, status_item)
            
        def remove_client(self, username):
            """Retirer un client de la table"""
            for row in range(self.clients_table.rowCount()):
                if self.clients_table.item(row, 1).text() == username:
                    # Changer le statut en rouge
                    status_item = QTableWidgetItem("●")
                    status_item.setForeground(QColor("#f38ba8"))
                    self.clients_table.setItem(row, 3, status_item)
                    break
                    
        def refresh_status(self):
            """Rafraîchir l'affichage du statut"""
            if self.master.port:
                self.master_info.setText(f"127.0.0.1:{self.master.port}")
                
        def closeEvent(self, event):
            """Fermeture de la fenêtre"""
            reply = QMessageBox.question(
                self, 'Confirmation',
                'Êtes-vous sûr de vouloir arrêter le serveur Master ?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.master.stop()
                event.accept()
            else:
                event.ignore()

# ---------- MAIN ----------
def main():
    """Point d'entrée principal"""
    print("\n" + "="*60)
    print("ONION ROUTING MASTER SERVER")
    print("="*60 + "\n")
    
    # Question au démarrage
    while True:
        choice = input("Voulez-vous utiliser l'interface graphique ? (oui / non) : ").strip().lower()
        if choice in ['oui', 'non', 'o', 'n']:
            break
        print("Veuillez répondre par 'oui' ou 'non'")
    
    # Normaliser la réponse
    use_gui = choice in ['oui', 'o']
    
    if not use_gui:
        # ====== MODE SHELL ======
        print("\n[MASTER] Mode shell activé\n")
        
        master_server = MasterServer(gui_mode=False)
        
        if not master_server.start():
            print("[MASTER] ✗ Échec du démarrage du serveur")
            sys.exit(1)
        
        print("\n[MASTER] Serveur en cours d'exécution...")
        print("[MASTER] Appuyez sur Ctrl+C pour arrêter\n")
        
        try:
            # Garder le programme actif
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n[MASTER] Arrêt demandé...")
            master_server.stop()
            print("[MASTER] Au revoir!")
            sys.exit(0)
    else:
        # ====== MODE GUI ======
        if not PYQT_AVAILABLE:
            print("\n[MASTER] ✗ PyQt6 n'est pas installé")
            print("[MASTER] Installez-le avec: pip install PyQt6")
            print("[MASTER] Basculement vers le mode shell...\n")
            
            master_server = MasterServer(gui_mode=False)
            
            if not master_server.start():
                print("[MASTER] ✗ Échec du démarrage du serveur")
                sys.exit(1)
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n[MASTER] Arrêt demandé...")
                master_server.stop()
                sys.exit(0)
        
        print("\n[MASTER] Lancement de l'interface graphique...\n")
        
        master_server = MasterServer(gui_mode=True)
        
        if not master_server.start():
            print("[MASTER] ✗ Échec du démarrage du serveur")
            sys.exit(1)
        
        # Créer l'application Qt
        app = QApplication(sys.argv)
        window = MasterWindow(master_server)
        window.show()
        
        sys.exit(app.exec())

if __name__ == "__main__":
    main()
