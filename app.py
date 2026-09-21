import os
import subprocess

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from database.db import (
    create_database,
    save_files,
    save_indexed_location,
    search_files,
    get_available_drives,
    quick_scan_location,
    get_indexed_locations
)

from scanner.scan import scan_folder


app = Flask(__name__)
app.secret_key = "secret_key"


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
        sort_by="relevance",
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

    sort_by = request.args.get(
        "sort",
        "relevance"
    )

    results = search_files(
        query,
        drive,
        sort_by
    )

    drives = get_available_drives()

    return render_template(
        "index.html",
        results=results,
        query=query,
        drive=drive,
        sort_by=sort_by,
        drives=drives
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

    flash(
        f"Successfully indexed {len(files)} files."
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

    sort_by = request.args.get(
        "sort",
        "relevance"
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
                sort=sort_by
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
                sort=sort_by
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
            sort=sort_by
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

    sort_by = request.args.get(
        "sort",
        "relevance"
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
                sort=sort_by
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
                sort=sort_by
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
            sort=sort_by
        )
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=False
    )