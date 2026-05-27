import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
RIOT_API_KEY = os.environ["RIOT_API_KEY"]

KST = ZoneInfo("Asia/Seoul")

LOL_LEAGUES = {
    "LCK": ["LCK"],
    "LPL": ["LPL"],
    "LEC": ["LEC"],
    "LCS": ["LCS"],
    "LCK CL": ["LCK Challengers", "LCK CL"],
}

VALORANT_LEAGUES = [
    "VCT Pacific",
    "VCT China",
    "VCT EMEA",
    "VCT Americas",
]


def riot_get(path, params=None):
    response = requests.get(
        f"https://esports-api.lolesports.com/persisted/gw/{path}",
        headers={"x-api-key": RIOT_API_KEY},
        params={"hl": "en-US", **(params or {})},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def get_lol_league_ids():
    data = riot_get("getLeagues")
    leagues = data["data"]["leagues"]

    result = {}
    for display_name, aliases in LOL_LEAGUES.items():
        for league in leagues:
            name = league.get("name", "")
            slug = league.get("slug", "")
            if any(alias.lower() in name.lower() or alias.lower() in slug.lower() for alias in aliases):
                result[display_name] = league["id"]
                break

    return result


def get_schedule_events(league_id):
    events = []

    first_page = riot_get("getSchedule", {"leagueId": league_id})
    schedule = first_page["data"]["schedule"]
    events.extend(schedule.get("events", []))

    for direction in ["older", "newer"]:
        page_token = schedule.get("pages", {}).get(direction)
        if page_token:
            page = riot_get("getSchedule", {"leagueId": league_id, "pageToken": page_token})
            events.extend(page["data"]["schedule"].get("events", []))

    return events


def event_kst_date(event):
    return datetime.fromisoformat(event["startTime"].replace("Z", "+00:00")).astimezone(KST).date()


def event_kst_time(event):
    return datetime.fromisoformat(event["startTime"].replace("Z", "+00:00")).astimezone(KST).strftime("%H:%M")


def team_name(team):
    return team.get("code") or team.get("name") or "TBD"


def format_completed_match(event):
    teams = event["match"]["teams"]
    left = teams[0]
    right = teams[1]

    left_score = left.get("result", {}).get("gameWins", 0)
    right_score = right.get("result", {}).get("gameWins", 0)

    return f"{team_name(left)} {left_score}-{right_score} {team_name(right)}"


def format_upcoming_match(event):
    teams = event["match"]["teams"]
    left = team_name(teams[0])
    right = team_name(teams[1])
    return f"{event_kst_time(event)} {left} vs {right}"


def collect_lol_data():
    today = datetime.now(KST).date()
    yesterday = today - timedelta(days=1)

    league_ids = get_lol_league_ids()

    results = {}
    today_matches = {}
    t1_matches = []

    for league_name in LOL_LEAGUES:
        results[league_name] = []
        today_matches[league_name] = []

        league_id = league_ids.get(league_name)
        if not league_id:
            continue

        for event in get_schedule_events(league_id):
            if event.get("type") != "match":
                continue

            match_date = event_kst_date(event)
            state = event.get("state")
            teams = event.get("match", {}).get("teams", [])
            team_text = " ".join(team_name(team) for team in teams).upper()
            has_t1 = "T1" in team_text

            if match_date == yesterday and state == "completed":
                line = format_completed_match(event)
                results[league_name].append(line)
                if has_t1:
                    t1_matches.append(f"LoL {league_name}: {line}")

            if match_date == today and state != "completed":
                line = format_upcoming_match(event)
                today_matches[league_name].append(line)
                if has_t1:
                    t1_matches.append(f"LoL {league_name}: {line}")

    return results, today_matches, t1_matches


def section_lines_by_league(data):
    lines = []
    for league_name, matches in data.items():
        if matches:
            for match in matches:
                lines.append(f"- {league_name}: {match}")
        else:
            lines.append(f"- {league_name}: 경기 없음")
    return "\n".join(lines)


def build_message():
    today_text = datetime.now(KST).strftime("%Y.%m.%d")
    lol_results, lol_today_matches, t1_matches = collect_lol_data()

    t1_section = "\n".join(f"- {match}" for match in t1_matches) if t1_matches else "- 경기 없음"

    valorant_results = "\n".join(f"- {league}: 경기 없음" for league in VALORANT_LEAGUES)
    valorant_today = "\n".join(f"- {league}: 경기 없음" for league in VALORANT_LEAGUES)

    return f"""[Daily Esports Results] {today_text} KST

📌 Yesterday Results

🔥 T1 Matches
{t1_section}

LoL
{section_lines_by_league(lol_results)}

VALORANT
{valorant_results}

📅 Today Matches

LoL
{section_lines_by_league(lol_today_matches)}

VALORANT
{valorant_today}
"""


def send_to_slack(text):
    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": text},
