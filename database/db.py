import sqlite3
from datetime import datetime
import os
import re
import csv
import logging
import threading


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("atlas")


# ============================================================
# CONTENT-EXTRACTABLE EXTENSIONS
# ============================================================

CONTENT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".txt",
    ".md",
    ".csv",
    ".pptx",
    ".xlsx",
}


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

    # --------------------------------------------------------
    # Migration: Add file_content column if missing
    # --------------------------------------------------------

    cursor.execute("PRAGMA table_info(files)")
    columns = [row[1] for row in cursor.fetchall()]

    if "file_content" not in columns:

        cursor.execute("""
            ALTER TABLE files
            ADD COLUMN file_content TEXT
        """)

        logger.info(
            "Added file_content column to files table."
        )

    if "content_last_indexed" not in columns:

        cursor.execute("""
            ALTER TABLE files
            ADD COLUMN content_last_indexed REAL
        """)

        logger.info(
            "Added content_last_indexed column to files table."
        )

    # --------------------------------------------------------
    # FTS5 full-text search index
    # --------------------------------------------------------

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='files_fts'
    """)

    if not cursor.fetchone():

        cursor.execute("""
            CREATE VIRTUAL TABLE files_fts
            USING fts5(
                file_name,
                file_content,
                content='files',
                content_rowid='id'
            )
        """)

        logger.info(
            "Created FTS5 virtual table files_fts."
        )

    # --------------------------------------------------------
    # Embeddings table for natural language search
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_embeddings (

            file_id INTEGER PRIMARY KEY,

            embedding BLOB NOT NULL,

            content_hash TEXT,

            FOREIGN KEY(file_id)
            REFERENCES files(id)
            ON DELETE CASCADE

        )
    """)

    # --------------------------------------------------------
    # Indexes for performance
    # --------------------------------------------------------

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_location
        ON files(indexed_location_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_extension
        ON files(extension)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_name
        ON files(file_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_content_indexed
        ON files(content_last_indexed)
    """)

    connection.commit()
    connection.close()


# ============================================================
# CONTENT EXTRACTION
# ============================================================

def extract_text_from_file(file_path, extension):
    """
    Extract text content from a file based on its extension.
    Returns extracted text or empty string on failure.
    """

    try:

        # --------------------------------------------------------
        # PDF extraction using pypdf
        # --------------------------------------------------------

        if extension == ".pdf":

            from pypdf import PdfReader

            reader = PdfReader(file_path)

            text_parts = []
            total_chars = 0

            for i, page in enumerate(reader.pages):

                # Limit to 50 pages or 200KB of text to avoid blocking on huge books
                if i >= 50 or total_chars >= 200_000:

                    break

                try:

                    page_text = page.extract_text()

                    if page_text:

                        text_parts.append(page_text)
                        total_chars += len(page_text)

                except Exception:

                    continue

            return "\n".join(text_parts)

        # --------------------------------------------------------
        # DOCX extraction using python-docx
        # --------------------------------------------------------

        elif extension == ".docx":

            from docx import Document

            doc = Document(file_path)

            text_parts = []

            for paragraph in doc.paragraphs:

                if paragraph.text.strip():

                    text_parts.append(paragraph.text)

            # Also extract text from tables
            for table in doc.tables:

                for row in table.rows:

                    for cell in row.cells:

                        if cell.text.strip():

                            text_parts.append(cell.text)

            return "\n".join(text_parts)

        # --------------------------------------------------------
        # Legacy DOC extraction using legacy-doc
        # --------------------------------------------------------

        elif extension == ".doc":

            try:

                from legacy_doc import extract_text

                with open(file_path, "rb") as f:

                    result = extract_text(f.read())

                    return result.text if result.text else ""

            except ImportError:

                logger.warning(
                    "legacy-doc not installed. "
                    "Cannot extract .doc files."
                )

                return ""

            except Exception as e:

                logger.debug(
                    "DOC extraction failed for %s: %s",
                    file_path, e
                )

                return ""

        # --------------------------------------------------------
        # TXT and MD — plain text reading
        # --------------------------------------------------------

        elif extension in (".txt", ".md"):

            encodings = ["utf-8", "latin-1", "cp1252"]

            for encoding in encodings:

                try:

                    with open(
                        file_path,
                        "r",
                        encoding=encoding,
                        errors="replace"
                    ) as f:

                        # Read up to 5MB to avoid huge files
                        return f.read(5 * 1024 * 1024)

                except (UnicodeDecodeError, ValueError):

                    continue

            return ""

        # --------------------------------------------------------
        # CSV extraction
        # --------------------------------------------------------

        elif extension == ".csv":

            text_parts = []

            encodings = ["utf-8", "latin-1", "cp1252"]

            for encoding in encodings:

                try:

                    with open(
                        file_path,
                        "r",
                        encoding=encoding,
                        errors="replace",
                        newline=""
                    ) as f:

                        reader = csv.reader(f)
                        row_count = 0

                        for row in reader:

                            text_parts.append(
                                " ".join(row)
                            )

                            row_count += 1

                            # Limit to 10000 rows
                            if row_count >= 10000:

                                break

                    break

                except (UnicodeDecodeError, ValueError):

                    continue

            return "\n".join(text_parts)

        # --------------------------------------------------------
        # PPTX extraction using python-pptx
        # --------------------------------------------------------

        elif extension == ".pptx":

            from pptx import Presentation

            prs = Presentation(file_path)

            text_parts = []

            for slide in prs.slides:

                for shape in slide.shapes:

                    if shape.has_text_frame:

                        for paragraph in shape.text_frame.paragraphs:

                            paragraph_text = paragraph.text.strip()

                            if paragraph_text:

                                text_parts.append(paragraph_text)

                    if shape.has_table:

                        for row in shape.table.rows:

                            for cell in row.cells:

                                if cell.text.strip():

                                    text_parts.append(
                                        cell.text.strip()
                                    )

            return "\n".join(text_parts)

        # --------------------------------------------------------
        # XLSX extraction using openpyxl
        # --------------------------------------------------------

        elif extension == ".xlsx":

            from openpyxl import load_workbook

            wb = load_workbook(
                file_path,
                read_only=True,
                data_only=True
            )

            text_parts = []

            for sheet in wb.sheetnames:

                ws = wb[sheet]

                row_count = 0

                for row in ws.iter_rows(
                    values_only=True
                ):

                    cell_values = [
                        str(cell)
                        for cell in row
                        if cell is not None
                    ]

                    if cell_values:

                        text_parts.append(
                            " ".join(cell_values)
                        )

                    row_count += 1

                    if row_count >= 10000:

                        break

            wb.close()

            return "\n".join(text_parts)

        else:

            return ""

    except PermissionError:

        logger.debug(
            "Permission denied: %s",
            file_path
        )

        return ""

    except FileNotFoundError:

        logger.debug(
            "File not found: %s",
            file_path
        )

        return ""

    except Exception as e:

        logger.debug(
            "Content extraction failed for %s: %s",
            file_path, e
        )

        return ""


# ============================================================
# INDEX CONTENT FOR A SINGLE FILE
# ============================================================

def index_file_content(file_id, file_path, extension):
    """
    Extract content from a file and store it in the database.
    Updates the FTS index as well.
    """

    if extension not in CONTENT_EXTENSIONS:

        return False

    content = extract_text_from_file(
        file_path, extension
    )

    # Truncate extremely long content (over 1MB of text)
    if len(content) > 1_000_000:

        content = content[:1_000_000]

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    try:

        # Update the files table
        cursor.execute("""
            UPDATE files
            SET
                file_content = ?,
                content_last_indexed = ?
            WHERE id = ?
        """, (
            content,
            datetime.now().timestamp(),
            file_id
        ))

        # Update the FTS index

        # First delete old entry
        cursor.execute("""
            DELETE FROM files_fts WHERE rowid = ?
        """, (file_id,))

        # Fetch the file_name for FTS
        cursor.execute("""
            SELECT file_name FROM files WHERE id = ?
        """, (file_id,))

        row = cursor.fetchone()

        if row:

            cursor.execute("""
                INSERT INTO files_fts(
                    rowid,
                    file_name,
                    file_content
                )
                VALUES (?, ?, ?)
            """, (
                file_id,
                row[0],
                content
            ))

        connection.commit()

        return True

    except Exception as e:

        logger.error(
            "Failed to index content for %s: %s",
            file_path, e
        )

        connection.rollback()

        return False

    finally:

        connection.close()


# ============================================================
# BATCH CONTENT INDEXING
# ============================================================

def index_all_content(progress_callback=None):
    """
    Index content for all files that have content-extractable
    extensions but haven't been indexed yet, or whose file
    has been modified since last indexing.
    Returns counts of success and failure.
    """

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    # Find files needing content indexing
    placeholders = ",".join(
        "?" for _ in CONTENT_EXTENSIONS
    )

    cursor.execute(f"""
        SELECT id, file_path, extension, last_modified,
               content_last_indexed
        FROM files
        WHERE LOWER(extension) IN ({placeholders})
        AND (
            content_last_indexed IS NULL
            OR content_last_indexed < last_modified
        )
        ORDER BY size ASC
    """, list(CONTENT_EXTENSIONS))

    files_to_index = cursor.fetchall()

    connection.close()

    total = len(files_to_index)
    success = 0
    failed = 0

    for i, (
        file_id,
        file_path,
        extension,
        last_modified,
        content_last_indexed
    ) in enumerate(files_to_index):

        try:

            result = index_file_content(
                file_id,
                file_path,
                extension.lower()
            )

            if result:

                success += 1

            else:

                failed += 1

        except Exception as e:

            logger.debug(
                "Index failed for %s: %s",
                file_path, e
            )

            failed += 1

        if progress_callback and (i + 1) % 50 == 0:

            progress_callback(
                i + 1, total, success, failed
            )

    return {
        "total": total,
        "success": success,
        "failed": failed
    }


# ============================================================
# REBUILD FTS INDEX
# ============================================================

def rebuild_fts_index():
    """
    Rebuild the FTS index from scratch using current
    files table data.
    """

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    try:

        # Clear and rebuild FTS
        cursor.execute("DELETE FROM files_fts")

        cursor.execute("""
            INSERT INTO files_fts(
                rowid,
                file_name,
                file_content
            )
            SELECT
                id,
                file_name,
                COALESCE(file_content, '')
            FROM files
        """)

        connection.commit()

        logger.info("FTS index rebuilt successfully.")

    except Exception as e:

        logger.error("FTS rebuild failed: %s", e)

        connection.rollback()

    finally:

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
    sort_by="relevance",
    file_type="all",
    search_mode="all"
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
    # CONTENT SEARCH VIA FTS (Layer 2)
    # ========================================================

    content_match_paths = set()

    if search_terms and search_mode in ("all", "content"):

        try:

            # Build FTS query: match all terms
            fts_terms = []

            for term in search_terms:

                # Escape FTS special characters
                clean_term = re.sub(
                    r'[^\w]', '', term
                )

                if clean_term:

                    fts_terms.append(clean_term)

            if fts_terms:

                fts_query = " AND ".join(fts_terms)

                # Search content only (not filename)
                # via FTS
                fts_sql = """
                    SELECT f.file_path
                    FROM files_fts fts
                    JOIN files f ON f.id = fts.rowid
                    WHERE files_fts MATCH ?
                    LIMIT 500
                """

                cursor.execute(
                    fts_sql,
                    (f"file_content : {fts_query}",)
                )

                for row in cursor.fetchall():

                    content_match_paths.add(row[0])

        except Exception as e:

            logger.debug(
                "FTS search failed: %s", e
            )

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
    # ========================================================

    if search_terms:

        conditions = []

        if search_mode in ("all", "filename"):

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
            # Search filename with separators removed
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

        # ------------------------------------------------
        # Include content-matched file paths
        # ------------------------------------------------

        if content_match_paths:

            placeholders_content = ",".join(
                "?" for _ in content_match_paths
            )

            conditions.append(
                f"file_path IN ({placeholders_content})"
            )

            parameters.extend(
                list(content_match_paths)
            )

        if conditions:

            sql += " WHERE (" + " OR ".join(
                conditions
            ) + ")"

        elif search_mode == "content":

            # Content-only mode with no matches
            sql += " WHERE 1=0"

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
    # FILE TYPE FILTER
    # ========================================================

    if file_type and file_type != "all":

        if search_terms or (
            drive and drive != "all"
        ):

            sql += """
                AND LOWER(extension) = ?
            """

        else:

            sql += """
                WHERE LOWER(extension) = ?
            """

        # Make sure the extension always has a dot.
        #
        # pdf  -> .pdf
        # .pdf -> .pdf

        selected_extension = file_type.lower()

        if not selected_extension.startswith("."):

            selected_extension = "." + selected_extension

        parameters.append(
            selected_extension
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
            # =================================================

            for token in tokens:

                if token.startswith(
                    query_lower
                ):

                    score += 250

                    break

            # =================================================
            # 7. SUBSTRING MATCH
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
            # =================================================

            if extension in {
                ".exe",
                ".msi"
            }:

                score += 250

            # =================================================
            # 12. PROGRAM FILES BOOST
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
            # =================================================

            if full_name_lower == query_lower:

                score += 2500

            # =================================================
            # 14. EXACT INTERNAL FILE SEARCH
            # =================================================

            if (
                extension in internal_file_extensions
                and full_name_lower == query_lower
            ):

                score += 3000

            # =================================================
            # 15. LONG TECHNICAL NAMES
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

            # =================================================
            # 17. CONTENT MATCH BOOST
            # =================================================

            if file_path in content_match_paths:

                score += 400

            return score

        # ----------------------------------------------------
        # Sort by calculated relevance.
        # ----------------------------------------------------

        results.sort(
            key=relevance_score,
            reverse=True
        )

    # ========================================================
    # DETERMINE MATCH TYPE FOR EACH RESULT
    # ========================================================

    def determine_match_type(file_name, file_path):
        """
        Determine how the file matched the query.
        Returns: 'filename', 'content', 'both', or 'none'
        """

        if not search_terms:

            return "none"

        name_lower = file_name.lower()
        query_lower = query.lower()

        # Check filename match
        filename_match = False

        for term in search_terms:

            if term.lower() in name_lower:

                filename_match = True

                break

        if not filename_match:

            normalized_name = normalize_text(
                file_name
            )

            if normalized_query in normalized_name:

                filename_match = True

        # Check content match
        content_match = file_path in content_match_paths

        if filename_match and content_match:

            return "both"

        elif content_match:

            return "content"

        elif filename_match:

            return "filename"

        else:

            return "filename"

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

        match_type = determine_match_type(
            file_name, file_path
        )

        formatted_results.append(
            (
                file_name,
                file_path,
                formatted_date,
                formatted_size,
                match_type
            )
        )

    return formatted_results
# ============================================================
# SEARCH SUGGESTIONS
# ============================================================

def get_search_suggestions(
    query,
    drive="all",
    file_type="all"
):

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    query = query.strip()

    if not query:

        connection.close()

        return []


    # --------------------------------------------------------
    # Search filenames beginning with or containing the query
    # --------------------------------------------------------

    sql = """
        SELECT
            file_name,
            file_path

        FROM files

        WHERE LOWER(file_name) LIKE ?
    """

    parameters = [
        f"%{query.lower()}%"
    ]


    # --------------------------------------------------------
    # Drive filter
    # --------------------------------------------------------

    if drive and drive != "all":

        sql += """
            AND UPPER(file_path) LIKE ?
        """

        parameters.append(
            f"{drive.upper()}%"
        )


    # --------------------------------------------------------
    # File type filter
    # --------------------------------------------------------

    if file_type and file_type != "all":

        selected_extension = file_type.lower()

        if not selected_extension.startswith("."):

            selected_extension = "." + selected_extension

        sql += """
            AND LOWER(extension) = ?
        """

        parameters.append(
            selected_extension
        )


    # --------------------------------------------------------
    # Limit suggestions
    # --------------------------------------------------------

    sql += """
        ORDER BY
            CASE
                WHEN LOWER(file_name) LIKE ? THEN 0
                ELSE 1
            END,
            file_name COLLATE NOCASE ASC

        LIMIT 8
    """

    parameters.append(
        f"{query.lower()}%"
    )


    cursor.execute(
        sql,
        parameters
    )

    rows = cursor.fetchall()

    connection.close()


    # --------------------------------------------------------
    # Remove duplicate filenames
    # --------------------------------------------------------

    suggestions = []

    seen = set()

    for file_name, file_path in rows:

        key = file_name.lower()

        if key in seen:

            continue

        seen.add(key)

        suggestions.append({
            "name": file_name,
            "path": file_path
        })


    return suggestions


# ============================================================
# EMBEDDING MODEL (Lazy Singleton)
# ============================================================

_embedding_model = None
_embedding_lock = threading.Lock()


def get_embedding_model():
    """
    Load the sentence-transformers model on first use.
    Thread-safe singleton pattern to avoid loading
    the model multiple times.
    """

    global _embedding_model

    if _embedding_model is not None:

        return _embedding_model

    with _embedding_lock:

        # Double-check after acquiring lock
        if _embedding_model is not None:

            return _embedding_model

        try:

            from sentence_transformers import (
                SentenceTransformer
            )

            logger.info(
                "Loading embedding model "
                "all-MiniLM-L6-v2..."
            )

            _embedding_model = SentenceTransformer(
                "all-MiniLM-L6-v2"
            )

            logger.info(
                "Embedding model loaded successfully."
            )

            return _embedding_model

        except ImportError:

            logger.error(
                "sentence-transformers not installed. "
                "Natural language search unavailable."
            )

            return None

        except Exception as e:

            logger.error(
                "Failed to load embedding model: %s",
                e
            )

            return None


# ============================================================
# GENERATE EMBEDDING
# ============================================================

def generate_embedding(text):
    """
    Generate a 384-dimensional embedding vector
    for the given text.
    Returns a numpy array or None on failure.
    """

    model = get_embedding_model()

    if model is None:

        return None

    try:

        import numpy as np

        # Truncate text to avoid exceeding model limits
        # (256 tokens ≈ ~1000 chars for safety)
        truncated = text[:2000]

        embedding = model.encode(
            truncated,
            show_progress_bar=False
        )

        return embedding.astype(np.float32)

    except Exception as e:

        logger.debug(
            "Embedding generation failed: %s", e
        )

        return None


# ============================================================
# NATURAL LANGUAGE SEARCH
# ============================================================

def natural_language_search(
    query,
    drive=None,
    file_type="all",
    top_k=50
):
    """
    Perform semantic search using sentence embeddings.

    How it works:
    1. Convert the user's natural language query into
       a 384-dimensional embedding vector.
    2. Compare this vector against pre-computed embeddings
       of all indexed file content and filenames.
    3. Use cosine similarity to rank results by
       semantic relevance.
    4. Return results sorted by similarity score,
       with match_type='semantic'.
    """

    import numpy as np

    model = get_embedding_model()

    if model is None:

        return []

    # Generate query embedding
    query_embedding = generate_embedding(query)

    if query_embedding is None:

        return []

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    # --------------------------------------------------------
    # Build filter conditions for drive and file_type
    # --------------------------------------------------------

    filter_sql = ""
    filter_params = []

    if drive and drive != "all":

        filter_sql += " AND UPPER(f.file_path) LIKE ?"
        filter_params.append(f"{drive.upper()}%")

    if file_type and file_type != "all":

        ext = file_type.lower()

        if not ext.startswith("."):

            ext = "." + ext

        filter_sql += " AND LOWER(f.extension) = ?"
        filter_params.append(ext)

    # --------------------------------------------------------
    # Retrieve all embeddings
    # --------------------------------------------------------

    cursor.execute(f"""
        SELECT
            e.file_id,
            e.embedding,
            f.file_name,
            f.file_path,
            f.size,
            f.last_modified
        FROM file_embeddings e
        JOIN files f ON f.id = e.file_id
        WHERE 1=1 {filter_sql}
    """, filter_params)

    rows = cursor.fetchall()

    connection.close()

    if not rows:

        return []

    # --------------------------------------------------------
    # Compute cosine similarity
    # --------------------------------------------------------

    results_with_score = []

    for row in rows:

        file_id = row[0]
        embedding_blob = row[1]
        file_name = row[2]
        file_path = row[3]
        size = row[4]
        last_modified = row[5]

        try:

            file_embedding = np.frombuffer(
                embedding_blob,
                dtype=np.float32
            )

            # Cosine similarity
            dot_product = np.dot(
                query_embedding, file_embedding
            )

            norm_q = np.linalg.norm(query_embedding)
            norm_f = np.linalg.norm(file_embedding)

            if norm_q == 0 or norm_f == 0:

                continue

            similarity = dot_product / (
                norm_q * norm_f
            )

            # Only include results above threshold
            if similarity > 0.25:

                results_with_score.append(
                    (
                        file_name,
                        file_path,
                        size,
                        last_modified,
                        float(similarity)
                    )
                )

        except Exception:

            continue

    # --------------------------------------------------------
    # Sort by similarity and take top_k
    # --------------------------------------------------------

    results_with_score.sort(
        key=lambda x: x[4],
        reverse=True
    )

    results_with_score = results_with_score[:top_k]

    # --------------------------------------------------------
    # Format results
    # --------------------------------------------------------

    def format_file_size(size):

        if size < 1024:

            return f"{size} B"

        elif size < 1024 ** 2:

            return f"{size / 1024:.2f} KB"

        elif size < 1024 ** 3:

            return f"{size / (1024 ** 2):.2f} MB"

        else:

            return f"{size / (1024 ** 3):.2f} GB"

    formatted_results = []

    for (
        file_name,
        file_path,
        size,
        last_modified,
        similarity
    ) in results_with_score:

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
                formatted_size,
                "semantic"
            )
        )

    return formatted_results


# ============================================================
# GENERATE AND STORE EMBEDDING FOR A SINGLE FILE
# ============================================================

def generate_file_embedding(file_id):
    """
    Generate and store embedding for a single file.
    """

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT file_name, file_content
        FROM files
        WHERE id = ?
    """, (file_id,))

    row = cursor.fetchone()

    if not row or not row[1]:

        connection.close()
        return False

    file_name, file_content = row

    combined_text = f"{file_name}\n{file_content[:2000]}"
    embedding = generate_embedding(combined_text)

    if embedding is not None:

        content_hash = "hash_" + str(len(file_content or ""))

        cursor.execute("""
            INSERT INTO file_embeddings
            (file_id, embedding, content_hash)
            VALUES (?, ?, ?)
            ON CONFLICT(file_id)
            DO UPDATE SET
                embedding = excluded.embedding,
                content_hash = excluded.content_hash
        """, (
            file_id,
            embedding.tobytes(),
            content_hash
        ))

        connection.commit()
        connection.close()
        return True

    connection.close()
    return False


# ============================================================
# GENERATE AND STORE EMBEDDINGS FOR ALL FILES
# ============================================================

def generate_all_embeddings(limit=500, progress_callback=None):
    """
    Generate embeddings for files that have content
    indexed but no embedding yet, or whose content
    has changed.
    """

    import numpy as np
    import hashlib

    model = get_embedding_model()

    if model is None:

        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "error": "Embedding model not available."
        }

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    # Find files with content but no embedding,
    # or outdated embedding
    cursor.execute("""
        SELECT
            f.id,
            f.file_name,
            f.file_path,
            f.file_content
        FROM files f
        LEFT JOIN file_embeddings e ON f.id = e.file_id
        WHERE f.file_content IS NOT NULL
        AND f.file_content != ''
        AND (
            e.file_id IS NULL
            OR e.content_hash != (
                'hash_' || CAST(LENGTH(f.file_content) AS TEXT)
            )
        )
        LIMIT ?
    """, (limit,))

    files_to_embed = cursor.fetchall()
    connection.close()

    total = len(files_to_embed)
    success = 0
    failed = 0

    for i, (
        file_id,
        file_name,
        file_path,
        file_content
    ) in enumerate(files_to_embed):

        try:

            # Create a combined text representation
            # including filename for context
            combined_text = (
                f"{file_name}\n{file_content[:2000]}"
            )

            embedding = generate_embedding(
                combined_text
            )

            if embedding is not None:

                # Store embedding in database
                content_hash = (
                    "hash_"
                    + str(len(file_content or ""))
                )

                conn = sqlite3.connect("atlas.db")
                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO file_embeddings
                    (file_id, embedding, content_hash)
                    VALUES (?, ?, ?)
                    ON CONFLICT(file_id)
                    DO UPDATE SET
                        embedding = excluded.embedding,
                        content_hash =
                            excluded.content_hash
                """, (
                    file_id,
                    embedding.tobytes(),
                    content_hash
                ))

                conn.commit()
                conn.close()

                success += 1

            else:

                failed += 1

        except Exception as e:

            logger.debug(
                "Embedding failed for %s: %s",
                file_path, e
            )

            failed += 1

        if progress_callback and (i + 1) % 100 == 0:

            progress_callback(
                i + 1, total, success, failed
            )

    return {
        "total": total,
        "success": success,
        "failed": failed
    }


# ============================================================
# CONTENT INDEXING STATUS
# ============================================================

def get_indexing_status():
    """
    Returns a summary of content indexing status.
    """

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM files"
    )
    total_files = cursor.fetchone()[0]

    placeholders = ",".join(
        "?" for _ in CONTENT_EXTENSIONS
    )

    cursor.execute(f"""
        SELECT COUNT(*) FROM files
        WHERE LOWER(extension) IN ({placeholders})
    """, list(CONTENT_EXTENSIONS))
    extractable_files = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM files
        WHERE file_content IS NOT NULL
        AND file_content != ''
    """)
    indexed_content = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM file_embeddings"
    )
    embedded_files = cursor.fetchone()[0]

    connection.close()

    return {
        "total_files": total_files,
        "extractable_files": extractable_files,
        "indexed_content": indexed_content,
        "embedded_files": embedded_files
    }


# ============================================================
# CLEAN STALE CONTENT AND EMBEDDINGS
# ============================================================

def clean_stale_records():
    """
    Remove content and embeddings for files that
    no longer exist in the files table.
    """

    connection = sqlite3.connect("atlas.db")
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM file_embeddings
        WHERE file_id NOT IN (
            SELECT id FROM files
        )
    """)

    deleted = cursor.rowcount

    connection.commit()
    connection.close()

    return deleted