import os

IGNORE_FOLDER_NAMES = {
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
    "mysys64",
    "cache",
    "caches",
    ".cache",
    "tmp",
    "temp",
    ".tmp",
    ".temp",
    "appdata",
    "programdata",
}


def is_ignored_path(path):
    normalized = os.path.normcase(os.path.abspath(path))
    parts = [part.lower() for part in os.path.normpath(normalized).split(os.sep)]
    return any(part in IGNORE_FOLDER_NAMES for part in parts)


def scan_folder(folder_path):
    files = []
    for root, dirs, filenames in os.walk(folder_path):
        dirs[:] = [
            folder for folder in dirs
            if folder.lower() not in IGNORE_FOLDER_NAMES
            and folder.lower() not in {name.lstrip(".") for name in IGNORE_FOLDER_NAMES}
        ]

        for file in filenames:
            full_path = os.path.join(root, file)
            if not is_ignored_path(full_path):
                files.append(full_path)

    return files