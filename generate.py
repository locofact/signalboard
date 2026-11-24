"""주식 시그널 사이트 생성기 (시제품).

장 마감 데이터를 받아 RSI, MACD, 이동평균을 계산하고
site/ 폴더에 정적 HTML 페이지를 만듭니다.

실행: python generate.py
결과: site/index.html, site/us/..., site/kr/...

주의: 시제품용으로 야후 파이낸스의 공개 차트 데이터를 씁니다.
광고 수익이 나는 공개 사이트에서는 상업용 데이터로 바꿔야 합니다.
"""

import html
import json
import os
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

from indicators import sma, rsi, macd, last_cross, pct
from tickers import US_INDEXES, US_TICKERS, KR_INDEXES, KR_TICKERS

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site")
SITE_NAME = "SignalBoard"

# ---------------------------------------------------------------- 데이터


def fetch(symbol):
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.request.quote(symbol)}?range=1y&interval=1d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
        res = d["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        off = res["meta"].get("gmtoffset", 0)
        rows = [
            (ts, c, v)
            for ts, c, v in zip(res["timestamp"], q["close"], q["volume"])
            if c is not None
        ]
        if len(rows) < 60:
            return None
        return {
            "symbol": symbol,
            "name": res["meta"].get("longName") or res["meta"].get("shortName") or symbol,
            "dates": [
                datetime.fromtimestamp(ts + off, timezone.utc).strftime("%Y-%m-%d")
                for ts, _, _ in rows
            ],
            "closes": [c for _, c, _ in rows],
            "volumes": [v or 0 for _, _, v in rows],
        }
    except Exception as e:  # 네트워크 오류, 상장폐지 등
        print(f"  ! {symbol} 데이터 실패: {e}")
        return None


def fetch_all(symbols):
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(zip(symbols, ex.map(fetch, symbols)))


def analyze(d, slug, name=None):
    c = d["closes"]
    r = rsi(c)
    _, _, h = macd(c)
    s20, s50 = sma(c, 20), sma(c, 50)
    price = c[-1]
    trend = "flat"
    if s20[-1] and s50[-1]:
        if price > s20[-1] > s50[-1]:
            trend = "up"
        elif price < s20[-1] < s50[-1]:
            trend = "down"
    return {
        "slug": slug,
        "symbol": d["symbol"],
        "name": name or d["name"],
        "date": d["dates"][-1],
        "price": price,
        "chg1d": pct(c[-1], c[-2]),
        "chg5d": pct(c[-1], c[-6]) if len(c) > 6 else None,
        "chg1m": pct(c[-1], c[-22]) if len(c) > 22 else None,
        "high52": max(c),
        "rsi": r[-1],
        "hist": h[-1],
        "cross": last_cross(h, 5),
        "sma20": s20[-1],
        "sma50": s50[-1],
        "trend": trend,
        "series": {
            "dates": d["dates"][-120:],
            "close": c[-120:],
            "sma20": s20[-120:],
            "sma50": s50[-120:],
            "rsi": r[-120:],
            "hist": h[-120:],
        },
    }


def build_lists(stocks):
    ok = [s for s in stocks if s["rsi"] is not None and s["chg1d"] is not None]
    by_chg = sorted(ok, key=lambda s: s["chg1d"], reverse=True)
    return {
        "gainers": by_chg[:5],
        "losers": by_chg[::-1][:5],
        "oversold": sorted([s for s in ok if s["rsi"] < 40], key=lambda s: s["rsi"])[:8],
        "bullcross": sorted(
            [s for s in ok if s["cross"] and s["cross"][0] == "bull"],
            key=lambda s: s["cross"][1],
        )[:8],
        "rising": sorted(
            [s for s in ok if s["trend"] == "up" and 50 <= s["rsi"] < 70 and s["chg1m"] is not None],
            key=lambda s: s["chg1m"],
            reverse=True,
        )[:8],
        "overbought": sorted([s for s in ok if s["rsi"] >= 70], key=lambda s: -s["rsi"])[:8],
    }


# ---------------------------------------------------------------- 문구

T = {
    "us": {
        "lang": "en",
        "market": "US Stocks",
        "title": "US Stock Signals Today: RSI, MACD & Momentum Screens",
        "desc": "Daily US stock dashboard: oversold RSI stocks, MACD bullish crossovers, momentum leaders and top movers, updated after market close.",
        "updated": "Data as of market close",
        "indexes": "Market overview",
        "gainers": "Top gainers today",
        "losers": "Top losers today",
        "oversold": "Oversold watch (lowest RSI)",
        "oversold_d": "14-day RSI below 40. Below 30 is commonly called oversold.",
        "bullcross": "MACD bullish crossover (last 5 days)",
        "bullcross_d": "MACD line crossed above its signal line, a common trend-reversal signal.",
        "rising": "Uptrend, not yet overbought",
        "rising_d": "Price above 20-day and 50-day averages, RSI between 50 and 70. Sorted by 1-month return.",
        "overbought": "Overbought (RSI 70+)",
        "overbought_d": "Strong recent run. Pullbacks are more common from these levels.",
        "all": "All tracked stocks",
        "none": "No stocks match this screen today.",
        "cols": ["Symbol", "Name", "Price", "1D", "5D", "1M", "RSI", "MACD", "Trend"],
        "trend": {"up": "Uptrend", "down": "Downtrend", "flat": "Sideways"},
        "macd": {"pos": "Bullish", "neg": "Bearish"},
        "days": lambda n: "today" if n == 0 else f"{n}d ago",
        "disclaimer": "For informational and educational purposes only. Not financial advice. Signals are generated automatically from past price data and do not predict future returns. Do your own research before investing.",
        "back": "← All US signals",
        "chart": "Price, RSI and MACD (last 120 trading days)",
        "similar": "Other stocks with signals today",
        "ad": "Ad space",
        "home_us": "US Stocks",
        "home_kr": "Korean Stocks",
    },
    "kr": {
        "lang": "ko",
        "market": "국내주식",
        "title": "오늘의 국내주식 시그널: RSI·MACD 과매도·추세전환 종목",
        "desc": "코스피·코스닥 주요 종목의 RSI 과매도, MACD 골든크로스, 상승 추세 종목을 장 마감 후 매일 정리합니다.",
        "updated": "장 마감 기준 데이터",
        "indexes": "시장 현황",
        "gainers": "오늘 상승률 상위",
        "losers": "오늘 하락률 상위",
        "oversold": "과매도 관찰 (RSI 낮은 순)",
        "oversold_d": "14일 RSI 40 미만 종목입니다. 보통 30 미만을 과매도로 봅니다.",
        "bullcross": "MACD 골든크로스 (최근 5거래일)",
        "bullcross_d": "MACD선이 시그널선을 위로 돌파한 종목으로, 대표적인 추세전환 신호입니다.",
        "rising": "상승 추세, 아직 과열 전",
        "rising_d": "주가가 20일·50일 이동평균 위에 있고 RSI가 50~70인 종목입니다. 1개월 수익률 순.",
        "overbought": "과열 (RSI 70 이상)",
        "overbought_d": "최근 급등한 종목입니다. 이 구간에서는 조정이 나오는 경우가 많습니다.",
        "all": "전체 종목",
        "none": "오늘은 해당 종목이 없습니다.",
        "cols": ["코드", "종목명", "현재가", "1일", "5일", "1개월", "RSI", "MACD", "추세"],
        "trend": {"up": "상승", "down": "하락", "flat": "횡보"},
        "macd": {"pos": "강세", "neg": "약세"},
        "days": lambda n: "오늘" if n == 0 else f"{n}일 전",
        "disclaimer": "이 페이지는 정보 제공 목적이며 투자 권유가 아닙니다. 모든 신호는 과거 주가로 자동 계산된 것으로 미래 수익을 보장하지 않습니다. 투자 판단과 책임은 본인에게 있습니다.",
        "back": "← 국내주식 시그널 전체",
        "chart": "주가·RSI·MACD (최근 120거래일)",
        "similar": "오늘 신호가 나온 다른 종목",
        "ad": "광고 영역",
        "home_us": "US Stocks",
        "home_kr": "국내주식",
    },
}


def fmt_price(v, mk):
    if v is None:
        return "-"
    return f"{v:,.0f}원" if mk == "kr" else f"${v:,.2f}"


def fmt_pct(v):
    if v is None:
        return '<span class="mute">-</span>'
    cls = "up" if v > 0 else "down" if v < 0 else "mute"
    return f'<span class="{cls}">{v:+.2f}%</span>'


def rsi_badge(v):
    if v is None:
        return "-"
    cls = "b-low" if v < 30 else "b-high" if v >= 70 else "b-mid"
    return f'<span class="badge {cls}">{v:.1f}</span>'


def esc(s):
    return html.escape(str(s))


def describe(s, mk):
    """종목 페이지용 자동 해설문 (검색 노출과 애드센스 승인에 도움)."""
    r, t = s["rsi"], T[mk]
    if mk == "us":
        if r < 30:
            rz = "in oversold territory (below 30), which some traders watch for a potential rebound"
        elif r >= 70:
            rz = "in overbought territory (above 70), suggesting the recent rally may be stretched"
        else:
            rz = "in neutral territory between 30 and 70"
        txt = [f"{esc(s['name'])} ({esc(s['slug'])}) closed at {fmt_price(s['price'], mk)} on {s['date']}. "
               f"Its 14-day RSI is {r:.1f}, {rz}."]
        if s["cross"]:
            kind, n = s["cross"]
            word = "bullish" if kind == "bull" else "bearish"
            txt.append(f"The MACD line crossed {'above' if kind=='bull' else 'below'} its signal line {t['days'](n)}, a {word} crossover.")
        else:
            txt.append(f"MACD momentum is currently {'positive' if s['hist'] and s['hist']>0 else 'negative'}.")
        txt.append({
            "up": "The stock is trading above both its 20-day and 50-day moving averages, a typical uptrend structure.",
            "down": "The stock is trading below both its 20-day and 50-day moving averages, a typical downtrend structure.",
            "flat": "The moving averages show no clear trend right now.",
        }[s["trend"]])
    else:
        if r < 30:
            rz = "과매도 구간(30 미만)으로, 반등을 노리는 투자자들이 주목하는 구간입니다"
        elif r >= 70:
            rz = "과열 구간(70 이상)으로, 단기 급등 이후 조정 가능성을 염두에 둘 만한 구간입니다"
        else:
            rz = "30~70 사이의 중립 구간입니다"
        txt = [f"{esc(s['name'])}({esc(s['slug'])})의 {s['date']} 종가는 {fmt_price(s['price'], mk)}입니다. "
               f"14일 RSI는 {r:.1f}로 {rz}."]
        if s["cross"]:
            kind, n = s["cross"]
            txt.append(f"{t['days'](n)} MACD선이 시그널선을 {'상향' if kind=='bull' else '하향'} 돌파하는 "
                       f"{'골든크로스' if kind=='bull' else '데드크로스'}가 발생했습니다.")
        else:
            txt.append(f"현재 MACD 모멘텀은 {'양(+)' if s['hist'] and s['hist']>0 else '음(-)'}의 상태입니다.")
        txt.append({
            "up": "주가가 20일·50일 이동평균선 위에 있어 전형적인 상승 추세 모양입니다.",
            "down": "주가가 20일·50일 이동평균선 아래에 있어 전형적인 하락 추세 모양입니다.",
            "flat": "이동평균선 기준으로는 뚜렷한 추세가 없습니다.",
        }[s["trend"]])
    return " ".join(txt)


# ---------------------------------------------------------------- 차트 (SVG)


def chart_svg(s):
    S = s["series"]
    n = len(S["close"])
    W, L, R = 760, 8, 56
    pw = W - L - R
    x = lambda i: L + pw * i / (n - 1)

    def path(vals, y):
        pts, cmd = [], "M"
        for i, v in enumerate(vals):
            if v is None:
                cmd = "M"
                continue
            pts.append(f"{cmd}{x(i):.1f},{y(v):.1f}")
            cmd = "L"
        return " ".join(pts)

    parts = []
    # 가격 패널
    top, h = 10, 220
    vals = [v for v in S["close"] + S["sma20"] + S["sma50"] if v is not None]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.05 or 1
    lo, hi = lo - pad, hi + pad
    yp = lambda v: top + h * (1 - (v - lo) / (hi - lo))
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        parts.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{yp(v):.1f}" y2="{yp(v):.1f}"/>'
                     f'<text class="ax" x="{W-R+6}" y="{yp(v)+4:.1f}">{v:,.0f}</text>')
    parts.append(f'<path class="sma50" d="{path(S["sma50"], yp)}"/>')
    parts.append(f'<path class="sma20" d="{path(S["sma20"], yp)}"/>')
    parts.append(f'<path class="price" d="{path(S["close"], yp)}"/>')
    parts.append(f'<text class="lbl" x="{L+4}" y="{top+14}">Price</text>'
                 f'<text class="lbl l20" x="{L+48}" y="{top+14}">MA20</text>'
                 f'<text class="lbl l50" x="{L+92}" y="{top+14}">MA50</text>')

    # RSI 패널
    top2, h2 = top + h + 24, 80
    yr = lambda v: top2 + h2 * (1 - v / 100)
    parts.append(f'<rect class="zone" x="{L}" y="{yr(70):.1f}" width="{pw}" height="{yr(30)-yr(70):.1f}"/>')
    for v in (30, 70):
        parts.append(f'<line class="grid dash" x1="{L}" x2="{W-R}" y1="{yr(v):.1f}" y2="{yr(v):.1f}"/>'
                     f'<text class="ax" x="{W-R+6}" y="{yr(v)+4:.1f}">{v}</text>')
    parts.append(f'<path class="rsi" d="{path(S["rsi"], yr)}"/>')
    parts.append(f'<text class="lbl" x="{L+4}" y="{top2+12}">RSI 14</text>')

    # MACD 히스토그램
    top3, h3 = top2 + h2 + 24, 70
    hv = [v for v in S["hist"] if v is not None] or [0]
    m = max(abs(min(hv)), abs(max(hv))) or 1
    mid = top3 + h3 / 2
    bw = max(pw / n - 1, 1)
    for i, v in enumerate(S["hist"]):
        if v is None:
            continue
        hh = (h3 / 2) * abs(v) / m
        y0 = mid - hh if v > 0 else mid
        parts.append(f'<rect class="{"hp" if v > 0 else "hn"}" x="{x(i)-bw/2:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{max(hh,0.5):.1f}"/>')
    parts.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{mid}" y2="{mid}"/>')
    parts.append(f'<text class="lbl" x="{L+4}" y="{top3+12}">MACD histogram</text>')

    # 날짜 축
    yb = top3 + h3 + 16
    for i in (0, n // 2, n - 1):
        anchor = "start" if i == 0 else "end" if i == n - 1 else "middle"
        parts.append(f'<text class="ax" x="{x(i):.1f}" y="{yb}" text-anchor="{anchor}">{S["dates"][i]}</text>')

    return f'<svg class="chart" viewBox="0 0 {W} {yb+6}" role="img" aria-label="price chart">{"".join(parts)}</svg>'


# ---------------------------------------------------------------- HTML


def page(mk, title, desc, body, depth):
    t = T[mk] if mk else T["us"]
    up = "../" * depth
    lang = t["lang"] if mk else "en"
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="stylesheet" href="{up}style.css">
</head>
<body class="mk-{mk or 'home'}">
<header class="top">
  <a class="logo" href="{up}index.html">📈 {SITE_NAME}</a>
  <nav>
    <a href="{up}us/index.html" class="{'on' if mk=='us' else ''}">US Stocks</a>
    <a href="{up}kr/index.html" class="{'on' if mk=='kr' else ''}">국내주식</a>
  </nav>
</header>
<main>
{body}
</main>
<footer>
  <p>{esc(t['disclaimer'])}</p>
  <p class="mute">© {datetime.now().year} {SITE_NAME}</p>
</footer>
<script>
document.querySelectorAll('table.sortable th').forEach((th, idx) => {{
  th.addEventListener('click', () => {{
    const tb = th.closest('table').tBodies[0];
    const asc = th.dataset.asc !== '1';
    th.closest('tr').querySelectorAll('th').forEach(x => delete x.dataset.asc);
    th.dataset.asc = asc ? '1' : '0';
    const rows = [...tb.rows];
    rows.sort((a, b) => {{
      const va = a.cells[idx].dataset.v, vb = b.cells[idx].dataset.v;
      const na = parseFloat(va), nb = parseFloat(vb);
      const r = (!isNaN(na) && !isNaN(nb)) ? na - nb : String(va).localeCompare(String(vb));
      return asc ? r : -r;
    }});
    rows.forEach(r => tb.appendChild(r));
  }});
}});
</script>
</body>
</html>"""


def ad_slot(mk):
    return f'<div class="ad">{esc(T[mk]["ad"])}</div>'


def mini_table(items, mk, extra=None):
    t = T[mk]
    if not items:
        return f'<p class="mute small">{esc(t["none"])}</p>'
    rows = []
    for s in items:
        ex = extra(s) if extra else fmt_pct(s["chg1d"])
        rows.append(
            f'<tr><td><a href="{esc(s["slug"])}.html"><b>{esc(s["slug"] if mk=="us" else s["name"])}</b></a>'
            f'<div class="mute small">{esc(s["name"] if mk=="us" else s["slug"])}</div></td>'
            f'<td class="r">{fmt_price(s["price"], mk)}</td><td class="r">{ex}</td></tr>'
        )
    return f'<table class="mini">{"".join(rows)}</table>'


def card(key, items, mk, extra=None):
    t = T[mk]
    d = t.get(key + "_d", "")
    return (f'<section class="card"><h2>{esc(t[key])}</h2>'
            + (f'<p class="mute small">{esc(d)}</p>' if d else "")
            + mini_table(items, mk, extra) + "</section>")


def market_page(mk, stocks, indexes, lists):
    t = T[mk]
    date = max(s["date"] for s in stocks)
    idx_html = "".join(
        f'<div class="idx"><div class="mute small">{esc(nm)}</div>'
        f'<div class="big">{i["price"]:,.2f}</div>{fmt_pct(i["chg1d"])}</div>'
        for nm, i in indexes
    )
    rsi_extra = lambda s: rsi_badge(s["rsi"])
    cross_extra = lambda s: f'<span class="badge b-low">{esc(t["days"](s["cross"][1]))}</span>'
    m1_extra = lambda s: fmt_pct(s["chg1m"])

    head = "".join(f"<th>{esc(c)}</th>" for c in t["cols"])
    rows = []
    for s in sorted(stocks, key=lambda s: s["slug"]):
        macd_txt = t["macd"]["pos"] if (s["hist"] or 0) > 0 else t["macd"]["neg"]
        rows.append(
            "<tr>"
            f'<td data-v="{esc(s["slug"])}"><a href="{esc(s["slug"])}.html"><b>{esc(s["slug"])}</b></a></td>'
            f'<td data-v="{esc(s["name"])}">{esc(s["name"])}</td>'
            f'<td class="r" data-v="{s["price"]}">{fmt_price(s["price"], mk)}</td>'
            f'<td class="r" data-v="{s["chg1d"] or 0}">{fmt_pct(s["chg1d"])}</td>'
            f'<td class="r" data-v="{s["chg5d"] or 0}">{fmt_pct(s["chg5d"])}</td>'
            f'<td class="r" data-v="{s["chg1m"] or 0}">{fmt_pct(s["chg1m"])}</td>'
            f'<td class="r" data-v="{s["rsi"] or 0}">{rsi_badge(s["rsi"])}</td>'
            f'<td data-v="{s["hist"] or 0}">{esc(macd_txt)}</td>'
            f'<td data-v="{s["trend"]}">{esc(t["trend"][s["trend"]])}</td>'
            "</tr>"
        )

    body = f"""
<div class="hero">
  <h1>{esc(t['title'])}</h1>
  <p class="mute">{esc(t['updated'])}: <b>{date}</b> · {len(stocks)}{' stocks' if mk == 'us' else '개 종목'}</p>
</div>
<h2 class="sec">{esc(t['indexes'])}</h2>
<div class="idxrow">{idx_html}</div>
{ad_slot(mk)}
<div class="grid">
  {card('oversold', lists['oversold'], mk, rsi_extra)}
  {card('bullcross', lists['bullcross'], mk, cross_extra)}
  {card('rising', lists['rising'], mk, m1_extra)}
  {card('overbought', lists['overbought'], mk, rsi_extra)}
  {card('gainers', lists['gainers'], mk)}
  {card('losers', lists['losers'], mk)}
</div>
{ad_slot(mk)}
<h2 class="sec">{esc(t['all'])}</h2>
<div class="tablewrap"><table class="full sortable"><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
"""
    return page(mk, t["title"], t["desc"], body, 1)


def stock_page(mk, s, lists):
    t = T[mk]
    label = s["slug"] if mk == "us" else s["name"]
    if mk == "us":
        title = f"{s['slug']} RSI & MACD Today: {s['name']} Technical Signals"
        desc = f"{s['slug']} 14-day RSI is {s['rsi']:.1f}. See MACD, moving-average trend and chart for {s['name']}, updated daily."
    else:
        title = f"{s['name']} RSI·MACD 오늘 시그널 ({s['slug']})"
        desc = f"{s['name']} 14일 RSI {s['rsi']:.1f}. MACD, 이동평균 추세와 차트를 매일 업데이트합니다."

    macd_txt = t["macd"]["pos"] if (s["hist"] or 0) > 0 else t["macd"]["neg"]
    if s["cross"]:
        kind, n = s["cross"]
        cross_txt = (("Bullish cross " if kind == "bull" else "Bearish cross ") + t["days"](n)) if mk == "us" \
            else (("골든크로스 " if kind == "bull" else "데드크로스 ") + t["days"](n))
    else:
        cross_txt = macd_txt

    seen = {s["slug"]}
    sim = []
    for key in ("oversold", "bullcross", "rising", "overbought"):
        for o in lists[key]:
            if o["slug"] not in seen and len(sim) < 8:
                seen.add(o["slug"])
                sim.append(o)

    body = f"""
<p><a href="index.html" class="small">{esc(t['back'])}</a></p>
<div class="hero">
  <h1>{esc(label)} <span class="mute">{esc(s['name'] if mk=='us' else s['slug'])}</span></h1>
  <p class="price">{fmt_price(s['price'], mk)} {fmt_pct(s['chg1d'])} <span class="mute small">· {s['date']}</span></p>
</div>
<div class="stats">
  <div class="stat"><div class="mute small">RSI (14)</div><div class="big">{rsi_badge(s['rsi'])}</div></div>
  <div class="stat"><div class="mute small">MACD</div><div class="big">{esc(cross_txt)}</div></div>
  <div class="stat"><div class="mute small">{'Trend' if mk=='us' else '추세'}</div><div class="big">{esc(t['trend'][s['trend']])}</div></div>
  <div class="stat"><div class="mute small">{'1 month' if mk=='us' else '1개월'}</div><div class="big">{fmt_pct(s['chg1m'])}</div></div>
</div>
<p class="desc">{describe(s, mk)}</p>
{ad_slot(mk)}
<section class="card"><h2>{esc(t['chart'])}</h2>{chart_svg(s)}</section>
<section class="card"><h2>{esc(t['similar'])}</h2>{mini_table(sim, mk, lambda o: rsi_badge(o['rsi']))}</section>
"""
    return page(mk, title, desc, body, 1)


def home_page(us_date, kr_date):
    body = f"""
<div class="hero center">
  <h1>Daily stock signals, made simple</h1>
  <p class="mute">RSI, MACD and trend screens updated after every market close.</p>
</div>
<div class="grid two">
  <a class="card pick" href="us/index.html"><h2>🇺🇸 US Stocks</h2><p class="mute">Oversold, MACD crossovers, momentum leaders</p><p class="small">As of {us_date}</p></a>
  <a class="card pick" href="kr/index.html"><h2>🇰🇷 국내주식</h2><p class="mute">과매도, 골든크로스, 상승 추세 종목</p><p class="small">{kr_date} 기준</p></a>
</div>
"""
    return page(None, f"{SITE_NAME}: Daily Stock Signals", "Daily RSI and MACD stock signals for US and Korean markets.", body, 0)


# ---------------------------------------------------------------- 실행


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_market(mk, ticker_list, index_list):
    print(f"[{mk}] 데이터 받는 중...")
    syms = [x if isinstance(x, str) else x[0] for x in ticker_list]
    names = {x[0]: x[1] for x in ticker_list if not isinstance(x, str)}
    data = fetch_all(syms + [s for s, _ in index_list])

    stocks = []
    for sym in syms:
        d = data.get(sym)
        if d:
            slug = sym if mk == "us" else sym.split(".")[0]
            stocks.append(analyze(d, slug, names.get(sym)))
    indexes = [(nm, analyze(data[s], s)) for s, nm in index_list if data.get(s)]
    lists = build_lists(stocks)

    out = os.path.join(OUT, mk)
    if os.path.isdir(out):
        shutil.rmtree(out)
    write(os.path.join(out, "index.html"), market_page(mk, stocks, indexes, lists))
    for s in stocks:
        write(os.path.join(out, f"{s['slug']}.html"), stock_page(mk, s, lists))
    print(f"[{mk}] {len(stocks)}개 종목 페이지 생성")
    return max(s["date"] for s in stocks)


def main():
    us_date = build_market("us", US_TICKERS, US_INDEXES)
    kr_date = build_market("kr", KR_TICKERS, KR_INDEXES)
    write(os.path.join(OUT, "index.html"), home_page(us_date, kr_date))
    shutil.copy(os.path.join(ROOT, "style.css"), os.path.join(OUT, "style.css"))
    print("완료:", os.path.join(OUT, "index.html"))


if __name__ == "__main__":
    main()
