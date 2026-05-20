import re
from datetime import date, timedelta

# Matches lines like: "3/6: <@123456>", "👑 3/6: <@123> <@456>", "X/6: <@789>"
_SCORE_LINE = re.compile(r"(\d|X)/6\*?\s*:\s*((?:<@!?\d+>\s*)+)", re.IGNORECASE)

# Extracts Discord user IDs from mentions (<@123> or <@!123>)
_MENTION = re.compile(r"<@!?(\d+)>")

# Only the midnight "yesterday's results" summary, not live "today's results"
_TRIGGER = re.compile(r"here are yesterday'?s? results", re.IGNORECASE)

# Extracts Wordle number from embed title/description e.g. "Wordle No. 1381"
_WORDLE_NUM = re.compile(r"wordle\s+no\.?\s*(\d+)", re.IGNORECASE)

# Wordle No. 0 = June 19, 2021
_WORDLE_EPOCH = date(2021, 6, 19)


def is_wordle_results(content: str) -> bool:
    return bool(_TRIGGER.search(content))


def parse_scores(content: str) -> list:
    """
    Returns a list of (user_id: str, attempts: int).
    attempts is 1-6, or 7 for a failed attempt (X/6).
    """
    results = []
    for line in content.splitlines():
        m = re.search(r"(\d|X)/6\*?\s*:", line, re.IGNORECASE)
        if not m:
            continue
        attempts = 7 if m.group(1).upper() == "X" else int(m.group(1))
        for uid in _MENTION.findall(line[m.end():]):
            results.append((uid, attempts))
    return results


def extract_wordle_num(message) -> int:
    """Try to find the Wordle number in message embeds, fallback to date calculation."""
    for embed in message.embeds:
        for text in (embed.title, embed.description, embed.footer.text if embed.footer else None):
            if text:
                m = _WORDLE_NUM.search(text)
                if m:
                    return int(m.group(1))
    # Fallback: "yesterday's results" posted at midnight local = same UTC date as puzzle
    if _TRIGGER.search(message.content):
        return (message.created_at.date() - _WORDLE_EPOCH).days
    return 0
