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
LEGACY_PLAYMETRICS_URL = "URL:https://playmetrics.com"


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


def set_property(block: str, key: str, value: str) -> str:
    lines = block.split("\n")
    end_index = lines.index("END:VEVENT")
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            lines[i] = f"{key}:{value}"
            replaced = True
            break
    if not replaced:
        lines.insert(end_index, f"{key}:{value}")
    return "\n".join(lines)


def tag_event(block: str, feed: dict[str, str]) -> str:
    uid_prefix = f"{feed['source_id']}--"

    uid_line = next((line for line in block.split("\n") if line.startswith("UID:")), None)
    if uid_line is None:
        raise ValueError("VEVENT block missing UID")

    uid = uid_line.split(":", 1)[1]
    if not uid.startswith(uid_prefix):
        block = set_property(block, "UID", uid_prefix + uid)

    summary_line = next(
        (line for line in block.split("\n") if line.startswith("SUMMARY:")),
        None,
    )
    if summary_line is not None:
        summary = summary_line.split(":", 1)[1]
        label = f"{feed['name']} - "
        if not summary.startswith(label):
            block = set_property(block, "SUMMARY", label + summary)

    marker = source_marker(feed["source_id"])
    if marker not in block:
        lines = block.split("\n")
        end_index = lines.index("END:VEVENT")
        lines.insert(end_index, marker)
        block = "\n".join(lines)
    return block


def is_legacy_playmetrics_event(block: str) -> bool:
    return LEGACY_PLAYMETRICS_URL in block and SOURCE_PREFIX not in block


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
        and not is_legacy_playmetrics_event(event)
    ]

    merged_events = kept_events[:]
    summary_lines: list[str] = []

    for feed in FEEDS:
        source_text = fetch_source(feed["url"])
        _, source_events, _ = split_events(source_text)
        tagged = [tag_event(event, feed) for event in source_events]
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
