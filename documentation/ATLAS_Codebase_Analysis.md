# ATLAS — Persistent Codebase Analysis & Investigation Log

**Status:** Complete — All Deliverables Generated & Verified  
**Repository Root:** `d:\Atlas`  
**Database:** `d:\Atlas\atlas.db` (~1.26 GB / 1,349,312,512 bytes, inspected read-only)  
**Target Environment:** Windows, Python 3.10+ (project `venv` uses Python 3.14), Flask 3.1.3, SQLite 3 with FTS5

---

## 1. Complete Project Structure

```text
d:\Atlas\
├── app.py                        # Flask entry point, HTTP routes, background indexing threads
├── atlas.db                      # Local SQLite database (75,314 file records; 10 indexed locations)
├── requirements.txt              # Python package dependencies
├── README.md                     # Project overview, features, setup, and usage guide
├── test_atlas.py                 # 43-case integration and search test suite
├── test_results.json             # Latest recorded JSON test output (43/43 PASS)
├── database\
│   └── db.py                     # Schema creation/migration, extractors, FTS5, ranking, NLP/embeddings
├── scanner\
│   └── scan.py                   # Directory traversal (os.walk) and ignored-folder filtering
├── templates\
│   └── index.html                # Main single-page Jinja2 UI + inline JS for search suggestions
├── static\
│   ├── css\
│   │   └── style.css             # Dark-theme responsive UI stylesheet
│   └── js\
│       └── script.js             # Empty placeholder (0 bytes); JS currently lives inline in index.html
├── docs\
│   └── projectplan.md            # Original Version 1 planning notes
└── test_corpus\                  # Isolated synthetic test documents (PDF, DOCX, DOC, PPTX, XLSX, TXT, MD, CSV, corrupt PDF)
```

---

## 2. Git Development History (Recent Commits)

1. `6b98053` — Update UI for quick scan and search controls
2. `3023872` — Style quick scan controls
3. `2211d1f` — Improve separator insensitive file search
4. `db2f5d0` — Improve search relevance ranking
5. `424d501` — added 'open folder' button
6. `83b181e` — filter based on file type
7. `876a8ac` — Improved UI
8. `d2bbcf4` — Layer 2 and 3 searching
9. `45ef9ef` — FTS ranking and Relevant file type
10. `fc3e6a3` — readme

---

## 3. Database Schema & Live State (Read-Only Verified)

### Tables
1. **`indexed_locations`** (10 rows)
   - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
   - `path` (`TEXT NOT NULL UNIQUE`)
   - `last_scanned` (`REAL`)
2. **`files`** (75,314 rows)
   - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
   - `file_name` (`TEXT NOT NULL`)
   - `file_path` (`TEXT NOT NULL UNIQUE`)
   - `extension` (`TEXT`)
   - `size` (`INTEGER`)
   - `last_modified` (`REAL`)
   - `indexed_location_id` (`INTEGER`, FK → `indexed_locations(id)`)
   - `file_content` (`TEXT`, added via non-destructive migration)
   - `content_last_indexed` (`REAL`, added via non-destructive migration)
3. **`files_fts`** (FTS5 Virtual Table, 75,314 rows)
   - `USING fts5(file_name, file_content, content='files', content_rowid='id')`
   - External-content FTS5 table backed by `files`.
4. **`file_embeddings`** (1,958 rows)
   - `file_id` (`INTEGER PRIMARY KEY`, FK → `files(id) ON DELETE CASCADE`)
   - `embedding` (`BLOB NOT NULL` — 384-dim `float32` NumPy array = 1,536 bytes/row)
   - `content_hash` (`TEXT` — `"hash_" + str(len(file_content))`)

### Indexes on `files`
- `idx_files_location` on `files(indexed_location_id)`
- `idx_files_extension` on `files(extension)`
- `idx_files_name` on `files(file_name)`
- `idx_files_content_indexed` on `files(content_last_indexed)`

### Live Content Extraction Distribution (Extractable Formats)
- `.txt`: 575 files | `.md`: 359 files | `.pdf`: 198 files | `.docx`: 26 files
- `.pptx`: 25 files | `.doc`: 4 files | `.xlsx`: 3 files | `.csv`: 2 files
- Total files with non-empty `file_content`: 47,406 (includes legacy/code files indexed prior to restricting `CONTENT_EXTENSIONS`).
- Total files with `content_last_indexed` timestamp: 1,299.

---

## 4. Module-by-Module Architecture & Functions

