import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

def build_message():
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y.%m.%d")

    return f"""[Daily Esports Results] {today} KST

📌 Yesterday Results

🔥 T1 Matches
- 경기 없음

LoL
- LCK: 경기 없음
- LPL: 경기 없음
- LEC: 경기 없음
- LCS: 경기 없음
- LCK CL: 경기 없음

VALORANT
- VCT Pacific: 경기 없음
- VCT China: 경기 없음
- VCT EMEA: 경기 없음
- VCT Americas: 경기 없음

📅 Today Matches

LoL
- 경기 없음

VALORANT
- 경기 없음
"""

def send_to_slack(text):
    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": text},
        timeout=10,
    )
    response.raise_for_status()

if __name__ == "__main__":
    send_to_slack(build_message())
