import socket
import threading
import time
import sys
import signal

# Configuration par défaut
MASTER_IP = "127.0.0.1"
MASTER_PORT = 6000

ROUTER_IP = "127.0.0.1"  # Sera demandé au démarrage
ROUTER_PORT = None  # Sera demandé au démarrage
private_key = None
router_id = None  # ID du routeur attribué par le master

# ---------- UTILITY FUNCTIONS ----------
def validate_ip(ip):
    """Valide une adresse IPv4"""
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False

# ---------- UNREGISTER ----------
def unregister(master_ip, master_port):
    """Se désincrire du master lors de l'arrêt"""
    global router_id
    
    if router_id is None:
        return False
    
    print(f"\n[ROUTER] Unregistering from master...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((master_ip, master_port))
        
        # Envoyer le type de requête
        sock.send(b"UNREGISTER_ROUTER")
        time.sleep(0.1)
        
        # Envoyer l'ID du routeur
        sock.send(str(router_id).encode())
        
        # Attendre la confirmation
        response = sock.recv(1024).decode().strip()
        sock.close()
        
        if response == "OK":
            print(f"[ROUTER] Successfully unregistered (ID: {router_id})")
            return True
        else:
            print(f"[ROUTER] Unregister response: {response}")
            return False
            
    except Exception as e:
        print(f"[ROUTER] X Unregister error: {type(e).__name__}: {e}")
        return False

# ---------- DECRYPT ----------
def decrypt(cipher_list, priv_key):
    if not priv_key:
        return ""
    d, n = priv_key
    decrypted = []
    for c in cipher_list:
        try:
            # Pour eviter les erreurs avec des grands nombres
            char_code = pow(c, d, n)
            if char_code < 0 or char_code > 1114111:  # Plage Unicode
                char_code = char_code % 256
            decrypted.append(chr(char_code))
        except:
            decrypted.append('?')
    return ''.join(decrypted)

# ---------- REGISTER ----------
def register(master_ip, master_port):
    global private_key, router_id
    print(f"[ROUTER] Connecting to master at {master_ip}:{master_port}...")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)  # Timeout de 10 secondes
            sock.connect((master_ip, master_port))

            # Envoyer le type
            sock.send(b"ROUTER")
            time.sleep(0.5)  # Petite pause

            # Envoyer l'adresse
            address_msg = f"{ROUTER_IP};{ROUTER_PORT}"
            sock.send(address_msg.encode())

            # Recevoir la réponse: ID;d;n
            data = sock.recv(1024).decode().strip()

            if not data:
                print(f"[ROUTER] X Empty response from master (attempt {attempt + 1}/{max_retries})")
                sock.close()
                time.sleep(2)
                continue

            if data.startswith("ERROR"):
                print(f"[ROUTER] X Master error: {data}")
                sock.close()
                return False

            # Parser: ID;d;n
            if ";" in data:
                parts = data.split(";")
                if len(parts) == 3:
                    router_id = int(parts[0])
                    d_str = parts[1]
                    n_str = parts[2]
                    private_key = (int(d_str), int(n_str))
                    sock.close()
                    print(f"[ROUTER] Registered successfully!")
                    print(f"[ROUTER] Router ID: {router_id}")
                    print(f"[ROUTER] Address: {ROUTER_IP}:{ROUTER_PORT}")
                    print(f"[ROUTER] Master: {master_ip}:{master_port}")
                    print(f"[ROUTER] Private key received")
                    return True
                else:
                    print(f"[ROUTER] X Invalid response format: {data}")
                    sock.close()
            else:
                print(f"[ROUTER] X Invalid response format: {data}")
                sock.close()

        except ConnectionRefusedError:
            print(f"[ROUTER] X Master not available (attempt {attempt + 1}/{max_retries})")
            print(f"[ROUTER] Make sure master.py is running on port {master_port}")
            time.sleep(3)
        except ConnectionResetError:
            print(f"[ROUTER] X Connection reset by master (attempt {attempt + 1}/{max_retries})")
            print(f"[ROUTER] Master might be rejecting connections")
            time.sleep(3)
        except socket.timeout:
            print(f"[ROUTER] X Connection timeout (attempt {attempt + 1}/{max_retries})")
            time.sleep(3)
        except Exception as e:
            print(f"[ROUTER] X Error: {type(e).__name__}: {e}")
            time.sleep(3)

    print("[ROUTER] X Failed to register after all attempts")
    return False

