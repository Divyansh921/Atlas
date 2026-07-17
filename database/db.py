import sqlite3
import os
def create_database ():
    connection = sqlite3.connect("atlas.db")    #open database
    cursor=connection.cursor()
    cursor.execute("""                 --telling SQLite to create the table
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        extension TEXT,
        size INTEGER,
        last_modified TEXT
    )
    """)

    connection.commit()   
    connection.close()


def save_files(files):

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    for file_path in files:

        file_name = os.path.basename(file_path)
        extension = os.path.splitext(file_path)[1]
        size = os.path.getsize(file_path)
        last_modified = os.path.getmtime(file_path)
        cursor.execute("""
            INSERT INTO files
            (file_name, file_path, extension, size, last_modified)
            VALUES (?, ?, ?, ?, ?)
        """, (file_name, file_path, extension, size, last_modified))

    connection.commit()
    connection.close()


def search_files(query):
    connection = sqlite3.connect("atlas.db")    #open database
    cursor=connection.cursor()
    cursor.execute("""
        SELECT file_name, file_path, last_modified FROM files WHERE file_name LIKE ?
    """, (f"%{query}%",))
    results = cursor.fetchall()
    connection.close()
    return results