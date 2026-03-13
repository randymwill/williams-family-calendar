from pathlib import Path

path = Path("calendar.ics")
text = path.read_text(encoding="utf-8", errors="replace")

text = text.replace("\r\n", "\n").replace("\r", "\n")
lines = [l.rstrip() for l in text.split("\n") if l.strip()]
normalized = "\r\n".join(lines) + "\r\n"

path.write_text(normalized, encoding="utf-8")
print("Normalized calendar.ics")
