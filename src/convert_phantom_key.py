"""
Utility script to convert a Phantom wallet base58-encoded private key
into Solana-compatible JSON keypair format (64-byte array).

Reads the private key from a .env file (recommended for safety).

This is commonly needed when you want to use the same keypair with
solders / solana-py libraries that expect the raw 64-byte secret key.

WARNING:
    Never commit the .env file to git!
    Add .env to .gitignore
"""

import base58
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# ────────────────────────────────────────────────
#  Load environment variables from .env file
# ────────────────────────────────────────────────
env_path = Path('.') / '.env'
print(env_path)
if not env_path.exists():
    print("❌ .env file not found in the current directory!")
    print("Please create .env and add your key like this:")
    exit(1)

load_dotenv(env_path)

# Get the base58 private key from environment
PHANTOM_BASE58_KEY = os.getenv("PHANTOM_PRIVATE_KEY")

if not PHANTOM_BASE58_KEY:
    print("❌ PHANTOM_PRIVATE_KEY not found in .env file")
    print("Example .env content:")
    print('PHANTOM_PRIVATE_KEY="5cvf..."')
    exit(1)

# Optional: basic length check before decoding (58 chars is typical)
if len(PHANTOM_BASE58_KEY) < 40 or len(PHANTOM_BASE58_KEY) > 100:
    print("⚠️  Suspicious private key length — please double-check")
    print(f"Got string of length {len(PHANTOM_BASE58_KEY)}")
    answer = input("Continue anyway? (y/N): ").strip().lower()
    if answer != 'y':
        exit(0)

try:
    # Decode base58 private key string → raw bytes
    decoded = base58.b58decode(PHANTOM_BASE58_KEY)
except Exception as e:
    print("❌ Base58 decode failed. Probably invalid private key format.")
    print(f"Error: {e}")
    exit(1)

# Solana keypairs are 64 bytes (32-byte seed + 32-byte pubkey)
if len(decoded) != 64:
    print(f"❌ Invalid key length after decoding: {len(decoded)} bytes (expected 64)")
    exit(1)

# Save as JSON array of integers (compatible with solders.Keypair.from_bytes)
output_file = "phantom_keypair.json"

with open(output_file, "w") as f:
    json.dump(list(decoded), f, indent=2)

print("✅ Conversion complete!")
print(f"Saved as: {output_file}")
print("You can now use this file with:")
print("   Keypair.from_bytes(bytes(json.load(open('phantom_keypair.json'))))")
print()
print("⚠️  Remember to .gitignore the .json file too if it contains real keys!")

# End :)