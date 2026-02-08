"""
Jupiter Aggregator swap execution module.
Handles getting quotes and performing actual swaps (buy/sell) via Jupiter v1 API.

Note: This uses an older Jupiter endpoint (v1). Consider migrating to Jupiter v6 API
      for better routing, reliability and features in production.

Dependencies:
- solders (for transaction signing & serialization)
- solana-py (RPC client)
- requests (API calls)
"""

import json
import requests
import base64

from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned
from solders.keypair import Keypair
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed

from config import (
    TESTING_MODE,
    PRIORITY_FEE_MICRO_LAMPORTS,
    JUPITER_QUOTE_URL,
    JUPITER_SWAP_URL,
    JUPITER_API_KEY,
    AMOUNT_PER_TRADE,
    DEFAULT_SLIPPAGE_BPS,
    KEYPAIR_PATH,
    RPC_ENDPOINT
)
from db import log_swap
from token_utils import get_token_info


def get_quote(input_mint: str, output_mint: str, amount: float = AMOUNT_PER_TRADE) -> dict | None:
    """
    Fetch a swap quote from Jupiter API.

    Args:
        input_mint:  Mint address of token to sell (input)
        output_mint: Mint address of token to buy (output)
        amount:      UI amount of input token to swap (human-readable)

    Returns:
        Quote response dict from Jupiter or None if failed
    """
    token_in = get_token_info(input_mint)
    token_out = get_token_info(output_mint)

    # Default to 9 decimals for SOL, otherwise use token metadata
    input_decimals = 9 if input_mint == "So11111111111111111111111111111111111111112" else token_in.get("decimals", 6)
    output_decimals = 9 if output_mint == "So11111111111111111111111111111111111111112" else token_out.get("decimals", 6)

    amount_raw = int(amount * (10 ** input_decimals))

    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_raw),
        "slippageBps": DEFAULT_SLIPPAGE_BPS
    }
    headers = {
        "x-api-key": JUPITER_API_KEY,
        "Accept": "application/json"
    }

    response = requests.get(JUPITER_QUOTE_URL, params=params, headers=headers)

    if response.status_code != 200:
        print("Quote error:", response.status_code, response.text)
        return None

    data = response.json()

    # Extract and pretty-print key quote info
    in_amount_raw = int(data["inAmount"])
    out_amount_raw = int(data["outAmount"])

    in_human = in_amount_raw / (10 ** input_decimals)
    out_human = out_amount_raw / (10 ** output_decimals)

    platform_fee = data.get("platformFee")
    if platform_fee and platform_fee.get("amount", "0") != "0":
        fee_raw = int(platform_fee["amount"])
        fee_bps = platform_fee["feeBps"]
        fee_human = fee_raw / (10 ** input_decimals)
        fee_text = f"Platform fee: {fee_human:,.6f} ({fee_bps / 100:.2f}%)"
    else:
        fee_text = "Platform fee: 0 (none set)"

    print()
    print("  → Quotation:")
    print(f"  → Expected out: {out_human:,.6f} {token_out.get('symbol', '??')}")
    print(f"  → Input:        {in_human:,.6f}")
    print(f"  → {fee_text}")
    print(f"  → Price impact: {float(data.get('priceImpactPct', 0)) * 100:.4f}%")
    print()

    return data


