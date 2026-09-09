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
        try:
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
        except(FileNotFoundError, PermissionError):
            continue

    connection.commit()
    connection.close()

def get_available_drives():
    drives=[]
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(f"{letter}:")

    return drives

def search_files(query, drive=None, sort_by="relevance"):

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    query = query or ""

    sql = """
        SELECT file_name, file_path, size, last_modified
        FROM files
        WHERE file_name LIKE ?
    """

    parameters = [f"%{query}%"]

    # Drive filter
    if drive and drive != "all":

        sql += """
            AND UPPER(file_path) LIKE ?
        """

        parameters.append(f"{drive.upper()}%")

    # Sorting
    if sort_by == "name_asc":

        sql += " ORDER BY file_name COLLATE NOCASE ASC"

    elif sort_by == "name_desc":

        sql += " ORDER BY file_name COLLATE NOCASE DESC"

    elif sort_by == "size_asc":

        sql += " ORDER BY size ASC"

    elif sort_by == "size_desc":

        sql += " ORDER BY size DESC"

    elif sort_by == "modified_newest":

        sql += " ORDER BY last_modified DESC"

    elif sort_by == "modified_oldest":

        sql += " ORDER BY last_modified ASC"

    elif sort_by == "type":

        sql += " ORDER BY extension COLLATE NOCASE ASC"

    else:
        # Default / relevance
        sql += " ORDER BY file_name COLLATE NOCASE ASC"

    cursor.execute(sql, parameters)

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

        formatted_date = datetime.fromtimestamp(
            last_modified
        ).strftime("%d %b %Y, %I:%M %p")

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