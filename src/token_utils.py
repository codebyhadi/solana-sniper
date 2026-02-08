"""
Token metadata & safety utilities.
Fetches info from Jupiter, RugCheck, GeckoTerminal, etc.
Used for filtering, scoring, and position management.
"""

import asyncio
import aiohttp
import requests
from typing import Optional, Dict

from config import (
    RUGCHECK_URL,
    VALID_POOL_LIQUIDITY,
    ALLOWED_DEXES,
    MIN_24H_VOLUME,
    MIN_POOL_SHARE,
    MIN_LIQUIDITY,
)
from db import token_has_swap


def get_token_info(token_mint: str) -> Optional[Dict]:
    """
    Fetch token metadata from Jupiter Aggregator asset search.

    Contains price, liquidity, market cap, holders, audit flags, 1h stats, etc.

    Args:
        token_mint: Token mint address

    Returns:
        Dict with token info or None if not found / error
    """
    url = f"https://datapi.jup.ag/v1/assets/search?query={token_mint}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://jup.ag/",
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not data:
            return None

        token = data[0]
        stats = token.get("stats1h", {})

        return {
            "usdPrice": token.get("usdPrice"),
            "liquidity": token.get("liquidity"),
            "mcap": token.get("mcap"),
            "symbol": token.get("symbol"),
            "mint": token.get("id"),
            "holderCount": token.get("holderCount", 0),
            "mint_authority": token.get("audit", {}).get("mintAuthorityDisabled", True),
            "freeze_authority": token.get("audit", {}).get("freezeAuthorityDisabled", True),
            "priceChange_H1": stats.get("priceChange"),
            "volume_H1": stats.get("buyVolume"),
            "createdAt": token.get("createdAt"),
            "name": token.get("name"),
        }

    except Exception as e:
        print(f"[JUPITER] {e}")
        return None


def get_token_price(mint: str) -> Optional[float]:
    """Quick helper: current USD price or None."""
    info = get_token_info(mint)
    return info.get("usdPrice") if info else None


async def get_token_rug_info(token_mint: str) -> Optional[Dict]:
    """
    Fetch RugCheck.xyz report for a token (with retry logic).

    Args:
        token_mint: Token mint address

    Returns:
        Dict with 'rug_score' and 'mutable' or None after retries
    """
    url = f"{RUGCHECK_URL}{token_mint}/report"

    async with aiohttp.ClientSession() as session:
        for _ in range(10):
            try:
                async with session.get(url, timeout=8) as r:
                    if r.status == 200:
                        data = await r.json()
                        return {
                            "rug_score": data.get("score"),
                            "mutable": data.get("tokenMeta", {}).get("mutable", True),
                        }
            except Exception:
                await asyncio.sleep(3)

    return None


def compute_effective_liquidity_from_gecko(token_mint: str) -> Dict:
    """
    Calculate "effective" liquidity using GeckoTerminal pools data.
    Considers only valid pools (min liquidity/volume, allowed DEXes)
    and applies concentration filter (only pools that are significant portion of max).

    Args:
        token_mint: Token mint address

    Returns:
        Dict with 'effective_lp', 'max_pool_lp', 'pools' count
    """
    url = f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{token_mint}/pools"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
    except:
        return {"effective_lp": 0.0}

    pools = r.json().get("data", [])
    valid = []

    for p in pools:
        a = p["attributes"]
        dex = p["relationships"]["dex"]["data"]["id"]

        liquidity = float(a.get("fdv_usd", 0))      # using FDV as proxy; could use reserve USD if available
        volume = float(a.get("volume_usd", {}).get("h24", 0))

        if (
            liquidity >= VALID_POOL_LIQUIDITY
            and volume >= MIN_24H_VOLUME
            and dex in ALLOWED_DEXES
        ):
            valid.append(liquidity)

    if not valid:
        return {"effective_lp": 0.0}

    max_lp = max(valid)
    effective_lp = sum(
        lp for lp in valid
        if lp >= max_lp * MIN_POOL_SHARE and lp >= MIN_LIQUIDITY
    )

    return {
        "effective_lp": effective_lp,
        "max_pool_lp": max_lp,
        "pools": len(valid),
    }


def already_closed_before(mint: str) -> bool:
    """
    Check if we previously sold this token when liquidity was higher
    than current liquidity (used to avoid re-buying dumped tokens).

    Args:
        mint: Token mint address

    Returns:
        True if we exited at higher liquidity than now
    """
    token_data = get_token_info(mint)
    if not token_data:
        return False

    swap = token_has_swap(mint)
    if not swap:
        return False

    last_exit_liq = swap.get("output_liqudation")
    current_liq = token_data.get("liquidity")

    if last_exit_liq is None or current_liq is None:
        return False

    try:
        return int(last_exit_liq) > int(current_liq)
    except (ValueError, TypeError):
        return False