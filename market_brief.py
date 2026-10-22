"""Live market briefing builder for Gold & Bitcoin.
Uses public Yahoo Finance chart endpoints and RSS headlines; falls back transparently when feeds fail.
This creates educational scenarios, never personalized trade instructions.
"""
import json
import math
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

UA = "GoldBitcoinBrief/1.0 (educational market dashboard)"
TIMEOUT = 12

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.read()

def yahoo_chart(symbol, range_="5d", interval="1h"):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol, safe="") + "?" + urllib.parse.urlencode({"range": range_, "interval": interval})
    data = json.loads(fetch(url).decode("utf-8"))["chart"]["result"][0]
    q = data["indicators"]["quote"][0]
    closes = [float(x) for x in (q.get("close") or []) if x is not None]
    timestamps = data.get("timestamp") or []
    currency = data.get("meta", {}).get("currency", "USD")
    if not closes:
        raise ValueError("No closes for " + symbol)
    return {"symbol": symbol, "price": closes[-1], "closes": closes, "currency": currency, "timestamp": timestamps[-1] if timestamps else None}

def fmt_price(x, decimals=2):
    return f"{x:,.{decimals}f}"

def pct_change(values, n=24):
    if len(values) <= n or values[-n-1] == 0:
        return None
    return (values[-1] / values[-n-1] - 1) * 100

def rsi(values, period=14):
    if len(values) < period + 1:
        return None
    diffs = [values[i] - values[i-1] for i in range(len(values)-period, len(values))]
    gains = sum(max(d, 0) for d in diffs) / period
    losses = sum(max(-d, 0) for d in diffs) / period
    if losses == 0:
        return 100.0 if gains else 50.0
    return 100 - (100 / (1 + gains / losses))

def headline_items():
    feeds = [
        ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
        ("CNBC World", "https://www.cnbc.com/id/100727362/device/rss/rss.html"),
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/")
    ]
    terms = re.compile(r"gold|bitcoin|crypto|federal reserve|fed |inflation|treasury|yield|dollar|oil|central bank|rate|market|economy|tariff|war|geopolit", re.I)
    found = []
    seen = set()
    for source, url in feeds:
        try:
            root = ET.fromstring(fetch(url))
            for item in root.findall(".//item")[:12]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
                desc = re.sub(r"\s+", " ", desc).strip()
                if title and terms.search(title + " " + desc) and title.lower() not in seen:
                    found.append({"source": source, "title": title[:180], "link": link, "description": desc[:260]})
                    seen.add(title.lower())
        except Exception as exc:
            print("News feed unavailable:", source, type(exc).__name__)
    return found[:5]

def scene(title, paragraph):
    return [title, paragraph]

