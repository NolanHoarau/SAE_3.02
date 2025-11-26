import socket
import threading
import random

# Stocke les routeurs présents, chaque entrée : tuple (ip, port, pubkey)
routers = []

def router_register(conn):
    # Reçoit la string : "ip;port;pubkey"
    data = conn.recv(1024).decode()
    ip, port, pubkey = data.split(";")
    routers.append((ip, int(port), pubkey))
    print(f"Routeur enregistré : IP={ip} Port={port}")
    conn.close()

def client_register(conn):
    # Reçoit nb_couches
    while True:    
        data = conn.recv(1024)
        try:
            nb_couches = int(data.decode())
            if nb_couches <= 0 or not isinstance(nb_couches, int):
                raise ValueError("Valeur incorrecte")
            if nb_couches > len(routers):
                conn.send(b"Erreur : Nombre de couches trop grand, pas assez de routeurs dispo")
                continue
        except Exception:
            conn.send(b"Erreur : Entrez un entier strictement positif")
            continue
        break

    if not routers:
        conn.send(b"Pas de routeurs disponibles.")
        conn.close()
        return
    elif nb_couches
    chemin = random.sample(routeurs, nb_couches)
    # Envoie le chemin sous format texte : "ip;port;pubkey|ip;port;pubkey|..."
    chemin_str = "|".join([f"{ip};{port};{pubkey}" for ip, port, pubkey in chemin])
    print(f"Chemin envoyé au client : {chemin_str}")
    conn.send(chemin_str.encode())
    conn.close()

def master_server(ip="0.0.0.0", port=6000):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((ip, port))
    server.listen()
    print(f"Master prêt sur {ip}:{port}")

    while True:
        conn, addr = server.accept()
        typ = conn.recv(32).decode()
        if typ.startswith("ROUTEUR"):
            thread = threading.Thread(target=router_register, args=(conn,))
            thread.start()
        elif typ.startswith("CLIENT"):
            thread = threading.Thread(target=client_register, args=(conn,))
            thread.start()
        else:
            print("Type inconnu reçu :", typ)
            conn.close()

if __name__ == "__main__":
    master_server()

