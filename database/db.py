import sqlite3
from datetime import datetime
import os


# ============================================================
# DATABASE CREATION
# ============================================================

def create_database():

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    # --------------------------------------------------------
    # Indexed locations
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS indexed_locations (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            path TEXT NOT NULL UNIQUE,

            last_scanned REAL

        )
    """)

    # --------------------------------------------------------
    # Files
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            file_name TEXT NOT NULL,

            file_path TEXT NOT NULL UNIQUE,

            extension TEXT,

            size INTEGER,

            last_modified REAL,

            indexed_location_id INTEGER,

            FOREIGN KEY(indexed_location_id)
            REFERENCES indexed_locations(id)

        )
    """)

    connection.commit()
    connection.close()


# ============================================================
# SAVE FILES
# ============================================================

def save_files(files, location_id):

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    for file_path in files:

        try:

            file_name = os.path.basename(file_path)

            extension = os.path.splitext(
                file_name
            )[1].lower()

            size = os.path.getsize(
                file_path
            )

            last_modified = os.path.getmtime(
                file_path
            )

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

                    indexed_location_id =
                        excluded.indexed_location_id
            """, (
                file_name,
                file_path,
                extension,
                size,
                last_modified,
                location_id
            ))

        except (
            FileNotFoundError,
            PermissionError,
            OSError
        ):

            continue

    connection.commit()
    connection.close()


# ============================================================
# SAVE INDEXED LOCATION
# ============================================================

def save_indexed_location(path):

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

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
        datetime.now().timestamp()
    ))

    connection.commit()

    cursor.execute("""
        SELECT id
        FROM indexed_locations
        WHERE path = ?
    """, (path,))

    location_id = cursor.fetchone()[0]

    connection.close()

    return location_id


# ============================================================
# GET AVAILABLE DRIVES
# ============================================================

def get_available_drives():

    drives = []

    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":

        drive = f"{letter}:\\"

        if os.path.exists(drive):

            drives.append(drive)

    return drives


# ============================================================
# GET INDEXED LOCATIONS
# ============================================================

def get_indexed_locations():

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            path,
            last_scanned

        FROM indexed_locations
    """)

    locations = cursor.fetchall()

    connection.close()

    return locations


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

    folder_path = result[0]

    # --------------------------------------------------------
    # Get current files from disk
    # --------------------------------------------------------

    current_files = {}

    try:

        for root, dirs, filenames in os.walk(folder_path):

            for filename in filenames:

                full_path = os.path.join(
                    root,
                    filename
                )

                try:

                    current_files[
                        os.path.normcase(
                            os.path.abspath(
                                full_path
                            )
                        )
                    ] = (
                        full_path,
                        os.path.getsize(full_path),
                        os.path.getmtime(full_path)
                    )

                except (
                    FileNotFoundError,
                    PermissionError,
                    OSError
                ):

                    continue

    except (
        FileNotFoundError,
        PermissionError,
        OSError
    ):

        connection.close()

        return {
            "error": "Unable to scan location."
        }

    # --------------------------------------------------------
    # Get files currently stored in database
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            file_path,
            size,
            last_modified

        FROM files

        WHERE indexed_location_id = ?
    """, (location_id,))

    database_files = cursor.fetchall()

    database_map = {}

    for file_id, file_path, size, last_modified in database_files:

        database_map[
            os.path.normcase(
                os.path.abspath(
                    file_path
                )
            )
        ] = (
            file_id,
            file_path,
            size,
            last_modified
        )

    added = 0
    modified = 0
    deleted = 0

    # ========================================================
    # CHECK ADDED + MODIFIED FILES
    # ========================================================

    for normalized_path, file_data in current_files.items():

        full_path, current_size, current_modified = file_data

        # ----------------------------------------------------
        # NEW FILE
        # ----------------------------------------------------

        if normalized_path not in database_map:

            file_name = os.path.basename(
                full_path
            )

            extension = os.path.splitext(
                file_name
            )[1].lower()

            # Because file_path is globally UNIQUE,
            # check whether it already exists somewhere else.

            cursor.execute("""
                SELECT id
                FROM files
                WHERE file_path = ?
            """, (full_path,))

            existing = cursor.fetchone()

            if existing:

                cursor.execute("""
                    UPDATE files

                    SET
                        file_name = ?,
                        extension = ?,
                        size = ?,
                        last_modified = ?,
                        indexed_location_id = ?

                    WHERE id = ?
                """, (
                    file_name,
                    extension,
                    current_size,
                    current_modified,
                    location_id,
                    existing[0]
                ))

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
                    full_path,
                    extension,
                    current_size,
                    current_modified,
                    location_id
                ))

            added += 1

        # ----------------------------------------------------
        # EXISTING FILE
        # ----------------------------------------------------

        else:

            file_id, file_path, old_size, old_modified = (
                database_map[normalized_path]
            )

            if (
                old_size != current_size
                or old_modified != current_modified
            ):

                cursor.execute("""
                    UPDATE files

                    SET
                        size = ?,
                        last_modified = ?

                    WHERE id = ?
                """, (
                    current_size,
                    current_modified,
                    file_id
                ))

                modified += 1

    # ========================================================
    # CHECK DELETED FILES
    # ========================================================

    for normalized_path, file_data in database_map.items():

        file_id = file_data[0]

        if normalized_path not in current_files:

            cursor.execute("""
                DELETE FROM files
                WHERE id = ?
            """, (file_id,))

            deleted += 1

    # ========================================================
    # UPDATE LAST SCANNED
    # ========================================================

    cursor.execute("""
        UPDATE indexed_locations

        SET last_scanned = ?

        WHERE id = ?
    """, (
        datetime.now().timestamp(),
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
# SEARCH FILES
# ============================================================

def search_files(
    query,
    drive=None,
    sort_by="relevance"
):

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    query = query or ""

    search_terms = query.split()

    # ========================================================
    # NORMALIZATION
    # ========================================================

    def normalize_text(text):

        text = text.lower()

        for character in [
            " ",
            "_",
            "-",
            ".",
            "(",
            ")",
            "[",
            "]"
        ]:

            text = text.replace(
                character,
                ""
            )

        return text

    normalized_query = normalize_text(
        query
    )

    normalized_terms = [
        normalize_text(term)
        for term in search_terms
    ]

    # ========================================================
    # BASE QUERY
    # ========================================================

    sql = """
        SELECT
            file_name,
            file_path,
            size,
            last_modified

        FROM files
    """

    parameters = []

    # ========================================================
    # SEARCH CANDIDATES
    #
    # IMPORTANT:
    #
    # SQLite is now given a broader search so that
    #
    # ExamForge
    # Exam Forge
    # Exam_Forge
    # Exam-Forge
    #
    # can all reach the Python relevance system.
    # ========================================================

    if search_terms:

        conditions = []

        # ----------------------------------------------------
        # Search using each original word
        # ----------------------------------------------------

        for term in search_terms:

            conditions.append(
                "file_name LIKE ?"
            )

            parameters.append(
                f"%{term}%"
            )

        # ----------------------------------------------------
        # Also search the filename with separators removed.
        #
        # SQLite cannot easily use our Python normalization,
        # so we remove common separators using REPLACE().
        # ----------------------------------------------------

        normalized_sql_name = """
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                LOWER(file_name),
                                ' ',
                                ''
                            ),
                            '_',
                            ''
                        ),
                        '-',
                        ''
                    ),
                    '.',
                    ''
                ),
                '(',
                ''
            )
        """

        normalized_sql_name = f"""
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                {normalized_sql_name},
                                ')',
                                ''
                            ),
                            '[',
                            ''
                        ),
                        ']',
                        ''
                    ),
                    ' ',
                    ''
                ),
                '\\t',
                ''
            )
        """

        # ----------------------------------------------------
        # The normalized query is added as another candidate
        # search.
        # ----------------------------------------------------

        conditions.append(
            normalized_sql_name + " LIKE ?"
        )

        parameters.append(
            f"%{normalized_query}%"
        )

        sql += " WHERE (" + " OR ".join(
            conditions
        ) + ")"

    # ========================================================
    # DRIVE FILTER
    # ========================================================

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

    # ========================================================
    # SORTING
    # ========================================================

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

        # Relevance is handled below.
        pass

    # ========================================================
    # EXECUTE SEARCH
    # ========================================================

    cursor.execute(
        sql,
        parameters
    )

    results = cursor.fetchall()

    connection.close()

    # ========================================================
    # RELEVANCE SORTING
    # ========================================================

    if sort_by == "relevance" and search_terms:

        def relevance_score(file):

            file_name = file[0]

            # Remove extension for name matching
            name_without_extension = os.path.splitext(
                file_name
            )[0]

            name_lower = name_without_extension.lower()

            normalized_name = normalize_text(
                name_without_extension
            )

            score = 0

            # ------------------------------------------------
            # 1. EXACT NORMALIZED FILENAME
            #
            # ExamForge
            # Exam Forge
            # Exam_Forge
            # Exam-Forge
            #
            # all become:
            #
            # examforge
            # ------------------------------------------------

            if normalized_name == normalized_query:

                score += 1200

            # ------------------------------------------------
            # 2. EXACT PHRASE
            # ------------------------------------------------

            if query.lower() in name_lower:

                score += 500

            # ------------------------------------------------
            # 3. COMBINED WORDS
            # ------------------------------------------------

            combined_query = "".join(
                normalized_terms
            )

            if combined_query in normalized_name:

                score += 450

            # ------------------------------------------------
            # 4. INDIVIDUAL WORD MATCHES
            # ------------------------------------------------

            matched_words = 0

            for term in normalized_terms:

                if term and term in normalized_name:

                    matched_words += 1

                    score += 100

            # ------------------------------------------------
            # 5. MATCH ALL WORDS
            # ------------------------------------------------

            if matched_words == len(
                normalized_terms
            ):

                score += 300

            # ------------------------------------------------
            # 6. CORRECT WORD ORDER / START
            # ------------------------------------------------

            if name_lower.startswith(
                search_terms[0].lower()
            ):

                score += 150

            # ------------------------------------------------
            # 7. SHORTER FILENAMES
            # ------------------------------------------------

            score += max(
                0,
                100 - len(file_name)
            )

            return score

        results.sort(
            key=relevance_score,
            reverse=True
        )

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

    for (
        file_name,
        file_path,
        size,
        last_modified
    ) in results:

        formatted_date = datetime.fromtimestamp(
            last_modified
        ).strftime(
            "%d %b %Y, %I:%M %p"
        )

        formatted_size = format_file_size(
            size
        )

        formatted_results.append(
            (
                file_name,
                file_path,
                formatted_date,
                formatted_size
            )
        )

    return formatted_results