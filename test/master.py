import socket
import threading
import random
import math
import mariadb
import time
import sys
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'database': 'routage_oignon',
    'user': 'routage_user',
    'password': 'wxcvbn%!',
    'port': 3306
}

# ---------- RSA ----------
def generate_keys():
    """Generer cle RSA publique/privee"""
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
    """Verifier si un nombre est premier"""
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
    """Se connecter a la base de donnee"""
    try:
        conn = mariadb.connect(**DB_CONFIG)
        return conn
    except mariadb.Error as e:
        print(f"[MASTER] X Database Error: {e}")
        return None

# ---------- INIT ----------
routers = []  # Liste des routeurs disponible
users = {}    # Utilisateurs actif : nom -> {ip, port, public_key, socket}
online_users = {}

# ---------- INIT ----------
def clear_database_tables():
    """Nettoyer toutes les tables dans la base de donnees au lancement"""
    db = get_db()
    if db:
        cur = db.cursor()
        try:
            # Recuperer toutes les tables de la base de donnees
            cur.execute("SHOW TABLES")
            tables = cur.fetchall()
            
            if tables:
                print(f"[MASTER] Clearing {len(tables)} tables...")
                
                # Desactiver les contraintes de cle etrangere temporairement
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                
                # Vider chaque table
                for table in tables:
                    table_name = table[0]
                    cur.execute(f"TRUNCATE TABLE {table_name}")
                    print(f"[MASTER]   Cleared table: {table_name}")
                
                # Reactiver les contraintes
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

# ---------- HANDLERS ----------
def handle_router(conn):
    """Gerer l'enregistrement des routeurs"""
    try:
        # Recevoir les infos du routeur
        data = conn.recv(1024).decode().strip()
        print(f"[MASTER] Router registration: {data}")
        
        if ";" in data:
            ip, port = data.split(";")
            port = int(port)

            # Generation de cles RSA pour ce routeur
            pub, priv = generate_keys()
            e, n = pub
            d, _ = priv

            # Sauvegarde sur la base de donnee
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

                # Ajout des infos dans la liste routers
                router_info = {
                    "id": router_id,
                    "ip": ip,
                    "port": port,
                    "e": e,
                    "n": n,
                    "d": d
                }
                routers.append(router_info)

                # Envoyer cle privee au routeur
                response = f"{d};{n}"
                conn.send(response.encode())
                print(f"[MASTER] Router {ip}:{port} registered (ID: {router_id})")
            else:
                conn.send(b"ERROR:DB_CONNECTION")
        else:
            conn.send(b"ERROR:INVALID_FORMAT")
            
    except Exception as e:
        print(f"[MASTER] X Router handler error: {e}")
        conn.send(b"ERROR:INTERNAL")
    finally:
        conn.close()

