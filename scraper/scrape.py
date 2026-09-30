"""Scrape 7-day SEC yields for money market funds into docs/data/yields.csv.

Each fund has its own expected posting time. A run only scrapes the funds whose latest
as-of date is behind what should be published by now, so the workflow can poll every
30 minutes cheaply and keep trying until the new value appears.

Usage: python scraper/scrape.py [--check | --all]
  --check  report (need=true/false) whether any fund is due; no browser needed
  --all    scrape every fund now, regardless of schedule (used for manual runs)"""
import csv, os, re, sys, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import holidays

VG = "https://investor.vanguard.com/investment-products/mutual-funds/profile/"
FUNDS = {  # ticker -> page URL (an empty URL skips that fund)
    "VMFXX": VG + "vmfxx",
    "VUSXX": VG + "vusxx",
    "VMSXX": VG + "vmsxx",
    "TTTXX": "https://www.blackrock.com/cash/en-us/products/282697/blf-treasury-trust-fund",
}
# When polling starts for a given as-of date D: (calendar days after D, hour, minute) in US Eastern.
# Observed: BlackRock posts D's value the evening of D (~8-9 pm); Vanguard posts it the next morning (~3-4 am).
# Start a little earlier than observed so a few extra attempts catch the first appearance.
RELEASE = {"VMFXX": (1, 2, 30), "VUSXX": (1, 2, 30), "VMSXX": (1, 2, 30), "TTTXX": (0, 19, 30)}
OFFDAY_EVERY_HOURS = 3    # on weekends/holidays, poll only every few hours (a value may or may not post)

CSV = Path(__file__).resolve().parent.parent / "docs" / "data" / "yields.csv"
LOG = Path(__file__).resolve().parent.parent / "logs" / "poll_log.csv"   # one row per fund per scrape attempt
ET = ZoneInfo("America/New_York")
NYSE, USFED = holidays.NYSE(), holidays.US()

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

def posting_day(d):
    """Days a fund publishes a new as-of value: weekdays that are neither NYSE nor US federal holidays."""
    return d.weekday() < 5 and d not in NYSE and d not in USFED

def release_dt(fund, d):
    days, h, m = RELEASE[fund]
    return dt.datetime.combine(d + dt.timedelta(days=days), dt.time(h, m), tzinfo=ET)

def expected_date(fund, now):
    """Latest as-of date that should be posted for this fund by `now`."""
    d = now.date()
    for _ in range(14):
        if posting_day(d) and release_dt(fund, d) <= now: return d
        d -= dt.timedelta(days=1)

def latest(data, fund): return max([d for d, f in data if f == fund], default="")

def due_funds(data, now):
    due = [f for f, u in FUNDS.items() if u and (e := expected_date(f, now)) and latest(data, f) < e.isoformat()]
    if due and not posting_day(now.date()) and not (now.hour % OFFDAY_EVERY_HOURS == 0 and now.minute < 30):
        return []     # weekend/holiday: throttle polling
    return due

def load():
    if not CSV.exists(): return {}
    with open(CSV, newline="") as f:
        return {(r["date"], r["fund"]): r["yield"] for r in csv.DictReader(f)}

def save(data):
    with open(CSV, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["date", "fund", "yield"])
        for (d, fund), y in sorted(data.items()): w.writerow([d, fund, y])

def scrape_fund(page, fund):
    bodies, status = {}, None
    def on_resp(r):
        if "json" in (r.headers.get("content-type") or "") and re.search(r"yield|price|fund|nav", r.url, re.I):
            try: bodies[r.url] = r.text()
            except Exception: pass
    page.on("response", on_resp)
    found, text = None, ""
    try:
        try:
            status = page.goto(FUNDS[fund], wait_until="commit", timeout=60000).status
        except Exception as e:
            raise RuntimeError(f"{fund}: no response from {FUNDS[fund]} within 60s ({type(e).__name__}); "
                               "the site may be blocking GitHub's servers") from None
        for _ in range(15):                     # poll up to ~45s for the page to render the yield
            page.wait_for_timeout(3000)
            try: text = re.sub(r"\s+", " ", page.evaluate(TEXT_JS))
            except Exception: continue          # page still navigating / body not ready
            found = extract(text)
            if found: break
    finally:
        page.remove_listener("response", on_resp)
    if not found:
        print(f"--- DEBUG {fund}: http={status} title={page.title()!r} url={page.url} visible chars={len(text)}")
        print("Text start:", text[:400])
        for hit in list(re.finditer(r"yield|as of", text, re.I))[:8]:
            print("  ...", text[max(0, hit.start() - 100):hit.end() + 150])
        for u, b in list(bodies.items())[:5]: print(f"--- API {u}\n{b[:2000]}")
        raise RuntimeError(f"{fund}: couldn't find 7-day yield / as-of date")
    return found

def log_poll(fund, as_of, status, trigger, when):
    """Append one poll result. status: new (as-of date never seen before) | unchanged | error."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new_file = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if new_file: w.writerow(["polled_at_et", "fund", "as_of", "status", "trigger"])
        w.writerow([when.isoformat(timespec="seconds"), fund, as_of, status, trigger])

def main():
    now, data = dt.datetime.now(ET), load()
    if "--check" in sys.argv:
        due = due_funds(data, now)
        print(f"{now:%Y-%m-%d %H:%M %Z} due: {due or 'nothing'}")
        out = os.environ.get("GITHUB_OUTPUT")
        if out: open(out, "a").write(f"need={'true' if due else 'false'}\n")
        return
    todo = [f for f, u in FUNDS.items() if u] if "--all" in sys.argv else due_funds(data, now)
    if not todo: print("Nothing due at", now.strftime("%Y-%m-%d %H:%M %Z")); return
    from playwright.sync_api import sync_playwright
    broken, trigger = [], ("manual" if "--all" in sys.argv else "schedule")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36")
        for fund in todo:
            try:
                d, y = scrape_fund(page, fund)
                log_poll(fund, d, "unchanged" if (d, fund) in data else "new", trigger, dt.datetime.now(ET))
                data[(d, fund)] = y
                exp = expected_date(fund, now)
                note = "" if exp is None or d >= exp.isoformat() else f" (still waiting for {exp})"
                print(f"{fund}: {y}% as of {d}{note}")
            except Exception as e:
                print(e, file=sys.stderr); broken.append(fund)
                log_poll(fund, "", "error", trigger, dt.datetime.now(ET))
        browser.close()
    save(data)
    if broken: sys.exit(1)   # parse failures only; "not posted yet" is normal and exits 0

if __name__ == "__main__": main()
