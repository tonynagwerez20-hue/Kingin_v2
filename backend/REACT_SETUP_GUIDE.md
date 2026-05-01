# React Dashboard: User & Maintenance Guide

**Status**: ✅ IMPLEMENTED & READY

This dashboard provides professional, real-time monitoring of your trading system.

---

## 🚀 Quick Start (Daily Operation)

### Step 1: Ensure Backend is Running
The dashboard depends on the FastAPI server:
```powershell
python data_feed/server.py
```

### Step 2: Start the Dashboard
```powershell
cd e:\s.y.s.t.e.m\dashboard-react
npm run dev
```

### Step 3: Open in Browser
Navigate to: **http://localhost:3000**

---

## 📂 Project Structure

```
dashboard-react/
├── app/                  # Next.js Pages & Routes
│   ├── page.tsx          # System Status Overview
│   ├── live/page.tsx     # High-Frequency Monitor
│   └── settings/page.tsx # Configuration
├── components/           # UI Components
│   ├── PriceTicker.tsx   # Real-time Price Display
│   ├── DeltaAnalysis.tsx # Orderflow Visualization
│   └── CandlestickChart.tsx # Professional Charts
├── hooks/                # Data Fetching Logic
│   └── useLatestPrice.ts # 200ms Polling Hook
└── public/               # Static Assets
```

---

## 🔧 Maintenance Tasks

### Updating Dependencies
If you add new features or components:
```powershell
npm install [package-name]
```

### Building for Production
For better performance and security:
```powershell
npm run build
npm start
```

### Changing API Endpoint
If the backend port changes, update the configuration in `hooks/` or `lib/api.ts`.

---

## 🛠 Troubleshooting

### "Cannot Connect to API"
1. Verify `python data_feed/server.py` is running.
2. Check `dashboard-react/.env.local` (if exists) for API URL.
3. Ensure CORS is enabled in `server.py`.

### Port 3000 in Use
If another app is using port 3000, run:
```powershell
npm run dev -- -p 3001
```

---

## ✅ System Status
- ✅ **Node.js**: Installed
- ✅ **Project Structure**: Created
- ✅ **Components**: Built
- ✅ **WebSocket/Polling**: Configured
- ✅ **Professional UI**: Active

*Document Version: 1.1.0*
*Last Updated: 2026-02-02*

