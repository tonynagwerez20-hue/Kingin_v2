# Quick Fix for ChunkLoadError

## The Error
```
ChunkLoadError: Loading chunk app/layout failed.
(timeout: http://localhost:3001/_next/static/chunks/app/layout.js)
```

## Cause
This error occurs when:
1. The Next.js dev server was interrupted or crashed
2. The browser cached old chunks from a previous session
3. Port conflicts or network issues

## Solution

### Step 1: Stop All Running Servers
Press `Ctrl+C` in any terminal windows running the dashboard or API server.

### Step 2: Clear Browser Cache
- Press `Ctrl+Shift+Delete` in your browser
- Select "Cached images and files"
- Click "Clear data"

OR simply use **Incognito/Private mode** (Ctrl+Shift+N)

### Step 3: Restart the Dashboard

**Option A: Use the Batch File (Recommended)**
```batch
# Double-click this file:
e:\s.y.s.t.e.m\launch_dashboard.bat
```

**Option B: Manual Restart**
```bash
# Terminal 1 - Backend
cd e:\s.y.s.t.e.m
python data_feed\server.py

# Terminal 2 - Frontend (use cmd, not PowerShell)
cd e:\s.y.s.t.e.m\dashboard-react
cmd /c "npm run dev"
```

### Step 4: Refresh Browser
- Navigate to http://localhost:3000
- Press `Ctrl+F5` for hard refresh

## PowerShell Issues

If you see errors about "execution policies" or "scripts disabled":

**Quick Fix:**
Always use `cmd` instead of PowerShell for npm commands:
```bash
cmd /c "npm run dev"
```

**Permanent Fix (Optional):**
Run PowerShell as Administrator and execute:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Still Not Working?

### Check Port Conflicts
```bash
# Check if port 3000 is in use
netstat -ano | findstr :3000

# Kill the process if needed (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### Delete .next Cache
```bash
cd e:\s.y.s.t.e.m\dashboard-react
rmdir /s /q .next
npm run dev
```

### Reinstall Dependencies
```bash
cd e:\s.y.s.t.e.m\dashboard-react
rmdir /s /q node_modules
npm install
npm run dev
```

## ZMQ Latency / "12-second Drift"

If you notice that the dashboard or engine price lags behind Sierra Chart by exactly 12-15 seconds:

### Cause
ZeroMQ's internal buffer is filling up with stale ticks, creating "buffer bloat". This happens if the Engine processing loop is slightly slower than the incoming tick stream.

### Solution
Ensue the `CONFLATE` option is enabled on the ZMQ SUB socket in `Engine/main_loop.py`:
```python
subscriber.setsockopt(zmq.CONFLATE, 1)
```
This forces the socket to only keep the **latest** message, effectively dropping the backlog and resetting latency to 0ms.

---

## Prevention

To avoid this error in the future:
1. Always use `Ctrl+C` to stop the dev server gracefully
2. Don't close terminal windows abruptly
3. Use the batch file for consistent launches
4. Keep browser cache cleared during development

---

**The dashboard should now be running successfully at http://localhost:3000!**

---

## MetaTrader 5 & ZMQ Bridge Issues

### 1. EA Not Receiving Signals
**Symptoms**: Python says "Signal Sent", but EA does absolutely nothing (no logs in Experts tab).

**Fix**:
1.  **Check `BACKTEST_MODE`**:
    - If running Live/ZMQ, ensure `BACKTEST_MODE` is `false`.
    - If reading CSV, ensure `BACKTEST_MODE` is `true`.
2.  **Check Port 5555**:
    - Run `netstat -ano | findstr :5555`.
    - If nothing shows, the EA is NOT listening. Re-init the EA on the chart.
3.  **Check DLLs**:
    - Go to `Tools -> Options -> Expert Advisors`.
    - Ensure "Allow DLL imports" is checked.

### 2. EA "Skipping" Historical Signals
**Symptoms**: EA says "SKIPPING EXPIRED SIGNAL" in the logs during a Visual Replay.

**Fix**:
- You missed the new parameter.
- Go to EA Inputs and set `ENABLE_VISUAL_REPLAY` = `true`.
- This tells the EA to ignore the timestamp check.

### 3. "Address in use" (ZMQ Error)
**Symptoms**: Python crashes with `ZMQError: Address in use`.

**Fix**:
- You have a zombie Python process or another script running.
- Run `taskkill /IM python.exe /F` to kill all Python scripts.
- Restart `main_loop.py`.
