"""
Global singleton-like wallet & RPC client context.
Loads keypair once and reuses RPC client to avoid repeated initialization.
"""

import json
from solana.rpc.api import Client
from solders.keypair import Keypair
from config import RPC_ENDPOINT, KEYPAIR_PATH

_client: Client | None = None
_keypair: Keypair | None = None


def get_wallet() -> tuple[Client, Keypair]:
    """
    Get (or lazily initialize) RPC client and keypair.

    Returns:
        (Client, Keypair) tuple
    """
    global _client, _keypair

    if _client is None or _keypair is None:
        if not isinstance(KEYPAIR_PATH, str):
            raise TypeError("KEYPAIR_PATH must be a file path string")

        with open(KEYPAIR_PATH, "r") as f:
            secret = json.load(f)

        _keypair = Keypair.from_bytes(bytes(secret))
        _client = Client(RPC_ENDPOINT)

    return _client, _keypair