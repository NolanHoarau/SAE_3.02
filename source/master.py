import socket

routers = []
clients = []

master = socket.socket(socket.AF_INET, socket.SOCKET_STREAM)
master.bind(("localhost", 63000))
master.listen(20)


