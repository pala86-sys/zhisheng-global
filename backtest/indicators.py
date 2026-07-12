"""技術指標計算"""

import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    volume = out["Volume"].astype(float)

    for n in (5, 10, 20, 60):
        out[f"MA{n}"] = close.rolling(n).mean()

    low_n = low.rolling(9).min()
    high_n = high.rolling(9).max()
    denom = (high_n - low_n).replace(0.0, np.nan)
    k = ((close - low_n) / denom) * 100.0
    out["K"] = k
    out["D"] = k.rolling(3).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    out["MACD"] = macd
    out["MACD_signal"] = signal
    out["MACD_hist"] = macd - signal

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["RSI"] = 100 - (100 / (1 + rs))

    out["HIGH20"] = high.rolling(20).max().shift(1)
    out["VOL_MA20"] = volume.rolling(20).mean()

    return out
