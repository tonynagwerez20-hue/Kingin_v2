import MetaTrader5 as mt5
print('MT5 version:', mt5.__version__)
result = mt5.initialize()
print('Init result:', result)
if not result:
    print('Error:', mt5.last_error())
mt5.shutdown()