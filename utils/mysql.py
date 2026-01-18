import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pymysql
from pymysql.cursors import DictCursor
from settings import DB_DATABASE, DB_HOST, DB_PASSWORD, DB_PORT, DB_USER

def connect():
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_DATABASE,
        port=DB_PORT,
        charset='utf8mb4',
        cursorclass=DictCursor
    )
    return connection

if __name__ == "__main__":
    conn = connect()
    with conn.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print("Database version:", version)
    conn.close()