def build_topic():
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%d %B %Y, %H:%M UTC")
    assets = {}
    for name, symbol, range_, interval in [
        ("Gold futures (GC=F)", "GC=F", "5d", "1h"),
        ("Bitcoin (BTC-USD)", "BTC-USD", "5d", "1h"),
        ("US Dollar Index (DX-Y.NYB)", "DX-Y.NYB", "5d", "1h"),
        ("US 10-year yield (^TNX)", "^TNX", "5d", "1h"),
        ("S&P 500 (^GSPC)", "^GSPC", "5d", "1h"),
    ]:
        try:
            assets[name] = yahoo_chart(symbol, range_, interval)
        except Exception as exc:
            print("Market data unavailable:", name, type(exc).__name__)

    news = headline_items()
    gold = assets.get("Gold futures (GC=F)")
    btc = assets.get("Bitcoin (BTC-USD)")
    dollar = assets.get("US Dollar Index (DX=NYB)") or assets.get("US Dollar Index (DX-Y.NYB)")
    yield10 = assets.get("US 10-year yield (^TNX)")
    sp = assets.get("S&P 500 (^GSPC)")

    def describe(name, item):
        if not item:
            return f"{name}: live quote unavailable in this run; verify on a second source before trading."
        p = pct_change(item["closes"], 24)
        change = "change unavailable" if p is None else f"{p:+.2f}% over roughly the latest 24 hourly bars"
        return f"{name}: latest available quote {fmt_price(item['price'])} {item['currency']}; {change}. Data fetched at {stamp}."

    def levels(name, item):
        if not item or len(item["closes"]) < 10:
            return f"{name}: insufficient recent candles for reliable levels; do not invent levels."
        vals = item["closes"]
        recent = vals[-24:] if len(vals) >= 24 else vals
        low, high = min(recent), max(recent)
        current = vals[-1]
        momentum = pct_change(vals, min(6, len(vals)-1))
        mom = "mixed/unclear" if momentum is None else ("positive" if momentum > 0.25 else "negative" if momentum < -0.25 else "flat")
        rv = rsi(vals, min(14, len(vals)-1))
        rsi_text = "unavailable" if rv is None else f"{rv:.0f}"
        return (f"{name}: current {fmt_price(current)}; recent 24-bar range {fmt_price(low)}–{fmt_price(high)}; "
                f"short-term momentum {mom}; RSI estimate {rsi_text}. Treat range edges as observation zones, not guaranteed support/resistance.")

    # Spoken copy is written like a presenter, not a feed reader. Keep raw URLs out of TTS.
    news_text = []
    for n in news[:4]:
        news_text.append(f"According to {n['source']}, the headline to watch is: {n['title']}.")
    if not news_text:
        news_text = ["We could not verify a fresh market headline from the available feeds during this run. So we will not invent a news catalyst; check the original financial news sources before trading."]
    macro = []
    if dollar:
        macro.append(f"US dollar index is {fmt_price(dollar['price'])}; a strengthening dollar can pressure USD-priced gold and may tighten global financial conditions, but the relationship is not mechanical.")
    else:
        macro.append("US dollar index data was unavailable; verify dollar direction before drawing macro conclusions.")
    if yield10:
        macro.append(f"US 10-year Treasury yield proxy is {fmt_price(yield10['price'])}%; rising yields can raise the opportunity cost of holding non-yielding gold.")
    else:
        macro.append("US Treasury yield data was unavailable; verify current yields before making macro claims.")
    if sp:
        macro.append(f"S&P 500 proxy is {fmt_price(sp['price'])}; broad risk sentiment can affect Bitcoin, but correlation changes over time.")
    else:
        macro.append("Broad equity-market data was unavailable; do not assume Bitcoin is tracking equities.")

    scenes = [
        scene("GOLD & BITCOIN | GLOBAL MARKET BRIEFING", f"Good day, and welcome to your global markets briefing. It is {stamp}. I’m taking you through the latest available Gold and Bitcoin prices, the global forces moving markets, the headlines worth watching, and the levels traders may want to monitor. These are scenarios, not guaranteed signals."),
        scene("MARKET SNAPSHOT", "First, let’s check the scoreboard. " + describe("Gold futures", gold) + " Now to Bitcoin. " + describe("Bitcoin", btc) + " Remember, these are the latest quotes returned by the data feed, not a promise that the price is still unchanged."),
        scene("GLOBAL MACRO CHECK", "Now let’s zoom out to the bigger picture. " + " ".join(macro) + " These relationships can change quickly, so we look for confirmation rather than treating any single number as a trade signal."),
        scene("LATEST MARKET NEWS", "Here are the headlines on our radar. " + " ".join(news_text[:2]) + " A headline alone does not tell us the market’s direction. We need to check when it was published, what was already expected, and how prices react."),
        scene("MORE HEADLINES TO WATCH", "A couple more things to keep on the watchlist. " + (" ".join(news_text[2:4]) if len(news_text) > 2 else "No additional relevant headline was returned by the available feeds. We will not fill the gap with made-up news. Check publication times and original sources before acting.")),
        scene("GOLD TECHNICAL MAP", "Now, let’s put Gold under the microscope. " + levels("Gold futures", gold) + " Here is the plan, not a prediction: a bullish scenario needs price to break and hold above the recent range high. A bearish scenario needs a clean break and hold below the range low. If price whipsaws or a breakout fails, standing aside is a valid decision."),
        scene("BITCOIN TECHNICAL MAP", "Over to Bitcoin, where volatility can move quickly. " + levels("Bitcoin", btc) + " For a bullish scenario, look for a confirmed break and hold above the recent range high. For a bearish scenario, look for a break and hold below the recent range low. Avoid chasing a sudden candle; if the level fails, reassess rather than forcing a trade."),
        scene("TRADE PLAN & RISK RULES", "Before we wrap up, here is the risk checklist. Decide the entry trigger, the level that proves the idea wrong, the stop distance, position size and target before placing a trade. A two-to-one potential reward-to-risk ratio is not a guarantee of profit. Be extra careful around major economic releases, and avoid trading when spreads or volatility are abnormal. Never risk money needed for essentials, and do not use leverage you do not fully understand. That’s your Gold and Bitcoin briefing. Stay patient, verify the data, and trade only with a plan."),
    ]
    chart_data = {
        "gold": (gold["closes"][-24:] if gold and len(gold["closes"]) >= 2 else []),
        "bitcoin": (btc["closes"][-24:] if btc and len(btc["closes"]) >= 2 else []),
    }
    return {
        "title": f"Gold & Bitcoin Market Briefing | Global News & Trade Scenarios | {now.strftime('%d %b %Y')}",
        "slug": "gold-bitcoin-market-briefing",
        "scenes": scenes,
        "chart_data": chart_data,
        "market_stats": {
            "gold": (f"Gold: {fmt_price(gold['price'])} USD" if gold else "Gold quote unavailable"),
            "bitcoin": (f"BTC: {fmt_price(btc['price'])} USD" if btc else "BTC quote unavailable"),
        },
    }
