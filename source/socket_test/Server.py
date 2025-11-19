import socket

# Crée le socket du serveur
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("localhost", 63000))  # Machine locale, port 63000
server.listen(1)   # Attend 1 connexion

print("Serveur en attente...")
client_socket, address = server.accept()
print("Connexion de", address)
message = client_socket.recv(1024)  # Reçoit 1024 octets max
print("Message recu:", message.decode())
client_socket.close()
server.close()

