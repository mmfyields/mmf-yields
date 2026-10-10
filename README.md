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

- **`.github/workflows/scrape.yml`** runs every 30 minutes. A quick check step decides whether any fund is due for a new value; if not, it exits without installing a browser.
- **`scraper/scrape.py`** loads each fund page in headless Chromium (Playwright), finds the "7-day yield" label, and reads the nearby percentage and its **"as of" date**. Rows are keyed by that as-of date, so re-runs never create duplicates.
- **Freshness and retries:** The script attempts to pull yield information from fund pages around the time these pages have been observed to update their yield information in the past. These times are based on limited observation and may be further tuned as more observations are made. Attempts are made every 30 minutes until its as-of date reaches the latest posting day (weekdays that are not NYSE or US federal holidays). On weekends and holidays polling is throttled to about every 3 hours. Only the funds that are due get scraped.
- **Posting-time log:** every scrape attempt is appended to `logs/poll_log.csv` (time in US Eastern, fund, as-of date shown, and whether it was `new`, `unchanged` or an `error`). The first `new` row for an as-of date is when the scraper first saw it, and the previous poll bounds that time from below. Run `python scraper/summarize_log.py` to see when each fund's values typically appear, then adjust `RELEASE` in `scraper/scrape.py` to match.
- **`docs/data/yields.csv`** is the data store (`date,fund,yield`, yield in percent, e.g. `3.78`). The workflow commits changes back to the repo.
- **`docs/index.html`** is the front end (Chart.js). It shows a data-quality banner (freshness, range of data, gaps), a chart and table with preset ranges (1 month, 6 months, YTD, 1 year, 5 years, max), a custom date-range lookup, and an optional tax-equivalent view (see Known limitations).

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
- Posting times and holiday handling are assumptions. The scraper treats NYSE and US federal holidays as days with no new value. If a fund posts on one of those days, or skips another day, the scraper may poll for a value that never appears until the next expected date takes over.
- The front end's "gaps" indicator counts every missing weekday, including market holidays.
- Tax-equivalent yields (optional, in the front end) are simplified estimates. With your federal and state marginal rates, VUSXX and TTTXX are shown as yield ÷ (1 − state rate), and VMSXX (treated as out-of-state) as yield ÷ (1 − federal rate). VMFXX is treated as fully taxable and left as reported. The calculation ignores the state-tax deduction cap, AMT, and any state-specific rules (some states only exempt fund income above a threshold), applies today's rates to all dates, and is not tax advice. Rates entered are kept only in your browser.
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
