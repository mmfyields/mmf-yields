# Money market yield tracker

A small, self-updating record of the **7-day SEC yield** for a few money market funds, with a static web page to chart and query it.

| Ticker | Fund | Source |
|--------|------|--------|
| VMFXX | Vanguard Federal Money Market Fund | Vanguard fund page |
| VUSXX | Vanguard Treasury Money Market Fund | Vanguard fund page |
| VMSXX | Vanguard Municipal Money Market Fund | Vanguard fund page |
| TTTXX | BlackRock Treasury Trust Fund | BlackRock fund page |

Live site (GitHub Pages): https://mmfyields.github.io/mmf-yields/

## How it works

- **`.github/workflows/scrape.yml`** runs on a schedule (evenings/nights US Eastern). A quick check step decides whether new data is due; if not, it exits without installing a browser.
- **`scraper/scrape.py`** loads each fund page in headless Chromium (Playwright), finds the "7-day yield" label, and reads the nearby percentage and its **"as of" date**. Rows are keyed by that as-of date, so re-runs never create duplicates.
- **Freshness and retries:** the script works out the latest expected trading day (weekends and NYSE holidays skipped). If a fund's page still shows an older as-of date, it waits and retries (3 attempts, 10 minutes apart); later scheduled runs try again.
- **`docs/data/yields.csv`** is the data store (`date,fund,yield`, yield in percent, e.g. `3.78`). The workflow commits changes back to the repo.
- **`docs/index.html`** is the front end (Chart.js). It shows a data-quality banner (freshness, range of data, gaps), a chart and table with preset ranges (1 month, 6 months, YTD, 1 year, 5 years, max), and a custom date-range lookup.

## Data sources

**From 2026-09-28 onward (scraped).** Values come from each fund company's public fund page, captured by the scraper above. Each row's date is the "as of" date shown on the page.

**Before 2026-09-28 (imported).** History for VMFXX, VUSXX, VMSXX and TTTXX from **2019-12-31 through 2026-09-28** was taken from the "Money Market Optimizer Spreadsheet", a very useful Google Sheet shared on the Bogleheads forum: https://www.bogleheads.org/forum/viewtopic.php?t=401821. Vanguard data was fetched with `vanguardGetCachedPriceYieldHistory()`, and BlackRock data was fetched with `cloudGetCachedSevenDayYieldHistory()`.

- The source had a row for every calendar day. Weekend and NYSE-holiday rows, which repeat the previous day's value, were dropped to match the scraper's trading-day convention.
- One value was corrected: VMFXX on 2026-09-14 read 1.00% in the source, while the four prior trading days and the following two were all 3.63%. This was replaced with an estimated 3.63%.
- TTTXX on 2024-12-02 and 2024-12-03 was excluded and appears as a gap. The source showed about 3.98% on those days between values near 4.50% on either side, while VUSXX, a similar Treasury fund, stayed near 4.55%. These values are definitely suspicious, but not as convincing of a typo / data entry error as the previous anomaly, so they were left out rather than estimated.
- TTTXX showed a negative yield of -0.01% on 2020-09-30. While it's certainly possible this is accurate, as rates were near zero at the time, it still seems suspicious. In any case, this value was excluded to avoid blowing up the chart.

I have not independently verified the imported history, and its accuracy depends on the original spreadsheet.

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
