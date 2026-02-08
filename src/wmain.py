"""
Wallet monitoring & auto-exit loop (take-profit / stop-loss / rug change).
Runs continuously, checks held tokens, calculates PNL, and sells when needed.

This is the "position manager" part of the bot.
"""

import asyncio
import os
import winloop

from db import get_swaps_for_token
from scorer import score_token, get_score_label_wallet
from token_utils import get_token_rug_info, get_token_info
from utils import send_telegram_message
from config import (
    EXCLUDED_TOKENS,
    BRIGHT_RED,
    BRIGHT_GREEN,
    RESET,
    BRIGHT_YELLOW,
    TAKE_PROFIT,
    STOP_LOSS,
    USDT,
    RUG_SCORE,
    BRIGHT_BLUE,
    REFRESH_TIME
)

from trader import swap
from wallet_utils import get_wallet_tokens_cached, get_sol_balance, get_token_balance

# Note: several imports appear broken/missing in original → assuming correct ones exist
# from wallet_utils import load_wallet, get_sol_balance, get_balance, get_balance_raw, get_wallet_tokens, get_token_info, get_token_rug_info


def safe_float(value, default=0.0):
    """Safe conversion to float with fallback."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

async def check_and_monitor(wallet=None):
    """Single monitoring cycle: check all held tokens, compute PNL, auto-sell if needed."""
    # client, keypair = load_wallet()           # ← missing in original; assuming it exists
    # wallet = keypair.pubkey()
    await asyncio.sleep(1)
    os.system('cls')

    # print(f" Wallet: {wallet}")
    print(f" SOL:    {get_sol_balance():,.6f} SOL")
    print(f" USDT:   {get_token_balance(USDT):,.6f} USDT")
    print("═" * 70)
    print(" Loading tokens...")

    tokens = get_wallet_tokens_cached()   # ←
    if not tokens:
        print("→ No tokens found in wallet!")
        return

    j = 0
    for i, t in enumerate(tokens, start=1):
        mint = t["mint"]
        print("-" * 70)
        await asyncio.sleep(2)
        if mint in EXCLUDED_TOKENS:
            print(f"⛔ Skipped: {mint}")
            continue

        token_info = get_token_info(mint)
        price = safe_float(token_info.get("usdPrice"))
        liquidity = safe_float(token_info.get("liquidity"))
        symbol = token_info.get("symbol", "N/A")
        explorer_url = f"https://jup.ag/tokens/{mint}"
        j += 1

        print(f" #{j}")
        print(f" Token:       {BRIGHT_BLUE}{mint}{RESET} →  {explorer_url}")
        print(f" Symbol:      {BRIGHT_BLUE}{symbol}{RESET}")
        print(f" Amount:      {BRIGHT_BLUE}{t['ui_amount']}{RESET}")
        print(f" Liquidity:   {BRIGHT_BLUE}{liquidity:,.2f}${RESET}")

        score, _ = score_token(mint, debug=False)
        token_rug = await get_token_rug_info(mint)

        if not token_rug:
            print("  → Rug check unavailable, skipping")
            continue

        rug_score = token_rug["rug_score"]
        swaps = get_swaps_for_token(mint)

        print("-" * 50)
        print(f"  → Score:       {score:.2f} {get_score_label_wallet(score)}")
        print(f"  → Rug Score:   {rug_score}")
        print("-" * 50)

        if not swaps:
            print(" Entry Price: No data")
            continue

        entry_price = safe_float(swaps[0].get("entering_price"))
        trade_size = safe_float(swaps[0].get("input_amount_ui"))

        if entry_price <= 0 or price <= 0:
            continue

        pnl_pct = ((price - entry_price) / entry_price) * 100
        pnl = pnl_pct * trade_size / 100

        print(f"  → Current Price:   {BRIGHT_BLUE}{price:,.8f}${RESET}")
        print(f"  → Total:           {BRIGHT_BLUE}{price*t['ui_amount']:,.8f}${RESET}")
        print("-" * 50)
        print(f"  → Entry Price:     {BRIGHT_BLUE}{entry_price:,.8f}${RESET}")
        print(f"  → Total Cost:      {BRIGHT_BLUE}{entry_price * t['ui_amount']:,.8f}${RESET}")
        print("-" * 50)
        if pnl < 0:
            print(f"  → PNL:     {BRIGHT_RED}{pnl:+,.2f}${RESET}")
            print(f"  → PNL%:    {BRIGHT_RED}{pnl_pct:+,.2f}%{RESET}")
            print("-" * 50)
        elif pnl_pct > 0:
            print(f"  → PNL:     {BRIGHT_GREEN}{pnl:+,.2f}${RESET}")
            print(f"  → PNL%:    {BRIGHT_GREEN}{pnl_pct:+,.2f}%{RESET}")
            print("-" * 50)
        else:
            print(f"  → PNL:     {BRIGHT_YELLOW}{pnl:+,.2f}${RESET}")
            print(f"  → PNL%:    {BRIGHT_YELLOW}{pnl_pct:+,.2f}%{RESET}")
            print("-" * 50)

        message = ""
        # Rug risk changed → exit
        if rug_score != RUG_SCORE:
            try:
                status = swap(mint, USDT, t['ui_amount'], "sell")
                if status == "success":
                    print(f"  → Position CLOSED - RUG SCORE CHANGED")
                    message = (
                        "🔴 <b>POSITION CLOSED</b> — RUG RISK CHANGED\n"
                        "━━━━━━━━━━\n"
                        f"💎 <b>{token_info.get('name', '—')}</b>  •  {token_info.get('symbol', '—')}\n"
                        f"📍 <code>{token_info.get('mint', '—')}</code>\n\n"
                        f"💰 PNL:     <b>{pnl:+,.2f} USDT</b>\n"
                        f"📊 PNL%:    <b>{pnl_pct:+,.2f}%</b>"
                    )
            except Exception as e:
                print(f"  → Sell execution error - RUG SCORE CHANGED: {e}")
            continue

        # Take profit / Stop loss
        if pnl_pct >= TAKE_PROFIT:
            try:
                status = swap(mint, USDT, t['ui_amount'], "sell")
                print("-" * 50)
                if status == "success":
                    print(f"  → Position CLOSED - TAKE PROFIT.")
                    message = (
                        "🟢 <b>POSITION CLOSED</b> — TAKE PROFIT 🎯\n"
                        "━━━━━━━━━━\n"
                        f"💎 <b>{token_info.get('name', '—')}</b>  •  {token_info.get('symbol', '—')}\n"
                        f"📍 <code>{token_info.get('mint', '—')}</code>\n\n"
                        f"💰 PNL:     <b>{pnl:+,.2f} USDT</b>\n"
                        f"📊 PNL%:    <b>{pnl_pct:+,.2f}%</b>"
                    )
            except Exception as e:
                print(f"  → Sell execution error - TAKE PROFIT: {e}")

        elif pnl_pct <= STOP_LOSS:
            try:
                status = swap(mint, USDT, t['ui_amount'], "sell")
                print("-" * 50)
                if status == "success":
                    print(f"  → Position CLOSED - STOP LOSS.")
                    message = (
                        "🔴 <b>POSITION CLOSED</b> — STOP LOSS\n"
                        "━━━━━━━━━━\n"
                        f"💎 <b>{token_info.get('name', '—')}</b>  •  {token_info.get('symbol', '—')}\n"
                        f"📍 <code>{token_info.get('mint', '—')}</code>\n\n"
                        f"💰 PNL:     <b>{pnl:+,.2f} USDT</b>\n"
                        f"📊 PNL%:    <b>{pnl_pct:+,.2f}%</b>"
                    )
            except Exception as e:
                print(f"  → Sell execution error - STOP LOSS: {e}")

        if message:
            await send_telegram_message(message)


async def main_loop():
    """Infinite monitoring loop with refresh interval."""
    while True:
        try:
            await asyncio.to_thread(os.system, 'cls')
            await check_and_monitor()
        except Exception as e:
            print(f" Cycle error: {e}")

        print(f"\n Waiting {REFRESH_TIME} seconds before next cycle...\n")
        await asyncio.sleep(REFRESH_TIME)


if __name__ == "__main__":
    try:
        asyncio.set_event_loop_policy(winloop.EventLoopPolicy())
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n Stopped by user (Ctrl+C)")