import ccxt
import pandas as pd
from strategy import add_indicators, signal_score
from config import QUOTE, TOP_N_SYMBOLS, TIMEFRAME


def get_top_symbols(exchange: ccxt.Exchange) -> list[str]:
    tickers = exchange.fetch_tickers()
    futures = {
        s: t for s, t in tickers.items()
        if s.endswith(f"/{QUOTE}") and t.get("quoteVolume") and t.get("quoteVolume", 0) > 0
    }
    ranked = sorted(futures.items(), key=lambda x: x[1]["quoteVolume"], reverse=True)
    # исключаем стейблкоины и синтетику
    exclude = {"USDC", "BUSD", "TUSD", "USDP", "DAI", "FDUSD", "WBTC", "WETH"}
    symbols = [
        s for s, _ in ranked
        if s.split("/")[0] not in exclude
    ]
    return symbols[:TOP_N_SYMBOLS]


def scan(exchange: ccxt.Exchange, candles_cache: dict | None = None) -> list[dict]:
    symbols  = get_top_symbols(exchange)
    results  = []

    for symbol in symbols:
        try:
            if candles_cache and symbol in candles_cache:
                df = candles_cache[symbol]
            else:
                raw = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=100)
                df  = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)
                if candles_cache is not None:
                    candles_cache[symbol] = df

            df = add_indicators(df)
            direction, score = signal_score(df)

            if direction != "none":
                results.append({
                    "symbol":    symbol,
                    "direction": direction,
                    "score":     score,
                    "atr":       df.iloc[-1]["atr"],
                    "price":     df.iloc[-1]["close"],
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
