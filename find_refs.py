import os

def search_string(root_dir, search_text):
    print(f"Searching for '{search_text}' in {root_dir}...")
    exclude_dirs = {'.git', 'venv', 'env', '__pycache__', 'node_modules', '.idea', '.vscode', 'staticfiles', 'media'}
    found_files = []
    
    for root, dirs, files in os.walk(root_dir):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith(('.html', '.py', '.js', '.css')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        if search_text in f.read():
                            print(f"[FOUND] {file_path}")
                            found_files.append(file_path)
                except Exception as e:
                    pass
                    
    return found_files

if __name__ == "__main__":
    base_dir = os.getcwd()
    search_string(base_dir, "fortune/images/zoo")
