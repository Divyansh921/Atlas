import sqlite3
from datetime import datetime
import os
def create_database ():
    connection = sqlite3.connect("atlas.db")    #open database
    cursor=connection.cursor()
    cursor.execute("""                 --telling SQLite to create the table
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL UNIQUE,
        extension TEXT,
        size INTEGER,
        last_modified REAL
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

            ON CONFLICT(file_path)
            DO UPDATE SET
                file_name = excluded.file_name,
                extension = excluded.extension,
                size = excluded.size,
                last_modified = excluded.last_modified;
                    """, (file_name, file_path, extension, size, last_modified))

    connection.commit()
    connection.close()

def search_files(query):
    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT file_name, file_path, size, last_modified
        FROM files
        WHERE file_name LIKE ?
    """, (f"%{query}%",))

    results = cursor.fetchall()
    connection.close()

    formatted_results = []

    def format_file_size(size):

        if size < 1024:
            return f"{size} B"

        elif size < 1024 ** 2:
            return f"{size / 1024:.2f} KB"

        elif size < 1024 ** 3:
            return f"{size / (1024 ** 2):.2f} MB"

        else:
            return f"{size / (1024 ** 3):.2f} GB"
    for file_name, file_path, size, last_modified in results:

        formatted_date = datetime.fromtimestamp(last_modified).strftime("%d %b %Y, %I:%M %p")
        formatted_size = format_file_size(size)
        formatted_results.append(
            (
                file_name,
                file_path,
                formatted_date,
                formatted_size
            )
        )

    return formatted_results