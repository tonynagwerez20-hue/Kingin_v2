# Trading on MT5 - Simplified Setup Guide

If you are executing trades through MetaTrader 5, Sierra Chart is not required for order execution. Sierra Chart is only relevant when you choose to use it as a market-data feed.

## What you need

### MetaTrader 5 for execution

Required:

- MT5 installed and logged into the intended account
- Algo Trading enabled
- Broker connection active
- ZMQ bridge EA attached if your execution path requires it
- Account/server details matching `config/trading_params_lite.json`

### Sierra Chart for optional DTC data feed

Required only if you use Sierra Chart as the data source:

- DTC Protocol Server enabled
- Data-feed connection active
- DTC ports available, commonly `11099`/`11098`

Not required for MT5 execution:

- Sierra Chart administrator mode
- Sierra Chart trading permissions
- Sierra Chart NTP sync

## Simplified startup for MT5 execution mode

### Step 1: Start MetaTrader 5

1. Open MT5.
2. Log into your demo or live account.
3. Enable Algo Trading.
4. Attach the ZMQ bridge EA if execution depends on it.
5. Confirm the configured account in `config/trading_params_lite.json` matches the MT5 account.

### Step 2: Start the local dashboard, if needed

```powershell
.\LAUNCH_DESKTOP_APP.bat
```

This starts the KingIn API and opens the React dashboard at `http://localhost:5000`.

### Step 3: Start the trading pipeline

```powershell
.\START_ALL.bat
```

The script turns the master switch on, starts the data-feed server, launches enabled dashboards, and runs the modular strategy pipeline.

Manual equivalent:

```powershell
python data_feed/server.py
python -m Engine.modular_bootstrapper
streamlit run dashboard/dashboard_app.py
```

## Data flow

```text
MT5 broker/account data -> Python engine -> risk checks -> validated signals -> MT5 execution
                              |
                              v
                    local API/dashboard logs
```

When Sierra Chart is enabled as a data feed:

```text
Sierra Chart DTC data -> Python engine -> MT5 execution
```

## Pre-flight checklist

Before forward testing:

| Check | Expected |
|-------|----------|
| MT5 open and connected | Yes |
| Algo Trading | Enabled |
| Config account/server | Matches MT5 |
| Lot size | Confirmed in config |
| Master switch | Enabled only when intended |
| Demo account | Strongly recommended first |

## About Sierra Chart NTP Error 1314

If you see NTP Error 1314 in Sierra Chart, it usually means Windows denied a time-sync privilege. For MT5 execution mode, this does not block MT5 order execution.

Optional ways to remove the message:

1. Run Sierra Chart as administrator.
2. Disable NTP time synchronization in Sierra Chart settings.

## Troubleshooting

### Data not flowing

Check:

1. MT5 is open and connected.
2. The configured symbol exists in your broker account.
3. If using Sierra Chart, DTC is listening on the configured port.
4. Python dependencies were installed from `requirements.txt`.

### Trades not executing

Check:

1. MT5 Algo Trading is enabled.
2. ZMQ bridge EA is attached if required.
3. The account in config matches the logged-in MT5 account.
4. Risk rules are not blocking the signal.
5. Master switch is enabled.

### Dashboard not updating

Check:

1. `python kingin_api.py` is running.
2. `kingin-vite` is running with `npm run dev`.
3. Browser is open at `http://localhost:5000`.

## Summary

For MT5 execution mode, MT5 is the critical execution component, Python runs the strategy/risk pipeline, and the dashboard is only the local monitoring/control surface.
