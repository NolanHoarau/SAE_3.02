# client.py
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
        """Register with the master server"""
        print("\n" + "="*60)
        print("CLIENT REGISTRATION")
        print("="*60)
        
        # Get username
        self.username = input("Enter your username: ")
        
        # Get and validate port
        while True:
            try:
                self.port = int(input("Enter your listening port (e.g., 7001, 7002): "))
                
                # Check if port is available
                try:
                    test_sock = socket.socket()
                    test_sock.bind(("127.0.0.1", self.port))
                    test_sock.close()
                    break
                except OSError:
                    print(f"❌ Port {self.port} is already in use. Please choose another.")
                    
            except ValueError:
                print("❌ Please enter a valid number.")
        
        print(f"\n🔗 Connecting to master at {MASTER_IP}:{MASTER_PORT}...")
        
        try:
            # Connect to master
            self.master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.master_socket.settimeout(10.0)
            self.master_socket.connect((MASTER_IP, MASTER_PORT))
            
            # Identify as client
            self.master_socket.send(b"CLIENT")
            time.sleep(0.1)  # Small delay
            
            # Send registration data
            reg_data = f"{self.username}::127.0.0.1::{self.port}"
            self.master_socket.send(reg_data.encode())
            
            # Get response
            response = self.master_socket.recv(1024).decode()
            
            if response.startswith("OK:"):
                # Extract public key
                _, e_str, n_str = response.split(":")
                self.public_key = (int(e_str), int(n_str))
                
                print(f"\n✅ Successfully registered as '{self.username}'")
                print(f"   📍 Listening on port: {self.port}")
                print(f"   🔑 Public key: ({e_str[:10]}..., {n_str[:10]}...)")
                
                # Remove timeout for normal operation
                self.master_socket.settimeout(None)
                return True
            else:
                print(f"\n❌ Registration failed: {response}")
                return False
                
        except ConnectionRefusedError:
            print("\n❌ Cannot connect to master server.")
            print("   Make sure master.py is running on port 6000")
            return False
        except socket.timeout:
            print("\n❌ Connection timeout.")
            print("   Master server is not responding")
            return False
        except Exception as e:
            print(f"\n❌ Registration error: {type(e).__name__}: {e}")
            return False
    
    def get_online_users(self):
        """Get list of online users from master"""
        try:
            self.master_socket.send(b"LIST")
            response = self.master_socket.recv(1024).decode()
            
            if response.startswith("ONLINE:"):
                users = response[7:].split(",")
                # Filter out empty strings and self
                return [u for u in users if u and u != self.username]
            return []
        except:
            return []
    
    def get_user_info(self, username):
        """Get information about a specific user"""
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
        """Request an onion routing path from master"""
        try:
            # Send path request
            request = f"PATH:{self.username}:{nb_layers}:{target_user}"
            self.master_socket.send(request.encode())
            
            # Get response
            response = self.master_socket.recv(4096).decode()
            
            if response.startswith("ERROR"):
                print(f"   ❌ Path error: {response}")
                return None, None
            
            if "||" not in response:
                print("   ❌ Invalid response format")
                return None, None
            
            # Parse response
            path_part, target_part = response.split("||", 1)
            
            # Parse routers in path
            routers = []
            for hop in path_part.split("|"):
                if hop:
                    ip, port, e, n = hop.split(";")
                    routers.append({
                        "ip": ip,
                        "port": int(port),
                        "pub_key": (int(e), int(n))
                    })
            
            # Parse target information
            target_ip, target_port = target_part.split(";")
            target_info = {
                "ip": target_ip,
                "port": int(target_port)
            }
            
            return routers, target_info
            
        except Exception as e:
            print(f"   ❌ Path request error: {e}")
            return None, None
    
    def encrypt_message(self, message, pub_key):
        """Encrypt message using RSA"""
        e, n = pub_key
        encrypted = []
        for char in message:
            try:
                encrypted.append(pow(ord(char), e, n))
            except:
                # Fallback for large numbers
                encrypted.append(ord(char) % n)
        return encrypted
    
    def build_onion(self, message, routers, target_info):
        """Build onion-encrypted message"""
        # Start with the final message
        current = message
        
        # Add layers from last to first router
        for i in range(len(routers)-1, -1, -1):
            router = routers[i]
            
            # Determine next hop
            if i == len(routers)-1:
                # Last router sends to target
                next_hop = f"{target_info['ip']};{target_info['port']}"
            else:
                # Router sends to next router
                next_router = routers[i+1]
                next_hop = f"{next_router['ip']};{next_router['port']}"
            
            # Create layer: next_hop|encrypted_data
            layer = f"{next_hop}|{current}"
            
            # Encrypt with router's public key
            encrypted = self.encrypt_message(layer, router['pub_key'])
            current = ",".join(str(x) for x in encrypted)
        
        return current
    
    def send_message(self, target_user, message):
        """Send a message to another user"""
        print(f"\n✉️  Preparing message for '{target_user}'...")
        
        # Get target user info
        print(f"   🔍 Looking up '{target_user}'...")
        user_info = self.get_user_info(target_user)
        
        if not user_info:
            print(f"   ❌ User '{target_user}' not found or offline")
            return
        
        # Ask for number of router layers
        while True:
            try:
                nb_layers = int(input(f"   🛣️  Number of router layers (1-3 recommended): "))
                if 1 <= nb_layers <= 5:
                    break
                print("   ⚠️  Please enter a number between 1 and 5")
            except ValueError:
                print("   ⚠️  Please enter a valid number")
        
        # Get routing path
        print(f"   📡 Requesting path from master...")
        routers, target_info = self.request_path(target_user, nb_layers)
        
        if not routers:
            return
        
        print(f"   ✅ Path obtained: {len(routers)} routers")
        
        # Build complete message with sender info
        complete_message = f"{self.username}:{message}"
        
        # Build onion
        print(f"   🧅 Building onion encryption...")
        onion = self.build_onion(complete_message, routers, target_info)
        
        # Send to first router
        first_router = routers[0]
        print(f"   🚀 Sending to first router: {first_router['ip']}:{first_router['port']}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((first_router["ip"], first_router["port"]))
            sock.send(onion.encode())
            sock.close()
            print(f"   ✅ Message sent successfully via {len(routers)} routers!")
            
        except ConnectionRefusedError:
            print(f"   ❌ Router {first_router['ip']}:{first_router['port']} not available")
        except socket.timeout:
            print(f"   ❌ Router connection timeout")
        except Exception as e:
            print(f"   ❌ Send error: {e}")
    
    def listen_for_messages(self):
        """Listen for incoming messages on our port"""
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", self.port))
            server.listen(5)
            
            print(f"\n📨 Message listener started on port {self.port}")
            
            while self.running:
                try:
                    conn, addr = server.accept()
                    
                    # Receive message
                    data = conn.recv(8192).decode()
                    conn.close()
                    
                    if data:
                        # Simple message display
                        if ":" in data:
                            sender, message = data.split(":", 1)
                            print(f"\n" + "="*50)
                            print(f"📩 NEW MESSAGE FROM {sender}")
                            print(f"{'='*50}")
                            print(f"{message}")
                            print(f"{'='*50}")
                        else:
                            print(f"\n📩 Received: {data}")
                        
                        # Show prompt again
                        sys.stdout.write("\n>> ")
                        sys.stdout.flush()
                        
                except:
                    pass
                
        except Exception as e:
            print(f"\n❌ Listener error: {e}")
        finally:
            if 'server' in locals():
                server.close()
    
    def keep_alive(self):
        """Send periodic pings to master to stay connected"""
        while self.running:
            try:
                if self.master_socket:
                    self.master_socket.send(b"PING")
                    response = self.master_socket.recv(1024)
                    if response != b"PONG":
                        print("\n⚠️  Lost connection to master")
                        self.running = False
            except:
                print("\n⚠️  Master connection error")
                self.running = False
            
            time.sleep(30)  # Ping every 30 seconds
    
    def chat_interface(self):
        """Main chat interface"""
        self.running = True
        
        # Start message listener thread
        listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
        listener_thread.start()
        
        # Start keep-alive thread
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
                    print("\n👋 Goodbye!")
                    self.running = False
                    if self.master_socket:
                        self.master_socket.send(b"QUIT")
                        self.master_socket.close()
                    break
                    
                elif cmd == "/list":
                    users = self.get_online_users()
                    if users:
                        print(f"\n👥 Online users ({len(users)}):")
                        for user in users:
                            print(f"  • {user}")
                    else:
                        print("\n📭 No other users online")
                    
                elif cmd.startswith("/msg "):
                    parts = cmd.split(" ", 2)
                    if len(parts) >= 2:
                        target = parts[1]
                        message = parts[2] if len(parts) > 2 else input("Message: ")
                        
                        if target == self.username:
                            print("\n🤔 You cannot message yourself!")
                        elif not message.strip():
                            print("\n⚠️  Message cannot be empty")
                        else:
                            self.send_message(target, message)
                    else:
                        print("\n⚠️  Usage: /msg <username> <message>")
                        
                elif cmd:
                    print(f"\n⚠️  Unknown command: {cmd}")
                    print("   Available: /list, /msg, /quit")
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type /quit to exit properly.")
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    def run(self):
        """Main client function"""
        if not self.register():
            print("\n❌ Registration failed. Exiting.")
            return
        
        self.chat_interface()
        print("\n✅ Client stopped.")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ONION CHAT CLIENT")
    print("="*60)
    
    client = Client()
    client.run()
