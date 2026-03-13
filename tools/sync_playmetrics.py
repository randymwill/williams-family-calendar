from pathlib import Path
from urllib.request import urlopen


FEEDS = [
    {
        "name": "Scott Gallagher Soccer",
        "url": (
            "https://calendar.playmetrics.com/calendars/c225/t437623/p0/"
            "t6B69E936/f/calendar.ics"
        ),
        "source_id": "playmetrics-soccer",
    },
    {
        "name": "Vetta Soccer",
        "url": (
            "https://calendar.google.com/calendar/ical/"
            "b40olq2kjdejp7utk1hqavko3uk0or52%40import.calendar.google.com/"
            "public/basic.ics"
        ),
        "source_id": "vetta-soccer",
    },
    {
        "name": "Little Dribblers Basketball",
        "url": (
            "https://calendar.google.com/calendar/ical/"
            "u5ilugnl0g96040h0ar5au92eh2v0c69%40import.calendar.google.com/"
            "public/basic.ics"
        ),
        "source_id": "little-dribblers-basketball",
    },
]

SOURCE_PREFIX = "X-CODEX-SOURCE:"


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_events(text: str) -> tuple[list[str], list[str], list[str]]:
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


def source_marker(source_id: str) -> str:
    return f"{SOURCE_PREFIX}{source_id}"


def event_has_source(block: str, source_id: str) -> bool:
    return source_marker(source_id) in block


def tag_event(block: str, source_id: str) -> str:
    marker = source_marker(source_id)
    if marker in block:
        return block
    end = "\nEND:VEVENT"
    if end not in block:
        raise ValueError("VEVENT block missing END:VEVENT")
    return block.replace(end, f"\n{marker}{end}")


def fetch_source(url: str) -> str:
    with urlopen(url) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> None:
    calendar_path = Path("calendar.ics")
    current_text = calendar_path.read_text(encoding="utf-8", errors="replace")
    header, current_events, footer = split_events(current_text)

    imported_source_ids = {feed["source_id"] for feed in FEEDS}
    kept_events = [
        event
        for event in current_events
        if not any(event_has_source(event, source_id) for source_id in imported_source_ids)
    ]

    merged_events = kept_events[:]
    summary_lines: list[str] = []

    for feed in FEEDS:
        source_text = fetch_source(feed["url"])
        _, source_events, _ = split_events(source_text)
        tagged = [tag_event(event, feed["source_id"]) for event in source_events]
        merged_events.extend(tagged)
        summary_lines.append(f"{feed['name']}: {len(tagged)} events")

    lines = header + merged_events + footer
    normalized = "\r\n".join(line.rstrip() for line in lines if line.strip()) + "\r\n"
    calendar_path.write_text(normalized, encoding="utf-8")

    print(f"Kept {len(kept_events)} local events")
    for line in summary_lines:
        print(line)


if __name__ == "__main__":
    main()
