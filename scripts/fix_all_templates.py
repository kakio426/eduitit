import re
import os

def fix_split_tags(directory):
    # {{ ... }} 사이에 줄바꿈이 있는 것을 찾아서 한 줄로 합칩니다.
    # \s+ 는 줄바꿈을 포함한 모든 공백을 의미합니다.
    # 이 스크립트는 {{ 와 }} 사이의 모든 줄바꿈과 여분의 공백을 단일 공백으로 치환합니다.
    
    tag_pattern = re.compile(r'\{\{([\s\S]*?)\}\}')
    logic_pattern = re.compile(r'\{%([\s\S]*?)%\}')
    
    count = 0
    
    for root, dirs, files in os.walk(directory):
        if any(skip in root for skip in ['.git', 'venv', 'node_modules', 'staticfiles', 'media', '__pycache__']):
            continue
            
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    new_content = content
                    
                    # {{ ... }} 처리
                    def merge_mustache(match):
                        inner = match.group(1)
                        if '\n' in inner:
                            # 줄바꿈이 있으면 한 줄로 합치고 공백 정리
                            merged = " ".join(inner.split())
                            return f"{{{{ {merged} }}}}"
                        return match.group(0)

                    new_content = tag_pattern.sub(merge_mustache, new_content)
                    
                    # {% ... %} 처리 (복잡한 if/for 블록 태그 자체는 제외하고 태그 기호 안의 줄바꿈만 처리)
                    def merge_logic(match):
                        inner = match.group(1)
                        if '\n' in inner:
                             merged = " ".join(inner.split())
                             return f"{{% {merged} %}}"
                        return match.group(0)
                        
                    new_content = logic_pattern.sub(merge_logic, new_content)

                    if new_content != content:
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        print(f"[FIXED] {path}")
                        count += 1
                        
                except Exception as e:
                    print(f"[ERROR] Failed to fix {path}: {e}")
    
    return count

if __name__ == "__main__":
    print("🧹 Cleaning up all split Django tags in the project...")
    fixed_count = fix_split_tags('.')
    print(f"\n✨ Done! Fixed {fixed_count} files.")
