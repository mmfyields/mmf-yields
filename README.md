# Money market yield tracker

A small, free, self-updating record of the **7-day SEC yield** for a few money market funds, with a static web page to chart and query it.

| Ticker | Fund | Source |
|--------|------|--------|
| VMFXX | Vanguard Federal Money Market Fund | Vanguard fund page |
| VUSXX | Vanguard Treasury Money Market Fund | Vanguard fund page |
| VMSXX | Vanguard Municipal Money Market Fund | Vanguard fund page |
| TTTXX | BlackRock Treasury Trust Fund | BlackRock Cash site |

Vanguard removed the price-history tool that showed past 7-day SEC yields, so this project keeps its own record.

Live site (GitHub Pages): https://mmfyields.github.io/mmf-yields/

## How it works

- **`.github/workflows/scrape.yml`** runs on a schedule (evenings/nights US Eastern). A quick check step decides whether new data is due; if not, it exits without installing a browser.
- **`scraper/scrape.py`** loads each fund page in headless Chromium (Playwright), finds the "7-day yield" label, and reads the nearby percentage and its **"as of" date**. Rows are keyed by that as-of date, so re-runs never create duplicates.
- **Freshness and retries:** the script works out the latest expected trading day (weekends and NYSE holidays skipped). If a fund's page still shows an older as-of date, it waits and retries (3 attempts, 10 minutes apart); later scheduled runs try again.
- **`docs/data/yields.csv`** is the data store (`date,fund,yield`, yield in percent, e.g. `3.78`). The workflow commits changes back to the repo.
- **`docs/index.html`** is the front end (Chart.js). It shows a data-quality banner (freshness, range of data, gaps), a chart and table with preset ranges (1 month, 6 months, YTD, 1 year, 5 years, max), and a custom date-range lookup.

## Data sources

**From 2026-09-28 onward (scraped).** Values come from each fund company's public fund page, captured by the scraper above. Each row's date is the "as of" date shown on the page.

**Before 2026-09-28 (Vanguard funds only, imported).** History for VMFXX, VUSXX and VMSXX from **2019-12-31 through 2026-09-28** was taken from the "Money Market Optimizer Spreadsheet", a Google Sheet shared on the Bogleheads forum: https://www.bogleheads.org/forum/viewtopic.php?t=401821. It was converted to this project's format (`history/vanguard-history-2019-2026.csv`) as follows:

- Decimal values were multiplied by 100 to give percentages (`0.0378` becomes `3.78`), rounded to two decimals.
- The source has a row for every calendar day. Weekend and NYSE-holiday rows, which repeat the previous day's value, were dropped to match the scraper's trading-day convention.
- One value was corrected: VMFXX on 2026-09-14 read 1.00% in the source, an apparent data-entry error, between neighboring days at 3.63% (the four prior trading days and the following two are all 3.63%). It was replaced with 3.63%. This is an estimate, not an observed value.
- The 2026-09-28 values match the scraped values.
- TTTXX has no imported history; its record starts with the first scrape.

I have not independently verified the imported history against Vanguard's records, and its accuracy depends on the original spreadsheet.

To merge another file in the same format without overwriting existing rows:

```
python scraper/merge_history.py path/to/history.csv
```

## Setup

1. Push this repo to GitHub (public repos get free Actions minutes).
2. **Settings > Pages:** deploy from branch `main`, folder `/docs`.
3. **Settings > Actions > General > Workflow permissions:** allow read and write.
4. **Actions:** run "Scrape money market yields" once manually to test.

To add a fund, add a ticker and page URL to `FUNDS` in `scraper/scrape.py` and to `FUNDS`/`COLORS` in `docs/index.html`. Check the debug output on the first run, since each site words and orders its yield differently.

## Known limitations

- Scrapers break when a site changes its layout. Failed runs show as errors in Actions and print debug output.
- The holiday calendar is NYSE's. Money market funds follow the Federal Reserve/bond market calendar, which differs on a few days a year (for example Columbus Day and Veterans Day), so the scraper may retry on those days for a number that never appears.
- The front end's "gaps" indicator counts every missing weekday, including market holidays.
- Different fund companies may calculate yields slightly differently, so compare across companies with care.
- GitHub may pause scheduled workflows in a repo with no activity for 60 days; the daily data commits normally prevent this.

## Disclaimer

This project is for personal, informational and educational use. It is **not** investment, tax or legal advice, and nothing here is a recommendation to buy, sell or hold any security.

- **No guarantee of accuracy.** Data is scraped from third-party websites and, for older dates, compiled from a community spreadsheet. It may be delayed, incomplete, mis-parsed or wrong. Check anything important against the fund company's official materials (fund pages, prospectus, statements).
- **Yields are not predictions.** A 7-day SEC yield is a backward-looking, annualized figure and changes daily. Past yields do not indicate future results. Money market funds are not FDIC-insured and can lose money.
- **No affiliation.** This project is not affiliated with, endorsed by or sponsored by Vanguard, BlackRock or any other company. Names and tickers are trademarks of their owners and appear only to identify the funds.
- **Website terms.** Automated access may be restricted by a site's terms of use. The scraper is designed for light use (a few page loads per day). You are responsible for making sure your use complies with those terms and applicable law.
- The software is provided "as is" without warranty of any kind (see the license).

## License

Code is released under the [MIT License](LICENSE). The yield figures are factual data published by third parties and are not covered by this license; no rights in the underlying data or in the imported spreadsheet are claimed.
