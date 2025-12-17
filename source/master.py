# master.py
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
    """Generate RSA public/private key pair"""
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
    """Check if a number is prime"""
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
    """Get database connection"""
    try:
        conn = mariadb.connect(**DB_CONFIG)
        return conn
    except mariadb.Error as e:
        print(f"[MASTER] ❌ Database Error: {e}")
        return None

# ---------- INIT ----------
routers = []  # List of available routers
users = {}    # Active users: username -> {ip, port, public_key, socket}
online_users = {}  # For quick lookup

# ---------- INIT ----------
# Ajoutez cette fonction AVANT load_routers()
def clear_database_tables():
    """Clear all tables in the database on startup"""
    db = get_db()
    if db:
        cur = db.cursor()
        try:
            # Récupérer toutes les tables de la base de données
            cur.execute("SHOW TABLES")
            tables = cur.fetchall()
            
            if tables:
                print(f"[MASTER] 🧹 Clearing {len(tables)} tables...")
                
                # Désactiver les contraintes de clé étrangère temporairement
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                
                # Vider chaque table
                for table in tables:
                    table_name = table[0]
                    cur.execute(f"TRUNCATE TABLE {table_name}")
                    print(f"[MASTER]   Cleared table: {table_name}")
                
                # Réactiver les contraintes
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
                db.commit()
                print(f"[MASTER] ✅ All tables cleared successfully")
            else:
                print(f"[MASTER] ℹ️  No tables found in database")
                
        except mariadb.Error as e:
            print(f"[MASTER] ❌ Error clearing tables: {e}")
            db.rollback()
        finally:
            db.close()
    else:
        print("[MASTER] ⚠️  Could not connect to database for cleanup")

def load_routers():
    """Load routers from database at startup"""
    global routers
    db = get_db()
    if db:
        cur = db.cursor()
        try:
            cur.execute("SELECT id, ip, port, e, n, d FROM routers")
            for r in cur.fetchall():
                routers.append({
                    "id": r[0],
                    "ip": r[1],
                    "port": r[2],
                    "e": r[3],
                    "n": r[4],
                    "d": r[5]
                })
            print(f"[MASTER] 📊 {len(routers)} routers loaded from database")
        except mariadb.Error as e:
            print(f"[MASTER] ℹ️  No routers in database yet (first run)")
        finally:
            db.close()
    else:
        print("[MASTER] ⚠️  Could not connect to database")

# ---------- HANDLERS ----------
def handle_router(conn):
    """Handle router registration"""
    try:
        # Receive router information
        data = conn.recv(1024).decode().strip()
        print(f"[MASTER] Router registration: {data}")
        
        if ";" in data:
            ip, port = data.split(";")
            port = int(port)

            # Generate RSA keys for this router
            pub, priv = generate_keys()
            e, n = pub
            d, _ = priv

            # Save to database
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

                # Add to active routers list
                router_info = {
                    "id": router_id,
                    "ip": ip,
                    "port": port,
                    "e": e,
                    "n": n,
                    "d": d
                }
                routers.append(router_info)

                # Send private key to router
                response = f"{d};{n}"
                conn.send(response.encode())
                print(f"[MASTER] ✅ Router {ip}:{port} registered (ID: {router_id})")
            else:
                conn.send(b"ERROR:DB_CONNECTION")
        else:
            conn.send(b"ERROR:INVALID_FORMAT")
            
    except Exception as e:
        print(f"[MASTER] ❌ Router handler error: {e}")
        conn.send(b"ERROR:INTERNAL")
    finally:
        conn.close()

