import mysql.connector
from mysql.connector import Error


def test_connection():
    try:
        # Connexion à la base de données
        connection = mysql.connector.connect(
            host='localhost',
            database='routage_oignon',
            user='routage_user',
            password='wxcvbn§!'
        )

        if connection.is_connected():
            print("Connexion réussie à la base de données")

            # Créer un curseur
            cursor = connection.cursor()

            # Tester une requête
            cursor.execute("SELECT * FROM routeurs")
            routeurs = cursor.fetchall()

            print(f"Nombre de routeurs trouvés : {len(routeurs)}")
            for routeur in routeurs:
                print(f"  - {routeur}")

            cursor.close()

    except Error as e:
        print(f"Erreur : {e}")

    finally:
        if connection.is_connected():
            connection.close()
            print("Connexion fermée")


if __name__ == "__main__":
    test_connection()