import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("localhost", 63000))
client.send(b"Je suis client")
print(client)
client.close()
