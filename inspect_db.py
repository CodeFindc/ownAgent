
import sqlite3
import os

if not os.path.exists("auth.db"):
    print("auth.db does not exist!")
else:
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("Columns in users table:")
    for col in columns:
        print(col)
    conn.close()
