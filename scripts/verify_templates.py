import re
import os
import sys

def check_django_tags(directory):
    # {{ ... }} 사이에 줄바꿈이 있는 패턴
    error_pattern = re.compile(r'\{\{[^}]*\n[^}]*\}\}')
    found_error = False
    
    for root, dirs, files in os.walk(directory):
        if any(skip in root for skip in ['.git', 'venv', 'node_modules', 'staticfiles', 'media', '__pycache__']):
            continue
            
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        matches = error_pattern.finditer(content)
                        for match in matches:
                            # 줄 번호 계산
                            line_num = content.count('\n', 0, match.start()) + 1
                            tag_text = match.group().replace('\n', '\\n')
                            print(f"[ERR] {path} (Line {line_num}): {tag_text}")
                            found_error = True
                except Exception as e:
                    pass
    
    return found_error

if __name__ == "__main__":
    if check_django_tags('.'):
        sys.exit(1)
    else:
        print("PASS: No split tags found.")
        sys.exit(0)
