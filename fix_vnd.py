import re
from pathlib import Path

pattern = re.compile(r"\{\{\s*([^}|]+?)\|floatformat:0\s*\}\}đ")
for path in Path("templates").rglob("*.html"):
    text = path.read_text(encoding="utf-8")
    new = pattern.sub(r"{{ \1|vnd }}", text)
    if new != text:
        path.write_text(new, encoding="utf-8")
        print("Sua:", path)