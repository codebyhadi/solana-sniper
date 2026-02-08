"""
Simple Flask web dashboard to view recent trades from the database.

Shows last 100 swaps with timestamp, action, amounts, signature, etc.
Run with: python app.py
Access: http://localhost:5000
"""

import mysql.connector
from flask import Flask, render_template
from datetime import datetime
from config import DB_CONFIG

app = Flask(__name__)


def get_db_connection():
    """Create MySQL connection using config."""
    return mysql.connector.connect(**DB_CONFIG)


@app.route('/')
def show_swaps():
    """
    Main route: display last 100 trades from swap_logs table.
    Renders index.html template.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT 
            created_at,
            wallet,
            action,
            output_mint,
            input_mint,
            input_amount_ui,
            output_amount_ui,
            price_impact_pct,
            tx_signature,
            status
        FROM swap_logs
        ORDER BY created_at DESC
        LIMIT 100
        """
        cursor.execute(query)
        trades = cursor.fetchall()

        return render_template('index.html', trades=trades, now=datetime.utcnow())

    except Exception as e:
        return f"Database error: {str(e)}", 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)