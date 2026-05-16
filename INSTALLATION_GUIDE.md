# KingIn Trading System — Installation Guide

## Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 64-bit | Windows 11 64-bit |
| Python | 3.10 | 3.11 |
| Node.js | 18 | 20 LTS |
| RAM | 4 GB | 8 GB |
| Storage | 2 GB | 5 GB (for backtest data) |
| MT5 | Any broker | With algo trading enabled |

## Developer Setup

```
git clone https://github.com/tonynagwerez20-hue/Kingin_v2.git
cd Kingin_v2
```

Install dependencies:
```
pip install -r requirements.txt
cd frontend && npm install
```

Then launch:
```
START_SYSTEM.bat
```

The dashboard will open as a desktop application via Electron.

## Production Build

Run the build script:
```
BUILD_APP.bat
```

This produces the installer in `frontend/installer_output/`:
- `KingIn Trading System Setup 2.0.0.exe` — NSIS installer (recommended)

## Installer (NSIS Setup.exe)

The NSIS installer:
- Creates a `KingIn Trading System` entry in Start Menu
- Creates a desktop shortcut with custom icon
- Creates an entry in Add/Remove Programs
- Offers custom install directory

## MT5 Prerequisites

1. Open MT5 → Tools → Options → Expert Advisors
2. Enable: Allow Algorithmic Trading
3. Enable: Allow DLL Imports
4. Ensure your MT5 account is logged in and "AutoTrading" is green in the toolbar.
