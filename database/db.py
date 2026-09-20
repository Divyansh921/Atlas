import sqlite3
from datetime import datetime
import os


# ============================================================
# SAVE FILES
# ============================================================

def save_files(files, location_id):

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
                (
                    file_name,
                    file_path,
                    extension,
                    size,
                    last_modified,
                    indexed_location_id
                )
                VALUES (?, ?, ?, ?, ?, ?)

                ON CONFLICT(file_path)
                DO UPDATE SET

                    file_name = excluded.file_name,
                    extension = excluded.extension,
                    size = excluded.size,
                    last_modified = excluded.last_modified,
                    indexed_location_id = excluded.indexed_location_id

            """, (
                file_name,
                file_path,
                extension,
                size,
                last_modified,
                location_id
            ))

        except (FileNotFoundError, PermissionError):

            continue

    connection.commit()
    connection.close()


# ============================================================
# QUICK SCAN
# ============================================================

def quick_scan_location(location_id):

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()


    # --------------------------------------------------------
    # Get indexed location
    # --------------------------------------------------------

    cursor.execute("""
        SELECT path
        FROM indexed_locations
        WHERE id = ?
    """, (location_id,))

    result = cursor.fetchone()


    if not result:

        connection.close()

        return {
            "error": "Indexed location not found."
        }


    folder = result[0]


    # Import here to avoid circular import
    from scanner.scan import scan_folder


    # --------------------------------------------------------
    # Scan actual folder
    # --------------------------------------------------------

    current_files = scan_folder(folder)

    current_files = set(current_files)


    # --------------------------------------------------------
    # Get files already stored for this location
    # --------------------------------------------------------

    cursor.execute("""
        SELECT file_path, size, last_modified
        FROM files
        WHERE indexed_location_id = ?
    """, (location_id,))


    database_files = {

        row[0]: {
            "size": row[1],
            "last_modified": row[2]
        }

        for row in cursor.fetchall()

    }


    added = 0
    modified = 0
    deleted = 0


    # ========================================================
    # NEW + MODIFIED FILES
    # ========================================================

    for file_path in current_files:

        try:

            file_name = os.path.basename(file_path)
            extension = os.path.splitext(file_path)[1]
            size = os.path.getsize(file_path)
            last_modified = os.path.getmtime(file_path)


            # ------------------------------------------------
            # NEW FILE
            # ------------------------------------------------

            if file_path not in database_files:

                cursor.execute("""
                    SELECT id, size, last_modified, indexed_location_id
                    FROM files
                    WHERE file_path = ?
                """, (file_path,))

                existing_file = cursor.fetchone()


                # File exists somewhere else in database
                if existing_file:

                    old_size = existing_file[1]
                    old_modified = existing_file[2]

                    cursor.execute("""
                        UPDATE files

                        SET
                            file_name = ?,
                            extension = ?,
                            size = ?,
                            last_modified = ?,
                            indexed_location_id = ?

                        WHERE file_path = ?

                    """, (
                        file_name,
                        extension,
                        size,
                        last_modified,
                        location_id,
                        file_path
                    ))


                    if (
                        old_size != size
                        or old_modified != last_modified
                    ):

                        modified += 1


                # Completely new file
                else:

                    cursor.execute("""
                        INSERT INTO files
                        (
                            file_name,
                            file_path,
                            extension,
                            size,
                            last_modified,
                            indexed_location_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        file_name,
                        file_path,
                        extension,
                        size,
                        last_modified,
                        location_id
                    ))

                    added += 1


            # ------------------------------------------------
            # EXISTING FILE
            # ------------------------------------------------

            else:

                old_file = database_files[file_path]


                if (
                    old_file["size"] != size
                    or old_file["last_modified"] != last_modified
                ):

                    cursor.execute("""
                        UPDATE files

                        SET
                            file_name = ?,
                            extension = ?,
                            size = ?,
                            last_modified = ?

                        WHERE file_path = ?
                        AND indexed_location_id = ?

                    """, (
                        file_name,
                        extension,
                        size,
                        last_modified,
                        file_path,
                        location_id
                    ))

                    modified += 1


        except (FileNotFoundError, PermissionError):

            continue


    # ========================================================
    # DELETED FILES
    # ========================================================

    for file_path in database_files:

        if file_path not in current_files:

            cursor.execute("""
                DELETE FROM files

                WHERE file_path = ?
                AND indexed_location_id = ?

            """, (
                file_path,
                location_id
            ))

            deleted += 1


    # ========================================================
    # UPDATE LAST SCANNED
    # ========================================================

    last_scanned = datetime.now().timestamp()


    cursor.execute("""
        UPDATE indexed_locations

        SET last_scanned = ?

        WHERE id = ?

    """, (
        last_scanned,
        location_id
    ))


    connection.commit()
    connection.close()


    return {
        "added": added,
        "modified": modified,
        "deleted": deleted
    }


