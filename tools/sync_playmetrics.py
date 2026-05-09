import hashlib
import json
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
WEST_HAM_PREFIX = "MO Girls 2017/2018 West Ham - "
STATE_PATH = Path("calendar_state.json")
CHANGE_REPORT_PATH = Path("calendar_changes.md")


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def unfold_ics(text: str) -> str:
    lines = normalize(text).split("\n")
    unfolded: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return "\n".join(unfolded)


def split_events(text: str) -> tuple[list[str], list[str], list[str]]:
    lines = unfold_ics(text).split("\n")
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


def get_property(block: str, key: str) -> str:
    prefix = f"{key}:"
    return next((line[len(prefix) :] for line in block.split("\n") if line.startswith(prefix)), "")


def to_title_case(text: str) -> str:
    return " ".join(word.capitalize() for word in text.split())


def rewrite_summary(feed: dict[str, str], summary: str) -> str:
    if feed["source_id"] == "vetta-soccer":
        label = f"{feed['name']} - "
        if summary.startswith(label):
            summary = summary[len(label) :]
        summary = summary.replace("G2 2017 ", "")
        return label + summary

    if feed["source_id"] != "playmetrics-soccer":
        label = f"{feed['name']} - "
        return summary if summary.startswith(label) else label + summary

    old_label = f"{feed['name']} - "
    if summary.startswith(old_label):
        summary = summary[len(old_label) :]

    if not summary.startswith(WEST_HAM_PREFIX):
        return summary

    detail = summary[len(WEST_HAM_PREFIX) :]
    if detail == "Practice":
        return "West Ham Practice - SG"
    if detail == "Game":
        return "West Ham Game - SG"
    if detail.startswith("TECH"):
        return "West Ham Tech Training - SG"

    return f"West Ham {to_title_case(detail)} - SG"


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
        block = set_property(block, "SUMMARY", rewrite_summary(feed, summary))

    marker = source_marker(feed["source_id"])
    if marker not in block:
        lines = block.split("\n")
        end_index = lines.index("END:VEVENT")
        lines.insert(end_index, marker)
        block = "\n".join(lines)
    return block


def source_name(source_id: str) -> str:
    if source_id == "manual":
        return "Manual Calendar"
    return next(
        (feed["name"] for feed in FEEDS if feed["source_id"] == source_id),
        source_id,
    )


def event_source(block: str) -> str:
    for feed in FEEDS:
        if event_has_source(block, feed["source_id"]):
            return feed["source_id"]
    return ""


def event_fingerprint(block: str) -> str:
    ignored_prefixes = ("DTSTAMP:", "CREATED:", "LAST-MODIFIED:", "SEQUENCE:")
    stable_lines = [
        line
        for line in block.split("\n")
        if line and not line.startswith(ignored_prefixes)
    ]
    return hashlib.sha256("\n".join(stable_lines).encode("utf-8")).hexdigest()


def event_snapshot(block: str) -> dict[str, str]:
    return {
        "summary": get_property(block, "SUMMARY"),
        "dtstart": get_property(block, "DTSTART;TZID=America/Chicago")
        or get_property(block, "DTSTART"),
        "dtend": get_property(block, "DTEND;TZID=America/Chicago")
        or get_property(block, "DTEND"),
        "location": get_property(block, "LOCATION"),
        "source": event_source(block),
        "fingerprint": event_fingerprint(block),
    }


def calendar_event_state(events: list[str]) -> dict[str, dict[str, str]]:
    state: dict[str, dict[str, str]] = {}
    for event in events:
        uid = get_property(event, "UID")
        if uid:
            snapshot = event_snapshot(event)
            if not snapshot["source"]:
                snapshot["source"] = "manual"
            state[uid] = snapshot
    return state


def load_previous_state() -> dict[str, dict[str, str]]:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def write_state(state: dict[str, dict[str, str]]) -> None:
    STATE_PATH.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def describe_event(event: dict[str, str]) -> str:
    parts = [event["summary"] or "(No summary)"]
    if event["dtstart"]:
        parts.append(event["dtstart"])
    if event["location"]:
        parts.append(event["location"])
    return " | ".join(parts)


def changed_fields(before: dict[str, str], after: dict[str, str]) -> list[str]:
    fields = ("summary", "dtstart", "dtend", "location")
    return [
        f"{field}: {before.get(field, '') or '(blank)'} -> {after.get(field, '') or '(blank)'}"
        for field in fields
        if before.get(field, "") != after.get(field, "")
    ]


def write_change_report(
    previous: dict[str, dict[str, str]],
    current: dict[str, dict[str, str]],
) -> None:
    added = sorted(set(current) - set(previous))
    deleted = sorted(set(previous) - set(current))
    updated = sorted(
        uid
        for uid in set(previous) & set(current)
        if previous[uid]["fingerprint"] != current[uid]["fingerprint"]
    )

    if not added and not updated and not deleted:
        CHANGE_REPORT_PATH.write_text("", encoding="utf-8")
        return

    lines = [
        "# Williams Family AI updated calendar changes detected",
        "",
        f"Added: {len(added)}",
        f"Updated: {len(updated)}",
        f"Deleted: {len(deleted)}",
        "",
    ]

    if added:
        lines.extend(["## Added", ""])
        for uid in added:
            event = current[uid]
            lines.append(f"- [{source_name(event['source'])}] {describe_event(event)}")
        lines.append("")

    if updated:
        lines.extend(["## Updated", ""])
        for uid in updated:
            before = previous[uid]
            after = current[uid]
            lines.append(f"- [{source_name(after['source'])}] {describe_event(after)}")
            for field in changed_fields(before, after):
                lines.append(f"  - {field}")
        lines.append("")

    if deleted:
        lines.extend(["## Deleted", ""])
        for uid in deleted:
            event = previous[uid]
            lines.append(f"- [{source_name(event['source'])}] {describe_event(event)}")
        lines.append("")

    CHANGE_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def should_import_event(block: str, feed: dict[str, str]) -> bool:
    if feed["source_id"] != "vetta-soccer":
        return True

    # Vetta/Google can briefly publish placeholder events while details settle.
    return "SUMMARY:Default Description" not in block and "DESCRIPTION:Default Description" not in block


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
        tagged = [
            tag_event(event, feed)
            for event in source_events
            if should_import_event(event, feed)
        ]
        merged_events.extend(tagged)
        summary_lines.append(f"{feed['name']}: {len(tagged)} events")

    lines = header + merged_events + footer
    normalized = "\r\n".join(line.rstrip() for line in lines if line.strip()) + "\r\n"
    calendar_path.write_text(normalized, encoding="utf-8")

    previous_state = load_previous_state()
    current_state = calendar_event_state(merged_events)
    write_change_report(previous_state, current_state)
    write_state(current_state)

    print(f"Kept {len(kept_events)} local events")
    for line in summary_lines:
        print(line)


if __name__ == "__main__":
    main()
