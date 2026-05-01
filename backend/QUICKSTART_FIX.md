# System Connectivity Fix - Quick Start Guide

## 🚨 CRITICAL: Follow These Steps FIRST

Your system has **3 blocking issues** that prevent trading:

1. **Network Blocking** (Error 10065)
2. **Permission Issues** (Error 1314)  
3. **Trading Disabled** (TradingIsSupported: 0)

---

## Step 1: Fix Sierra Chart (5 minutes)

### A. Run as Administrator
1. **Close Sierra Chart completely**
2. Right-click `SierraChart_64.exe`
3. Select **"Run as Administrator"**
4. ✅ This fixes Error 1314 (NTP sync failure)

### B. Unblock Firewall
1. Open **Windows Defender Firewall**
2. Click **"Allow an app through Windows Firewall"**
3. Find `SierraChart_64.exe`
4. ✅ Check **BOTH** "Private" and "Public" boxes
5. If using VPN: **Disable it temporarily**
6. ✅ This fixes Error 10065 (unreachable host)

### C. Enable Trading in DTC Server
1. In Sierra Chart: `Global Settings` → `Sierra Chart Server Settings`
2. Select **"DTC Protocol Server"**
3. ✅ Check **"Enable DTC Protocol Server"**
4. ✅ Check **"Allow Trading"** ← **CRITICAL**
5. Click OK and **restart Sierra Chart**
6. ✅ This fixes TradingIsSupported: 0

---

## Step 2: Fix MetaTrader 5 (3 minutes)

### A. Enable Algo Trading
1. Open MetaTrader 5
2. Click **"Algo Trading"** button (top toolbar)
3. ✅ Ensure it's **GREEN** (enabled)

### B. Allow DLL Imports
1. `Tools` → `Options` → `Expert Advisors`
2. ✅ Check **"Allow DLL imports"**
3. Click OK

### C. Verify EA Status
1. Look at chart with attached EA
2. Check top-right corner icon:
   - 🙂 **Smiley face** = Working ✅
   - ☹️ **Sad face** = Failed ❌
3. If sad face: Check "Experts" tab for errors
4. If "Libs not found": Install [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

---

## Step 3: Run Diagnostic (1 minute)

```powershell
cd e:\s.y.s.t.e.m
python tests/diag_system_health.py
```

**Expected output:**
```
✅ DTC Live Port (11099): REACHABLE
✅ DTC Login: SUCCESS
✅ MT5 Bridge: CONNECTED
✅ Account Balance: $10,000.00
✅ API Status: DTC
✅ Latest Price: 2654.75
✅ Database: CONNECTED

ALL SYSTEMS OPERATIONAL ✨
```

If you see ❌ errors, follow the fix suggestions in the output.

---

## Step 4: Start System (Correct Order)

**IMPORTANT**: Start in this exact order:

### 1. Sierra Chart
```
Right-click → Run as Administrator
Wait for green "Conn" status bar
```

### 2. MetaTrader 5
```
Ensure Algo Trading is GREEN
Verify EA shows smiley face 🙂
```

### 3. Data Feed Server
```powershell
cd e:\s.y.s.t.e.m
python data_feed/server.py
```
Wait for: `[DTC] LIVE Logon Success`

### 4. Trading Engine
```powershell
cd e:\s.y.s.t.e.m
python Engine/main_loop.py
```
Wait for: `✅ [Pre-Flight] MT5 account balance: $10,000.00`

### 5. Dashboard
```powershell
cd e:\s.y.s.t.e.m
streamlit run dashboard/dashboard_app.py
```

---

## Success Indicators

| Component | Success Message | Failure Message |
|-----------|----------------|-----------------|
| **Sierra Chart** | `TradingIsSupported: 1` | `Error 10065` or `Error 1314` |
| **DTC** | `LIVE Logon Success` | `Connection refused` |
| **MT5** | `Account balance: $10,000.00` | `Timeout on request` |
| **API** | `Latest price: 2654.75` | `No data available` |

---

## Troubleshooting

### Still seeing Error 10065?
- Disable VPN completely
- Check Windows Firewall logs
- Try pinging data feed server

### Still seeing Error 1314?
- Ensure you right-clicked and selected "Run as Administrator"
- Check User Account Control (UAC) settings

### MT5 Bridge timeout?
- Verify EA is running (smiley face)
- Check MT5 "Experts" tab for errors
- Reinstall VC++ Redistributable if needed

### TradingIsSupported still 0?
- Double-check "Allow Trading" is checked in DTC settings
- Restart Sierra Chart after changing settings

---

## Need Help?

See detailed troubleshooting in:
- `implementation_plan.md` - Full configuration guide
- `tests/diag_system_health.py` - Automated diagnostic tool

Run diagnostic first, it will tell you exactly what's wrong!
