import ccxt
import pandas as pd
from datetime import datetime, timedelta, timezone
from strategy import add_indicators, get_signal
from config import (
    TIMEFRAME, BACKTEST_DAYS,
    TRADE_USDT, LEVERAGE, COMMISSION, QUOTE, TOP_N_SYMBOLS,
    MAX_OPEN_TRADES, INITIAL_DEPOSIT,
    TAKE_PROFIT_PCT, STOP_LOSS_PCT,
)


EXCLUDE = {"USDC", "BUSD", "TUSD", "USDP", "DAI", "FDUSD", "WBTC", "WETH"}


def get_symbols(exchange: ccxt.Exchange) -> list[str]:
    tickers = exchange.fetch_tickers()
    ranked  = sorted(
        [(s, t) for s, t in tickers.items()
         if s.endswith(f"/{QUOTE}") and t.get("quoteVolume", 0) > 0
         and s.split("/")[0] not in EXCLUDE],
        key=lambda x: x[1]["quoteVolume"], reverse=True,
    )
    return [s for s, _ in ranked[:TOP_N_SYMBOLS]]


def fetch_ohlcv(exchange: ccxt.Exchange, symbol: str, days: int) -> pd.DataFrame:
    since = exchange.parse8601(
        (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    )
    all_candles = []
    while True:
        candles = exchange.fetch_ohlcv(symbol, TIMEFRAME, since=since, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        since = candles[-1][0] + 1
        if len(candles) < 1000:
            break
    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df.drop_duplicates()


def run_backtest():
    exchange = ccxt.binance({"enableRateLimit": True})

    print(f"Получаем топ-{TOP_N_SYMBOLS} монет по объёму...")
    symbols = get_symbols(exchange)
    print(f"Монеты: {', '.join(s.split('/')[0] for s in symbols)}\n")

    all_trades  = []
    position    = TRADE_USDT * LEVERAGE
    commission  = position * COMMISSION * 2

    for symbol in symbols:
        try:
            df = fetch_ohlcv(exchange, symbol, BACKTEST_DAYS)
            df = add_indicators(df)
        except Exception as e:
            print(f"  {symbol}: пропущено ({e})")
            continue

        in_trade    = False
        entry_price = 0.0
        direction   = ""
        tp = sl     = 0.0

        for i in range(51, len(df)):
            window = df.iloc[:i + 1]
            row    = df.iloc[i]

            if in_trade:
                result = pnl = None
                if direction == "long":
                    if row["high"] >= tp:
                        pnl, result = position * TAKE_PROFIT_PCT, "win"
                    elif row["low"] <= sl:
                        pnl, result = -position * STOP_LOSS_PCT, "loss"
                else:
                    if row["low"] <= tp:
                        pnl, result = position * TAKE_PROFIT_PCT, "win"
                    elif row["high"] >= sl:
                        pnl, result = -position * STOP_LOSS_PCT, "loss"

                if result:
                    all_trades.append({
                        "symbol": symbol, "result": result,
                        "pnl": pnl, "net": pnl - commission,
                        "date": row.name,
                    })
                    in_trade = False
                continue

            signal = get_signal(window)
            if signal != "none":
                entry_price = row["close"]
                direction   = signal
                if signal == "long":
                    tp = entry_price * (1 + TAKE_PROFIT_PCT)
                    sl = entry_price * (1 - STOP_LOSS_PCT)
                else:
                    tp = entry_price * (1 - TAKE_PROFIT_PCT)
                    sl = entry_price * (1 + STOP_LOSS_PCT)
                in_trade = True

        print(f"  {symbol:<15} — {sum(1 for t in all_trades if t['symbol'] == symbol)} сделок")

    if not all_trades:
        print("Сделок не найдено.")
        return

    res           = pd.DataFrame(all_trades).sort_values("date")
    wins          = (res["result"] == "win").sum()
    losses        = (res["result"] == "loss").sum()
    total         = len(res)
    win_rate      = wins / total * 100
    gross_pnl     = res["pnl"].sum()
    net_pnl       = res["net"].sum()
    total_comm    = commission * total
    avg_win       = res[res["result"] == "win"]["net"].mean()
    avg_loss      = res[res["result"] == "loss"]["net"].mean()
    pf_denom      = abs(res[res["result"] == "loss"]["net"].sum())
    profit_factor = res[res["result"] == "win"]["net"].sum() / pf_denom if pf_denom else float("inf")

    # эквити — последовательно, макс MAX_OPEN_TRADES одновременно
    equity = [INITIAL_DEPOSIT]
    for _, t in res.iterrows():
        equity.append(equity[-1] + t["net"])
    eq      = pd.Series(equity)
    max_dd  = ((eq.cummax() - eq) / eq.cummax() * 100).max()

    per_month   = net_pnl / (BACKTEST_DAYS / 30)
    roi         = net_pnl / INITIAL_DEPOSIT * 100

    top_symbols = (
        res[res["result"] == "win"]
        .groupby("symbol")["net"].sum()
        .sort_values(ascending=False)
        .head(5)
    )

    print()
    print("=" * 50)
    print(f"  МУЛЬТИВАЛЮТНЫЙ БЕКТЕСТ ({BACKTEST_DAYS} дней)")
    print(f"  {TOP_N_SYMBOLS} монет | {TIMEFRAME} | Плечо {LEVERAGE}x")
    print("=" * 50)
    print(f"  Всего сделок:       {total}")
    print(f"  Побед / Поражений:  {wins} / {losses}")
    print(f"  Win Rate:           {win_rate:.1f}%")
    print(f"  Profit Factor:      {profit_factor:.2f}")
    print(f"  PnL (gross):        ${gross_pnl:.2f}")
    print(f"  Комиссии:           -${total_comm:.2f}")
    print(f"  PnL (net):          ${net_pnl:.2f}")
    print(f"  ROI за период:      {roi:.1f}%")
    print(f"  Прибыль/месяц:      ${per_month:.2f}")
    print(f"  Ср. выигрыш:        ${avg_win:.2f}")
    print(f"  Ср. проигрыш:       ${avg_loss:.2f}")
    print(f"  Макс. просадка:     {max_dd:.1f}%")
    print(f"  Итог. депозит:      ${equity[-1]:.2f}")
    print()
    print("  Топ-5 монет по прибыли:")
    for sym, pnl in top_symbols.items():
        print(f"    {sym:<18} +${pnl:.2f}")
    print("=" * 50)


if __name__ == "__main__":
    run_backtest()
