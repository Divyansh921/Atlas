import os
import sys
import socket
import subprocess
import threading
import logging
import webbrowser

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify
)

from database.db import (
    create_database,
    save_files,
    save_indexed_location,
    search_files,
    get_available_drives,
    quick_scan_location,
    get_indexed_locations,
    get_search_suggestions,
    natural_language_search,
    index_all_content,
    generate_all_embeddings,
    get_indexing_status
)

from scanner.scan import scan_folder

logger = logging.getLogger("atlas")


def get_resource_path(relative_path):
    """Resolve asset paths for both dev mode and PyInstaller frozen builds."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


app = Flask(
    __name__,
    template_folder=get_resource_path("templates"),
    static_folder=get_resource_path("static")
)
app.secret_key = os.environ.get("ATLAS_SECRET_KEY", "atlas-local-desktop-key")


# ============================================================
# CREATE DATABASE
# ============================================================

create_database()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    drives = get_available_drives()

    return render_template(
        "index.html",
        results=None,
        query="",
        drive="all",
        file_type="relevant",
        sort_by="relevance",
        mode="all",
        drives=drives,
        message=""
    )


# ============================================================
# SEARCH
# ============================================================

@app.route("/search")
def search():

    query = request.args.get(
        "query",
        ""
    ).strip()

    drive = request.args.get(
        "drive",
        "all"
    )

    file_type = request.args.get(
        "file_type",
        "relevant"
    )

    sort_by = request.args.get(
        "sort",
        "relevance"
    )

    mode = request.args.get(
        "mode",
        "all"
    )

    if mode == "semantic":

        results = natural_language_search(
            query,
            drive=drive,
            file_type=file_type
        )

    else:

        results = search_files(
            query,
            drive=drive,
            sort_by=sort_by,
            file_type=file_type,
            search_mode=mode
        )

    drives = get_available_drives()

    return render_template(
        "index.html",
        results=results,
        query=query,
        drive=drive,
        file_type=file_type,
        sort_by=sort_by,
        mode=mode,
        drives=drives
    )


# ============================================================
# SEARCH SUGGESTIONS
# ============================================================

@app.route("/suggestions")
def suggestions():

    query = request.args.get(
        "query",
        ""
    ).strip()

    drive = request.args.get(
        "drive",
        "all"
    )

    file_type = request.args.get(
        "file_type",
        "relevant"
    )


    # --------------------------------------------------------
    # Do not show suggestions for very short searches
    # --------------------------------------------------------

    if len(query) < 2:

        return jsonify([])


    # --------------------------------------------------------
    # Get suggestions from database
    # --------------------------------------------------------

    suggestions = get_search_suggestions(
        query,
        drive,
        file_type
    )


    return jsonify(
        suggestions
    )


# ============================================================
# NORMAL SCAN
# ============================================================

@app.route("/scan")
def scan():

    folder = request.args.get(
        "folder"
    )

    if not folder:

        return "No folder selected."

    location_id = save_indexed_location(
        folder
    )

    files = scan_folder(
        folder
    )

    save_files(
        files,
        location_id
    )

    print(
        "INDEXED LOCATION SAVED:",
        folder
    )

    print(
        "LOCATION ID:",
        location_id
    )

    # Automatically index content for newly scanned files in the background
    threading.Thread(
        target=index_all_content,
        daemon=True
    ).start()

    flash(
        f"Successfully indexed {len(files)} files. "
        f"Document content indexing started in the background."
    )

    return redirect(
        url_for("home")
    )


# ============================================================
# QUICK SCAN
# ============================================================

@app.route("/quick-scan")
def quick_scan():

    locations = get_indexed_locations()

    if not locations:

        flash(
            "No indexed locations found."
        )

        return redirect(
            url_for("home")
        )

    total_added = 0
    total_modified = 0
    total_deleted = 0

    for (
        location_id,
        path,
        last_scanned
    ) in locations:

        result = quick_scan_location(
            location_id
        )

        if "error" in result:

            continue

        total_added += result["added"]

        total_modified += result["modified"]

        total_deleted += result["deleted"]

    # Re-index content for newly added / modified files in background
    if total_added > 0 or total_modified > 0:

        threading.Thread(
            target=index_all_content,
            daemon=True
        ).start()

    flash(
        f"Quick Scan complete — "
        f"{total_added} added, "
        f"{total_modified} modified, "
        f"{total_deleted} deleted."
    )

    return redirect(
        url_for("home")
    )


# ============================================================
# CONTENT & EMBEDDINGS INDEXING ROUTES
# ============================================================

_indexing_lock = threading.Lock()
_indexing_status_state = {
    "indexing_content": False,
    "indexing_embeddings": False
}


@app.route("/index-content")
def index_content_route():

    def task():

        with _indexing_lock:

            _indexing_status_state["indexing_content"] = True

        try:

            res = index_all_content()

            logger.info(
                "Content indexing complete: %s",
                res
            )

        except Exception as e:

            logger.error(
                "Content indexing failed: %s",
                e
            )

        finally:

            with _indexing_lock:

                _indexing_status_state["indexing_content"] = False

    threading.Thread(
        target=task,
        daemon=True
    ).start()

    flash(
        "Document content indexing started in the background."
    )

    return redirect(
        url_for("home")
    )


@app.route("/generate-embeddings")
def generate_embeddings_route():

    def task():

        with _indexing_lock:

            _indexing_status_state["indexing_embeddings"] = True

        try:

            res = generate_all_embeddings()

            logger.info(
                "Embedding generation complete: %s",
                res
            )

        except Exception as e:

            logger.error(
                "Embedding generation failed: %s",
                e
            )

        finally:

            with _indexing_lock:

                _indexing_status_state["indexing_embeddings"] = False

    threading.Thread(
        target=task,
        daemon=True
    ).start()

    flash(
        "AI Semantic Indexing started in the background."
    )

    return redirect(
        url_for("home")
    )


@app.route("/indexing-status")
def indexing_status_route():

    status = get_indexing_status()

    status.update(
        _indexing_status_state
    )

    return jsonify(status)


# ============================================================
# OPEN FILE
# ============================================================

@app.route("/open")
def openfile():

    path = request.args.get(
        "path"
    )

    query = request.args.get(
        "query",
        ""
    )

    drive = request.args.get(
        "drive",
        "all"
    )

    file_type = request.args.get(
        "file_type",
        "relevant"
    )

    sort_by = request.args.get(
        "sort",
        "relevance"
    )

    mode = request.args.get(
        "mode",
        "all"
    )


    # --------------------------------------------------------
    # No file path received
    # --------------------------------------------------------

    if not path:

        flash(
            "No file selected."
        )

        return redirect(
            url_for("home")
        )


    # --------------------------------------------------------
    # Check if file still exists
    # --------------------------------------------------------

    if not os.path.exists(path):

        flash(
            "File no longer exists."
        )

        return redirect(
            url_for(
                "search",
                query=query,
                drive=drive,
                file_type=file_type,
                sort=sort_by,
                mode=mode
            )
        )


    # --------------------------------------------------------
    # Try to open file
    # --------------------------------------------------------

    try:

        os.startfile(
            path
        )

    except Exception as e:

        print(
            "ERROR OPENING FILE:",
            e
        )

        flash(
            "Atlas could not open this file."
        )

        return redirect(
            url_for(
                "search",
                query=query,
                drive=drive,
                file_type=file_type,
                sort=sort_by,
                mode=mode
            )
        )


    # --------------------------------------------------------
    # Return to search results
    # --------------------------------------------------------

    return redirect(
        url_for(
            "search",
            query=query,
            drive=drive,
            file_type=file_type,
            sort=sort_by,
            mode=mode
        )
    )


# ============================================================
# OPEN FOLDER
# ============================================================

@app.route("/open-folder")
def open_folder():

    path = request.args.get(
        "path"
    )

    query = request.args.get(
        "query",
        ""
    )

    drive = request.args.get(
        "drive",
        "all"
    )

    file_type = request.args.get(
        "file_type",
        "relevant"
    )

    sort_by = request.args.get(
        "sort",
        "relevance"
    )

    mode = request.args.get(
        "mode",
        "all"
    )


    # --------------------------------------------------------
    # No file path received
    # --------------------------------------------------------

    if not path:

        flash(
            "No file selected."
        )

        return redirect(
            url_for("home")
        )


    # --------------------------------------------------------
    # Check if file still exists
    # --------------------------------------------------------

    if not os.path.exists(path):

        flash(
            "File no longer exists."
        )

        return redirect(
            url_for(
                "search",
                query=query,
                drive=drive,
                file_type=file_type,
                sort=sort_by,
                mode=mode
            )
        )


    # --------------------------------------------------------
    # Open Windows Explorer and select the file
    # --------------------------------------------------------

    try:

        subprocess.Popen(
            [
                "explorer",
                "/select,",
                os.path.normpath(path)
            ]
        )

    except Exception as e:

        print(
            "ERROR OPENING FOLDER:",
            e
        )

        flash(
            "Atlas could not open the file location."
        )

        return redirect(
            url_for(
                "search",
                query=query,
                drive=drive,
                file_type=file_type,
                sort=sort_by,
                mode=mode
            )
        )


    # --------------------------------------------------------
    # Return to search results
    # --------------------------------------------------------

    return redirect(
        url_for(
            "search",
            query=query,
            drive=drive,
            file_type=file_type,
            sort=sort_by,
            mode=mode
        )
    )


# ============================================================
# RUN APPLICATION
# ============================================================

def find_available_port(preferred_port=5000):
    """Return preferred_port if free on 127.0.0.1, otherwise an available local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", preferred_port)) != 0:
            return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def open_browser(port):
    webbrowser.open_new(f"http://127.0.0.1:{port}")

@app.route("/shutdown", methods=["POST"])
def shutdown_app():
    """Gracefully terminate the background server process."""
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"status": "shutting_down"}

if __name__ == "__main__":
    port = find_available_port(5000)
    threading.Timer(1.2, open_browser, args=(port,)).start()
    app.run(
        host="127.0.0.1",
        port=port,
        debug=False,
        use_reloader=False
    )