### `app.py` (668 lines)
- Initializes SQLite schema via `create_database()` at import time.
- **Routes:**
  - `GET /` (`home`): Fetches `get_available_drives()`, renders `index.html` with defaults (`drive="all"`, `file_type="relevant"`, `sort_by="relevance"`, `mode="all"`).
  - `GET /search` (`search`): Reads `query`, `drive`, `file_type`, `sort`, `mode`. Dispatches `mode == "semantic"` to `natural_language_search()`; otherwise dispatches to `search_files()`.
  - `GET /suggestions` (`suggestions`): Returns JSON list (max 8) from `get_search_suggestions()` if `len(query) >= 2`.
  - `GET /scan` (`scan`): Saves root in `indexed_locations`, walks folder via `scan_folder()`, saves metadata via `save_files()`, spawns daemon thread running `index_all_content()`, flashes message, redirects to `/`.
  - `GET /quick-scan` (`quick_scan`): Iterates over `get_indexed_locations()`, calls `quick_scan_location(location_id)` for each. Spawns daemon thread for `index_all_content()` if `total_added > 0 or total_modified > 0`.
  - `GET /index-content` (`index_content_route`): Spawns daemon thread running `index_all_content()`, updates `_indexing_status_state["indexing_content"]`.
  - `GET /generate-embeddings` (`generate_embeddings_route`): Spawns daemon thread running `generate_all_embeddings()`, updates `_indexing_status_state["indexing_embeddings"]`.
  - `GET /indexing-status` (`indexing_status_route`): Returns JSON from `get_indexing_status()` merged with `_indexing_status_state`.
  - `GET /open` (`openfile`): Validates `os.path.exists(path)`, opens file with `os.startfile(path)` (Windows), redirects back to `/search` preserving `query`, `drive`, `file_type`, `sort`, `mode`.
  - `GET /open-folder` (`open_folder`): Validates `os.path.exists(path)`, runs `subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])`, redirects back to `/search`.

### `scanner/scan.py` (51 lines)
- `IGNORE_FOLDER_NAMES`: 24 folder names (`venv`, `.venv`, `env`, `.env`, `.git`, `__pycache__`, `node_modules`, `.vscode`, `.idea`, `build`, `dist`, `.pytest_cache`, `.mypy_cache`, `msys64`, `mysys64`, `cache`, `caches`, `.cache`, `tmp`, `temp`, `.tmp`, `.temp`, `appdata`, `programdata`).
- `is_ignored_path(path)`: Normalizes path case/absoluteness and checks if any path component is in `IGNORE_FOLDER_NAMES`.
- `scan_folder(folder_path)`: Uses `os.walk`, prunes ignored `dirs[:]`, and collects non-ignored file paths.

### `database/db.py` (2,975 lines)
- **Intent & Filter Helpers:** `detect_query_intent(query)` (regex-based extraction of `TYPE_ALIASES` and relative/month date bounds like `today`, `yesterday`, `last week`, `this week`, `last month`, `this month`, month names + optional year); `apply_type_filter(file_type, query_extensions)`.
- **Schema & Migrations:** `create_database()`.
- **Content Extraction:** `extract_text_from_file(file_path, extension)` supporting `.pdf` (`pypdf`, capped at 50 pages / 200,000 chars), `.docx` (`python-docx`, paragraphs + tables), `.doc` (`legacy_doc`), `.txt`/`.md` (UTF-8/Latin-1/CP1252, capped at 5 MB), `.csv` (`csv.reader`, capped at 10,000 rows), `.pptx` (`python-pptx`, text frames + tables), `.xlsx` (`openpyxl` read-only/data-only, capped at 10,000 rows/sheet).
- **Content Indexing:** `index_file_content(file_id, file_path, extension)` (caps stored text at 1,000,000 chars, updates `files` and `files_fts`), `index_all_content(progress_callback=None)`, `rebuild_fts_index()`.
- **Metadata & Quick Scan:** `save_files(files, location_id)` (upsert on `file_path`), `save_indexed_location(path)`, `get_available_drives()`, `get_indexed_locations()`, `quick_scan_location(location_id)` (compares disk vs DB using `os.path.normcase(os.path.abspath(...))`, deletes ignored paths, inserts new, updates modified, deletes missing).
- **Search (Layers 1 & 2):** `search_files(query, drive=None, sort_by="relevance", file_type="relevant", search_mode="all")`.
  - Strips `stop_words` from `query` using `re.findall(r"[A-Za-z0-9]+", query)`.
  - If `search_mode in ("all", "content")`, queries `files_fts` with `file_content : <term1> AND <term2>` (`LIMIT 500`).
  - Builds SQL `WHERE` clause combining filename `LIKE` terms, separator-stripped `normalized_sql_name`, `file_path IN (...)` for content hits, drive filter, `apply_type_filter`, date bounds from `detect_query_intent`, and `ignored_patterns` exclusions.
  - Filters rows again in Python with `is_ignored_path(row[1])`.
  - Ranks results in Python via `relevance_score(file)` (17+ rules: intent extension +1400/-900, date +600, exact name +3000, stem +1800, normalized +1600, token +500, all tokens +700, prefix +250, substring +40, user ext +80, internal ext -250, internal dir -180, exe/msi +250, Program Files +100, exact override +2500/+3000, content match +400, etc.).
  - Returns 5-tuples `(file_name, file_path, formatted_date, formatted_size, match_type)`.
