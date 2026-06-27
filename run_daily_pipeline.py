import os
import sys

print("\n=========================================")
print("DIAGNOSTIC LOG: MAPPING CONTAINER FILES")
print("=========================================\n")

print(f"Current Working Directory: {os.getcwd()}")
print(f"Python Search Paths (sys.path): {sys.path}\n")

print("--- Root Folder Layout (/app) ---")
try:
    for root, dirs, files in os.walk("/app"):
        # Don't print hidden git or cache files
        if '.git' in root or '__pycache__' in root:
            continue
        level = root.replace("/app", "").count(os.sep)
        indent = " " * 4 * level
        print(f"{indent}[Folder] {os.path.basename(root)}/")
        sub_indent = " " * 4 * (level + 1)
        for f in files:
            print(f"{sub_indent}{f}")
except Exception as e:
    print(f"Error mapping directories: {e}")

print("\n=========================================")
