# MT5 EA Installation Verification Checklist

## Pre-Compilation Checklist

### 1. ZeroMQ DLL Installation

The HedgeEA v2.01+ uses **Direct DLL calls**. You do NOT need any external MQL5 include libraries.

**Required Files (2 total):**
- `libzmq.dll` (64-bit for MT5)
- `libsodium.dll` (64-bit for MT5)

**Installation:**
1. Copy both DLLs to: `<MT5_DATA_FOLDER>/MQL5/Libraries/`
2. **⚠️ CRITICAL:** Ensure you use 64-bit DLLs. MT5 will fail to load 32-bit (MT4) DLLs.

**Verify Locations:**
- [ ] `<MT5_DATA_FOLDER>/MQL5/Libraries/libzmq.dll`
- [ ] `<MT5_DATA_FOLDER>/MQL5/Libraries/libsodium.dll`

---

### 2. EA File Location

**Verify:**
- [ ] `<MT5_DATA_FOLDER>/MQL5/Experts/HedgeEA.mq5`

---

### 3. Compilation

**Steps:**
1. Open **MetaEditor** (F4 in MT5).
2. Navigator → Experts → **HedgeEA.mq5**.
3. Press **F7** (Compile).

**Expected Output:**
```text
0 error(s), 0 warning(s)
HedgeEA.ex5 generated successfully
```

---

### 4. EA Attachment

**Steps:**
1. Open **XAUUSD** chart.
2. Drag **HedgeEA** onto the chart.
3. **CRITICAL:** Check **"Allow DLL imports"** in the "Common" or "Dependencies" tab.
4. Click OK.

**Expected UI Result:**
- Blue "cap" or smiley icon in the top-right corner.
- Experts log shows initialization.

---

### 5. Verify Hub Connection

**Check Experts Log:**
```text
=== HedgeEA Initialization (Direct ZMQ v2.01) ===
[INFO] HedgeEA initialized successfully
[INFO] Listening on localhost:5555 for topic 'SIGNAL'
```

---

## Post-Installation Testing

### Test 1: Signal Reception
1. Start the Python system: Run `START_ALL.bat`.
2. Run the test script: `python tests/test_mt5_signals.py`.
3. Check MT5 log for `[INFO] Processing signal: ...`.

### Troubleshooting
- **Cannot load library**: DLLs missing or 32-bit instead of 64-bit.
- **Failed to connect**: Python bridge not running or port 5555 blocked.
- **undeclared identifier**: Ensure you are using HedgeEA v2.01.

---

**✅ Final Verification Checklist:**
- [ ] DLLs in `MQL5/Libraries/`
- [ ] `HedgeEA.mq5` compiled with 0 errors
- [ ] "Allow DLL imports" checked
- [ ] Python system running and connected
