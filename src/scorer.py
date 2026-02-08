"""
Token scoring engine — evaluates memecoins based on multiple momentum,
distribution, safety, and exit-liquidity factors.

Score range: 0–100 (additive system)
Higher = cleaner / more promising short-term momentum play.
"""

import pprint
from datetime import timezone
from datetime import datetime

from token_utils import get_token_info, compute_effective_liquidity_from_gecko


def parse_iso_datetime(value) -> datetime | None:
    """Minimal ISO datetime parser used internally by score_token."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except:
        return None


def score_token(mint: str, debug: bool = False) -> tuple[float, dict]:
    """
    Main scoring function — returns score 0–100 and trace dict for debugging.

    Scoring categories (max points):
    - LP/MC ratio           26
    - Token age             12
    - Holder count          12
    - Holder concentration  10
    - Net buyers ratio       8
    - Holder growth (1h)     6
    - Liquidity growth (1h)  6
    - Pool count             4
    - LP concentration       2
    ... etc.

    Args:
        mint: Token mint address
        debug: If True, pretty-print trace dict

    Returns:
        (score: float, trace: dict)
    """
    score = 0
    trace = {}

    token = get_token_info(mint)
    if not token:
        return 0, {"error": "token_info_unavailable"}

    # ── 1. LP / MC Ratio (MAX = 26) ────────────────────────────────
    pools_info = compute_effective_liquidity_from_gecko(mint)
    effective_lp = float(pools_info.get("effective_lp", 0.0))
    max_pool_lp = float(pools_info.get("max_pool_lp", 0.0))

    mc = float(token.get("mcap") or token.get("fdv") or 0)

    lp_mc = effective_lp / mc if mc > 0 else 0.0

    trace.update({
        "effective_lp": effective_lp,
        "max_pool_lp": max_pool_lp,
        "mc": mc,
        "lp_mc_ratio": round(lp_mc, 4),
    })

    if lp_mc >= 0.25:   score += 26; trace["lp_mc_score"] = 26
    elif lp_mc >= 0.18: score += 22; trace["lp_mc_score"] = 22
    elif lp_mc >= 0.12: score += 18; trace["lp_mc_score"] = 18
    elif lp_mc >= 0.08: score += 12; trace["lp_mc_score"] = 12
    elif lp_mc >= 0.05: score += 8;  trace["lp_mc_score"] = 8

    # ── 2. Token Age (newer = better — but not too new) ─────────────
    created_time = token.get("createdAt")
    trace["createdAt_raw"] = created_time

    age_minutes = None
    created_dt = parse_iso_datetime(created_time)

    if created_dt:
        created_dt = created_dt.astimezone(timezone.utc)
        age_minutes = round(
            (datetime.now(timezone.utc) - created_dt).total_seconds() / 60,
            2
        )

    trace["age_minutes"] = age_minutes

    if age_minutes is not None:
        if age_minutes <= 20:  score += 12; trace["age_score"] = 12
        elif age_minutes <= 60: score += 9; trace["age_score"] = 9
        elif age_minutes <= 180: score += 6; trace["age_score"] = 6
        elif age_minutes <= 720: score += 3; trace["age_score"] = 3

    # ── 3. Holder Count ─────────────────────────────────────────────
    holders = int(token.get("holderCount") or 0)
    trace["holders"] = holders

    if holders >= 10000: score += 12
    elif holders >= 5000: score += 9
    elif holders >= 2000: score += 6
    elif holders >= 600: score += 4
    elif holders >= 200: score += 2

    # ── 4. Top Holders Concentration (lower = better) ──────────────
    top_pct = float(token.get("topHoldersPercentage") or 100)
    trace["top_holders_pct"] = top_pct

    if top_pct <= 20: score += 10
    elif top_pct <= 30: score += 6
    elif top_pct <= 40: score += 3

    # ... (remaining categories truncated in original — same logic continues)

    final_score = min(score, 100)
    trace["final_score"] = final_score

    if debug:
        pprint.pprint(trace)

    return final_score, trace


def get_score_label(score: float) -> str:
    """Human-readable label for discovery/buy phase."""
    if score >= 75: return "🔥 A+ | Very Clean (Strong Buy)"
    if score >= 60: return "🟢 A | Clean (Buy)"
    if score >= 45: return "🟡 B | Medium (Watch / Small Size)"
    if score >= 30: return "🟠 C | Risky (Speculative)"
    return "🔴 D | Weak / Skip"


def get_score_label_wallet(score: float) -> str:
    """Human-readable label for position monitoring phase."""
    if score >= 75: return "🔥 A+ | Very Clean (Strong Keep)"
    if score >= 60: return "🟢 A | Clean (Keep)"
    if score >= 45: return "🟡 B | Medium (Watch / Small Size)"
    if score >= 30: return "🟠 C | Risky (Speculative) - Sell"
    return "🔴 D | Weak / Skip - Sell"