# ---------- HANDLE MESSAGES ----------
def handle_connection(conn, addr):
    try:
        data = conn.recv(1048576).decode()  # Un tres grand nombre (2^20) pour que tout le message soit recu
        if not data or private_key is None:
            conn.close()
            return

        print(f"[ROUTER] Received {len(data)} bytes from {addr}")

        # Convertir en liste d'entiers
        cipher_list = []
        parts = data.split(",")
        for part in parts:
            part = part.strip()
            if part:
                try:
                    cipher_list.append(int(part))
                except ValueError:
                    print(f"[ROUTER] Warning: Invalid number '{part}'")

        if not cipher_list:
            print("[ROUTER] No valid data received")
            conn.close()
            return

        # Dechiffrer
        plain = decrypt(cipher_list, private_key)
        if not plain:
            print("[ROUTER] Decryption failed")
            conn.close()
            return

        print(f"[ROUTER] Decrypted: {plain[:100]}...")

        # Parser: next_ip;next_port|encrypted_payload
        if "|" in plain:
            header, payload = plain.split("|", 1)
            if ";" in header:
                next_ip, next_port_str = header.split(";")
                try:
                    next_port = int(next_port_str)
                    # Forwarder au prochain saut
                    print(f"[ROUTER] Forwarding to {next_ip}:{next_port}")
                    forward_sock = socket.socket()
                    forward_sock.settimeout(5)
                    forward_sock.connect((next_ip, next_port))
                    forward_sock.send(payload.encode())
                    forward_sock.close()
                    print(f"[ROUTER] Forwarded successfully")
                except ValueError:
                    print(f"[ROUTER] X Invalid port: {next_port_str}")
                except ConnectionRefusedError:
                    print(f"[ROUTER] X Next hop {next_ip}:{next_port} refused connection")
                except Exception as e:
                    print(f"[ROUTER] X Forward error: {type(e).__name__}: {e}")
            else:
                # Message final
                print(f"[ROUTER] Final message: {payload[:100]}...")
        else:
            print(f"[ROUTER] Received: {plain[:100]}...")

    except Exception as e:
        print(f"[ROUTER] X Handler error: {type(e).__name__}: {e}")
    finally:
        conn.close()

# ---------- SERVER ----------
def start_server():
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ROUTER_IP, ROUTER_PORT))
        server.listen(5)
        print(f"[ROUTER] Listening on {ROUTER_IP}:{ROUTER_PORT}")
        print("[ROUTER] Waiting for messages...")

        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_connection, args=(conn, addr), daemon=True).start()

    except Exception as e:
        print(f"[ROUTER] X Server error: {type(e).__name__}: {e}")
        return False

    return True

# ---------- CLEANUP ----------
# Variables globales pour le cleanup
master_ip_global = None
master_port_global = None

def cleanup_handler():
    """Handler pour nettoyer proprement lors de l'arrêt"""
    global master_ip_global, master_port_global
    if master_ip_global and master_port_global:
        unregister(master_ip_global, master_port_global)

def signal_handler(signum, frame):
    """Handler pour les signaux d'interruption"""
    print("\n[ROUTER] Shutdown signal received...")
    cleanup_handler()
    sys.exit(0)

# ---------- MAIN ----------
def main():
    global ROUTER_IP, ROUTER_PORT, master_ip_global, master_port_global

    print(f"\n{'='*60}")
    print("ROUTER CONFIGURATION")
    print(f"{'='*60}")

    # Demander l'IP du routeur
    while True:
        ip_input = input(f"Enter router IP address (default: {MASTER_IP}): ").strip()
        if ip_input == "":
            ROUTER_IP = MASTER_IP
            break
        elif validate_ip(ip_input):
            ROUTER_IP = ip_input
            break
        else:
            print("X Invalid IP address format. Please use IPv4 format (e.g., 127.0.0.1)")

    # Demander le port du routeur
    while True:
        try:
            port_input = input("Enter router listening port (5001, 5002, 5003...): ")
            port = int(port_input)

            if port < 1024 or port > 65535:
                print("X Port must be between 1024 and 65535")
                continue

            # Vérifier si le port est disponible
            try:
                test_sock = socket.socket()
                test_sock.bind((ROUTER_IP, port))
                test_sock.close()
                ROUTER_PORT = port
                break
            except OSError:
                print(f"X Port {port} on {ROUTER_IP} is already in use. Please choose another.")

        except ValueError:
            print("X Please enter a valid number.")

    # Demander l'IP du Master
    master_ip = MASTER_IP
    while True:
        master_ip_input = input(f"Enter Master server IP (default: {MASTER_IP}): ").strip()
        if master_ip_input == "":
            master_ip = MASTER_IP
            break
        elif validate_ip(master_ip_input):
            master_ip = master_ip_input
            break
        else:
            print("X Invalid IP address format. Please use IPv4 format (e.g., 127.0.0.1)")

    # Demander le port du Master
    master_port = MASTER_PORT
    while True:
        master_port_input = input(f"Enter Master server port (default: {MASTER_PORT}): ").strip()
        if master_port_input == "":
            master_port = MASTER_PORT
            break
        try:
            port_num = int(master_port_input)
            if 1 <= port_num <= 65535:
                master_port = port_num
                break
            else:
                print("X Port must be between 1 and 65535")
        except ValueError:
            print("X Please enter a valid number")

    # Sauvegarder les informations du master pour le cleanup
    master_ip_global = master_ip
    master_port_global = master_port
    import atexit
    # Enregistrer les handlers de nettoyage
    atexit.register(cleanup_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"\n{'='*60}")
    print(f"ROUTER CONFIGURATION SUMMARY")
    print(f"{'='*60}")
    print(f"Router address: {ROUTER_IP}:{ROUTER_PORT}")
    print(f"Master server: {master_ip}:{master_port}")
    print(f"{'='*60}")

    # S'enregistrer auprès du master
    if not register(master_ip, master_port):
        print("[ROUTER] X Cannot continue without registration")
        sys.exit(1)

    print("\n[ROUTER] Press Ctrl+C to stop the router")
    print("[ROUTER] The router will automatically unregister from master\n")

    # Démarrer le serveur
    try:
        if not start_server():
            print("[ROUTER] X Server failed to start")
            cleanup_handler()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n[ROUTER] Keyboard interrupt received")
        cleanup_handler()
        sys.exit(0)

if __name__ == "__main__":
    main()
