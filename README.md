# Solana Memecoin Sniper Bot (Pump.fun focused)

**Very high risk – for education & experimentation only**

Automated bot that:

- Scans new Pump.fun tokens
- Filters using RugCheck + liquidity + scoring logic
- Buys promising tokens via Jupiter Aggregator
- Monitors open positions → auto-sells on TP / SL / rug risk change
- Logs trades to MySQL
- Sends Telegram notifications

## ⚠️ WARNINGS

- **This can lose ALL your money quickly**
- Many tokens are rugs / honeypots / pump & dumps
- Never use real significant funds
- Jupiter v1 API is **deprecated** → consider upgrading
- Private keys and API tokens **must never** be committed

## Features (current)

- Pump.fun new token scanner
- Multi-factor scoring (LP/MC, holders, momentum, age, etc)
- Take-profit / Stop-loss automation
- Telegram alerts (new tokens + position open/close)
- Basic Flask dashboard for trade history
- MySQL trade logging

## Folder structure
solana-sniper-bot/
├── src/                    ← all python code
├── templates/              ← Flask HTML (if used)
├── data/                   ← optional logs
├── .env                    ← your secrets (gitignored)
├── .env.example
├── requirements.txt
├── README.md
└── .gitignore

## Setup

1.Clone repository
```bash
git clone ...
cd solana-sniper-bot

2.Create & fill .env
Bashcp .env.example .env
# edit .env with real values !!!
# edit config.py with real values !!!(RPC_ENDPOINT,JUPITER_API_KEY,DB_CONFIG,BOT_TOKEN and CHAT_ID)

3.Install dependencies
Bashpython -m venv venv
source venv/bin/activate    # or venv\Scripts\activate on Windows
pip install -r requirements.txt

4.Convert Phantom private key (one time)
Bashpython src/convert_phantom_key.py
# or just copy-paste the 64-byte array into phantom_keypair.json

5.Create MySQL database & table
CREATE DATABASE solana_sniper;
USE solana_sniper;

CREATE TABLE swap_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    wallet VARCHAR(44),
    action ENUM('buy','sell','swap'),
    entering_price VARCHAR(64),
    input_mint VARCHAR(44),
    input_amount_ui DECIMAL(24,9),
    input_amount_raw BIGINT,
    output_mint VARCHAR(44),
    output_amount_ui DECIMAL(24,9),
    output_amount_raw BIGINT,
    tx_signature VARCHAR(88) UNIQUE,
    price_impact_pct FLOAT,
    slippage_bps INT,
    status VARCHAR(32),
    error_message TEXT,
    output_liqudation DECIMAL(18,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

6.Run monitoring / trading loops
# Discovery + auto-buy
python src/main.py

# Position manager (TP/SL/rug exit)
python src/wmain.py

# Optional: trade history dashboard
python src/app.py   # → http://localhost:5000
