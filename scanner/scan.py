import os

def scan_folder(folder_path):
    files = []

    ignore_folders = ["venv", ".git", "__pycache__", "node_modules"]

    for root, dirs, filenames in os.walk(folder_path):

        dirs[:] = [folder for folder in dirs if folder not in ignore_folders]

        for file in filenames:
            full_path = os.path.join(root, file)
            files.append(full_path)

    return files