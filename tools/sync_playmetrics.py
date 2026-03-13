from pathlib import Path
from urllib.request import urlopen


PLAYMETRICS_URL = (
    "https://calendar.playmetrics.com/calendars/c225/t437623/p0/"
    "t6B69E936/f/calendar.ics"
)


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_events(text: str) -> tuple[str, list[str], str]:
    lines = normalize(text).split("\n")
    begin = "BEGIN:VEVENT"
    end = "END:VEVENT"

    header: list[str] = []
    footer: list[str] = []
    events: list[str] = []

    i = 0
    while i < len(lines) and lines[i] != begin:
        header.append(lines[i])
        i += 1

    while i < len(lines):
        if lines[i] == begin:
            start = i
            while i < len(lines) and lines[i] != end:
                i += 1
            if i >= len(lines):
                raise ValueError("Unterminated VEVENT block")
            events.append("\n".join(lines[start : i + 1]))
            i += 1
        else:
            footer = lines[i:]
            break

    return header, events, footer


def is_playmetrics_event(block: str) -> bool:
    return "URL:https://playmetrics.com" in block


def fetch_source() -> str:
    with urlopen(PLAYMETRICS_URL) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> None:
    calendar_path = Path("calendar.ics")
    current_text = calendar_path.read_text(encoding="utf-8", errors="replace")
    source_text = fetch_source()

    header, current_events, footer = split_events(current_text)
    _, source_events, _ = split_events(source_text)

    kept_events = [event for event in current_events if not is_playmetrics_event(event)]
    merged_events = kept_events + source_events

    lines = header + merged_events + footer
    normalized = "\r\n".join(line.rstrip() for line in lines if line.strip()) + "\r\n"
    calendar_path.write_text(normalized, encoding="utf-8")

    print(
        f"Synced PlayMetrics events: kept {len(kept_events)} local events, "
        f"imported {len(source_events)} PlayMetrics events"
    )


if __name__ == "__main__":
    main()
