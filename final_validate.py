
import os
import re

def validate_and_fix(directory):
    files_fixed = 0
    split_tags_found = 0
    
    for root, dirs, files in os.walk(directory):
        if any(S in root for S in ['.git', '__pycache__', 'node_modules']):
            continue
            
        for file in files:
            if not file.endswith('.html'):
                continue
                
            path = os.path.join(root, file)
            
            try:
                # 1. Force UTF-8 Reading (Handle UTF-16/BOM)
                with open(path, 'rb') as f:
                    raw = f.read()
                
                content = None
                
                # Check BOMs
                if raw.startswith(b'\xff\xfe'): # UTF-16 LE
                    content = raw.decode('utf-16')
                elif raw.startswith(b'\xfe\xff'): # UTF-16 BE
                    content = raw.decode('utf-16')
                elif raw.startswith(b'\xef\xbb\xbf'): # UTF-8 BOM
                    content = raw.decode('utf-8-sig')
                else:
                    try:
                        content = raw.decode('utf-8')
                    except:
                        try:
                            content = raw.decode('cp949') # Korean Windows fallback
                        except:
                            print(f"[SKIP] Could not decode {path}")
                            continue

                original_content = content
                
                # 2. Fix Split Tags (Syntax Error Prevention)
                # Regex for {{ ... }} spanning lines
                content = re.sub(r'\{\{([^}]*?)[\r\n]+([^}]*?)\}\}', lambda m: f"{{{{ {m.group(1).strip()} {m.group(2).strip()} }}}}", content)
                # Regex for {% ... %} spanning lines
                content = re.sub(r'\{%([^%]*?)[\r\n]+([^%]*?)%\}', lambda m: f"{{% {m.group(1).strip()} {m.group(2).strip()} %}}", content)

                if content != original_content:
                    split_tags_found += 1
                    print(f"[FIXED TAGS] {path}")
                
                # Save as UTF-8 No BOM
                with open(path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(content)
                    files_fixed += 1
                    
            except Exception as e:
                print(f"[ERROR] {path}: {e}")

    print(f"Verified {files_fixed} files. Fixed tags in {split_tags_found} files.")

if __name__ == "__main__":
    validate_and_fix(r"c:\Users\kakio\eduitit")
