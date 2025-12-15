# router.py - VERSION CORRIGÉE
import socket
import threading
import time
import sys

# CONFIGURATION - CHANGEZ LE PORT POUR CHAQUE INSTANCE !
ROUTER_PORT = 5001  # Changez à 5002, 5003, etc. pour d'autres routeurs
MASTER_IP = "127.0.0.1"
MASTER_PORT = 6000

private_key = None

# ---------- DECRYPT ----------
def decrypt(cipher_list, priv_key):
    if not priv_key:
        return ""
    d, n = priv_key
    decrypted = []
    for c in cipher_list:
        try:
            # Pour éviter les erreurs avec des grands nombres
            char_code = pow(c, d, n)
            if char_code < 0 or char_code > 1114111:  # Plage Unicode
                char_code = char_code % 256
            decrypted.append(chr(char_code))
        except:
            decrypted.append('?')
    return ''.join(decrypted)

# ---------- REGISTER ----------
def register():
    global private_key
    
    print(f"[ROUTER] Connecting to master at {MASTER_IP}:{MASTER_PORT}...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)  # Timeout de 10 secondes
            sock.connect((MASTER_IP, MASTER_PORT))
            
            # Envoyer le type
            sock.send(b"ROUTER")
            time.sleep(0.5)  # Petite pause
            
            # Envoyer l'adresse
            address_msg = f"127.0.0.1;{ROUTER_PORT}"
            sock.send(address_msg.encode())
            
            # Recevoir la clé privée
            data = sock.recv(1024).decode().strip()
            
            if not data:
                print(f"[ROUTER] ❌ Empty response from master (attempt {attempt + 1}/{max_retries})")
                sock.close()
                time.sleep(2)
                continue
                
            if data.startswith("ERROR"):
                print(f"[ROUTER] ❌ Master error: {data}")
                sock.close()
                return False
            
            # Parser la clé privée
            if ";" in data:
                d_str, n_str = data.split(";")
                private_key = (int(d_str), int(n_str))
                sock.close()
                
                print(f"[ROUTER] ✅ Registered successfully!")
                print(f"[ROUTER]   Port: {ROUTER_PORT}")
                print(f"[ROUTER]   Private key received")
                return True
            else:
                print(f"[ROUTER] ❌ Invalid response format: {data}")
                sock.close()
                
        except ConnectionRefusedError:
            print(f"[ROUTER] ❌ Master not available (attempt {attempt + 1}/{max_retries})")
            print(f"[ROUTER]   Make sure master.py is running on port {MASTER_PORT}")
            time.sleep(3)
            
        except ConnectionResetError:
            print(f"[ROUTER] ❌ Connection reset by master (attempt {attempt + 1}/{max_retries})")
            print(f"[ROUTER]   Master might be rejecting connections")
            time.sleep(3)
            
        except socket.timeout:
            print(f"[ROUTER] ❌ Connection timeout (attempt {attempt + 1}/{max_retries})")
            time.sleep(3)
            
        except Exception as e:
            print(f"[ROUTER] ❌ Error: {type(e).__name__}: {e}")
            time.sleep(3)
    
    print("[ROUTER] ❌ Failed to register after all attempts")
    return False

# ---------- HANDLE MESSAGES ----------
def handle_connection(conn, addr):
    try:
        data = conn.recv(8192).decode()
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
        
        # Déchiffrer
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
                    
                    print(f"[ROUTER] ✅ Forwarded successfully")
                    
                except ValueError:
                    print(f"[ROUTER] ❌ Invalid port: {next_port_str}")
                except ConnectionRefusedError:
                    print(f"[ROUTER] ❌ Next hop {next_ip}:{next_port} refused connection")
                except Exception as e:
                    print(f"[ROUTER] ❌ Forward error: {type(e).__name__}: {e}")
            else:
                # Message final
                print(f"[ROUTER] 📨 Final message: {payload[:100]}...")
        else:
            print(f"[ROUTER] 📨 Received: {plain[:100]}...")
            
    except Exception as e:
        print(f"[ROUTER] ❌ Handler error: {type(e).__name__}: {e}")
    finally:
        conn.close()

# ---------- SERVEUR ----------
def start_server():
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", ROUTER_PORT))
        server.listen(5)
        
        print(f"[ROUTER] ✅ Listening on port {ROUTER_PORT}")
        print("[ROUTER] ⏳ Waiting for messages...")
        
        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_connection, args=(conn, addr), daemon=True).start()
            
    except Exception as e:
        print(f"[ROUTER] ❌ Server error: {type(e).__name__}: {e}")
        return False
    return True

# ---------- MAIN ----------
def main():
    print(f"\n{'='*50}")
    print(f"ROUTER ON PORT {ROUTER_PORT}")
    print(f"{'='*50}")
    
    # Vérifier que le port n'est pas déjà utilisé
    try:
        test_sock = socket.socket()
        test_sock.bind(("127.0.0.1", ROUTER_PORT))
        test_sock.close()
    except OSError:
        print(f"[ROUTER] ❌ Port {ROUTER_PORT} is already in use!")
        print(f"[ROUTER]   Try changing ROUTER_PORT in the code")
        sys.exit(1)
    
    # S'enregistrer auprès du master
    if not register():
        print("[ROUTER] ❌ Cannot continue without registration")
        sys.exit(1)
    
    # Démarrer le serveur
    if not start_server():
        print("[ROUTER] ❌ Server failed to start")
        sys.exit(1)

if __name__ == "__main__":
    main()
