# Chat routage en oignon

Système de messagerie sécurisé avec routage en oignon et chiffrement RSA multi-couches.

---
## Groupe

Nom du groupe : Axolotl \
Participants :
- HOARAU Nolan
- RABAH Soumaya

---

##  Installation Rapide

### Linux/Debian
```bash
# Installer les dépendances
sudo apt update
sudo apt install -y libmariadb-dev python3-venv python3-dev build-essential mariadb-server

# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les packages Python
pip install -r requirements.txt
```

### Windows
1. Installer Python: https://www.python.org/downloads/
2. Installer MariaDB: https://mariadb.org/download/

```powershell
# Créer l'environnement virtuel
python -m venv venv
venv\Scripts\activate

# Installer les packages Python
pip install -r requirements.txt
```

## Configuration Base de Données

```bash
# Se connecter à MariaDB
mysql -u root -p

# Exécuter ces commandes
CREATE DATABASE routage_oignon;
CREATE USER 'routage_user'@'localhost' IDENTIFIED BY 'wxcvbn%!';
GRANT ALL PRIVILEGES ON routage_oignon.* TO 'routage_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

## Démarrage

**IMPORTANT: Démarrer dans cet ordre**

### 1. Master Server (VM 1)
```bash
source venv/bin/activate  # Linux
venv\Scripts\activate     # Windows

python master.py
# Choisir: 1 (GUI) ou 2 (CLI)
```

### 2. Routeurs (VM 2) - 3 recommandé ou plus
ouvrir un routeur par terminal
```bash
source venv/bin/activate
python router.py
# Port: 5001, 5002, 5003...
```

### 3. Clients (VM 3/4/...)
```bash
source venv/bin/activate
python client.py
# Choisir: 1 (GUI) ou 2 (CLI)
# Port: 7001, 7002...
```

## Utilisation

### Mode GUI Client
- Sélectionner un destinataire dans la liste
- Taper votre message
- choisir le nbr de couches
- Cliquer "Envoyer"

### Mode CLI
```bash
/list                    # Voir les utilisateurs en ligne
/msg bob Salut Bob!      # Envoyer un message
/quit                     # Quitter
```

## Dépannage Rapide

**"Port already in use"**
Vous pouvez choisir un autre port ou alors le stopper manuellement si souhaité :
```bash
# Linux
sudo lsof -i :6000
sudo kill -9 <PID>

# Windows
netstat -ano | findstr :6000
taskkill /PID <PID> /F
```

**"Can't connect to database"**
```bash
# Linux
sudo systemctl start mariadb

# Windows - Services → MariaDB → Démarrer
```

**"Master not available"**
- Vérifier que master.py est lancé
- Vérifier l'IP et port
- Vérifier la connexion entre les machines via un `ping`

## Ports par Défaut

| Composant | Port      |
| --------- | --------- |
| Master    | 6000      |
| Routeurs  | 5001-5099 |
| Clients   | 7001-7099 |

## Architecture

```
CLIENT → ROUTEUR 1 → ROUTEUR 2 → ROUTEUR 3 → CLIENT
         (déchiffre   (déchiffre   (déchiffre
          couche 3)    couche 2)    couche 1)
```

Chaque message est chiffré en plusieurs couches. Chaque routeur ne déchiffre qu'une seule couche, garantissant l'anonymat.

---
## Vidéo

Pour plus de detail vous pouvez regarder la video de demonstration
https://www.youtube.com/watch?v=OQUEaK-J1Cs
