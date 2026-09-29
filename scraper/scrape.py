"""Scrape 7-day SEC yields for money market funds into docs/data/yields.csv.
Usage: python scraper/scrape.py [--check]   (--check only reports whether new data is due)"""
import csv, os, re, sys, time, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import holidays

VG = "https://investor.vanguard.com/investment-products/mutual-funds/profile/"
FUNDS = {  # ticker -> page URL (an empty URL skips that fund)
    "VMFXX": VG + "vmfxx",
    "VUSXX": VG + "vusxx",
    "VMSXX": VG + "vmsxx",
    "TTTXX": "https://www.blackrock.com/cash/en-us/products/282697/blf-treasury-trust-fund",
    "FIGXX": "https://fundresearch.fidelity.com/mutual-funds/summary/316175108",
}
CSV = Path(__file__).resolve().parent.parent / "docs" / "data" / "yields.csv"
ET, NYSE = ZoneInfo("America/New_York"), holidays.NYSE()
PUBLISH_HOUR_ET = 18      # don't expect today's number before this hour (ET)
ATTEMPTS, WAIT_SEC = 3, 600

MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
LABEL = re.compile(r"7[- ]?day\s+(?:SEC\s+)?yield", re.I)      # "7 day SEC yield", "7 Day SEC Yield", "7-Day Yield"
PCT = re.compile(r"([+-]?\d+\.\d+)\s*%")
DATE = re.compile(rf"(\d{{1,2}})/(\d{{1,2}})/(\d{{4}})|({MONTH})\.?\s+(\d{{1,2}}),\s*(\d{{4}})|(\d{{1,2}})[- ]({MONTH})[- ](\d{{4}})", re.I)
# Formats seen: "3.78% ... as of 09/28/2026" (Vanguard), "as of 28-Sep-2026 3.72%" (BlackRock), "AS OF 09/28/2026 +3.71%" (Fidelity)

def month_num(name): return ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"].index(name[:3].lower()) + 1

def extract(text):
    """Return (iso_date, yield_str) from the first yield label followed closely by a % value and a date (either order)."""
    for m in LABEL.finditer(text):
        w = text[m.end(): m.end() + 200]
        pct, d = PCT.search(w), DATE.search(w)
        if not (pct and d): continue
        g = d.groups()
        if g[0]: mo, da, yr = int(g[0]), int(g[1]), int(g[2])
        elif g[3]: mo, da, yr = month_num(g[3]), int(g[4]), int(g[5])
        else: mo, da, yr = month_num(g[7]), int(g[6]), int(g[8])
        return f"{yr:04d}-{mo:02d}-{da:02d}", pct.group(1).lstrip("+")
    return None

TEXT_JS = """() => { const out=[]; const skip=['SCRIPT','STYLE','NOSCRIPT','TEMPLATE'];
  const walk=n=>{ if(n.nodeType===3) out.push(n.textContent);
    else if(n.nodeType===1 && skip.includes(n.tagName)) return;
    else { if(n.shadowRoot) walk(n.shadowRoot); n.childNodes.forEach(walk); } };
  walk(document.body); return out.join(' '); }"""

def trading_day(d): return d.weekday() < 5 and d not in NYSE

def expected_date():
    now = dt.datetime.now(ET)
    d = now.date() if now.hour >= PUBLISH_HOUR_ET else now.date() - dt.timedelta(days=1)
    while not trading_day(d): d -= dt.timedelta(days=1)
    return d.isoformat()

def load():
    if not CSV.exists(): return {}
    with open(CSV, newline="") as f:
        return {(r["date"], r["fund"]): r["yield"] for r in csv.DictReader(f)}

def save(data):
    with open(CSV, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "fund", "yield"])
        for (d, fund), y in sorted(data.items()): w.writerow([d, fund, y])

def stale_funds(data, exp):
    return [f for f, u in FUNDS.items() if u and max([d for d, x in data if x == f], default="") < exp]

def scrape_fund(page, fund):
    bodies = {}
    def on_resp(r):
        if "json" in (r.headers.get("content-type") or "") and re.search(r"yield|price|fund|nav", r.url, re.I):
            try: bodies[r.url] = r.text()
            except Exception: pass
    page.on("response", on_resp)
    try:
        page.goto(FUNDS[fund], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000)
        text = re.sub(r"\s+", " ", page.evaluate(TEXT_JS))
    finally:
        page.remove_listener("response", on_resp)
    found = extract(text)
    if not found:
        print(f"--- DEBUG {fund}: title={page.title()!r} url={page.url} visible chars={len(text)}")
        for hit in list(re.finditer(r"yield|as of", text, re.I))[:8]:
            print("  ...", text[max(0, hit.start() - 100):hit.end() + 150])
        for u, b in list(bodies.items())[:5]: print(f"--- API {u}\n{b[:2000]}")
        raise RuntimeError(f"{fund}: couldn't find 7-day SEC yield / as-of date")
    return found

def main():
    exp, data = expected_date(), load()
    todo = stale_funds(data, exp)
    if "--check" in sys.argv:
        out = os.environ.get("GITHUB_OUTPUT")
        line = f"need={'true' if todo else 'false'}\n"
        (open(out, "a").write(line) if out else print(line, end=""))
        return
    for f, u in FUNDS.items():
        if not u: print(f"{f}: skipped (no URL configured)")
    if not todo: print("Up to date through", exp); return
    from playwright.sync_api import sync_playwright
    broken = set()   # funds whose page couldn't be parsed; don't wait/retry on these
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36")
        for attempt in range(1, ATTEMPTS + 1):
            for fund in todo:
                try:
                    d, y = scrape_fund(page, fund)
                    data[(d, fund)] = y; print(f"{fund}: {y}% as of {d}")
                except Exception as e:
                    print(e, file=sys.stderr); broken.add(fund)
            save(data)
            todo = [f for f in stale_funds(data, exp) if f not in broken]
            if not todo: break
            if attempt < ATTEMPTS:
                print(f"Still waiting for {exp}: {todo}; retrying in {WAIT_SEC // 60} min"); time.sleep(WAIT_SEC)
        browser.close()
    if todo: print(f"Not yet published for {exp}: {todo} (next scheduled run will retry)")
    if broken: sys.exit(1)

if __name__ == "__main__": main()
