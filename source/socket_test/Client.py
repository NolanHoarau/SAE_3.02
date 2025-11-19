import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("localhost", 63000)) # Connecte sur la machine local, port 63000
client.send(b"salut le serveur")
client.close()
