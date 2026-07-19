from flask import Flask, render_template, request, redirect, url_for, flash 

from database.db import create_database, save_files, search_files
from scanner.scan import scan_folder

app = Flask(__name__)
app.secret_key = "secret_key"
# Create the database 
create_database()


@app.route("/")
def home():
    return render_template(
        "index.html",
        results=None,
        query="",
        message=""
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
    folder = request.args.get("folder")
  
    if not folder:
        return "No folder selected."
    files = scan_folder(folder)   
    save_files(files)

    flash(f"Successfully indexed {len(files)} files.")

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=False)