# LEGACY: MQL-ZMQ Required Files

> [!IMPORTANT]
> This document is kept for legacy reference only. 
> As of **HedgeEA v2.01**, the system uses **Direct DLL Calls** and no longer requires any internal MQL5 include libraries (`.mqh` files).

## Current Requirement (v2.01+)

The system now only requires two files in the `MQL5/Libraries` folder:
1. `libzmq.dll` (64-bit)
2. `libsodium.dll` (64-bit)

## Why the change?
Newer builds of MetaTrader 5 (3850+) introduced strict type checking that broke the original `mql-zmq` include library wrapper. By migrating to direct DLL calls, we have achieved:
- **Universal Compatibility**: Works on all MT5 versions.
- **Zero Config**: No more "Include folder" setup errors.
- **Performance**: Faster execution by bypassing the class wrappers.

---

### Legacy Reference (mql-zmq 1.x)
*The following was required for v2.0 and earlier:*

- Include/Mql/Zmq.mqh
- Include/Zmq/Context.mqh
- Include/Zmq/Socket.mqh
- ... (many others)

**If you are still using an old version of the EA, please upgrade to HedgeEA.mq5 v2.01.**