- **Search (Layer 3):** `get_embedding_model()` (lazy thread-safe singleton loading `SentenceTransformer("all-MiniLM-L6-v2")`), `generate_embedding(text)` (truncates to 2,000 chars, returns `np.float32` 384-dim vector), `natural_language_search(query, drive=None, file_type="relevant", top_k=50)` (extracts intent, strips stop words into `topic_query`, embeds `topic_query`, queries `file_embeddings JOIN files` with SQL filters, computes cosine similarity, applies +0.08/-0.05 date boost and +0.12/-0.12 extension boost, filters `similarity > 0.25`, returns top `top_k` 5-tuples with `match_type="semantic"`).
- **Embedding Management:** `generate_file_embedding(file_id)`, `generate_all_embeddings(limit=500, progress_callback=None)`, `get_indexing_status()`, `clean_stale_records()`.

---

## 5. Verified Features vs. Limitations & Quirks

### Verified (from live code + `test_results.json` 43/43 PASS)
- Layer 1 filename, extension, separator-insensitive, and drive filtering.
- Layer 2 content extraction and FTS5 search for `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.pptx`, `.xlsx`.
- Graceful handling of corrupted PDFs and `.doc` files without crashing.
- Quick Scan detection of added/modified/deleted files and re-indexing of modified content.
- Hybrid query intent detection (`detect_query_intent`) for file types and dates.
- `Relevant` vs `All Types` vs specific extension filtering.
- Ignored folder exclusion at scan time, Quick Scan, and search time.
- Layer 3 semantic embedding generation (`all-MiniLM-L6-v2`) and cosine similarity search.

### Confirmed Limitations, Bugs & Unverified Items
1. **Windows-Only Dependencies:** `os.startfile()` and `explorer /select,` in `app.py`, plus `A:\`–`Z:\` drive probing in `get_available_drives()`, tie ATLAS to Windows.
2. **UI Suggestion/Mode Gap:** Inline JS in `templates/index.html` calls `/suggestions` with `query`, `drive`, `file_type`, but does not pass `mode`, and `get_search_suggestions()` only searches `file_name` (not content).
3. **`natural_language_search()` Coverage Gap:** Only searches files present in `file_embeddings`. `generate_all_embeddings()` only embeds files with non-empty `file_content` and processes at most `limit=500` per invocation. Furthermore, `sort_by` is ignored in `semantic` mode.
4. **FTS5 Synchronization on Deletion:** `quick_scan_location()` deletes rows from `files` directly (`DELETE FROM files WHERE id = ?`) without deleting corresponding entries from `files_fts` (an external-content FTS5 table) or calling `rebuild_fts_index()`. Also, lines 1102–1109 contain a duplicate `DELETE FROM files WHERE id = ?` statement when cleaning ignored paths, and do not increment `deleted`.
5. **Embedding Hash Heuristic:** `content_hash` uses `"hash_" + str(len(file_content))`, meaning if a file's content changes without changing its character length, `generate_all_embeddings()` will not detect the change.
6. **Hardcoded `atlas.db` Relative Path:** `sqlite3.connect("atlas.db")` assumes the Flask app is launched from `d:\Atlas`.
7. **Sequential Cosine Similarity:** `natural_language_search()` loads all filtered embeddings into Python and loops row-by-row rather than using a vector index (e.g., FAISS / `sqlite-vec`).
8. **Legacy `.doc` Extraction:** Tested with a synthetic OLE header (`legacy_project_spec.doc`, 62 bytes) which returned 0 chars gracefully; real-world complex Word 97–2003 `.doc` files were not benchmarked in `test_atlas.py`.
9. **Empty `static/js/script.js`:** All frontend JS is currently embedded inline at the bottom of `templates/index.html`.
10. **Unverified at Runtime in This Session:** Flask HTTP routes were not re-executed in this documentation-only session (verified statically; previous session logs are superseded by current source inspection).

---

## 6. Investigation Progress
- [x] Directory & file tree inspection
- [x] Git history inspection
- [x] Read-only SQLite database inspection (`atlas.db`)
- [x] Complete read of `app.py`, `scanner/scan.py`, `database/db.py`, `templates/index.html`, `requirements.txt`, `README.md`, `test_atlas.py`, `test_results.json`
- [x] Generate architecture, workflow, and database ER diagrams (`documentation/diagrams/`)
- [x] Generate Document 1: `documentation/ATLAS_Final_Project_Report.docx`
- [x] Generate Document 2: `documentation/ATLAS_Complete_Project_Guide.docx`
- [x] Programmatically verify both `.docx` files (structure, headings, formatting, fonts, margins, tables, embedded figures)
