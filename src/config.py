"""
Central configuration file for the Solana memecoin sniper bot.

Contains:
- Trading parameters (risk, TP/SL, position sizing)
- API endpoints & keys
- Filtering rules (liquidity, rug score, volume, etc.)
- Telegram & database credentials
- ANSI color codes for console output
"""

# ── Trading Behavior ────────────────────────────────────────
TESTING_MODE = False                    # When True, most swaps are simulated
TESTING_WALLET = "paper_wallet_001"     # Just for logging / display

WALLET_BASE = "USDT"                    # Quote currency for buys/sells
REFRESH_TIME = 60                       # Scanner loop interval (seconds)

SENT_MINTS = set()                      # Prevent duplicate Telegram messages

MAX_OPEN_POSITIONS = 2
STOP_LOSS = -50                         # % loss → auto sell
TAKE_PROFIT = 40                        # % profit → auto sell

RISK_PER_TRADE = 0.01                   # 1% of capital per trade
AMOUNT_PER_TRADE = 100 * RISK_PER_TRADE # UI amount in USDT

START_CAPITAL = 15                      # Starting simulated capital (USDT)
MIN_LIQUIDITY = 100_000                 # Minimum pool liquidity (USD)
DEFAULT_SLIPPAGE_BPS = 50               # 0.5% default slippage tolerance
MIN_POOL_SHARE = 0.10                   # Pool must be ≥10% of largest pool
MIN_24H_VOLUME = 5_000                  # Avoid dead / parked liquidity
PRIORITY_FEE_MICRO_LAMPORTS = 100_000   # ~0.0001 SOL
VALID_POOL_LIQUIDITY = 25_000           # Min LP to consider pool "real"

ALLOWED_DEXES = {"raydium", "orca", "meteora", "pump-fun"}

# ── Scoring Thresholds ──────────────────────────────────────
MIN_SCORE = 55
AGGRESSIVE_SCORE = 60
RUG_SCORE = 1                           # Desired RugCheck.xyz score

# ── Common Token Addresses ──────────────────────────────────
WSOL = "So11111111111111111111111111111111111111112"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

# ── RPC & API Endpoints ─────────────────────────────────────
RPC_ENDPOINT = "https://mainnet.helius-rpc.com/?api..."
RUGCHECK_URL = "https://api.rugcheck.xyz/v1/tokens/"
PUMPFUN_URL = "https://frontend-api-v3.pump.fun/homepage-cache/search?marketCapMin=20000&marketCapMax=2950000&volume24hMin=20000&limit=100&offset=0&includeNsfw=false&sortBy=created_timestamp&sortOrder=DESC"

KEYPAIR_PATH = "phantom_keypair.json"

# Jupiter Aggregator v1 API (deprecated — consider upgrading to v6)
JUPITER_QUOTE_URL = "https://api.jup.ag/swap/v1/quote"
JUPITER_SWAP_URL = "https://api.jup.ag/swap/v1/swap"
JUPITER_API_KEY = "78a64a71-..."

# ── Blacklisted tokens/mints ────────────────────────────────
EXCLUDED_TOKENS = {
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
   # "Cm6fNnMk7NfzStP9CZpsQA2v3jjzbcYGAxdJySmHpump",  # example
}

# ── ANSI Console Colors ─────────────────────────────────────
RESET = '\x1b[0m'
RED = '\x1b[31m'
GREEN = '\x1b[32m'
YELLOW = '\x1b[33m'
BLUE = '\x1b[34m'
MAGENTA = '\x1b[35m'
CYAN = '\x1b[36m'
WHITE = '\x1b[37m'
BRIGHT_RED = '\x1b[91m'
BRIGHT_GREEN = '\x1b[92m'
BRIGHT_YELLOW = '\x1b[93m'
BRIGHT_BLUE = '\x1b[94m'
BRIGHT_MAGENTA = '\x1b[95m'
BRIGHT_CYAN = '\x1b[96m'
BRIGHT_WHITE = '\x1b[97m'

# ── MySQL Database Config ───────────────────────────────────
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'solana_sniper'
}

# ── Telegram Notifications ──────────────────────────────────
BOT_TOKEN = "8577132741:..."
CHAT_ID = 72                 # Your Telegram chat ID