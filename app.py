import os

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
    search_files,
    get_available_drives
)

from scanner.scan import scan_folder


app = Flask(__name__)
app.secret_key = "secret_key"

# Create the database
create_database()


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


@app.route("/search")
def search():

    query = request.args.get("query", "").strip()

    drive = request.args.get("drive", "all")

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


@app.route("/scan")
def scan():

    folder = request.args.get("folder")

    if not folder:
        return "No folder selected."

    files = scan_folder(folder)

    save_files(files)

    flash(
        f"Successfully indexed {len(files)} files."
    )

    return redirect(url_for("home"))


@app.route("/open")
def openfile():

    path = request.args.get("path")

    query = request.args.get("query", "")
    drive = request.args.get("drive", "all")
    sort_by = request.args.get("sort", "relevance")

    if not path:
        flash("No file selected.")

        return redirect(url_for("home"))

    os.startfile(path)

    return redirect(
        url_for(
            "search",
            query=query,
            drive=drive,
            sort=sort_by
        )
    )


if __name__ == "__main__":
    app.run(debug=False)