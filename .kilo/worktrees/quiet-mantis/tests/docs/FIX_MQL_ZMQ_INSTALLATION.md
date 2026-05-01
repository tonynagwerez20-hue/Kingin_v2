# Fix MQL-ZMQ Installation - Copy All Required Files

## Problem
The Zmq.mqh file requires additional include files that weren't copied initially.

## Solution - Copy ALL Include Files

You need to copy **two complete folders** from the mql-zmq library:

### Step 1: Copy the Zmq Folder (Complete)

**From:**
```
c:\Users\molly\Desktop\hedge\MT5\mql-zmq-master\mql-zmq-master\Include\Zmq\
```

**To:**
```
C:\Users\molly\AppData\Roaming\MetaQuotes\Terminal\B21F5A265C286EF349353BDBE31D8254\MQL5\Include\Zmq\
```

**PowerShell Command:**
```powershell
Copy-Item -Path "c:\Users\molly\Desktop\hedge\MT5\mql-zmq-master\mql-zmq-master\Include\Zmq" `
          -Destination "C:\Users\molly\AppData\Roaming\MetaQuotes\Terminal\B21F5A265C286EF349353BDBE31D8254\MQL5\Include\Zmq" `
          -Recurse -Force
```

This copies:
- AtomicCounter.mqh
- Context.mqh
- Errno.mqh
- Socket.mqh
- SocketOptions.mqh
- Z85.mqh
- Zmq.mqh
- ZmqMsg.mqh

### Step 2: Copy the Mql Folder (Complete)

**From:**
```
c:\Users\molly\Desktop\hedge\MT5\mql-zmq-master\mql-zmq-master\Include\Mql\
```

**To:**
```
C:\Users\molly\AppData\Roaming\MetaQuotes\Terminal\B21F5A265C286EF349353BDBE31D8254\MQL5\Include\Mql\
```

**PowerShell Command:**
```powershell
Copy-Item -Path "c:\Users\molly\Desktop\hedge\MT5\mql-zmq-master\mql-zmq-master\Include\Mql" `
          -Destination "C:\Users\molly\AppData\Roaming\MetaQuotes\Terminal\B21F5A265C286EF349353BDBE31D8254\MQL5\Include\Mql" `
          -Recurse -Force
```

This copies:
- Lang/Error.mqh
- Lang/GlobalVariable.mqh
- Lang/Mql.mqh
- Lang/Native.mqh

### Step 3: Verify DLLs Are Copied

**Verify these exist:**
```
C:\Users\molly\AppData\Roaming\MetaQuotes\Terminal\B21F5A265C286EF349353BDBE31D8254\MQL5\Libraries\libzmq.dll
C:\Users\molly\AppData\Roaming\MetaQuotes\Terminal\B21F5A265C286EF349353BDBE31D8254\MQL5\Libraries\libsodium.dll
```

**If missing, copy:**
```powershell
Copy-Item "c:\Users\molly\Desktop\hedge\MT5\mql-zmq-master\mql-zmq-master\Library\MT5\libzmq.dll" `
          "C:\Users\molly\AppData\Roaming\MetaQuotes\Terminal\B21F5A265C286EF349353BDBE31D8254\MQL5\Libraries\libzmq.dll"

Copy-Item "c:\Users\molly\Desktop\hedge\MT5\mql-zmq-master\mql-zmq-master\Library\MT5\libsodium.dll" `
          "C:\Users\molly\AppData\Roaming\MetaQuotes\Terminal\B21F5A265C286EF349353BDBE31D8254\MQL5\Libraries\libsodium.dll"
```

---

## Complete PowerShell Script

Run this in PowerShell to copy everything at once:

```powershell
# Your MT5 Data Folder
$MT5_DATA = "C:\Users\molly\AppData\Roaming\MetaQuotes\Terminal\B21F5A265C286EF349353BDBE31D8254"

# Source folder
$SOURCE = "c:\Users\molly\Desktop\hedge\MT5\mql-zmq-master\mql-zmq-master"

# Copy Include folders (complete)
Copy-Item -Path "$SOURCE\Include\Zmq" -Destination "$MT5_DATA\MQL5\Include\Zmq" -Recurse -Force
Copy-Item -Path "$SOURCE\Include\Mql" -Destination "$MT5_DATA\MQL5\Include\Mql" -Recurse -Force

# Copy DLLs
Copy-Item "$SOURCE\Library\MT5\libzmq.dll" "$MT5_DATA\MQL5\Libraries\libzmq.dll" -Force
Copy-Item "$SOURCE\Library\MT5\libsodium.dll" "$MT5_DATA\MQL5\Libraries\libsodium.dll" -Force

Write-Host "✅ All files copied successfully!" -ForegroundColor Green
Write-Host "Now compile HedgeEA.mq5 in MetaEditor" -ForegroundColor Cyan
```

---

## After Copying

1. **Refresh MetaEditor**: Close and reopen MetaEditor
2. **Compile EA**: F7 on HedgeEA.mq5
3. **Expected Result**: `0 error(s), 0 warning(s)`

---

## Final Folder Structure

After copying, your MT5 Include folder should look like this:

```
MQL5/
  └── Include/
      ├── Mql/
      │   └── Lang/
      │       ├── Error.mqh
      │       ├── GlobalVariable.mqh
      │       ├── Mql.mqh
      │       └── Native.mqh
      └── Zmq/
          ├── AtomicCounter.mqh
          ├── Context.mqh
          ├── Errno.mqh
          ├── Socket.mqh
          ├── SocketOptions.mqh
          ├── Z85.mqh
          ├── Zmq.mqh
          └── ZmqMsg.mqh
```
