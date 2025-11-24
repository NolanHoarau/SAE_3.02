## Groupe

Nom du groupe : Axolotl \
Participants :
- HOARAU Nolan
- RABAH Soumaya

---
## Socket

Un **socket** est un point de communication qui permet à deux programmes (sur le même ordinateur ou sur des machines différentes) d’échanger des données par le réseau. En Python, tout se fait avec le module standard `socket`.

### Les bases

*Pour un Serveur et un client :*

Serveur :
```python
import socket

# Crée le socket du serveur
serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serveur.bind(("localhost", 63000))  # Machine locale, port 63000
serveur.listen(1)   # Attend 1 connexion

print("Serveur en attente...")
client_socket, adresse = serveur.accept()
print("Connexion de", adresse)
message = client_socket.recv(1024)  # Reçoit 1024 octets max
print("Message recu:", message.decode())
client_socket.close()
serveur.close()
```


| Fonctions / Méthodes | Description                                                               |
| -------------------- | ------------------------------------------------------------------------- |
| `socket.socket(...)` | créer le socket (TCP ou UDP)                                              |
| `bind((ip, port))`   | elle contient un tuple qui associe le socket à une adresse/port (serveur) |
| `listen(n)`          | attends une ou plusieurs connexions entrante                              |
| `accept()`           | elle accepte la connexion entrante                                        |
| `recv(n)`            | recoit des données avec `n` octets                                        |
| `decode()`           | converti des octets (données binaires) en chaine de caractère (unicode)   |
| `close()`            | ferme la connexion                                                        |

Client :
```python
import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("localhost", 63000))   # Connecte sur machine locale, port 63000
client.send(b"Salut le serveur !")
client.close()
```

| Fonctions / Méthodes | Description                                                               |
| -------------------- | ------------------------------------------------------------------------- |
| `connect()`          | elle contient un tuple pour se connecter à une addresse/port d'un serveur |
| `send(b"data")`      | envoie des données en binaire (octets)                                    |

Le module **socket** éhange des données sous forme d'octets (**données binaires**) et non de chaines de caractères donc on utilise `b"data"` pour envoyer des données binaire et la fonction `decode()` pour convertir ce message (en octets) en chaine de caractères (**unicode**).

| Serveur                                                                                                                 | CLient              |
| ----------------------------------------------------------------------------------------------------------------------- | ------------------- |
| $ python3 Server.py<br><br>Serveur en attente...<br>Connexion de ('127.0.0.1', 62674)<br>Message recu: salut le serveur | $ python3 Client.py |

## Les Threads

| Fonctions / Méthodes           | Description                                                        |
| ------------------------------ | ------------------------------------------------------------------ |
| `Thread(target=..., args=...)` | Crée un nouveau thread qui lancera une fonction avec des arguments |
| `start()`                      | Démarre l’exécution du thread                                      |
| `join()`                       | Attend que le thread se termine avant de continuer                 |
| `current_thread()`             | Renvoie le thread en cours d’exécution                             |
| `active_count()`               | Nombre de threads vivants actuellement                             |
| `Lock()`                       | Crée un verrou pour synchroniser l’accès à une ressource partagée  |
| `is_alive()`                   | Vérifie si un thread est encore en exécution                       |
| `getName()/setName()`          | Donne ou change le nom d’un thread                                 |
```python
import threading

def tache():
    # ici la tache a faire

mon_thread = threading.Thread(target=tache)
mon_thread.start()
mon_thread.join()
```