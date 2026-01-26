
import os

path = r"c:\Users\kakio\eduitit\core\templates\core\includes\card_product.html"
try:
    # Try reading as UTF-16LE (common PowerShell redirect encoding)
    with open(path, 'rb') as f:
        content = f.read().decode('utf-16')
except Exception:
    # Fallback or other attempts
    content = None

if content:
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print("Fixed encoding to UTF-8")
else:
    print("Could not read as UTF-16")
