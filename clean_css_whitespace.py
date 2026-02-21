import os

css_path = r"c:\Users\ASUS\Desktop\Inside\app\static\style.css"

with open(css_path, "rb") as f:
    content = f.read()

# Decode
text = content.decode("utf-8", errors="replace")

# Split lines and filter out multiple empty lines
lines = text.splitlines()
cleaned_lines = []
last_was_empty = False

for line in lines:
    if not line.strip():
        if not last_was_empty:
            cleaned_lines.append("")
        last_was_empty = True
    else:
        cleaned_lines.append(line)
        last_was_empty = False

final_text = "\n".join(cleaned_lines)

with open(css_path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("style.css compressed and cleaned.")
