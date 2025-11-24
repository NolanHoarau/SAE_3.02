import socket
import threading

clients = [] # liste des clients

def connect_devices(connexion, address):
    print("Connecté à :", address)
    clients.append(connexion)
    data = connexion.recv(1024) # recoit max 1024 octets
    print(f"{address[0]} : {data.decode()}")
    connexion.close()

router = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
router.bind(("localhost", 63000)) # association socket a une addresse/port
router.listen(10) # connexions max
print(router)
print("connexion...")

while True:
    connexion, address = router.accept()
    thread = threading.Thread(target=connect_devices, args=(connexion, address))
    thread.start()