def swap(
    input_mint: str,
    output_mint: str,
    amount: float,
    action: str = "buy",
    client: Client = None
) -> str:

    """
    Execute a real swap through Jupiter Aggregator.

    Steps:
      1. Get fresh quote
      2. Request serialized swap transaction
      3. Sign & send via RPC
      4. Confirm transaction
      5. Log result to database

    Args:
        input_mint:  Token to sell
        output_mint: Token to buy
        amount:      UI amount of input token
        action:      "buy" or "sell" (mainly for logging)
        client:      Optional existing RPC client (creates new if None)

    Returns:
        "success", "failed", "timeout" or similar status string
    """
    if TESTING_MODE:
        print(f"[TEST MODE] Simulated {action.upper()} {amount} {input_mint} → {output_mint}")
        return "success"  # or "False" — depending on your testing needs

    if client is None:
        client = Client(RPC_ENDPOINT)

    # Load wallet keypair from JSON file
    if not isinstance(KEYPAIR_PATH, str):
        raise TypeError("KEYPAIR_PATH must be a file path string")

    with open(KEYPAIR_PATH, "r") as f:
        secret = json.load(f)
    keypair = Keypair.from_bytes(bytes(secret))
    wallet_str = str(keypair.pubkey())

    headers = {
        "x-api-key": JUPITER_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    token_in = get_token_info(input_mint)
    token_out = get_token_info(output_mint)

    input_decimals = 9 if input_mint == "So11111111111111111111111111111111111111112" else token_in.get("decimals", 6)
    output_decimals = 9 if output_mint == "So11111111111111111111111111111111111111112" else token_out.get("decimals", 6)

    in_amount_raw = int(amount * 10 ** input_decimals)
    expected_in_ui = in_amount_raw / 10 ** input_decimals

    quote = get_quote(input_mint, output_mint, amount)
    if not quote:
        return "failed"

    out_amount_raw = int(quote["outAmount"])
    expected_out_ui = out_amount_raw / 10 ** output_decimals
    price_impact_pct = float(quote.get("priceImpactPct", 0))
    enter_price = expected_in_ui / expected_out_ui if expected_out_ui > 0 else 0.0

    # ── Print trade summary ────────────────────────────────────────
    print(f"\nGetting quote for {in_amount_raw:,} raw units → {action.upper()}")
    print("═══════════════════════════════════════════════════════")
    print(f"Action:       {action.upper()}")
    print(f"Input:        {expected_in_ui:,.6f} {token_in.get('symbol', '?')} (raw: {in_amount_raw})")
    print(f"Expected out: {expected_out_ui:,.6f} {token_out.get('symbol', '?')} (raw: {out_amount_raw})")
    print(f"Price impact: {price_impact_pct:.4f}%")
    print(f"Approx rate:  1 {token_in.get('symbol', 'input')} → {expected_out_ui/expected_in_ui:,.8f} {token_out.get('symbol', 'output')}")
    print(f"Entry price:  {enter_price:,.8f} {token_in.get('symbol', 'input')}/{token_out.get('symbol', 'output')}")
    print("═══════════════════════════════════════════════════════")

    # Request actual swap transaction
    print("Requesting swap transaction...")
    swap_payload = {
        "quoteResponse": quote,
        "userPublicKey": wallet_str,
        "wrapAndUnwrapSol": True,
        "computeUnitPriceMicroLamports": PRIORITY_FEE_MICRO_LAMPORTS,
    }
    swap_resp = requests.post(
        JUPITER_SWAP_URL,
        json=swap_payload,
        headers=headers,
        timeout=15
    )

    if swap_resp.status_code != 200:
        print("Swap tx request failed:", swap_resp.status_code, swap_resp.text[:400])
        return "failed"

    swap_data = swap_resp.json()
    swap_tx_encoded = swap_data["swapTransaction"]

    # Deserialize transaction
    print("Preparing transaction...")
    raw_tx_bytes = base64.b64decode(swap_tx_encoded)
    tx = VersionedTransaction.from_bytes(raw_tx_bytes)

    # Sign
    print("Signing transaction...")
    signature = keypair.sign_message(to_bytes_versioned(tx.message))
    signed_tx = VersionedTransaction.populate(tx.message, [signature])

    # Send & confirm
    print("Sending transaction...")
    try:
        tx_signature = client.send_raw_transaction(
            bytes(signed_tx),
            opts=TxOpts(
                skip_preflight=True,
                preflight_commitment=Confirmed,
                max_retries=5
            )
        ).value

        print("═" * 70)
        print("Transaction sent!")
        print("Signature :", str(tx_signature))
        print("Explorer  :", f"https://solscan.io/tx/{tx_signature}")
        print("Waiting for confirmation...")

        confirmed = client.confirm_transaction(
            tx_signature,
            commitment="confirmed",
            sleep_seconds=1.5
        )

        if confirmed.value:
            print("→ SUCCESS — Confirmed!")
            status = "success"
        else:
            print("→ Confirmation timeout.")
            status = "timeout"

    except Exception as e:
        print("Swap failed during send/confirm:", str(e))
        status = "failed"

    # Log to database
    log_swap(
        wallet=wallet_str,
        action=action,
        entering_price=f"{enter_price:.8f}",
        input_mint=input_mint,
        input_amount_ui=expected_in_ui,
        input_amount_raw=in_amount_raw,
        output_mint=output_mint,
        output_amount_ui=expected_out_ui,
        output_amount_raw=out_amount_raw,
        output_liqudation=token_out.get('liquidity', 0),
        tx_signature=str(tx_signature) if 'tx_signature' in locals() else None,
        price_impact_pct=price_impact_pct,
        slippage_bps=DEFAULT_SLIPPAGE_BPS,
        status=status
    )

    print("═" * 70)
    return status