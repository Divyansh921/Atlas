import os

def scan_folder(folder_path):
    files = []

    ignore_folders = [
        "venv",
        ".venv",
        "env",
        ".env",
        ".git",
        "__pycache__",
        "node_modules",
        ".vscode",
        ".idea",
        "build",
        "dist",
        ".pytest_cache",
        ".mypy_cache",
        "msys64",
    ]
    for root, dirs, filenames in os.walk(folder_path):

        dirs[:] = [folder for folder in dirs if folder not in ignore_folders]

        for file in filenames:
            full_path = os.path.join(root, file)
            files.append(full_path)

    return files