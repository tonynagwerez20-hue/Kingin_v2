"""
Transfer signals from gold_research_trades.csv to backtest_signals.csv with 0.01 lot size
"""
import pandas as pd

# Read the source file
df = pd.read_csv('data/gold_research_trades.csv')

# Change lot size to 0.01
df['Lots'] = 0.01

# Write to backtest_signals.csv
df.to_csv('data/backtest_signals.csv', index=False)

print(f'Transferred {len(df)} signals with 0.01 lot size')
print(f'Format: time,Symbol,Action,price,SL,Lots,Description,Magic')
print(df['Action'].value_counts())
