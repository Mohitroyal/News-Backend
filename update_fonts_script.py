import os
import glob

template_dir = r"c:\Users\MOHIT\Downloads\newscraft-ai-figma-design\production_backend\app\renderer\templates"
files = glob.glob(os.path.join(template_dir, "**", "*.css"), recursive=True)
files.extend(glob.glob(os.path.join(template_dir, "**", "*.html"), recursive=True))

replacement_fonts = "'Noto Serif Telugu', 'Noto Sans Telugu', 'Noto Serif Devanagari', 'Noto Sans Devanagari', 'Noto Serif Kannada', 'Noto Sans Kannada', 'Noto Serif Malayalam', 'Noto Sans Malayalam', 'Noto Serif Tamil', 'Noto Sans Tamil', 'Noto Serif Bengali', 'Noto Sans Bengali', 'Noto Serif Gujarati', 'Noto Sans Gujarati', 'Noto Serif Gurmukhi', 'Noto Sans Gurmukhi', 'Noto Serif Oriya', 'Noto Sans Oriya'"

for fpath in set(files):
    if "master_layout" in fpath:
        continue # Already updated this one carefully

    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    if replacement_fonts in content:
        continue
    
    new_content = content.replace("'Noto Serif Telugu', 'Noto Sans Telugu'", replacement_fonts)
    new_content = new_content.replace("'Noto Sans Telugu'", replacement_fonts)
    
    if new_content != content:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {fpath}")
