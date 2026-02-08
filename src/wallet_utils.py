"""
Wallet & position management utilities.
Handles balance checks, token account discovery, position limits,
and basic capital/position size calculations.
"""

from time import time
from solders.pubkey import Pubkey
from solana.rpc.types import TokenAccountOpts
from solana.rpc.commitment import Confirmed
from spl.token.constants import TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID
from wallet_context import get_wallet
from config import (
    MAX_OPEN_POSITIONS,
    EXCLUDED_TOKENS,
    USDT,
    WSOL,
    AMOUNT_PER_TRADE,
)
from token_utils import get_token_price

# ── Cache for token accounts (RPC calls are expensive) ───────
_TOKEN_CACHE = {"ts": 0, "data": None}
CACHE_TTL = 5  # seconds

def get_sol_balance() -> float:
    """Get SOL balance of the trading wallet (in SOL, not lamports)."""
    client, keypair = get_wallet()
    resp = client.get_balance(keypair.pubkey())
    return resp.value / 1_000_000_000

def get_token_balance(mint: str) -> float:
    """
    Get UI balance of a specific SPL token in the wallet.

    Args:
        mint: Token mint address

    Returns:
        Float UI amount (0.0 if no account or zero balance)
    """
    client, keypair = get_wallet()
    wallet = keypair.pubkey()

    opts = TokenAccountOpts(mint=Pubkey.from_string(mint))
    resp = client.get_token_accounts_by_owner(wallet, opts)

    if not resp.value:
        return 0.0

    acc = resp.value[0].pubkey
    bal = client.get_token_account_balance(acc)
    return float(bal.value.ui_amount or 0.0)

def _fetch_tokens(program_id) -> list[dict]:
    """Internal helper: fetch token accounts for a given token program."""
    client, keypair = get_wallet()
    wallet = keypair.pubkey()

    resp = client.get_token_accounts_by_owner_json_parsed(
        wallet,
        TokenAccountOpts(program_id=program_id),
        commitment=Confirmed,
    )

    tokens = []
    for acc in resp.value:
        info = acc.account.data.parsed["info"]
        amount = int(info["tokenAmount"]["amount"])
        if amount == 0:
            continue

        tokens.append({
            "mint": info["mint"],
            "amount": amount,
            "decimals": int(info["tokenAmount"]["decimals"]),
            "ui_amount": float(info["tokenAmount"]["uiAmount"]),
            "program": str(program_id),
        })
    return tokens


def get_wallet_tokens_cached() -> list[dict]:
    """
    Get list of all non-zero token accounts in wallet (TOKEN + TOKEN-2022).
    Uses 5-second cache to reduce RPC load.

    Returns:
        List of token dicts with mint, ui_amount, etc.
    """
    now = time()
    if _TOKEN_CACHE["data"] and now - _TOKEN_CACHE["ts"] < CACHE_TTL:
        return _TOKEN_CACHE["data"]

    tokens = []
    tokens.extend(_fetch_tokens(TOKEN_PROGRAM_ID))
    tokens.extend(_fetch_tokens(TOKEN_2022_PROGRAM_ID))

    _TOKEN_CACHE.update({"data": tokens, "ts": now})
    return tokens


def can_open_position() -> bool:
    """Check if we can open a new position (under max open limit)."""
    tokens = get_wallet_tokens_cached()
    opened = sum(
        1 for t in tokens if t["mint"] not in EXCLUDED_TOKENS
    )
    return opened < MAX_OPEN_POSITIONS


def already_opened(mint: str) -> bool:
    """Check if we already hold this token in wallet."""
    tokens = get_wallet_tokens_cached()
    return any(t["mint"] == mint for t in tokens)


def calculate_position_size() -> bool:
    """
    Very basic capital check: do we have enough USDT + some SOL buffer?

    Returns:
        True if USDT balance ≥ AMOUNT_PER_TRADE and SOL value > ~1 USD
    """
    usdt_balance = get_token_balance(USDT)
    sol_balance = get_sol_balance()
    sol_price = get_token_price(WSOL)

    if sol_price is None:
        return False

    sol_value = sol_balance * sol_price
    return usdt_balance > AMOUNT_PER_TRADE and sol_value > 1