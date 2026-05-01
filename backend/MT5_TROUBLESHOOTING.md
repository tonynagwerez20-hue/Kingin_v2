# MT5 Network & Authorization Troubleshooting Guide

## Problem: "Failed to initialize MT5: Terminal: Authorization failed"

Your MT5 Terminal isn't able to connect to the network. Here's how to fix it:

---

## STEP 1: Configure MT5 Credentials

Edit `config/trading_params_lite.json` and locate this section:

```json
"pipeline": {
    "data_provider": {
        "config": {
            "login": YOUR_ACCOUNT_NUMBER,
            "password": "YOUR_PASSWORD",
            "server": "YOUR_SERVER"
        }
    }
}
```

**Replace with YOUR actual values:**

- **login**: Your 9-digit MT5 account number (e.g., `298686191`)
- **password**: Your MT5 password (the one you use to log into the terminal)
- **server**: The server name from MT5 terminal window title (e.g., `Exness-MT5Trial9`)

**Example:**
```json
"pipeline": {
    "data_provider": {
        "config": {
            "login": 298686191,
            "password": "YourMT5Password",
            "server": "Exness-MT5Trial9"
        }
    }
}
```

> **IMPORTANT**: Do NOT wrap numbers in quotes. Login must be a number: `298686191` not `"298686191"`

---

## STEP 2: Verify MT5 Terminal is Running & Connected

1. **Open MetaTrader5 Terminal**
   - Click Start button
   - Search for "MetaTrader5" or find it in Programs folder
   - Double-click to launch it

2. **Check Connection Status**
   - Look at the bottom-right of MT5 window
   - You should see "Connected" indicator
   - If it says "Not Connected", click the connect button

3. **Verify Server Settings**
   - In MT5, go to Tools → Options
   - Check the "Servers" tab
   - Find your broker's server and ensure it's selected
   - Click "Connect" if needed

---

## STEP 3: Test Network Connection

Run the diagnostic script:

```bash
python diagnose_mt5.py
```

**Expected output if working:**
```
✓ MT5 initialization SUCCESS
✓ Terminal info retrieved:
  ✓ Login SUCCESS
  ✓ Account info retrieved
```

**If you see errors, follow the recommendations below.**

---

## COMMON ISSUES & FIXES

### Issue: "MT5 initialization FAILED - Terminal: Authorization failed"

**Cause:** MT5 Terminal is not running or not connected to network

**Fix:**
1. Open MT5 Terminal (Start > MetaTrader5)
2. Wait for it to fully load (30-60 seconds)
3. Look for "Connected" indicator at bottom-right
4. If not connected, click Tools > Options > Servers > Connect

---

### Issue: "Terminal is NOT connected to server"

**Cause:** Network connectivity issue

**Fix:**
1. Check internet connection (open browser, verify it works)
2. Check firewall/antivirus - MT5 may be blocked
   - Windows Firewall: Settings > Privacy & Security > Firewall > Allow app through firewall
   - Add MetaTrader5.exe to allowed apps
3. If using VPN, try disabling it
4. Restart MT5 terminal
5. Check broker website - may be server maintenance

---

### Issue: "Login FAILED" or wrong credentials error

**Cause:** Wrong account, password, or server name

**Fix:**
1. Verify account number is exactly 9 digits
   - Check MT5 window title
   - Tools > Options > Account tab
2. Make sure password is correct (case-sensitive!)
3. Check server name - must be EXACT match
   - Look at MT5 window title bar
   - Should look like: "MetaTrader 5 - Exness-MT5Trial9" 
   - Copy exact server name: `Exness-MT5Trial9`
4. If unsure, try demo account first

---

### Issue: "No symbols available - network/connection issue"

**Cause:** MT5 connected but can't download market data

**Fix:**
1. Wait 1-2 minutes after MT5 opens (needs to sync data)
2. Right-click on chart → Refresh
3. Check broker's market hours (some trade only during business hours)
4. Restart MT5
5. Check broker website for status

---

## STEP 4: Troubleshooting Network Issues

### Check if internet is working:
```bash
ping google.com
```

### Check if MT5 can reach broker:
```bash
ping exness.com
```
(Replace with your broker's domain)

### Try different network:
- Try mobile hotspot if available
- Try connecting from different WiFi network
- Try wired connection if using WiFi

### Windows Firewall Issues:
1. Open Settings
2. Go to Privacy & Security → Firewall & network protection
3. Click "Allow an app through firewall"
4. Find and enable MetaTrader5.exe for both Private and Public networks
5. Restart MT5

### Antivirus/VPN Issues:
- Temporarily disable antivirus and try connecting
- Disable VPN if enabled
- Add MT5 to antivirus whitelist

---

## STEP 5: Verify Installation

Make sure required Python packages are installed:

```bash
pip install MetaTrader5
pip install pywin32
```

---

## DEBUGGING: Run with Account Credentials Directly

If config file method doesn't work, run diagnostic with credentials directly:

```bash
python diagnose_mt5.py 298686191 YourPassword "Exness-MT5Trial9"
```

Replace with YOUR values:
- `298686191` → Your account number
- `YourPassword` → Your MT5 password
- `Exness-MT5Trial9` → Your server name

---

## STILL NOT WORKING?

1. **Check MT5 version** - Should be latest version
   - In MT5: Help → About
   - Version should be 5.x or higher

2. **Try Demo Account** - Test with broker's demo account first

3. **Contact Broker Support** - Ask them to verify:
   - Your account is active
   - Your credentials are correct
   - No IP restrictions or security blocks
   - Server is operational

4. **Restart Everything**:
   ```bash
   # Close all Python processes
   taskkill /F /IM python.exe
   
   # Close MT5
   taskkill /F /IM terminal.exe
   
   # Wait 10 seconds
   
   # Reopen MT5
   # Then test again
   ```

---

## FINAL CHECK

Once everything is working, test the full system:

1. Ensure MT5 is running and connected
2. Run: `python diagnose_mt5.py`
3. Should see all green checkmarks ✓
4. Then try logging in through the dashboard

---

**Questions?** Check the broker's FAQ or contact their support team.
