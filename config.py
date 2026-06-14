import os
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")

TIMEFRAME  = "4h"
LEVERAGE   = 3
QUOTE      = "USDT"

TOP_N_SYMBOLS   = 50    # сколько монет сканировать по объёму
MAX_OPEN_TRADES = 3     # макс одновременных позиций
TRADE_USDT      = 50    # размер одной позиции в USDT (margin)
COMMISSION      = 0.0002

EMA_FAST   = 9
EMA_MID    = 21
EMA_SLOW   = 50
RSI_PERIOD = 14
RSI_MIN    = 45
RSI_MAX    = 70
MACD_FAST  = 12
MACD_SLOW  = 26
MACD_SIG   = 9
ATR_PERIOD  = 14
ATR_SL_MULT = 1.5
ATR_TP_MULT = 3.0

# Фиксированные % цели (используются вместо ATR)
TAKE_PROFIT_PCT = 0.03   # 3%
STOP_LOSS_PCT   = 0.01   # 1%  → RR = 3:1

BACKTEST_DAYS   = 180
INITIAL_DEPOSIT = 500
