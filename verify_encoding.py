
import os

path = r"c:\Users\kakio\eduitit\signatures\templates\signatures\create.html"
with open(path, 'rb') as f:
    raw = f.read()

print(f"File: {path}")
print(f"Size: {len(raw)} bytes")
print(f"First 10 bytes: {raw[:10].hex()}")

try:
    content = raw.decode('utf-8')
    print("UTF-8 Decode: Success")
    print("Sample Korean text check:")
    # Look for "연수" (Training) - expected in the title or h1
    if "연수" in content:
        print("Found '연수' (Success)")
    else:
        print("Could NOT find '연수' (Fail?)")
        # Print a snippet around where it should be
        print("Snippet:", content[30:100])
except Exception as e:
    print(f"UTF-8 Decode: Failed ({e})")