def handle_client(conn):
    """Gerer la connexion et l'enregistrement du Client"""
    username = None
    
    try:
        # Mettre un delai de depassement pour l'enregistrement
        conn.settimeout(10.0)
        
        # Recevoir les donnees d'enregistrement du client
        data = conn.recv(1024).decode().strip()
        print(f"[MASTER] Client registration: {data}")
        
        if "::" in data:
            parts = data.split("::")
            if len(parts) >= 3:
                username = parts[0]
                ip = parts[1]
                port = int(parts[2])
                
                # Generation des cles RSA pour les utilisateurs
                pub, _ = generate_keys()
                e, n = pub
                
                # Sauvegarder les utilisateurs dans la base de donnee
                db = get_db()
                if not db:
                    conn.send(b"ERROR:DB_CONNECTION")
                    conn.close()
                    return
                
                cur = db.cursor()
                
                # Verifier si l'utilisateur exciste deja
                cur.execute("SELECT username FROM users WHERE username = ?", (username,))
                if cur.fetchone():
                    # Misse a jour de l'utilisateur existant
                    cur.execute("""
                        UPDATE users SET 
                        ip=?, port=?, public_key_e=?, public_key_n=?, is_online=TRUE,
                        last_seen=NOW()
                        WHERE username=?
                    """, (ip, port, e, n, username))
                else:
                    # Ajout du nouvel utilisateur
                    cur.execute("""
                        INSERT INTO users 
                        (username, ip, port, public_key_e, public_key_n, is_online)
                        VALUES (?, ?, ?, ?, ?, TRUE)
                    """, (username, ip, port, e, n))
                
                db.commit()
                db.close()
                
                # Stocker dans la memoire
                users[username] = {
                    "ip": ip,
                    "port": port,
                    "public_key": (e, n),
                    "socket": conn
                }
                online_users[username] = True
                
                # Envoie du succes avec la cle publique
                response = f"OK:{e}:{n}"
                conn.send(response.encode())
                print(f"[MASTER] User '{username}' registered at {ip}:{port}")
                
                # Supprimer le delais de depassement pour les commandes en boucles
                conn.settimeout(None)
                
                # Commandes en boucle
                try:
                    print("\n")
                    while True:
                        cmd_data = conn.recv(1024).decode().strip()
                        
                        # Verifier si le client est deconnecte
                        if not cmd_data:
                            print(f"[MASTER] Client '{username}' disconnected")
                            break
                        
                        # Gerer les commandes
                        if cmd_data == "QUIT":
                            print(f"[MASTER] Client '{username}' quit")
                            break
                            
                        elif cmd_data == "LIST":
                            # Liste des utilisateurs en ligne
                            user_list = list(users.keys())
                            response = f"ONLINE:{','.join(user_list)}"
                            conn.send(response.encode())
                            print(f"[MASTER] Sent user list to '{username}'")
                            
                        elif cmd_data.startswith("GET:"):
                            # Recevoir les infos de l'utilisateur
                            target = cmd_data[4:]
                            if target in users:
                                info = users[target]
                                e, n = info["public_key"]
                                response = f"USER:{info['ip']}:{info['port']}:{e}:{n}"
                            else:
                                response = "NOT_FOUND"
                            conn.send(response.encode())
                            
                        elif cmd_data.startswith("PATH:"):
                            # Demander le chemin pour le routage en oignon
                            # Format: PATH:sender:layers:target
                            _, sender, layers_str, target = cmd_data.split(":", 3)
                            layers = int(layers_str)
                            
                            # Valider la cible
                            if target not in users:
                                conn.send(b"ERROR:TARGET_NOT_FOUND")
                                continue
                                
                            # Valider les couches
                            if layers > len(routers):
                                layers = len(routers)
                                
                            if layers <= 0:
                                conn.send(b"ERROR:NO_ROUTERS_AVAILABLE")
                                continue
                            
                            # Creer un chemin aleatoire de routeurs
                            path_routers = random.sample(routers, layers)
                            target_info = users[target]
                            
                            # Creation du chemin en chaine de caractere
                            path_str = "|".join([
                                f"{r['ip']};{r['port']};{r['e']};{r['n']}" 
                                for r in path_routers
                            ])
                            
                            # Creation des infos de la cible
                            target_str = f"{target_info['ip']};{target_info['port']}"
                            
                            # Envoie la reponse complete
                            response = f"{path_str}||{target_str}"
                            conn.send(response.encode())
                            print(f"[MASTER] Path created: {sender} -> {target} ({layers} hops)")
                            
                        elif cmd_data == "PING":
                            # ping pour garder la connexion
                            conn.send(b"PONG")
                            
                        else:
                            conn.send(b"ERROR:UNKNOWN_COMMAND")
                            
                except ConnectionResetError:
                    print(f"[MASTER] Client '{username}' connection reset")
                except Exception as e:
                    print(f"[MASTER] X Command error for '{username}': {type(e).__name__}")
                
            else:
                conn.send(b"ERROR:INVALID_DATA")
        else:
            conn.send(b"ERROR:INVALID_FORMAT")
            
    except socket.timeout:
        print(f"[MASTER] Registration timeout for client")
    except Exception as e:
        print(f"[MASTER] X Client handler error: {type(e).__name__}: {e}")
    finally:
        # Nettoyage des utilisateurs
        if username and username in users:
            del users[username]
        if username and username in online_users:
            del online_users[username]
        
        # Mise a jour de la base de donnee
        if username:
            db = get_db()
            if db:
                cur = db.cursor()
                cur.execute("UPDATE users SET is_online = FALSE WHERE username = ?", (username,))
                db.commit()
                db.close()
        
        conn.close()
        if username:
            print(f"[MASTER] Cleaned up client '{username}'")

# ---------- MAIN SERVER ----------
def main():
    """fonction main du Master"""
    print("\n" + "="*60)
    print("ONION ROUTING MASTER SERVER")
    print("="*60)

    # Effacer toutes les tables au demarrage
    clear_database_tables()
    
    # Essayer differents ports si besoin
    ports_to_try = [6000, 6001, 6002, 7000]
    server = None
    
    for port in ports_to_try:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", port))
            server.listen(10)
            
            print(f"\n[MASTER] Server started on 127.0.0.1:{port}")
            print(f"[MASTER] Available routers: {len(routers)}")
            print(f"[MASTER] Online users: {len(users)}")
            print(f"[MASTER] Waiting for connections...")
            print("-" * 60)
            break
            
        except OSError as e:
            if port == ports_to_try[-1]:
                print(f"\n[MASTER] X Could not bind to any port")
                print(f"[MASTER] Error: {e}")
                print("[MASTER] Try: sudo kill $(sudo lsof -t -i:6000-7000)")
                sys.exit(1)
            print(f"[MASTER] /!\\ Port {port} busy, trying next...")
            continue
    
    # Boucle d'approbation
    while True:
        try:
            conn, addr = server.accept()
            print(f"\n[MASTER] New connection from {addr}")
            
            # Recevoir le type de connexion a vec delais de depassement
            conn.settimeout(5.0)
            try:
                typ_data = conn.recv(10).decode().strip()
                print(f"[MASTER] Connection type: {typ_data}")
                
                if typ_data == "ROUTER":
                    print(f"[MASTER] New router from {addr}")
                    threading.Thread(target=handle_router, args=(conn,), daemon=True).start()
                elif typ_data == "CLIENT":
                    print(f"[MASTER] New client from {addr}")
                    threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
                else:
                    print(f"[MASTER] ? Unknown type: {typ_data}")
                    conn.send(b"ERROR:UNKNOWN_TYPE")
                    conn.close()
                    
            except socket.timeout:
                print(f"[MASTER] Connection timeout from {addr}")
                conn.close()
                
        except KeyboardInterrupt:
            print("\n\n[MASTER] Shutdown requested...")
            break
        except Exception as e:
            print(f"[MASTER] X Accept error: {type(e).__name__}: {e}")
            continue
    
    # Fermeture propre
    if server:
        server.close()
    print("[MASTER] Server stopped")

if __name__ == "__main__":
    main()
