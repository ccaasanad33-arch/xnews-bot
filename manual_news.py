#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time, sqlite3, requests
from datetime import datetime, timezone
from typing import List
import yfinance as yf

TG_TOKEN = os.getenv("TG_TOKEN")          # توكن بوت تيليجرام
TG_CHAT  = os.getenv("TG_CHAT")           # آي دي القناة/الجروب/الشخص
DBFILE   = os.getenv("DB_FILE", os.path.expanduser("~/xnews-bot/sent.db"))

# الرموز: إمّا من متغير بيئة SYMBOLS=TSLA,AAPL,NVDA أو عدّل القائمة هنا
SYMBOLS_ENV = os.getenv("SYMBOLS", "").strip()
if SYMBOLS_ENV:
    SYMBOLS: List[str] = [s.strip().upper() for s in SYMBOLS_ENV.split(",") if s.strip()]
else:
    SYMBOLS: List[str] = ["TSLA","AAPL","MSFT","NVDA","XAUUSD"]

MAX_NEWS_PER_SYMBOL = 3  # عدد الأخبار لكل رمز في كل دورة

def log(*args):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}]", *args, flush=True)

def db_init():
    os.makedirs(os.path.dirname(DBFILE), exist_ok=True)
    con = sqlite3.connect(DBFILE)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sent (
            symbol TEXT NOT NULL,
            news_id TEXT NOT NULL,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(symbol, news_id)
        )
    """)
    con.commit()
    return con

def is_sent(con, symbol: str, news_id: str) -> bool:
    cur = con.cursor()
    cur.execute("SELECT 1 FROM sent WHERE symbol=? AND news_id=? LIMIT 1", (symbol, news_id))
    return cur.fetchone() is not None

def mark_sent(con, symbol: str, news_id: str):
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO sent(symbol, news_id) VALUES(?, ?)", (symbol, news_id))
    con.commit()

def tg_send(text: str) -> bool:
    if not TG_TOKEN or not TG_CHAT:
        log("⚠️ TG env missing (TG_TOKEN/TG_CHAT)"); return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True},
            timeout=20
        )
        ok = r.ok and r.json().get("ok", False)
        if not ok:
            log("⚠️ Telegram error:", r.text[:200])
        return ok
    except Exception as e:
        log("⚠️ Telegram exception:", e)
        return False

def fetch_news(symbol: str):
    try:
        t = yf.Ticker(symbol)
        return t.news or []
    except Exception as e:
        log(f"⚠️ yfinance error for {symbol}:", e)
        return []

def fmt_time(ts: int) -> str:
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ""

def run_once(con):
    for sym in SYMBOLS:
        log(f"🔎 {sym}: جلب الأخبار…")
        items = fetch_news(sym)[:MAX_NEWS_PER_SYMBOL]
        if not items:
            time.sleep(0.2); continue
        for it in items:
            title = it.get("title") or ""
            link  = it.get("link") or it.get("url") or ""
            pubts = it.get("providerPublishTime") or 0
            uuid  = it.get("uuid") or (title + link)[:64]
            if not uuid or is_sent(con, sym, uuid): 
                continue
            lines = [f"📰 {sym}\n{title}"]
            if pubts: lines.append(f"🕘 {fmt_time(pubts)}")
            if link:  lines.append(link)
            if tg_send("\n".join(lines)):
                mark_sent(con, sym, uuid)
                time.sleep(0.4)
        time.sleep(0.3)

def main():
    log("✅ بدأ التشغيل (manual, بدون watchlist).")
    log("الرموز:", ", ".join(SYMBOLS))
    con = db_init()
    while True:
        try:
            run_once(con)
        except Exception as e:
            log("⚠️ Error:", e)
        log("⏳ انتظار 10 دقایق…")
        time.sleep(600)

if __name__ == "__main__":
    main()
