"""Scrape 7-day SEC yields for Vanguard money market funds into docs/data/yields.csv.
Usage: python scraper/scrape.py [--check]   (--check only reports whether new data is due)"""
import csv, os, re, sys, time, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import holidays

FUNDS = ["VMFXX", "VUSXX", "VMSXX"]
URL = "https://investor.vanguard.com/investment-products/mutual-funds/profile/{}"
CSV = Path(__file__).resolve().parent.parent / "docs" / "data" / "yields.csv"
ET, NYSE = ZoneInfo("America/New_York"), holidays.NYSE()
PUBLISH_HOUR_ET = 18      # don't expect today's number before this hour (ET)
ATTEMPTS, WAIT_SEC = 3, 600

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
    return [f for f in FUNDS if max([d for d, x in data if x == f], default="") < exp]

RX = re.compile(r"7-day SEC yield.{0,400}?(\d+\.\d+)\s*%.{0,400}?as of\s*(\d{1,2})/(\d{1,2})/(\d{4})", re.I | re.S)

TEXT_JS = """() => { const out=[]; const walk=n=>{ if(n.nodeType===3) out.push(n.textContent);
  else { if(n.shadowRoot) walk(n.shadowRoot); n.childNodes.forEach(walk); } }; walk(document.body); return out.join(' '); }"""

def scrape_fund(page, fund):
    seen = []
    def on_resp(r):
        if "json" in (r.headers.get("content-type") or ""): seen.append(r.url)
    page.on("response", on_resp)
    try:
        page.goto(URL.format(fund), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000)
        text = re.sub(r"\s+", " ", page.evaluate(TEXT_JS))
    finally:
        page.remove_listener("response", on_resp)
    m = RX.search(text)
    if not m:
        print(f"--- DEBUG {fund}: title={page.title()!r} url={page.url} chars={len(text)}")
        print("Text start:", text[:500])
        for hit in list(re.finditer(r"SEC|yield", text, re.I))[:6]:
            print("  ...", text[max(0, hit.start() - 80):hit.end() + 120])
        print("JSON responses:", *seen[:25], sep="\n  ")
        raise RuntimeError(f"{fund}: couldn't find 7-day SEC yield / as-of date")
    mo, da, yr = int(m[2]), int(m[3]), int(m[4])
    return f"{yr:04d}-{mo:02d}-{da:02d}", m[1]

def main():
    exp, data = expected_date(), load()
    todo = stale_funds(data, exp)
    if "--check" in sys.argv:
        out = os.environ.get("GITHUB_OUTPUT")
        line = f"need={'true' if todo else 'false'}\n"
        (open(out, "a").write(line) if out else print(line, end=""))
        return
    if not todo: print("Up to date through", exp); return
    from playwright.sync_api import sync_playwright
    failed = False
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36")
        for attempt in range(1, ATTEMPTS + 1):
            for fund in todo:
                try:
                    d, y = scrape_fund(page, fund)
                    data[(d, fund)] = y; print(f"{fund}: {y}% as of {d}")
                except Exception as e:
                    print(e, file=sys.stderr); failed = True
            save(data)
            todo = stale_funds(data, exp)
            if not todo: break
            if attempt < ATTEMPTS:
                print(f"Still waiting for {exp}: {todo}; retrying in {WAIT_SEC // 60} min"); time.sleep(WAIT_SEC)
        browser.close()
    if todo: print(f"Not yet published for {exp}: {todo} (next scheduled run will retry)")
    if failed and todo: sys.exit(1)

if __name__ == "__main__": main()