# ============================================================
# GET INDEXED LOCATIONS
# ============================================================

def get_indexed_locations():

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()


    cursor.execute("""
        SELECT id, path, last_scanned

        FROM indexed_locations

        ORDER BY path
    """)


    locations = cursor.fetchall()

    connection.close()

    return locations


# ============================================================
# SAVE INDEXED LOCATION
# ============================================================

def save_indexed_location(path):

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()


    last_scanned = datetime.now().timestamp()


    cursor.execute("""
        INSERT INTO indexed_locations
        (
            path,
            last_scanned
        )

        VALUES (?, ?)

        ON CONFLICT(path)
        DO UPDATE SET
            last_scanned = excluded.last_scanned

    """, (
        path,
        last_scanned
    ))


    cursor.execute("""
        SELECT id

        FROM indexed_locations

        WHERE path = ?

    """, (
        path,
    ))


    location_id = cursor.fetchone()[0]


    connection.commit()
    connection.close()


    return location_id


# ============================================================
# CREATE DATABASE
# ============================================================

def create_database():

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()


    # Create locations first
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS indexed_locations(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            path TEXT NOT NULL UNIQUE,

            last_scanned REAL

        )
    """)


    # Create files table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            file_name TEXT NOT NULL,

            file_path TEXT NOT NULL UNIQUE,

            extension TEXT,

            size INTEGER,

            last_modified REAL,

            indexed_location_id INTEGER,

            FOREIGN KEY (indexed_location_id)
            REFERENCES indexed_locations(id)

        )
    """)


    connection.commit()
    connection.close()


# ============================================================
# GET AVAILABLE DRIVES
# ============================================================

def get_available_drives():

    drives = []


    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":

        drive = f"{letter}:\\"

        if os.path.exists(drive):

            drives.append(f"{letter}:")


    return drives


# ============================================================
# SEARCH FILES
# ============================================================

def search_files(query, drive=None, sort_by="relevance"):

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()


    query = query or ""

    search_terms = query.split()


    # --------------------------------------------------------
    # Base query
    # --------------------------------------------------------

    sql = """
        SELECT
            file_name,
            file_path,
            size,
            last_modified

        FROM files
    """


    parameters = []


    # --------------------------------------------------------
    # Search terms
    # --------------------------------------------------------

    if search_terms:

        conditions = []


        for term in search_terms:

            conditions.append(
                "file_name LIKE ?"
            )

            parameters.append(
                f"%{term}%"
            )


        sql += " WHERE " + " AND ".join(conditions)


    # --------------------------------------------------------
    # Drive filter
    # --------------------------------------------------------

    if drive and drive != "all":

        if search_terms:

            sql += """
                AND UPPER(file_path) LIKE ?
            """

        else:

            sql += """
                WHERE UPPER(file_path) LIKE ?
            """


        parameters.append(
            f"{drive.upper()}%"
        )


    # --------------------------------------------------------
    # Sorting
    # --------------------------------------------------------

    if sort_by == "name_asc":

        sql += """
            ORDER BY file_name COLLATE NOCASE ASC
        """


    elif sort_by == "name_desc":

        sql += """
            ORDER BY file_name COLLATE NOCASE DESC
        """


    elif sort_by == "size_asc":

        sql += """
            ORDER BY size ASC
        """


    elif sort_by == "size_desc":

        sql += """
            ORDER BY size DESC
        """


    elif sort_by == "modified_newest":

        sql += """
            ORDER BY last_modified DESC
        """


    elif sort_by == "modified_oldest":

        sql += """
            ORDER BY last_modified ASC
        """


    elif sort_by == "type":

        sql += """
            ORDER BY extension COLLATE NOCASE ASC
        """


    else:

        sql += """
            ORDER BY file_name COLLATE NOCASE ASC
        """


    cursor.execute(
        sql,
        parameters
    )


    results = cursor.fetchall()

    connection.close()


    # ========================================================
    # FORMAT RESULTS
    # ========================================================

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
        ).strftime(
            "%d %b %Y, %I:%M %p"
        )


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