import os 

def scan_folder(folder_path):
    files=[]
    for root, dirs, filenames in os.walk(folder_path):
        for file in filenames:
            full_path = os.path.join(root,file)
            files.append(full_path)
    return files