import sqlite3
from datetime import datetime
import os
import re


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
    # SQLite performs a broad search first.
    #
    # This allows filenames such as:
    #
    # ExamForge
    # Exam Forge
    # Exam_Forge
    # Exam-Forge
    #
    # to reach the Python relevance system.
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
        # Search filename with separators removed.
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

        # Relevance is handled in Python below.
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

        # ----------------------------------------------------
        # File types normally useful to users.
        # ----------------------------------------------------

        user_file_extensions = {

            # Documents
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".rtf",
            ".odt",

            # Spreadsheets
            ".xls",
            ".xlsx",
            ".csv",
            ".ods",

            # Presentations
            ".ppt",
            ".pptx",
            ".odp",

            # Images
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".svg",
            ".tif",
            ".tiff",

            # Video
            ".mp4",
            ".mkv",
            ".avi",
            ".mov",
            ".wmv",

            # Audio
            ".mp3",
            ".wav",
            ".flac",
            ".aac",
            ".m4a",

            # Archives
            ".zip",
            ".rar",
            ".7z",
            ".tar",
            ".gz",

            # Source/project files
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".html",
            ".css",
            ".json",
            ".xml",
            ".sql",

            # Design/project files
            ".psd",
            ".ai",
            ".cdr",
            ".indd",

            # Applications
            ".exe",
            ".msi"
        }

        # ----------------------------------------------------
        # Internal / technical file types.
        #
        # These are NOT hidden.
        # They simply rank lower for broad searches.
        # ----------------------------------------------------

        internal_file_extensions = {

            ".dll",
            ".sys",
            ".drv",
            ".ocx",
            ".ax",
            ".cpl",

            ".tmp",
            ".temp",
            ".log",

            ".dat",
            ".db",
            ".db-wal",
            ".db-shm",

            ".ini",
            ".cfg",
            ".conf",
            ".config",

            ".manifest",

            ".ph1",
            ".ph2",
            ".ph3",
            ".ph4",
            ".ph5",
            ".ph6",

            ".vg1",
            ".vg2",
            ".vg3",

            ".dl1",
            ".dl2",
            ".dl3",

            ".fo1",
            ".fo2",
            ".fo3"
        }

        # ----------------------------------------------------
        # Internal directories.
        # ----------------------------------------------------

        internal_directory_names = {

            "windows",
            "system32",
            "syswow64",
            "programdata",
            "appdata",
            "node_modules",
            "__pycache__",
            ".git",
            "cache",
            "caches",
            "temp",
            "tmp"
        }

        # ----------------------------------------------------
        # Split filename into meaningful tokens.
        #
        # Examples:
        #
        # CorelProperties
        # -> Corel + Properties
        #
        # System.Private.CoreLib
        # -> System + Private + Core + Lib
        #
        # Exam_Forge
        # -> Exam + Forge
        # ----------------------------------------------------

        def filename_tokens(text):

            text = os.path.splitext(text)[0]

            # Split camelCase / PascalCase
            text = re.sub(
                r"([a-z])([A-Z])",
                r"\1 \2",
                text
            )

            # Split letters and numbers
            text = re.sub(
                r"([A-Za-z])([0-9])",
                r"\1 \2",
                text
            )

            text = re.sub(
                r"([0-9])([A-Za-z])",
                r"\1 \2",
                text
            )

            # Split punctuation/separators
            text = re.sub(
                r"[^A-Za-z0-9]+",
                " ",
                text
            )

            return [
                token.lower()
                for token in text.split()
                if token
            ]

        # ----------------------------------------------------
        # Calculate relevance score.
        # ----------------------------------------------------

        def relevance_score(file):

            file_name = file[0]
            file_path = file[1]

            extension = os.path.splitext(
                file_name
            )[1].lower()

            name_without_extension = os.path.splitext(
                file_name
            )[0]

            name_lower = name_without_extension.lower()

            full_name_lower = file_name.lower()

            tokens = filename_tokens(
                file_name
            )

            query_lower = query.lower()

            normalized_name = normalize_text(
                name_without_extension
            )

            score = 0

            # =================================================
            # 1. EXACT COMPLETE FILENAME
            # =================================================

            if full_name_lower == query_lower:

                score += 3000

            # =================================================
            # 2. EXACT FILENAME WITHOUT EXTENSION
            # =================================================

            if name_lower == query_lower:

                score += 1800

            # =================================================
            # 3. EXACT NORMALIZED FILENAME
            #
            # Exam Forge
            # Exam_Forge
            # Exam-Forge
            # ExamForge
            #
            # can all match.
            # =================================================

            if normalized_name == normalized_query:

                score += 1600

            # =================================================
            # 4. QUERY TOKEN MATCHES
            # =================================================

            query_tokens = []

            for term in normalized_terms:

                query_tokens.extend(
                    filename_tokens(term)
                )

            query_tokens = [
                token
                for token in query_tokens
                if token
            ]

            matched_tokens = 0

            for token in query_tokens:

                if token in tokens:

                    matched_tokens += 1

                    score += 500

            # =================================================
            # 5. ALL QUERY TOKENS MATCH
            # =================================================

            if (
                query_tokens
                and matched_tokens == len(query_tokens)
            ):

                score += 700

            # =================================================
            # 6. QUERY STARTS A FILENAME TOKEN
            #
            # Corel -> CorelProperties
            #
            # This is useful and gets a moderate boost.
            # =================================================

            for token in tokens:

                if token.startswith(
                    query_lower
                ):

                    score += 250

                    break

            # =================================================
            # 7. SUBSTRING MATCH
            #
            # Corel -> CoreLib
            #
            # This remains searchable, but receives only
            # a small score because it isn't a proper token.
            # =================================================

            for token in tokens:

                if (
                    query_lower
                    and query_lower in token
                    and token != query_lower
                ):

                    score += 40

                    break

            # =================================================
            # 8. USER-FRIENDLY FILE TYPE BOOST
            # =================================================

            if extension in user_file_extensions:

                score += 80

            # =================================================
            # 9. INTERNAL FILE TYPE PENALTY
            # =================================================

            if extension in internal_file_extensions:

                score -= 250

            # =================================================
            # 10. INTERNAL DIRECTORY PENALTY
            # =================================================

            path_parts = os.path.normpath(
                file_path
            ).lower().split(os.sep)

            internal_directory_found = False

            for part in path_parts:

                if part in internal_directory_names:

                    internal_directory_found = True

                    break

            if internal_directory_found:

                score -= 180

            # =================================================
            # 11. EXECUTABLE BOOST
            #
            # Searches such as:
            #
            # Chrome
            # Adobe
            # Corel
            #
            # should favor actual applications.
            # =================================================

            if extension in {
                ".exe",
                ".msi"
            }:

                score += 250

            # =================================================
            # 12. PROGRAM FILES BOOST
            #
            # Installed applications commonly live here.
            # =================================================

            lower_path = file_path.lower()

            if (
                "\\program files\\"
                in lower_path
                or "\\program files (x86)\\"
                in lower_path
            ):

                score += 100

            # =================================================
            # 13. EXACT FILE OVERRIDE
            #
            # Explicit searches should always remain strong.
            # =================================================

            if full_name_lower == query_lower:

                score += 2500

            # =================================================
            # 14. EXACT INTERNAL FILE SEARCH
            #
            # Example:
            #
            # chrome.dll
            # CorelProperties.propdesc
            #
            # These must remain searchable.
            # =================================================

            if (
                extension in internal_file_extensions
                and full_name_lower == query_lower
            ):

                score += 3000

            # =================================================
            # 15. LONG TECHNICAL NAMES
            #
            # Slight penalty for very long generated/internal
            # files.
            # =================================================

            if (
                extension in internal_file_extensions
                and len(file_name) > 35
            ):

                score -= min(
                    120,
                    (len(file_name) - 35) * 2
                )

            # =================================================
            # 16. SMALL LENGTH TIE-BREAKER
            # =================================================

            score += max(
                0,
                30 - len(file_name)
            )

            return score

        # ----------------------------------------------------
        # Sort by calculated relevance.
        # ----------------------------------------------------

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