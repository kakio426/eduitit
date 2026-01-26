
import os
import re

def check_html_files(directory):
    split_tag_pattern = re.compile(r'\{\{.*[\r\n].*\}\}|\{%.*[\r\n].*%\}', re.DOTALL)
    unclosed_tag_pattern = re.compile(r'\{\{[^}]*$|\{([^%]*$)|%\}') # oversimplified but a start
    
    results = []
    
    for root, dirs, files in os.walk(directory):
        if '.git' in root or 'node_modules' in root:
            continue
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Check for split tags
                        # Note: some split tags are actually OK if they are within a script or block, 
                        # but in Django templates, split tags inside {{ }} are problematic.
                        
                        # Find all {{ ... }}
                        double_braces = re.findall(r'\{\{.*?\}\}', content, re.DOTALL)
                        for tag in double_braces:
                            if '\n' in tag or '\r' in tag:
                                results.append(f"Split tag found in {path}: {tag.strip()}")
                                
                        # Find all {% ... %}
                        # These are generally more tolerant but let's check anyway
                        percent_tags = re.findall(r'\{%.*?%\}', content, re.DOTALL)
                        for tag in percent_tags:
                            if '\n' in tag:
                                # Some tags like block/if/for/with are often multi-line in content,
                                # but the tag itself (the {% ... %}) should usually be single line 
                                # unless it's a very complex tag.
                                if not any(x in tag for x in ['block', 'if', 'for', 'with', 'include']):
                                    results.append(f"Possible problematic split % tag in {path}: {tag.strip()}")

                except Exception as e:
                    results.append(f"Error reading {path}: {e}")
                    
    return results

if __name__ == "__main__":
    base_dir = r"c:\Users\kakio\eduitit"
    issues = check_html_files(base_dir)
    if issues:
        print("\n".join(issues))
    else:
        print("No issues found.")
