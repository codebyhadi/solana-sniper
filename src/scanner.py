"""
Asynchronous Pump.fun token scanner.
Periodically fetches newly created / trending tokens from Pump.fun API,
applies basic filters (rug score, liquidity), and sends Telegram notifications
for qualifying tokens.

Main entry point for token discovery phase of the sniper bot.
"""

import aiohttp
import asyncio
import pytz

from datetime import datetime
from config import (
    PUMPFUN_URL,
    RUG_SCORE,
    MIN_LIQUIDITY,
    BRIGHT_GREEN,
    RESET,
    BRIGHT_RED,
    BRIGHT_BLUE,
    SENT_MINTS
)
from token_utils import get_token_info, get_token_rug_info
from utils import send_telegram_message, parse_iso_datetime


async def fetch_tokens() -> list[dict] | None:
    """
    Fetch recent Pump.fun tokens, filter them by rug score and liquidity,
    print formatted console output, and send Telegram alerts for new tokens.

    Returns:
        List of qualifying token dicts (each with at least 'mint'), or None on failure
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(PUMPFUN_URL, timeout=10) as response:
            if response.status != 200:
                print(f"Failed to fetch PumpFun tokens: {response.status}")
                return None

            data = await response.json()

            if not isinstance(data, list):
                print("PumpFun data is not a list")
                return None

            tokens = []
            i = 0
            j = 0

            for node in data:
                mint = node.get('mint')
                if not mint:
                    continue

                # Rate limit courtesy delay
                await asyncio.sleep(3)

                token_info = get_token_info(mint)
                if not token_info:
                    continue

                # ── Rug check ───────────────────────────────────────────────
                rug_info = await get_token_rug_info(mint)
                if not rug_info:
                    print("Skipping token due to RugCheck failure")
                    continue

                rug_score = rug_info["rug_score"]
                liquidity = round(token_info.get('liquidity', 0), 2)

                if rug_score != RUG_SCORE:
                    #j += 1
                    #print(f"{j} - {mint} ==> {BRIGHT_BLUE}{rug_score} score{RESET}")
                    continue

                if liquidity < MIN_LIQUIDITY:
                    #j += 1
                    #print(f"{j} - {mint} ==> {BRIGHT_RED}{liquidity} USD{RESET}")
                    continue

                # ── Passed filters ──────────────────────────────────────────
                i += 1

                # Convert creation timestamp to Dubai timezone for readability
                created_str = token_info.get("createdAt")
                utc_dt = parse_iso_datetime(created_str)
                if utc_dt:
                    dubai_tz = pytz.timezone("Asia/Dubai")
                    dubai_dt = utc_dt.astimezone(dubai_tz)
                    created_display = dubai_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
                else:
                    created_display = "Unknown"

                usd_price = token_info.get('usdPrice', 0)
                symbol = token_info.get('symbol', '-')
                explorer_url = f"https://jup.ag/tokens/{mint}"

                # ── Console output block ────────────────────────────────────
                print(f"{RESET}")
                print("┌──────────────────────────────────────────────────────────────────────────┐")
                print(f"│  Token Information #{i:<38}")
                print("├──────────────────────────────────────────────────────────────────────────┤")
                print(f"│  Mint     : {BRIGHT_GREEN}{mint:<44}{RESET}")
                print(f"│  {BRIGHT_GREEN}{explorer_url:<44}{RESET}")
                print(f"│  Name     : {BRIGHT_GREEN}{node.get('name', '—'):<44}{RESET}")
                print(f"│  Symbol   : {BRIGHT_GREEN}{symbol:<44}{RESET}")
                print(f"│  Liquidity: {BRIGHT_GREEN}{liquidity:>8}{RESET}")
                print(f"│  Price    : {BRIGHT_GREEN}{usd_price:>12}{RESET}")
                print(f"│  Created  : {BRIGHT_GREEN}{created_display:<44}{RESET}")
                print("└──────────────────────────────────────────────────────────────────────────┘")

                token = {'mint': mint}
                tokens.append(token)

                # ── Telegram notification (only once per mint) ──────────────
                if mint not in SENT_MINTS:
                    message = (
                        "🪙 <b>Token Snapshot</b>\n"
                        "━━━━━━━━━━\n"
                        f"🔗 <b>Mint:</b> <code>{mint}</code>\n"
                        f"🏷️ <b>Symbol:</b>  {symbol}\n"
                        f"📛 <b>Name:</b>    {node.get('name', 'Unknown')}\n"
                        f"💰 <b>Price:</b>   ${usd_price:,.8f}\n"
                        f"🌊 <b>Liquidity:</b> ${liquidity:,.2f}\n"
                        f"🕒 <b>Created:</b>  {created_display}\n"
                        "━━━━━━━━━━"
                    )
                    await send_telegram_message(message)
                    SENT_MINTS.add(mint)

                print()

            return tokens


if __name__ == "__main__":
    result = asyncio.run(fetch_tokens())
    if result:
        print(f"Final result: {len(result)} tokens")