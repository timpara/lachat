import MySQLdb
import os

def user_data():
    conn = MySQLdb.connect(host=os.getenv("SQL_LA_CHAT_HOST"),
                           user = os.getenv("SQL_LA_CHAT_USER"),
                           passwd = os.getenv("SQL_LA_CHAT_PASSWORD"),
                           db = os.getenv("SQL_LA_CHAT_DB"))
    c = conn.cursor()

    return c, conn


