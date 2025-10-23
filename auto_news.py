import os, re, json, time, requests, yfinance as yf
from datetime import datetime, timezone

# ===== الإعدادات من المتغيرات البيئية =====
TG_TOKEN   = os.getenv("TG_TOKEN")
TG_CHAT    = os.getenv("TG_CHAT")
TV_WL_ID   = os.getenv("TV_WL_ID", "205726241")  # غيّرها ببيئتك إذا لزم
TV_COOKIES = os.getenv("TV_COOKIES")             # لازم تكون موجودة

def tg_send(text: str):
    if not (TG_TOKEN and TG_CHAT):
        print("⚠️ TG_TOKEN/TG_CHAT مفقودة"); return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True},
            timeout=20
        )
    except Exception as e:
        print("Telegram error:", e)

def human(ts):
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""

def get_symbols_from_page(wl_id: str):
    if not TV_COOKIES:
        raise RuntimeError("TV_COOKIES فارغة")
    url = f"https://www.tradingview.com/watchlists/{wl_id}/"
    r = requests.get(url, headers={
        "user-agent": "Mozilla/5.0",
        "cookie": TV_COOKIES,
        "accept": "text/html,application/xhtml+xml",
        "accept-language": "en-US,en;q=0.9,ar;q=0.8",
    }, timeout=25)
    print("GET", url, "HTTP", r.status_code)
    r.raise_for_status()
    html = r.text

    # 1) NEXT_DATA
    m = re.search(r'id="__NEXT_DATA__"[^>]*>\s*({.*?})\s*</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            js = json.dumps(data)
            found = re.findall(r'"symbol"\s*:\s*"([A-Z0-9_:-]+)"', js)
            out = []
            for s in found:
                sym = s.split(":")[-1]
                if sym and sym not in out:
                    out.append(sym)
            if out:
                return out
        except Exception:
            pass

    # 2) INITIAL_STATE (fallback)
    m = re.search(r'__INITIAL_STATE__\s*=\s*({.*?});\s*</script>', html, re.S)
    if m:
        try:
            state = json.loads(m.group(1))
            paths = [
                ("watchlists","entities","lists","byId"),
                ("watchlists","entities","byId"),
                ("watchlists","lists","byId"),
            ]
            for path in paths:
                obj = state
                ok = True
                for k in path:
                    obj = obj.get(k) if isinstance(obj, dict) else None
                    if obj is None:
                        ok = False
                        break
                if ok and wl_id in obj:
                    wl = obj[wl_id]
                    syms = []
                    for it in wl.get("symbols", []):
                        s = (it.get("symbol") or it.get("symbol_name") or "").strip()
                        if ":" in s: s = s.split(":")[-1]
                        if s and s not in syms:
                            syms.append(s)
                    if syms:
                        return syms
        except Exception:
            pass
    raise RuntimeError("لم أجد رموز داخل الصفحة")

def fetch_news(sym: str):
    try:
        t = yf.Ticker(sym)
        items = t.news or []
        out = []
        for n in items[:3]:
            title = n.get("title","")
            link  = n.get("link") or n.get("url") or ""
            ts    = n.get("providerPublishTime") or 0
            out.append((title, link, human(ts)))
        return out
    except Exception as e:
        print("yfinance error", sym, e); return []

def run_once():
    syms = get_symbols_from_page(TV_WL_ID)
    print("Symbols:", len(syms), syms[:10])
    for sym in syms:
        items = fetch_news(sym)
        if not items:
            time.sleep(0.3); continue
        lines = [f"📰 {sym}"]
        for t,l,ts in items:
            part = f"• {t}\n{l}"
            if ts: part += f"\n🕒 {ts}"
            lines.append(part)
        tg_send("\n\n".join(lines))
        time.sleep(0.7)

if __name__ == "__main__":
       while True:
        try:
            run_once()
        except Exception as e:
            print("⚠️ Error:", e)
        time.sleep(600)  # كل 10 دقايق
PY
