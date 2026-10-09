import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://api.jolpi.ca/ergast/f1"
OUTPUT_FILE = "f1.ics"


def fetch_season(year):
    url = f"{API_BASE}/{year}/races/?limit=100"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Formula1-calendar/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data["MRData"]["RaceTable"]["Races"]


def escape_ics(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def parse_session(session):
    if not session or not session.get("date") or not session.get("time"):
        return None

    return datetime.fromisoformat(
        f"{session['date']}T{session['time'].replace('Z', '+00:00')}"
    ).astimezone(timezone.utc)


def create_event(uid, summary, start, duration_minutes, location):
    end = start.timestamp() + duration_minutes * 60
    end_time = datetime.fromtimestamp(end, tz=timezone.utc)

    return [
        "BEGIN:VEVENT",
        f"UID:{uid}@formula1-calendar",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end_time.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{escape_ics(summary)}",
        f"LOCATION:{escape_ics(location)}",
        "BEGIN:VALARM",
        "TRIGGER:-PT30M",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{escape_ics(summary)} starts in 30 minutes",
        "END:VALARM",
        "END:VEVENT",
    ]


def main():
    current_year = datetime.now(timezone.utc).year
    now = datetime.now(timezone.utc)
    events = []
    seen = set()

    for year in (current_year, current_year + 1):
        try:
            races = fetch_season(year)
        except Exception as error:
            print(f"Could not fetch {year} schedule: {error}")
            continue

        for race in races:
            race_name = race["raceName"]
            circuit = race["Circuit"]["circuitName"]
            round_number = race["round"]

            sessions = [
                ("Qualifying", race.get("Qualifying"), 60),
                ("Grand Prix", {
                    "date": race.get("date"),
                    "time": race.get("time"),
                }, 120),
            ]

            for session_name, session_data, duration in sessions:
                start = parse_session(session_data)

                if start is None or start <= now:
                    continue

                uid = (
                    f"{year}-round-{round_number}-"
                    f"{session_name.lower().replace(' ', '-')}"
                )

                if uid in seen:
                    continue

                seen.add(uid)

                events.extend(
                    create_event(
                        uid,
                        f"F1 {race_name} - {session_name}",
                        start,
                        duration,
                        circuit,
                    )
                )

    calendar = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Formula1//F1 Calendar//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Formula 1 - Qualifying & Grand Prix",
        *events,
        "END:VCALENDAR",
        "",
    ]

    Path(OUTPUT_FILE).write_text(
        "\r\n".join(calendar),
        encoding="utf-8",
    )

    print(f"Generated {OUTPUT_FILE}")
    print(f"Upcoming sessions included: {len(seen)}")


if __name__ == "__main__":
    main()
