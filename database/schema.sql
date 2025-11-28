-- Création de la base de données
CREATE DATABASE IF NOT EXISTS routage_oignon CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE routage_oignon;

-- Table des routeurs
CREATE TABLE routeurs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(50) UNIQUE NOT NULL,
    adresse_ip VARCHAR(45) NOT NULL,
    port INT NOT NULL,
    cle_publique TEXT NOT NULL,
    statut ENUM('actif', 'inactif') DEFAULT 'actif',
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_maj TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Table des clients
CREATE TABLE clients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(50) UNIQUE NOT NULL,
    adresse_ip VARCHAR(45) NOT NULL,
    port INT NOT NULL,
    statut ENUM('connecte', 'deconnecte') DEFAULT 'deconnecte',
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_maj TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Table de routage
CREATE TABLE table_routage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    routeur_id INT NOT NULL,
    destination VARCHAR(50) NOT NULL,
    next_hop VARCHAR(50) NOT NULL,
    interface VARCHAR(20) NOT NULL,
    rule_id INT NOT NULL,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (routeur_id) REFERENCES routeurs(id) ON DELETE CASCADE
);

-- Table des logs
CREATE TABLE logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    routeur_id INT,
    type_evenement ENUM('connexion', 'deconnexion', 'message_recu', 'message_envoye', 'erreur') NOT NULL,
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (routeur_id) REFERENCES routeurs(id) ON DELETE SET NULL
);

-- Table de topologie
CREATE TABLE topologie (
    id INT AUTO_INCREMENT PRIMARY KEY,
    routeur_source_id INT NOT NULL,
    routeur_destination_id INT NOT NULL,
    statut ENUM('actif', 'inactif') DEFAULT 'actif',
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (routeur_source_id) REFERENCES routeurs(id) ON DELETE CASCADE,
    FOREIGN KEY (routeur_destination_id) REFERENCES routeurs(id) ON DELETE CASCADE
);

-- Index pour améliorer les performances
CREATE INDEX idx_routeur_nom ON routeurs(nom);
CREATE INDEX idx_client_nom ON clients(nom);
CREATE INDEX idx_routage_routeur ON table_routage(routeur_id);
CREATE INDEX idx_logs_routeur ON logs(routeur_id);
CREATE INDEX idx_logs_timestamp ON logs(timestamp);