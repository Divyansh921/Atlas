from flask import Flask, render_template, request

from database.db import create_database, save_files, search_files
from scanner.scan import scan_folder

app = Flask(__name__)

# Create the database 
create_database()


@app.route("/")
def home():
    return render_template(
        "index.html",
        results=None,
        query=""
    )


@app.route("/search")
def search():

    query = request.args.get("query") #get what user typed

    results = search_files(query) #search database

    return render_template(
        "index.html",
        results=results,
        query=query
    )


@app.route("/scan")
def scan():

    folder = r"D:\Atlas"

    files = scan_folder(folder)

    save_files(files)

    return f"Saved {len(files)} files to Atlas database."


if __name__ == "__main__":
    app.run(debug=False)