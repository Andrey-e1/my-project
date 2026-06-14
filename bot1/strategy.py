import pandas as pd
import ta
from config import (
    EMA_FAST, EMA_MID, EMA_SLOW,
    RSI_PERIOD, RSI_MIN, RSI_MAX,
    MACD_FAST, MACD_SLOW, MACD_SIG,
    ATR_PERIOD,
)

ADX_PERIOD    = 14
ADX_MIN       = 25    # только сильный тренд
VOL_MULT      = 1.3   # объём должен превышать среднее
MACD_GROWING  = True  # гистограмма MACD должна расти


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = ta.trend.EMAIndicator(df["close"], window=EMA_FAST).ema_indicator()
    df["ema_mid"]  = ta.trend.EMAIndicator(df["close"], window=EMA_MID).ema_indicator()
    df["ema_slow"] = ta.trend.EMAIndicator(df["close"], window=EMA_SLOW).ema_indicator()
    df["rsi"]      = ta.momentum.RSIIndicator(df["close"], window=RSI_PERIOD).rsi()
    macd           = ta.trend.MACD(df["close"], MACD_FAST, MACD_SLOW, MACD_SIG)
    df["macd_hist"] = macd.macd_diff()
    df["macd"]      = macd.macd()
    df["macd_sig"]  = macd.macd_signal()
    df["atr"]       = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=ATR_PERIOD
    ).average_true_range()
    adx            = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=ADX_PERIOD)
    df["adx"]      = adx.adx()
    df["vol_ma"]   = df["volume"].rolling(20).mean()
    # нормированный ATR — волатильность относительно цены
    df["atr_pct"]  = df["atr"] / df["close"]
    return df.dropna()


def signal_score(df: pd.DataFrame) -> tuple[str, float]:
    if len(df) < 3:
        return "none", 0.0

    c = df.iloc[-1]
    p = df.iloc[-2]

    # 1. Тренд выровнен
    trend_up   = c["ema_fast"] > c["ema_mid"] > c["ema_slow"]
    trend_down = c["ema_fast"] < c["ema_mid"] < c["ema_slow"]

    # 2. ADX — тренд сильный, не боковик
    strong_trend = c["adx"] >= ADX_MIN

    # 3. MACD бычий/медвежий И гистограмма растёт (набирает силу)
    macd_bull = (c["macd_hist"] > 0 and c["macd"] > c["macd_sig"]
                 and c["macd_hist"] > p["macd_hist"])
    macd_bear = (c["macd_hist"] < 0 and c["macd"] < c["macd_sig"]
                 and c["macd_hist"] < p["macd_hist"])

    # 4. Объём подтверждает движение
    vol_ok     = c["volume"] >= c["vol_ma"] * VOL_MULT
    vol_factor = min(c["volume"] / c["vol_ma"], 4.0) if c["vol_ma"] > 0 else 1.0

    # 5. Скор = сила тренда * ADX * объём
    ema_spread = abs(c["ema_fast"] - c["ema_slow"]) / c["ema_slow"]

    # Pullback к EMA21 в направлении тренда
    near_ema21_long  = abs(c["close"] - c["ema_mid"]) / c["ema_mid"] < 0.015  # в 1.5% от EMA21
    near_ema21_short = abs(c["close"] - c["ema_mid"]) / c["ema_mid"] < 0.015

    # RSI: откат без перепроданности (40-58 на лонг)
    rsi_pullback_long  = 40 <= c["rsi"] <= 58
    rsi_pullback_short = 42 <= c["rsi"] <= 60

    if (trend_up and strong_trend and macd_bull
            and near_ema21_long and rsi_pullback_long and vol_ok):
        score = ema_spread * (c["adx"] / 100) * vol_factor
        return "long", score

    if (trend_down and strong_trend and macd_bear
            and near_ema21_short and rsi_pullback_short and vol_ok):
        score = ema_spread * (c["adx"] / 100) * vol_factor
        return "short", score

    return "none", 0.0


def get_signal(df: pd.DataFrame) -> str:
    direction, _ = signal_score(df)
    return direction
