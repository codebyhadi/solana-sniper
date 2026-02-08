"""
Main sniper bot loop — token discovery + scoring + buy execution.

Coordinates:
- Token scanning (scanner.py)
- Scoring (scorer.py)
- Position checks (wallet_utils.py)
- Swap execution (trader.py)
"""

import aiohttp
import asyncio
import os
import time

from scanner import fetch_tokens
from scorer import score_token, get_score_label
from utils import send_telegram_message

from wallet_utils import calculate_position_size, can_open_position, already_opened
from trader import get_quote, swap
from token_utils import already_closed_before, get_token_info

from config import START_CAPITAL, MIN_SCORE, USDT, AMOUNT_PER_TRADE, RESET, BRIGHT_GREEN, REFRESH_TIME
from typing import Optional


class TradingBot:
    """Main trading bot class — manages capital simulation and main loop."""

    def __init__(self):
        self.capital: float = START_CAPITAL
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """Initialize reusable HTTP session."""
        self.session = aiohttp.ClientSession()

    async def close(self):
        """Clean up HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def run_once(self):
        """Single discovery + trading cycle."""
        if not self.session or self.session.closed:
            await self.initialize()

        try:
            time.sleep(1)  # small breathing room
            tokens = await fetch_tokens()
            if not tokens:
                print(" No tokens discovered...")
                return

            print("=" * 60)
            print(f"\nDiscovered {BRIGHT_GREEN}{len(tokens)}{RESET} tokens")

            for token_data in tokens:
                await self.process_token(token_data)

        except Exception as e:
            print(f" Critical error in run_once: {e}")

    async def process_token(self, token: dict):
        """Evaluate and potentially buy one discovered token."""
        mint = token.get('mint')
        if not mint:
            return

        print("\n" + "=" * 60)

        if already_closed_before(mint):
            print(f"  → Already Closed → {mint}")
            return

        if already_opened(mint):
            print(f"  → Already opened → {mint}")
            return

        if not can_open_position():
            print("  → Max positions reached")
            return

        token_data = get_token_info(mint)
        print(f" Evaluating {mint} | {token_data.get('name', 'Unknown token ???')}")

        score, trace = score_token(mint, debug=False)
        print(f"  → Score: {score:.2f} {get_score_label(score)}")

        if score < MIN_SCORE:
            print("  → Score too low")
            return

        # Very basic capital check
        if not calculate_position_size():
            print("  → No capital left")
            return

        print(f"  → Planned position size: ${AMOUNT_PER_TRADE:.2f}")

        get_quote(USDT, mint)  # just prints quote — not used for execution

        try:
            status = swap(USDT, mint, AMOUNT_PER_TRADE)
            if status == "success":
                self.capital -= AMOUNT_PER_TRADE
                print(f"  → Position OPENED | Capital left: ${self.capital:.2f}")

                message = (
                    "🟢 <b>POSITION OPENED</b> 🚀\n"
                    "━━━━━━━━━━\n"
                    f"💎 Name:   <b>{token_data.get('name', '—')}</b>\n"
                    f"🔤 Symbol: <b>{token_data.get('symbol', '—')}</b>\n"
                    f"📍 Mint:   <code>{token_data.get('mint', '—')}</code>\n"
                    f"💰 Price:  ${token_data.get('usdPrice', '—'):.6f}\n"
                    f"🌊 Liquidity: ${token_data.get('liquidity', '—'):,.0f}"
                )
                await send_telegram_message(message)
            else:
                print(f"  → Swap failed / canceled")

        except Exception as e:
            print(f"  → Buy execution error: {e}")

    async def run_forever(self):
        """Main infinite loop with sleep between cycles."""
        await self.initialize()
        try:
            while True:
                print(f" Bot started | capital = {self.capital:,.2f} USDT | checking every {REFRESH_TIME}s")
                print("=" * 70)
                await self.run_once()
                print("─" * 70)
                print(f" Waiting {REFRESH_TIME} seconds...\n")
                await asyncio.sleep(REFRESH_TIME)
                os.system('cls')
        except KeyboardInterrupt:
            print("\n Stopped by user (Ctrl+C)")
        finally:
            await self.close()
            print(" Session closed. Goodbye.")


async def main():
    bot = TradingBot()
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())