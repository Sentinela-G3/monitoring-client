import psutil
import mysql.connector

cnx = mysql.connector.connect(
    host = "",
    user = "",
    password = "",
    database = ""
)

mycursor = cnx.cursor()

cnx.close()
