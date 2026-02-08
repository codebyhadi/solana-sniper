"""
Database utilities for the Solana sniper bot.
Handles logging of trades/swaps and querying past activity for tokens.

Uses MySQL via mysql-connector-python.
All monetary values are stored as Decimal for precision.
"""

from contextlib import closing
import mysql.connector
from decimal import Decimal
from config import DB_CONFIG
from typing import Dict, Optional, List


def get_db_connection():
    """Create and return a new MySQL connection using config settings."""
    return mysql.connector.connect(**DB_CONFIG)


def log_swap(
    wallet: str,
    action: str,                    # 'buy', 'sell', 'swap'
    entering_price: str,
    input_mint: str,
    input_amount_ui: float | Decimal,
    input_amount_raw: int,
    output_mint: str,
    output_amount_ui: float | Decimal,
    output_amount_raw: int,
    output_liqudation: float | Decimal,   # liquidity at time of trade (for later PNL calc)
    tx_signature: str,
    price_impact_pct: float = None,
    slippage_bps: int = None,
    status: str = "success",
    error_message: str = None
) -> None:
    """
    Log a swap / trade into the `swap_logs` table.
    Uses UPSERT logic — if tx_signature already exists, only updates status/error.

    Args:
        wallet:             Public key of the wallet performing the trade
        action:             'buy', 'sell', or 'swap'
        entering_price:     Entry price string (usually quote/input per output token)
        input_mint:         Mint address of input token
        input_amount_ui:    Human-readable input amount
        input_amount_raw:   Raw amount (smallest units, e.g. lamports or token wei)
        output_mint:        Mint address of output token
        output_amount_ui:   Human-readable output amount
        output_amount_raw:  Raw output amount
        output_liqudation:  Liquidity (USD) of the output token pool at trade time
        tx_signature:       Solana transaction signature (base58)
        price_impact_pct:   Price impact percentage from quote (optional)
        slippage_bps:       Slippage tolerance used (basis points)
        status:             'success', 'failed', 'timeout', etc.
        error_message:      Error details if failed (optional)

    Returns:
        None
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO swap_logs (
            wallet, action, entering_price, 
            input_mint, input_amount_ui, input_amount_raw,
            output_mint, output_amount_ui, output_amount_raw,
            tx_signature, price_impact_pct, slippage_bps, status, error_message, output_liqudation
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            status = VALUES(status),
            error_message = VALUES(error_message),
            updated_at = CURRENT_TIMESTAMP
        """
        values = (
            wallet,
            action,
            str(entering_price),
            input_mint,
            Decimal(str(input_amount_ui)),   # safe conversion
            input_amount_raw,
            output_mint,
            Decimal(str(output_amount_ui)),
            output_amount_raw,
            str(tx_signature),
            price_impact_pct,
            slippage_bps,
            status,
            error_message,
            Decimal(str(output_liqudation))
        )
        cursor.execute(query, values)
        conn.commit()
        print(f"✓ Swap logged: {tx_signature[:12]}...")
    except Exception as e:
        print("Error saving to DB:", str(e))
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def token_has_swap(mint: str) -> Optional[Dict]:
    """
    Check if we have previously traded this token (output_mint = mint).
    Returns the most recent swap log row (as dict) or None.

    Args:
        mint: Token mint address to check

    Returns:
        dict with swap log fields or None if never traded
    """
    query = "SELECT * FROM swap_logs WHERE output_mint = %s ORDER BY id DESC LIMIT 1"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, (mint,))
        row = cursor.fetchone()

        if row is None:
            return None

        # Convert tuple → dict using column names
        columns = [desc[0] for desc in cursor.description]
        result = dict(zip(columns, row))
        return result

    finally:
        cursor.close()
        conn.close()


def get_swaps_for_token(mint: str) -> List[Dict]:
    """
    Retrieve all historical swaps where this token was the output (i.e. we bought it).

    Args:
        mint: Token mint address

    Returns:
        List of dicts containing swap log fields, newest first
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
    SELECT 
        created_at,
        action,
        input_amount_ui,
        output_amount_ui,
        entering_price,
        price_impact_pct,
        status,
        tx_signature
    FROM swap_logs
    WHERE output_mint = %s ORDER BY id DESC
    """
    cursor.execute(query, (mint,))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results