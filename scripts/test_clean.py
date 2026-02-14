
import re

def clean_markdown(text):
    if not text:
        return text
    
    # 1. Remove Bold/Italic (***, **, *, __, _)
    text = re.sub(r'(\*{1,3}|_{1,3})', '', text)
    
    # 2. Remove Headings (### Title) at the start of any line
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    
    # 3. Remove Blockquotes (> Text) at the start of any line
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    
    # 4. Remove inline code (`code`)
    text = re.sub(r'`', '', text)
    
    # 5. Remove horizontal rules (---, ___, ***)
    text = re.sub(r'^[-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    return text.strip()

test_text = "### 1. Title\n\n**Bold** and *Italic*\n\n> Tip: Hello"
print(f"Original: {repr(test_text)}")
print(f"Cleaned: {repr(clean_markdown(test_text))}")
