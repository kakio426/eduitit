
import os
import re

def fix_html_files(directory):
    double_brace_pattern = re.compile(r'\{\{.*?\}\}', re.DOTALL)
    percent_tag_pattern = re.compile(r'\{%.*?%\}', re.DOTALL)
    
    fixed_count = 0
    
    for root, dirs, files in os.walk(directory):
        if any(x in root for x in ['.git', 'node_modules', '.gemini', '.venv', 'staticfiles']):
            continue
            
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    new_content = content
                    
                    def fix_double(match):
                        tag = match.group(0)
                        if '\n' in tag or '\r' in tag:
                            inner = tag[2:-2].strip()
                            inner = re.sub(r'\s+', ' ', inner)
                            return f"{{{{ {inner} }}}}"
                        return tag
                    
                    new_content = double_brace_pattern.sub(fix_double, new_content)
                    
                    def fix_percent(match):
                        tag = match.group(0)
                        if '\n' in tag or '\r' in tag:
                            # We keep block tags multi-line if they contain content, 
                            # but the {% ... %} part itself should be single line.
                            inner = tag[2:-2].strip()
                            inner = re.sub(r'\s+', ' ', inner)
                            return f"{{% {inner} %}}"
                        return tag
                    
                    new_content = percent_tag_pattern.sub(fix_percent, new_content)

                    if new_content != content:
                        with open(path, 'w', encoding='utf-8', newline='\n') as f:
                            f.write(new_content)
                        fixed_count += 1
                        print(f"Fixed tags in: {path}")

                except Exception as e:
                    print(f"Error processing {path}: {e}")
                    
    print(f"Done. Fixed tags in {fixed_count} files.")

if __name__ == "__main__":
    base_dir = r"c:\Users\kakio\eduitit"
    fix_html_files(base_dir)
