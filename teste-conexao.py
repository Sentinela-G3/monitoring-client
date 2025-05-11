import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

AMBIENTE = os.getenv("AMBIENTE", "local")

CONFIG = {
    "local": {
        "host": "127.0.0.1",
        "port": 3307,
        "user": "root",
        "password": "senha123",
        "database": "Sentinela"
    }
}

config_db = {key: CONFIG[AMBIENTE][key] for key in ("host", "user", "password", "database")}

try:
    cnx = mysql.connector.connect(**config_db)
    print("Conexão bem-sucedida com o banco de dados.")
except mysql.connector.Error as err:
    print(f"Erro na conexão: {err}")
