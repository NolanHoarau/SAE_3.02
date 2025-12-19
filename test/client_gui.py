#!/usr/bin/env python3
"""
Interface graphique pour Onion Chat
Utilise PyQt6 et s'intègre avec la logique du client.py existant
"""

import sys
import socket
import threading
import time
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QComboBox, QMessageBox, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QTextCursor

# Configuration
MASTER_IP = "127.0.0.1"
MASTER_PORT = 6000


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
        self.port = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Onion Chat - Connexion")
        self.setFixedSize(400, 300)
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
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Titre
        title = QLabel("🧅 Connexion à Onion Chat")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        layout.addSpacing(10)
        
        # Nom d'utilisateur
        username_label = QLabel("Nom d'utilisateur :")
        layout.addWidget(username_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Entrez votre nom")
        self.username_input.setMinimumHeight(40)
        layout.addWidget(self.username_input)
        
        # Port
        port_label = QLabel("Port d'écoute :")
        layout.addWidget(port_label)
        
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("7001, 7002, 7003...")
        self.port_input.setMinimumHeight(40)
        layout.addWidget(self.port_input)
        
        layout.addSpacing(10)
        
        # Bouton de connexion
        connect_btn = QPushButton("Se connecter")
        connect_btn.setMinimumHeight(45)
        connect_btn.clicked.connect(self.validate_and_connect)
        layout.addWidget(connect_btn)
        
        self.setLayout(layout)
        
        # Enter pour valider
        self.username_input.returnPressed.connect(self.validate_and_connect)
        self.port_input.returnPressed.connect(self.validate_and_connect)
        
    def validate_and_connect(self):
        username = self.username_input.text().strip()
        port_text = self.port_input.text().strip()
        
        if not username:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un nom d'utilisateur")
            return
            
        if not port_text:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un port")
            return
            
        try:
            port = int(port_text)
            if port < 1024 or port > 65535:
                QMessageBox.warning(self, "Erreur", "Le port doit être entre 1024 et 65535")
                return
        except ValueError:
            QMessageBox.warning(self, "Erreur", "Le port doit être un nombre")
            return
            
        self.username = username
        self.port = port
        self.accept()


class ChatClient:
    """Gestion de la connexion et communication avec le Master"""
    
    def __init__(self):
        self.username = None
        self.port = None
        self.public_key = None
        self.master_socket = None
        self.running = False
        self.signals = MessageSignals()
        
    def register(self, username, port):
        """Inscription avec le Master"""
        self.username = username
        self.port = port
        
        # Vérifier si le port est disponible
        try:
            test_sock = socket.socket()
            test_sock.bind(("127.0.0.1", self.port))
            test_sock.close()
        except OSError:
            return False, f"Port {self.port} déjà utilisé"
        
        try:
            # Connexion au Master
            self.master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.master_socket.settimeout(10.0)
            self.master_socket.connect((MASTER_IP, MASTER_PORT))
            
            # Identifier en tant que Client
            self.master_socket.send(b"CLIENT")
            time.sleep(0.1)
            
            # Envoyer les données d'inscription
            reg_data = f"{self.username}::127.0.0.1::{self.port}"
            self.master_socket.send(reg_data.encode())
            
            # Réponse du Master
            response = self.master_socket.recv(1024).decode()
            
            if response.startswith("OK:"):
                _, e_str, n_str = response.split(":")
                self.public_key = (int(e_str), int(n_str))
                self.master_socket.settimeout(None)
                return True, "Connexion réussie"
            else:
                return False, f"Échec: {response}"
                
        except ConnectionRefusedError:
            return False, "Impossible de se connecter au serveur Master"
        except socket.timeout:
            return False, "Délai de connexion dépassé"
        except Exception as e:
            return False, f"Erreur: {e}"
    
    def get_online_users(self):
        """Liste des utilisateurs en ligne"""
        try:
            self.master_socket.send(b"LIST")
            response = self.master_socket.recv(1024).decode()
            
            if response.startswith("ONLINE:"):
                users = response[7:].split(",")
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
            
            if response.startswith("ERROR") or "||" not in response:
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
        user_info = self.get_user_info(target_user)
        
        if not user_info:
            return False, f"Utilisateur '{target_user}' introuvable"
        
        routers, target_info = self.request_path(target_user, nb_layers)
        
        if not routers:
            return False, "Impossible d'obtenir un chemin"
        
        complete_message = f"{self.username}:{message}"
        onion = self.build_onion(complete_message, routers, target_info)
        
        first_router = routers[0]
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((first_router["ip"], first_router["port"]))
            sock.send(onion.encode())
            sock.close()
            
            return True, f"Envoyé via {len(routers)} routeur(s)"
            
        except Exception as e:
            return False, f"Erreur d'envoi: {e}"
    
    def listen_for_messages(self):
        """Écoute des messages entrants"""
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", self.port))
            server.listen(5)
            
            while self.running:
                try:
                    conn, addr = server.accept()
                    data = conn.recv(8192).decode()
                    conn.close()
                    
                    if data and ":" in data:
                        sender, message = data.split(":", 1)
                        current_time = datetime.now().strftime("%H:%M")
                        self.signals.message_received.emit(sender, message, current_time)
                        
                except:
                    if not self.running:
                        break
                    pass
                
        except Exception as e:
            self.signals.error_occurred.emit(f"Erreur d'écoute: {e}")
        finally:
            if 'server' in locals():
                server.close()
    
    def keep_alive(self):
        """Maintien de la connexion"""
        while self.running:
            try:
                if self.master_socket:
                    self.master_socket.send(b"PING")
                    response = self.master_socket.recv(1024)
                    if response != b"PONG":
                        self.running = False
                        self.signals.connection_lost.emit()
            except:
                self.running = False
                self.signals.connection_lost.emit()
            
            time.sleep(30)
    
    def start(self):
        """Démarrer les threads"""
        self.running = True
        threading.Thread(target=self.listen_for_messages, daemon=True).start()
        threading.Thread(target=self.keep_alive, daemon=True).start()
    
    def stop(self):
        """Arrêter proprement"""
        self.running = False
        if self.master_socket:
            try:
                self.master_socket.send(b"QUIT")
                self.master_socket.close()
            except:
                pass


class ChatWindow(QMainWindow):
    """Fenêtre principale de chat"""
    
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.current_recipient = None
        
        # Connecter les signaux
        self.client.signals.message_received.connect(self.on_message_received)
        self.client.signals.connection_lost.connect(self.on_connection_lost)
        self.client.signals.error_occurred.connect(self.on_error)
        
        self.init_ui()
        self.update_user_list()
        
    def init_ui(self):
        self.setWindowTitle(f"Onion Chat - {self.client.username}")
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
        
        # Indicateur de connexion
        connection_status = QLabel("● Connecté")
        connection_status.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 14px;")
        header_layout.addWidget(connection_status)
        
        header_layout.addStretch()
        
        # Bouton de déconnexion
        disconnect_btn = QPushButton("✕ Déconnexion")
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
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedWidth(50)
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
        self.layers_input.setFixedWidth(50)
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
            if nb_layers < 1 or nb_layers > 5:
                QMessageBox.warning(self, "Erreur", "Le nombre de couches doit être entre 1 et 5")
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
        
        # NOUVELLE VERSION : Plus simple et plus fiable
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

    def on_connection_lost(self):
        """Connexion perdue"""
        QMessageBox.warning(self, "Connexion perdue", "La connexion au serveur a été perdue")
    
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


def main():
    """Point d'entrée de l'interface graphique"""
    app = QApplication(sys.argv)
    
    # Fenêtre de connexion
    login = LoginWindow()
    if login.exec() != QDialog.DialogCode.Accepted:
        return
    
    # Créer le client et se connecter
    client = ChatClient()
    success, message = client.register(login.username, login.port)
    
    if not success:
        QMessageBox.critical(None, "Erreur de connexion", message)
        return
    
    # Démarrer le client
    client.start()
    
    # Afficher la fenêtre de chat
    chat_window = ChatWindow(client)
    chat_window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
