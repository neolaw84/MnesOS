import re
from datetime import timedelta, datetime
from typing import Dict, Any

def _format_game_time_context(bot_memory: Dict[str, Any]) -> str:
    """Return a small prompt snippet for in-game time context."""
    if "game_time" not in bot_memory:
        return ""
    return (
        "\n\n### In-Game Time Context:\n"
        f"state.game_time = {bot_memory.get('game_time')!r}\n"
        "Use this as canonical in-game time context."
    )

def _parse_duration_token(token: str) -> timedelta:
    token = token.strip()
    iso = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", token)
    if iso:
        h = int(iso.group(1) or 0)
        m = int(iso.group(2) or 0)
        s = int(iso.group(3) or 0)
        if h == 0 and m == 0 and s == 0:
            raise ValueError(
                f"advance_time duration cannot be empty (received: {token!r}; "
                "expected ISO duration like 'PT15M' or shorthand like '15m')"
            )
        return timedelta(hours=h, minutes=m, seconds=s)

    simple = re.fullmatch(r"(\d+)\s*([dhms])", token.lower())
    if simple:
        val = int(simple.group(1))
        unit = simple.group(2)
        if unit == "d":
            return timedelta(days=val)
        if unit == "h":
            return timedelta(hours=val)
        if unit == "m":
            return timedelta(minutes=val)
        return timedelta(seconds=val)

    raise ValueError(f"Unsupported advance_time duration format: {token!r}")

def _coerce_game_time_to_datetime(gt: Any) -> datetime:
    """Robustly parse variant game_time formats (reused from orchestrator logic)."""
    if isinstance(gt, datetime):
        return gt
    if not isinstance(gt, str) or not gt.strip():
        # Fallback to epoch if missing/junk
        return datetime(2026, 4, 1, 0, 0, 0)
    
    # Try ISO formats
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]:
        try:
            return datetime.strptime(gt, fmt)
        except ValueError:
            continue
    # Last ditch: return epoch
    return datetime(2026, 4, 1, 0, 0, 0)
