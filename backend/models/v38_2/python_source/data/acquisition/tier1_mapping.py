"""Forex Factory + ALFRED hybrid economic-calendar acquisition.

Acquires USD Tier-1 events from Forex Factory historical calendar pages
(2018-01-01 → latest), cross-checks actual/previous values against ALFRED
(FRED) vintage data using realtime_start/realtime_end (vintage_date), and
produces a PIT audit.

Design:
  - FF provides: event timestamp, currency, impact, event name, actual,
    forecast (consensus), previous. Historical pages are fetched week-by-week.
  - ALFRED provides: genuine point-in-time vintage indicator values (the value
    as first published, before later revisions) via the fredgraph CSV endpoint
    with vintage_date. No API key needed for the CSV endpoint.
  - Cross-check: FF actual/previous vs ALFRED vintage values. If they match,
    the actual is PIT-verified (proven as-of-T). If they differ, FF was revised.
  - FF forecasts are RETAINED but labeled PIT_UNVERIFIED unless a pre-release
    forecast timestamp can be demonstrated (FF does not expose one).

No fabrication: only values shown by FF/ALFRED are recorded. Missing fields
stay missing. No inference, no interpolation, no substitution.
"""
from __future__ import annotations

# Tier-1 USD event definitions and FF→FRED series mapping.
# Each entry: (ff_event_patterns, fred_series_id, fred_series_name, category)
# ff_event_patterns: substrings to match against FF event names (case-insensitive).
# fred_series_id: the FRED/ALFRED series for vintage cross-check, or None if
#                 no indicator series exists (e.g. FOMC Minutes is an event, not
#                 an indicator).

TIER1_EVENTS = [
    # NOTE: order matters — more specific patterns must come first.
    # "Core CPI m/m" before "CPI m/m" so Core CPI doesn't match the CPI pattern.
    {
        "name": "Core CPI m/m",
        "ff_patterns": ["Core CPI m/m"],
        "fred_series": "CPILFESL",
        "fred_name": "Consumer Price Index: All Urban Consumers (Less Food & Energy)",
        "fred_units": "Index",
        "category": "inflation",
        "directionality": "inverse",
        "freq": "monthly",
        "is_pct": True,
        "pct_period": "mom",
    },
    {
        "name": "CPI m/m",
        "ff_patterns": ["CPI m/m"],
        "fred_series": "CPIAUCSL",
        "fred_name": "Consumer Price Index: All Urban Consumers (All Items)",
        "fred_units": "Index",
        "category": "inflation",
        "directionality": "inverse",
        "freq": "monthly",
        "is_pct": True,
        "pct_period": "mom",
    },
    {
        "name": "Non-Farm Payrolls",
        "ff_patterns": ["Non-Farm Employment Change", "Non-Farm Payrolls", "NFP"],
        "fred_series": "PAYEMS",
        "fred_name": "All Employees, Total Nonfarm",
        "fred_units": "Thousands of Persons",
        "category": "payrolls",
        "directionality": "inverse",
        "freq": "monthly",
        "is_pct": False,
        "pct_period": None,
    },
    {
        "name": "Unemployment Rate",
        "ff_patterns": ["Unemployment Rate"],
        "fred_series": "UNRATE",
        "fred_name": "Civilian Unemployment Rate",
        "fred_units": "Percent",
        "category": "unemployment",
        "directionality": "direct",
        "freq": "monthly",
        "is_pct": True,
        "pct_period": None,
    },
    {
        "name": "Average Hourly Earnings m/m",
        "ff_patterns": ["Average Hourly Earnings m/m", "AHE m/m"],
        "fred_series": "AHETPI",
        "fred_name": "Average Hourly Earnings of Production and Nonsupervisory Employees: Total Private",
        "fred_units": "Dollars per Hour",
        "category": "wages",
        "directionality": "inverse",
        "freq": "monthly",
        "is_pct": True,
        "pct_period": "mom",
    },
    {
        "name": "FOMC Rate Decision",
        "ff_patterns": ["Federal Funds Rate", "FOMC Rate Decision", "Fed Funds Rate"],
        "fred_series": "FEDFUNDS",
        "fred_name": "Effective Federal Funds Rate (monthly, lagged)",
        "fred_units": "Percent",
        "category": "central_bank",
        "directionality": "inverse",
        "freq": "monthly",
        "is_pct": True,
        "pct_period": None,
    },
    {
        "name": "FOMC Meeting Minutes",
        "ff_patterns": ["FOMC Meeting Minutes", "FOMC Minutes"],
        "fred_series": None,
        "fred_name": "(no FRED indicator series — event/text release only)",
        "fred_units": "",
        "category": "cb_communication",
        "directionality": "direct",
        "freq": "8peryear",
        "is_pct": False,
        "pct_period": None,
    },
    {
        "name": "GDP",
        "ff_patterns": ["Advance GDP", "Prelim GDP", "Final GDP", "GDP"],
        "fred_series": "A191RL1Q225SBEA",
        "fred_name": "Real Gross Domestic Product (quarterly, annualized % change)",
        "fred_units": "Percent",
        "category": "gdp",
        "directionality": "inverse",
        "freq": "quarterly",
        "is_pct": True,
        "pct_period": "qoq_ann",
    },
    {
        "name": "Core Retail Sales m/m",
        "ff_patterns": ["Core Retail Sales m/m", "Core Retail Sales"],
        "fred_series": "RSAFS",
        "fred_name": "Retail Sales: Retail Trade (monthly)",
        "fred_units": "Millions of Dollars",
        "category": "retail_sales",
        "directionality": "inverse",
        "freq": "monthly",
        "is_pct": True,
        "pct_period": "mom",
    },
    {
        "name": "Retail Sales m/m",
        "ff_patterns": ["Retail Sales m/m", "Retail Sales"],
        "fred_series": "RSAFS",
        "fred_name": "Retail Sales: Retail Trade (monthly)",
        "fred_units": "Millions of Dollars",
        "category": "retail_sales",
        "directionality": "inverse",
        "freq": "monthly",
        "is_pct": True,
        "pct_period": "mom",
    },
    {
        "name": "Core PPI m/m",
        "ff_patterns": ["Core PPI m/m"],
        "fred_series": "WPSFD49202",
        "fred_name": "Producer Price Index: Final Demand Less Foods and Energy",
        "fred_units": "Index",
        "category": "ppi",
        "directionality": "inverse",
        "freq": "monthly",
        "is_pct": True,
        "pct_period": "mom",
    },
    {
        "name": "PPI m/m",
        "ff_patterns": ["PPI m/m"],
        "fred_series": "WPSFD4111",
        "fred_name": "Producer Price Index: Final Demand",
        "fred_units": "Index",
        "category": "ppi",
        "directionality": "inverse",
        "freq": "monthly",
        "is_pct": True,
        "pct_period": "mom",
    },
]


def match_tier1(event_name: str) -> dict | None:
    """Match an FF event name to a Tier-1 event definition. Returns the dict or None.

    Matching priority: more specific patterns first (e.g., "Core CPI" before "CPI").
    Excludes ADP Non-Farm (separate event from NFP).
    """
    name_lower = event_name.lower().strip()
    # Exclude ADP — it's a separate employment report, not the official NFP
    if "adp" in name_lower:
        return None
    for ev in TIER1_EVENTS:
        for pat in ev["ff_patterns"]:
            if pat.lower() in name_lower:
                return ev
    return None
