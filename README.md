# ATLAS

ATLAS is a local-first file search engine for Windows. It indexes file metadata and document content, provides filename and full-text search, and uses local semantic embeddings to support everyday natural-language queries.

ATLAS does not upload indexed file contents or search queries to an external service.

## Features

- **File metadata search** across filenames, extensions, paths, sizes, and modification dates
- **Full-text document search** using SQLite FTS5
- **Natural-language semantic search** using `all-MiniLM-L6-v2`
- **Hybrid intent detection** for file formats and dates
- **Relevant file filter** for common personal and professional documents
- **Quick Scan** to detect added, modified, deleted, and newly ignored files
- **Background document and embedding indexing**
- **Drive selection, search modes, sorting, open-file, and open-folder actions**
- **Local SQLite database** for metadata and extracted content

## Supported Documents

Document content extraction currently supports:

- PDF (`.pdf`)
- Microsoft Word (`.doc`, `.docx`)
- PowerPoint (`.pptx`)
- Excel (`.xlsx`)
- Plain text (`.txt`)
- Markdown (`.md`)
- CSV (`.csv`)

Metadata indexing and filename search support additional file types.

## Search Modes

### All (Name + Content)

Combines filename matching with SQLite FTS5 content results and relevance ranking.

### Filename Only

Searches indexed filenames and paths.

### Content Only

Searches extracted document text.

### Natural Language (AI)

Uses local Sentence Transformers embeddings to find semantically related documents. Natural-language queries can also use deterministic metadata rules for format and date constraints.

Examples:

```text
pdf notes of python saved in june
presentation about machine learning created last month
ppt about networking
pdf containing Python
```

## Filters and Ranking

**Relevant** is the default TYPE filter. It includes:

- PDF
- DOC/DOCX
- PPT/PPTX
- XLS/XLSX
- TXT
- MD
- CSV

**All Files** restores broad results without the Relevant extension restriction. Individual extension filters remain available.

Explicit format names in natural-language queries influence ranking. For example, a PDF query prioritizes PDF files, while a PowerPoint query prioritizes `.ppt` and `.pptx` files.

Date phrases such as `today`, `yesterday`, `last week`, `this week`, `last month`, `this month`, or a month name are matched against file modification metadata.

## Ignored Folders

Initial scanning and Quick Scan exclude common development and system folders, including:

- `venv`, `.venv`, `env`, `.env`
- `mysys64`, `msys64`
- `.git`, `.vscode`, `.idea`
- `node_modules`, `__pycache__`
- `build`, `dist`
- cache and temporary directories

Ignored paths are also excluded again at search time. Quick Scan removes matching ignored-path records when rescan encounters previously indexed files. It does not perform a broad database deletion.

## Requirements

- Windows
- Python 3.10 or newer
- Flask
- PyPDF
- python-docx
- python-pptx
- openpyxl
- legacy-doc
- Sentence Transformers
- PyTorch

See [`requirements.txt`](requirements.txt) for package requirements.

## Installation

```powershell
git clone https://github.com/Divyansh921/Atlas.git
cd Atlas

py -m venv venv
.\venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

The first semantic search or embedding operation downloads `sentence-transformers/all-MiniLM-L6-v2` unless it is already cached locally.

## Running ATLAS

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

ATLAS creates or opens `atlas.db` in the project directory. Existing database records are preserved across application restarts.

## Using ATLAS

1. Open the application.
2. Use **Scan** to index a folder.
3. Use **Quick Scan** to update already indexed locations.
4. Start **Content Indexing** to extract searchable text.
5. Start **AI Semantic Indexing** to generate local document embeddings.
6. Search with filename, content, or natural-language mode.
7. Use the Type, Drive, Mode, and Sort controls to refine results.

## Project Structure

```text
app.py                 Flask application and routes
database/
  db.py                SQLite schema, indexing, and search implementation
scanner/
  scan.py              Folder traversal and ignored-path detection
templates/
  index.html           Main search interface
static/
  css/style.css        Application styling
  js/script.js         Suggestions and frontend behavior
test_atlas.py          Integration and search test suite
test_corpus/           Isolated document fixtures
atlas.db               Local SQLite index
requirements.txt       Python dependencies
```

## Testing

Run the test suite with the project virtual environment:

```powershell
.\venv\Scripts\python.exe test_atlas.py
```

The suite covers:

- Database migration and schema
- Filename, content, and semantic search
- PDF and presentation ranking
- Natural-language file-type and date intent
- Relevant and All Files filters
- Individual extension filters
- Ignored-folder detection
- Quick Scan modified-file handling
- Document extraction
- Embedding generation
- Search suggestions

Detailed results are written to [`test_results.json`](test_results.json).

## Database

ATLAS uses SQLite:

- `files`: indexed file metadata and extracted content
- `files_fts`: FTS5 full-text index
- `indexed_locations`: scanned roots and scan timestamps
- `file_embeddings`: stored semantic embeddings

Database migrations add missing columns and tables without recreating existing records.

The existing database should be backed up before major upgrades:

```powershell
Copy-Item atlas.db atlas.backup.db
```

## Model Limitation

`all-MiniLM-L6-v2` is a lightweight general-purpose embedding model. It is useful for practical topic matching but is not a conversational reasoning model.

ATLAS improves it with:

- File-type intent extraction
- Modification-date filtering
- Filename relevance boosts
- FTS5 content confirmation
- Relevant-file filtering

A larger model or external API is not required for the current implementation.
