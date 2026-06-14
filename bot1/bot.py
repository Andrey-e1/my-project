import ccxt
import time
import logging
from datetime import datetime
from strategy import add_indicators, get_signal
from config import (
    API_KEY, API_SECRET, SYMBOL, TIMEFRAME, LEVERAGE,
    TRADE_USDT, TAKE_PROFIT_PCT, STOP_LOSS_PCT, MAX_OPEN_TRADES
)
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def get_exchange():
    return ccxt.binance({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })


def fetch_candles(exchange) -> pd.DataFrame:
    candles = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def get_open_positions(exchange) -> list:
    positions = exchange.fetch_positions([SYMBOL])
    return [p for p in positions if float(p["contracts"]) > 0]


def place_order(exchange, side: str, price: float):
    amount = round(TRADE_USDT * LEVERAGE / price, 3)
    order = exchange.create_market_order(SYMBOL, side, amount)
    log.info(f"Открыта сделка: {side.upper()} {amount} {SYMBOL} @ ~{price:.2f}")

    if side == "buy":
        tp_price = round(price * (1 + TAKE_PROFIT_PCT), 2)
        sl_price = round(price * (1 - STOP_LOSS_PCT), 2)
        tp_side = "sell"
    else:
        tp_price = round(price * (1 - TAKE_PROFIT_PCT), 2)
        sl_price = round(price * (1 + STOP_LOSS_PCT), 2)
        tp_side = "buy"

    exchange.create_order(SYMBOL, "TAKE_PROFIT_MARKET", tp_side, amount,
                          params={"stopPrice": tp_price, "reduceOnly": True, "closePosition": True})
    exchange.create_order(SYMBOL, "STOP_MARKET", tp_side, amount,
                          params={"stopPrice": sl_price, "reduceOnly": True, "closePosition": True})

    log.info(f"  TP: {tp_price} | SL: {sl_price}")
    return order


def run():
    log.info("Бот запущен")
    exchange = get_exchange()

    try:
        exchange.set_leverage(LEVERAGE, SYMBOL)
    except Exception as e:
        log.warning(f"Не удалось установить плечо: {e}")

    while True:
        try:
            positions = get_open_positions(exchange)
            if len(positions) >= MAX_OPEN_TRADES:
                log.info(f"Открытых позиций: {len(positions)}, ждём...")
                time.sleep(30)
                continue

            df = fetch_candles(exchange)
            df = add_indicators(df)
            signal = get_signal(df)

            if signal == "long":
                price = df.iloc[-1]["close"]
                place_order(exchange, "buy", price)
            elif signal == "short":
                price = df.iloc[-1]["close"]
                place_order(exchange, "sell", price)
            else:
                log.info("Сигнала нет, ждём...")

        except ccxt.NetworkError as e:
            log.error(f"Сетевая ошибка: {e}")
        except ccxt.ExchangeError as e:
            log.error(f"Ошибка биржи: {e}")
        except Exception as e:
            log.error(f"Неожиданная ошибка: {e}", exc_info=True)

        time.sleep(60)


if __name__ == "__main__":
    run()
