# Institutional Trading System - Desktop App

A professional desktop trading application built with React + Tauri, featuring 8 floating panels for comprehensive market analysis and trade management.

## Features

- **8 Floating Panels**: Market Bias, Active Signal, Last Trade, 7-Layer Confluence, Account Overview, Open Positions, Active Warnings, Pipeline Log
- **Real-time Data**: Polls engine_state.json every 2 seconds for live trading data
- **Native Desktop App**: Built with Tauri for native performance and system integration
- **Professional UI**: Dark theme with draggable, minimizable panels
- **MT5 Integration**: Reads live trading data from MetaTrader 5
- **Session Management**: Secure login with session persistence

## Quick Start

### Prerequisites
- Node.js 18+ and npm
- Rust (for Tauri)
- MetaTrader 5 terminal running

### Development Mode
```bash
# Install dependencies
npm install

# Launch desktop app in development mode
npm run tauri dev
```

Or use the provided batch file:
```bash
LAUNCH_DESKTOP_APP.bat
```

### Production Build
```bash
# Build the desktop app
npm run tauri build
```

Or use the provided batch file:
```bash
BUILD_DESKTOP_APP.bat
```

The built executable will be in `src-tauri/target/release/`.

## Architecture

- **Frontend**: React with custom CSS (no external UI libraries)
- **Backend**: Tauri (Rust) for native desktop integration
- **Data Source**: Reads `engine_state.json` from the same directory as the executable
- **Communication**: Tauri commands for secure file system access

## Panel Layout

1. **Market Bias** - Current market direction and confluence score
2. **Active Signal** - Current trading signal with entry/exit details
3. **Last Trade** - Most recent executed trade information
4. **7-Layer Confluence** - Multi-timeframe analysis layers
5. **Account Overview** - Balance, equity, floating P&L
6. **Open Positions** - Current open trades table
7. **Active Warnings** - System alerts and notifications
8. **Pipeline Log** - Real-time engine processing log
9. **🧠 ML Filter** - Machine Learning confidence scoring and decision results

## Data Schema

The app reads from `engine_state.json` with this structure:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "symbol": "XAUUSD",
  "bias": "BULLISH",
  "current_price": 2050.50,
  "signal_action": "LONG",
  "entry_price": 2050.50,
  "stop_loss": 2045.00,
  "take_profit": 2060.00,
  "lot_size": 0.01,
  "execution_type": "MARKET",
  "confluence_score": 6.0,
  "killzone_name": "London Open",
  "session_time": "08:00-11:00 UTC",
  "rr_ratio": "1:1.91",
  "layers": [
    {"name": "KillzoneFilterLayer", "passed": true, "score": 1.0, "reason": "Active"}
  ],
  "ml_filter": {
    "confidence": 0.85,
    "threshold": 0.75,
    "decision": "TRADE",
    "features": {
      "ob_strength": 0.92,
      "fvg_present": true,
      "bos_aligned": true,
      "liquidity_swept": false,
      "adr_pct": 0.65,
      "pips_to_liquidity": 25.5,
      "session": 1,
      "htf_bias": 0.75
    }
  },
  "last_trade": {
    "action": "LONG", "symbol": "XAUUSD", "price": 2050.00,
    "sl": 2045.00, "tp": 2060.00, "lots": 0.01,
    "bias": "BULLISH", "execution_type": "MARKET",
    "confluence_score": 5.75, "timestamp": "2024-01-01T12:00:00Z"
  },
  "account_equity": 1000.00,
  "account_balance": 980.00,
  "floating_pnl": 20.00,
  "open_trades_count": 1,
  "open_positions": [
    {
      "symbol": "XAUUSD", "type": "BUY", "lots": 0.01,
      "open_price": 2050.00, "current_price": 2052.50,
      "sl": 2045.00, "tp": 2060.00, "floating_pnl": 2.50,
      "open_time": "2024-01-01T12:00:00Z"
    }
  ],
  "active_warnings": ["Low liquidity detected"],
  "pipeline_log": ["[12:00:00] Signal generated", "[12:00:01] Order placed"]
}
```

## Usage

1. **Login**: Enter your MT5 credentials (stored encrypted locally)
2. **Engine Control**: Use the Start/Stop/Restart buttons to control the trading engine
3. **Monitor**: Watch real-time data across all 8 panels
4. **Panel Management**: Click panel headers to minimize, drag to reposition
5. **Panel Toggle**: Use bottom toolbar to show/hide panels

## Development

### Project Structure
```
├── src/                    # React frontend
│   ├── App.jsx            # Main app shell
│   ├── Dashboard.jsx      # Main dashboard component
│   ├── Login.jsx          # Authentication component
│   ├── BrandLogo.jsx      # Logo component
│   └── styles.css         # Global styles
├── src-tauri/             # Tauri backend
│   ├── src/main.rs        # Rust backend
│   └── tauri.conf.json    # Tauri configuration
├── dist/                  # Built frontend (generated)
└── package.json           # Node.js dependencies
```

### Adding New Panels

1. Add panel configuration to `Dashboard.jsx` state
2. Create panel component in the grid layout
3. Add data handling in the `fetchState` function
4. Update panel toggle logic

### Tauri Commands

- `read_engine_state()` - Reads engine_state.json from executable directory
- `write_dashboard_command(command)` - Writes dashboard commands to JSON file

## Troubleshooting

### App Won't Start
- Ensure Node.js and Rust are installed
- Run `npm install` to install dependencies
- Check that MT5 is running and engine_state.json exists

### No Data Showing
- Verify engine_state.json is being updated by the trading engine
- Check file permissions for the executable directory
- Ensure timestamp in engine_state.json is recent (< 10 seconds old)

### Build Fails
- Clear node_modules: `rm -rf node_modules && npm install`
- Clear Tauri target: `rm -rf src-tauri/target`
- Check Rust toolchain: `rustc --version`

## License

Proprietary - Institutional Trading System