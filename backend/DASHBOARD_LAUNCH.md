# Dashboard Auto-Launch Guide

## Quick Start

### Windows Users (Recommended)

Simply double-click the `launch_dashboard.bat` file in the root directory:

```
e:\s.y.s.t.e.m\launch_dashboard.bat
```

This will:
1. Start the FastAPI backend server (port 8000)
2. Start the React dashboard (port 3000)
3. Automatically open http://localhost:3000 in your default browser

### Alternative: Python Script

```bash
cd e:\s.y.s.t.e.m
python launch_dashboard.py
```

### Manual Start

If you prefer to start services manually:

**Terminal 1 - Backend Server:**
```bash
cd e:\s.y.s.t.e.m
python data_feed\server.py
```

**Terminal 2 - React Dashboard:**
```bash
cd e:\s.y.s.t.e.m\dashboard-react
npm run dev
```

**Browser:**
Navigate to http://localhost:3000

---

## Dashboard Features

### Real-Time Monitoring

- **Connection Status**: DTC feed, MT5 bridge, and engine status with uptime tracking
- **Market Data**: Live gold price, bid/ask, broker spread, and volume (1-second updates)
- **EA Latency**: Round-trip ping time to MT5 EA with status indicators
- **Trade Timeline**: Open positions with live P&L and recent closed trades
- **Trading Metrics**: Account balance, total P&L, win rate, open trades count

### Update Intervals

- Market Data: 1 second
- Trades: 2 seconds  
- System Status: 5 seconds
- Latency: 5 seconds

---

## Troubleshooting

### Dashboard Won't Load

1. **Check Backend Server**:
   - Ensure `python data_feed\server.py` is running
   - Check http://localhost:8000/status in browser
   - Look for errors in server terminal

2. **Check React Server**:
   - Ensure `npm run dev` completed successfully
   - Check for port 3000 conflicts
   - Try `npm install` if dependencies are missing

3. **Check Browser**:
   - Clear browser cache
   - Try incognito/private mode
   - Check browser console for errors (F12)

### MT5 Latency Shows "Not Responding"

1. **Check MT5 EA**:
   - Ensure HedgeEA is running in MT5
   - Check MT5 terminal for EA errors
   - Verify ZMQ port 5557 is not blocked

2. **Check Bridge Connection**:
   - Restart MT5 terminal
   - Recompile and reload HedgeEA
   - Check Windows Firewall settings

### DTC Feed Shows "Disconnected"

1. **Check Sierra Chart**:
   - Ensure Sierra Chart is running
   - Verify DTC server is enabled (port 11099)
   - Check Sierra Chart connection logs

2. **Check Data Source**:
   - Verify `DATA_SOURCE_TYPE` in environment
   - Check `data_feed\server.py` startup logs
   - Ensure historical data has loaded

---

## Advanced Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# Data Source
DATA_SOURCE_TYPE=DTC  # or CSV

# Sierra Chart DTC
SIERRA_DTC_HOST=127.0.0.1
SIERRA_DTC_PORT=11099
SIERRA_SYMBOL=XAUUSD

# MT5 Bridge
TRADING_SYMBOL=XAUUSD  # or broker-specific symbol
```

### Port Configuration

If ports 3000 or 8000 are in use:

**Backend (server.py)**:
Edit the last line:
```python
uvicorn.run(app, host='0.0.0.0', port=8001)  # Change port
```

**Frontend (package.json)**:
```json
"scripts": {
  "dev": "next dev -p 3001"  // Change port
}
```

Update dashboard URL in launch scripts accordingly.

---

## Performance Tips

### Reduce Update Frequency

For slower systems, increase polling intervals in components:

**MarketDataPanel.tsx**:
```typescript
const interval = setInterval(fetchData, 2000); // Change from 1000 to 2000
```

**TradeTimeline.tsx**:
```typescript
const interval = setInterval(fetchTrades, 5000); // Change from 2000 to 5000
```

### Disable Unused Features

Comment out components in `app/page.tsx` if not needed:

```typescript
// <LatencyMonitor />  // Disable if not using MT5
// <TradeTimeline />   // Disable if not trading
```

---

## System Requirements

- **Python**: 3.8 or higher
- **Node.js**: 16.x or higher
- **npm**: 8.x or higher
- **MT5**: Terminal with HedgeEA installed
- **Sierra Chart**: With DTC server enabled (if using DTC mode)

---

## Support

For issues or questions:
1. Check the walkthrough.md for detailed implementation details
2. Review server logs in terminal
3. Check browser console (F12) for frontend errors
4. Verify all services are running (Python server, React dev server, MT5, Sierra Chart)