def handle_client(conn):
    """Handle client connection and registration"""
    username = None
    
    try:
        # Set initial timeout for registration
        conn.settimeout(10.0)
        
        # Receive client registration data
        data = conn.recv(1024).decode().strip()
        print(f"[MASTER] Client registration: {data}")
        
        if "::" in data:
            parts = data.split("::")
            if len(parts) >= 3:
                username = parts[0]
                ip = parts[1]
                port = int(parts[2])
                
                # Generate RSA keys for user
                pub, _ = generate_keys()
                e, n = pub
                
                # Save user to database
                db = get_db()
                if not db:
                    conn.send(b"ERROR:DB_CONNECTION")
                    conn.close()
                    return
                
                cur = db.cursor()
                
                # Check if user already exists
                cur.execute("SELECT username FROM users WHERE username = ?", (username,))
                if cur.fetchone():
                    # Update existing user
                    cur.execute("""
                        UPDATE users SET 
                        ip=?, port=?, public_key_e=?, public_key_n=?, is_online=TRUE,
                        last_seen=NOW()
                        WHERE username=?
                    """, (ip, port, e, n, username))
                else:
                    # Insert new user
                    cur.execute("""
                        INSERT INTO users 
                        (username, ip, port, public_key_e, public_key_n, is_online)
                        VALUES (?, ?, ?, ?, ?, TRUE)
                    """, (username, ip, port, e, n))
                
                db.commit()
                db.close()
                
                # Store in memory
                users[username] = {
                    "ip": ip,
                    "port": port,
                    "public_key": (e, n),
                    "socket": conn
                }
                online_users[username] = True
                
                # Send success response with public key
                response = f"OK:{e}:{n}"
                conn.send(response.encode())
                print(f"[MASTER] ✅ User '{username}' registered at {ip}:{port}")
                
                # Remove timeout for command loop
                conn.settimeout(None)
                
                # Command loop
                try:
                    while True:
                        cmd_data = conn.recv(1024).decode().strip()
                        
                        # Check if client disconnected
                        if not cmd_data:
                            print(f"[MASTER] 📤 Client '{username}' disconnected")
                            break
                        
                        # Handle commands
                        if cmd_data == "QUIT":
                            print(f"[MASTER] 👋 Client '{username}' quit")
                            break
                            
                        elif cmd_data == "LIST":
                            # List online users
                            user_list = list(users.keys())
                            response = f"ONLINE:{','.join(user_list)}"
                            conn.send(response.encode())
                            print(f"[MASTER] Sent user list to '{username}'")
                            
                        elif cmd_data.startswith("GET:"):
                            # Get user info
                            target = cmd_data[4:]
                            if target in users:
                                info = users[target]
                                e, n = info["public_key"]
                                response = f"USER:{info['ip']}:{info['port']}:{e}:{n}"
                            else:
                                response = "NOT_FOUND"
                            conn.send(response.encode())
                            
                        elif cmd_data.startswith("PATH:"):
                            # Request path for onion routing
                            # Format: PATH:sender:layers:target
                            _, sender, layers_str, target = cmd_data.split(":", 3)
                            layers = int(layers_str)
                            
                            # Validate target
                            if target not in users:
                                conn.send(b"ERROR:TARGET_NOT_FOUND")
                                continue
                                
                            # Validate layers
                            if layers > len(routers):
                                layers = len(routers)
                                
                            if layers <= 0:
                                conn.send(b"ERROR:NO_ROUTERS_AVAILABLE")
                                continue
                            
                            # Create random path through routers
                            path_routers = random.sample(routers, layers)
                            target_info = users[target]
                            
                            # Build path string
                            path_str = "|".join([
                                f"{r['ip']};{r['port']};{r['e']};{r['n']}" 
                                for r in path_routers
                            ])
                            
                            # Build target info
                            target_str = f"{target_info['ip']};{target_info['port']}"
                            
                            # Send complete response
                            response = f"{path_str}||{target_str}"
                            conn.send(response.encode())
                            print(f"[MASTER] 🛣️  Path created: {sender} -> {target} ({layers} hops)")
                            
                        elif cmd_data == "PING":
                            # Keep-alive ping
                            conn.send(b"PONG")
                            
                        else:
                            conn.send(b"ERROR:UNKNOWN_COMMAND")
                            
                except ConnectionResetError:
                    print(f"[MASTER] 🔌 Client '{username}' connection reset")
                except Exception as e:
                    print(f"[MASTER] ❌ Command error for '{username}': {type(e).__name__}")
                
            else:
                conn.send(b"ERROR:INVALID_DATA")
        else:
            conn.send(b"ERROR:INVALID_FORMAT")
            
    except socket.timeout:
        print(f"[MASTER] ⏰ Registration timeout for client")
    except Exception as e:
        print(f"[MASTER] ❌ Client handler error: {type(e).__name__}: {e}")
    finally:
        # Cleanup
        if username and username in users:
            del users[username]
        if username and username in online_users:
            del online_users[username]
        
        # Update database
        if username:
            db = get_db()
            if db:
                cur = db.cursor()
                cur.execute("UPDATE users SET is_online = FALSE WHERE username = ?", (username,))
                db.commit()
                db.close()
        
        conn.close()
        if username:
            print(f"[MASTER] 🧹 Cleaned up client '{username}'")

# ---------- MAIN SERVER ----------
def main():
    """Main server function"""
    print("\n" + "="*60)
    print("ONION ROUTING MASTER SERVER")
    print("="*60)

    # Effacer toutes les tables au démarrage
    clear_database_tables()

    # Load routers from database
    load_routers()
    
    # Try different ports if needed
    ports_to_try = [6000, 6001, 6002, 7000]
    server = None
    
    for port in ports_to_try:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", port))
            server.listen(10)
            
            print(f"\n[MASTER] ✅ Server started on 127.0.0.1:{port}")
            print(f"[MASTER] 📊 Available routers: {len(routers)}")
            print(f"[MASTER] 👤 Online users: {len(users)}")
            print(f"[MASTER] 📡 Waiting for connections...")
            print("-" * 60)
            break
            
        except OSError as e:
            if port == ports_to_try[-1]:
                print(f"\n[MASTER] ❌ Could not bind to any port")
                print(f"[MASTER] Error: {e}")
                print("[MASTER] Try: sudo kill $(sudo lsof -t -i:6000-7000)")
                sys.exit(1)
            print(f"[MASTER] ⚠️  Port {port} busy, trying next...")
            continue
    
    # Main accept loop
    while True:
        try:
            conn, addr = server.accept()
            print(f"\n[MASTER] 🔗 New connection from {addr}")
            
            # Get connection type with timeout
            conn.settimeout(5.0)
            try:
                typ_data = conn.recv(10).decode().strip()
                print(f"[MASTER] Connection type: {typ_data}")
                
                if typ_data == "ROUTER":
                    print(f"[MASTER] 🚦 New router from {addr}")
                    threading.Thread(target=handle_router, args=(conn,), daemon=True).start()
                elif typ_data == "CLIENT":
                    print(f"[MASTER] 👤 New client from {addr}")
                    threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
                else:
                    print(f"[MASTER] ❓ Unknown type: {typ_data}")
                    conn.send(b"ERROR:UNKNOWN_TYPE")
                    conn.close()
                    
            except socket.timeout:
                print(f"[MASTER] ⏰ Connection timeout from {addr}")
                conn.close()
                
        except KeyboardInterrupt:
            print("\n\n[MASTER] 🛑 Shutdown requested...")
            break
        except Exception as e:
            print(f"[MASTER] ❌ Accept error: {type(e).__name__}: {e}")
            continue
    
    # Clean shutdown
    if server:
        server.close()
    print("[MASTER] 👋 Server stopped")

if __name__ == "__main__":
    main()
