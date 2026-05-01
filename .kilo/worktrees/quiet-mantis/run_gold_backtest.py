"""
Gold Research Strategy - Backtest Runner
=========================================
Simple standalone script to generate backtest signals.

Usage:
    python run_gold_backtest.py

Output:
    data/backtest_signals.csv - Signals for MT5 EA backtesting
"""

import pandas as pd
import numpy as np
import sys
import os
import logging
from datetime import datetime, timedelta

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the strategy
from Engine.igof.layers.gold_research.strategy_interface import GoldResearchStrategy

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BacktestRunner")


def generate_sample_data(n_bars=3000):
    """Generate realistic Gold-like OHLCV data."""
    np.random.seed(42)
    
    end_time = datetime.now()
    timestamps = pd.date_range(end=end_time, periods=n_bars, freq='H')
    
    base_price = 2650.0
    returns = np.random.normal(0.0001, 0.005, n_bars)
    trend = np.linspace(0, 0.02, n_bars)
    close_prices = base_price * np.exp(np.cumsum(returns + trend))
    
    high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.002, n_bars)))
    low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.002, n_bars)))
    open_prices = np.roll(close_prices, 1)
    open_prices[0] = base_price
    
    volume = (10000 + np.random.exponential(5000, n_bars)).astype(int)
    
    return pd.DataFrame({
        'time': timestamps,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volume
    })


def run_backtest():
    """Run the backtest and generate signals."""
    logger.info("=== Gold Research Strategy Backtest ===")
    
    # Use 8 years of XAUUSD H1 data for comprehensive training
    data_path = "data/XAUUSDm_H1_8 years data.csv"
    if os.path.exists(data_path):
        logger.info(f"Loading 8-year dataset from {data_path}")
        # This CSV has tab-separated values with special format
        df = pd.read_csv(data_path, sep='\t')
        
        # Parse the date and time columns
        df['time'] = pd.to_datetime(df['<DATE>'] + ' ' + df['<TIME>'], format='%Y.%m.%d %H:%M:%S')
        df = df.rename(columns={
            '<OPEN>': 'open',
            '<HIGH>': 'high', 
            '<LOW>': 'low',
            '<CLOSE>': 'close',
            '<TICKVOL>': 'volume'
        })
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
    else:
        logger.info("No 8-year data found, checking for backup data...")
        backup_path = "data/XAUUSDm_H1_202401012300_202603032000.csv"
        if os.path.exists(backup_path):
            logger.info(f"Loading backup data from {backup_path}")
            df = pd.read_csv(backup_path, sep='\t')
            df['time'] = pd.to_datetime(df['<DATE>'] + ' ' + df['<TIME>'], format='%Y.%m.%d %H:%M:%S')
            df = df.rename(columns={
                '<OPEN>': 'open',
                '<HIGH>': 'high', 
                '<LOW>': 'low',
                '<CLOSE>': 'close',
                '<TICKVOL>': 'volume'
            })
            df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
        else:
            logger.info("No data found, generating sample data")
            df = generate_sample_data(3000)
    logger.info(f"Using {len(df)} bars of data (8-year dataset)")
    
    # Split: 95% train, 5% test (user requested)
    train_size = int(len(df) * 0.95)
    train_df = df.iloc[:train_size].copy()
    test_df = df.iloc[train_size:].copy()
    
    logger.info(f"Training on {len(train_df)} bars, testing on {len(test_df)} bars")
    
    # Initialize and train strategy with relaxed parameters for 8-year data
    # Use lower out-of-bounds threshold to allow trades across different market regimes
    strategy = GoldResearchStrategy(lite_mode=True)
    
    # Adjust signal parameters for 8-year data (spans multiple regimes)
    strategy.signal_logic.out_of_bounds_threshold = 0.10  # 10%
    strategy.signal_logic.proximity_threshold = 0.50  # 50% - more flexible
    strategy.signal_logic.min_range_pct = 0.001  # 0.1% instead of 0.2%
    train_result = strategy.train(train_df)
    
    if train_result.get('status') != 'trained':
        logger.error(f"Training failed: {train_result}")
        return
    
    logger.info(f"Training complete. R² High: {train_result.get('train_r2_high', 0):.4f}")
    
    # Generate signals
    signals = []
    buffer_df = train_df.copy()
    
    for i in range(len(test_df)):
        buffer_df = pd.concat([buffer_df, test_df.iloc[i:i+1]], ignore_index=True)
        if len(buffer_df) > 200:
            buffer_df = buffer_df.tail(200).reset_index(drop=True)
        
        current_price = float(test_df.iloc[i]['close'])
        signal, bounds = strategy.run_tick(buffer_df)
        
        # Debug first few signals
        if i < 5:
            logger.info(f"Bar {i}: price={current_price:.2f}, pred_high={bounds.get('pred_high', 0):.2f}, pred_low={bounds.get('pred_low', 0):.2f}, signal={signal}")
            if 'error' in bounds:
                logger.info(f"  Error: {bounds['error']}")
        
        signals.append({
            'time': test_df.iloc[i]['time'],
            'signal': signal,
            'price': current_price,
            'pred_high': bounds.get('pred_high', 0),
            'pred_low': bounds.get('pred_low', 0),
            'signal_details': str(bounds.get('signal_details', {})) if 'signal_details' in bounds else ''
        })
        
        if (i + 1) % 100 == 0:
            logger.info(f"Processed {i + 1}/{len(test_df)} bars")
    
    # Save signals
    signals_df = pd.DataFrame(signals)
    output_path = "data/backtest_signals.csv"
    signals_df.to_csv(output_path, index=False)
    
    # Summary
    buy_signals = (signals_df['signal'] == 'BUY').sum()
    sell_signals = (signals_df['signal'] == 'SELL').sum()
    wait_signals = (signals_df['signal'] == 'WAIT').sum()
    
    logger.info(f"=== Signal Distribution ===")
    logger.info(f"BUY: {buy_signals}, SELL: {sell_signals}, WAIT: {wait_signals}")
    logger.info(f"Signals saved to {output_path}")
    
    # Also save in Hedge EA format
    hedge_signals = signals_df[signals_df['signal'].isin(['BUY', 'SELL'])].copy()
    hedge_signals['Action'] = hedge_signals['signal'].map({'BUY': 'LONG', 'SELL': 'SHORT'})
    hedge_signals['Symbol'] = 'XAUUSD'
    hedge_signals['SL'] = hedge_signals.apply(
        lambda x: x['pred_low'] if x['signal'] == 'BUY' else x['pred_high'], axis=1
    )
    hedge_signals['Lots'] = 0.1
    hedge_signals['Description'] = 'GoldResearch-Range'
    hedge_signals['Magic'] = 654321
    
    hedge_output = "data/gold_research_trades.csv"
    hedge_signals[['time', 'Symbol', 'Action', 'price', 'SL', 'Lots', 'Description', 'Magic']].to_csv(
        hedge_output, index=False
    )
    logger.info(f"Hedge EA signals saved to {hedge_output}")


if __name__ == "__main__":
    run_backtest()
