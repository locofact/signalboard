"""기술적 지표 계산 (외부 라이브러리 없이 순수 파이썬)."""


def sma(values, n):
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(values, n):
    out = [None] * len(values)
    if len(values) < n:
        return out
    k = 2 / (n + 1)
    prev = sum(values[:n]) / n
    out[n - 1] = prev
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values, n=14):
    """Wilder 방식 RSI."""
    out = [None] * len(values)
    if len(values) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_g, avg_l = gains / n, losses / n
    out[n] = 100 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    for i in range(n + 1, len(values)):
        d = values[i] - values[i - 1]
        avg_g = (avg_g * (n - 1) + max(d, 0)) / n
        avg_l = (avg_l * (n - 1) + max(-d, 0)) / n
        out[i] = 100 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def macd(values, fast=12, slow=26, signal=9):
    ef, es = ema(values, fast), ema(values, slow)
    line = [None if a is None or b is None else a - b for a, b in zip(ef, es)]
    start = next((i for i, v in enumerate(line) if v is not None), len(line))
    sig_part = ema(line[start:], signal)
    sig = [None] * start + sig_part
    hist = [None if a is None or b is None else a - b for a, b in zip(line, sig)]
    return line, sig, hist


def last_cross(hist, lookback=5):
    """최근 lookback일 안에 MACD 히스토그램이 0을 뚫은 경우.
    반환: ('bull'|'bear', 며칠 전) 또는 None"""
    n = len(hist)
    for back in range(0, lookback):
        i = n - 1 - back
        if i < 1 or hist[i] is None or hist[i - 1] is None:
            continue
        if hist[i - 1] <= 0 < hist[i]:
            return ("bull", back)
        if hist[i - 1] >= 0 > hist[i]:
            return ("bear", back)
    return None


def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (a / b - 1) * 100
