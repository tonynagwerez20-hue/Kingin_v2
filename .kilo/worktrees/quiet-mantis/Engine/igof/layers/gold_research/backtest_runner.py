"""
Gold Research Strategy - Backtest Runner
=========================================
Generates signals from historical data for backtesting.

Usage:
    python gold_research_strategy/backtest_runner.py
    
Output:
    CSV file with signals compatible with backtesting/Hedge EA format.

The script will:
1. Load 6 months of XAUUSD data
2. Train the strategy on first 80% of data
3. Generate signals for remaining 20%
4. Save signals to data/gold_research_signals.csv
"""

import pandas as pd
import numpy as np
import sys
import os
import logging
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

# Use relative import
from . import GoldResearchStrategy, GoldStrategyBuilder

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BacktestRunner")


def load_or_generate_data(symbol="XAUUSD", timeframe="H1"):
    """
    Load data from CSV or generate sample data if not available.
    
    Expected CSV format: time,open,high,low,close,volume
    """
    # Try multiple locations for the 6-month data
    possible_paths = [
        f"data/backtest/{symbol}_{timeframe}_6mo.csv",
        f"data/{symbol}_{timeframe}_6mo.csv",
        f"data/{symbol}_{timeframe}.csv",
        "data/upgraded_signals.csv"
    ]
    
    for data_path in possible_paths:
        if os.path.exists(data_path):
            logger.info(f"Loading data from {data_path}")
            
            if "upgraded_signals" in data_path:
                # Convert from signal format to OHLCV
                return convert_signals_to_ohlcv(data_path)
            
            df = pd.read_csv(data_path)
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
            return df
    
    # Generate sample data for demonstration
    logger.warning(f"No data file found. Generating sample {symbol} data for demonstration.")
    return generate_sample_data(symbol=symbol, timeframe=timeframe)


def convert_signals_to_ohlcv(signals_path: str) -> pd.DataFrame:
    """
    Convert upgraded_signals.csv format to OHLCV for backtesting.
    This generates realistic OHLC data based on signal entry points.
    """
    signals = pd.read_csv(signals_path)
    signals['Time'] = pd.to_datetime(signals['Time'])
    
    # Generate OHLCV data from signal entries
    # We'll expand each signal into a bar
    ohlcv_data = []
    
    for _, row in signals.iterrows():
        entry_price = row['Price']
        action = row['Action']
        
        # Generate realistic OHLC values around entry price
        spread = entry_price * 0.0002  # Typical spread
        
        if action == "LONG":
            open_price = entry_price
            high = entry_price + spread * 2
            low = entry_price - spread
            close_price = entry_price + spread
        else:  # SHORT
            open_price = entry_price
            high = entry_price + spread
            low = entry_price - spread * 2
            close_price = entry_price - spread
        
        ohlcv_data.append({
            'time': row['Time'],
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': 10000
        })
    
    return pd.DataFrame(ohlcv_data)


def generate_sample_data(symbol="XAUUSD", timeframe="H1", n_bars=3000):
    """
    Generate realistic sample OHLCV data for testing.
    """
    np.random.seed(42)
    
    # Generate timestamps
    end_time = datetime.now()
    if timeframe == "H1":
        freq = 'H'
    elif timeframe == "H4":
        freq = '4H'
    elif timeframe == "M15":
        freq = '15min'
    else:
        freq = 'H'
    
    timestamps = pd.date_range(end=end_time, periods=n_bars, freq=freq)
    
    # Generate realistic Gold-like price movements
    base_price = 2650.0
    
    # Create price series with trends and volatility
    returns = np.random.normal(0.0001, 0.005, n_bars)  # Daily-like returns
    trend = np.linspace(0, 0.02, n_bars)  # Slight upward trend
    
    close_prices = base_price * np.exp(np.cumsum(returns + trend))
    
    # Generate OHLC from close
    high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.002, n_bars)))
    low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.002, n_bars)))
    open_prices = np.roll(close_prices, 1)
    open_prices[0] = base_price
    
    # Generate volume (higher around volatility)
    base_volume = 10000
    volume = (base_volume + np.random.exponential(5000, n_bars)).astype(int)
    
    df = pd.DataFrame({
        'time': timestamps,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volume
    })
    
    return df


def run_backtest(df: pd.DataFrame, train_ratio: float = 0.8):
    """
    Run backtest on the data.
    
    Args:
        df: OHLCV data
        train_ratio: Ratio of data for training (rest for testing)
    """
    logger.info(f"Running backtest on {len(df)} bars")
    
    # Split data
    train_size = int(len(df) * train_ratio)
    train_df = df.iloc[:train_size].copy()
    test_df = df.iloc[train_size:].copy()
    
    logger.info(f"Training on {len(train_df)} bars, testing on {len(test_df)} bars")
    
    # Initialize strategy
    strategy = GoldResearchStrategy(lite_mode=True)
    
    # Train
    logger.info("Training strategy...")
    train_result = strategy.train(train_df)
    
    if train_result.get('status') != 'trained':
        logger.error(f"Training failed: {train_result}")
        return None
    
    logger.info(f"Training complete. R² High: {train_result.get('train_r2_high', 0):.4f}, "
                f"R² Low: {train_result.get('train_r2_low', 0):.4f}")
    
    # Generate signals for test period
    signals = []
    
    logger.info("Generating signals for test period...")
    
    # Use a rolling window for prediction
    buffer_df = train_df.copy()
    
    for i in range(len(test_df)):
        # Add current bar to buffer
        buffer_df = pd.concat([buffer_df, test_df.iloc[i:i+1]], ignore_index=True)
        
        # Keep only recent bars for feature generation
        if len(buffer_df) > 200:
            buffer_df = buffer_df.tail(200).reset_index(drop=True)
        
        # Get current price
        current_price = float(test_df.iloc[i]['close'])
        
        # Generate prediction
        signal, bounds = strategy.run_tick(buffer_df)
        
        # Store result
        signals.append({
            'time': test_df.iloc[i]['time'],
            'open': test_df.iloc[i]['open'],
            'high': test_df.iloc[i]['high'],
            'low': test_df.iloc[i]['low'],
            'close': test_df.iloc[i]['close'],
            'volume': test_df.iloc[i]['volume'],
            'signal': signal,
            'pred_high': bounds.get('pred_high', 0),
            'pred_low': bounds.get('pred_low', 0),
            'current_price': current_price
        })
        
        if (i + 1) % 100 == 0:
            logger.info(f"Processed {i + 1}/{len(test_df)} bars")
    
    # Convert to DataFrame
    signals_df = pd.DataFrame(signals)
    
    # Calculate simple metrics
    buy_signals = (signals_df['signal'] == 'BUY').sum()
    sell_signals = (signals_df['signal'] == 'SELL').sum()
    wait_signals = (signals_df['signal'] == 'WAIT').sum()
    
    logger.info(f"Signal distribution: BUY={buy_signals}, SELL={sell_signals}, WAIT={wait_signals}")
    
    return signals_df


def convert_to_hedge_format(signals_df: pd.DataFrame, output_path: str):
    """
    Convert signals to Hedge EA compatible format.
    
    Expected format: time,action,entry,exit,outcome,pnl_dollars,balance
    """
    trades = []
    position = None
    entry_price = 0
    entry_time = None
    balance = 10000.0  # Starting balance
    
    for i, row in signals_df.iterrows():
        current_time = row['time']
        current_price = row['close']
        
        # Entry logic
        if position is None:
            if row['signal'] == 'BUY':
                position = 'LONG'
                entry_price = current_price
                entry_time = current_time
            elif row['signal'] == 'SELL':
                position = 'SHORT'
                entry_price = current_price
                entry_time = current_time
        # Exit logic
        elif position == 'LONG':
            # Exit on SELL signal or price target reached
            if row['signal'] == 'SELL' or current_price >= row['pred_high']:
                pnl = current_price - entry_price
                balance += pnl
                trades.append({
                    'time': entry_time,
                    'action': 'LONG',
                    'entry': entry_price,
                    'exit': current_price,
                    'outcome': 'WIN' if pnl > 0 else 'LOSS',
                    'pnl_dollars': pnl,
                    'balance': balance
                })
                position = None
                
        elif position == 'SHORT':
            # Exit on BUY signal or price target reached
            if row['signal'] == 'BUY' or current_price <= row['pred_low']:
                pnl = entry_price - current_price
                balance += pnl
                trades.append({
                    'time': entry_time,
                    'action': 'SHORT',
                    'entry': entry_price,
                    'exit': current_price,
                    'outcome': 'WIN' if pnl > 0 else 'LOSS',
                    'pnl_dollars': pnl,
                    'balance': balance
                })
                position = None
    
    # Close any open position at the end
    if position is not None:
        final_price = signals_df.iloc[-1]['close']
        if position == 'LONG':
            pnl = final_price - entry_price
        else:
            pnl = entry_price - final_price
        balance += pnl
        trades.append({
            'time': entry_time,
            'action': position,
            'entry': entry_price,
            'exit': final_price,
            'outcome': 'WIN' if pnl > 0 else 'LOSS',
            'pnl_dollars': pnl,
            'balance': balance
        })
    
    trades_df = pd.DataFrame(trades)
    trades_df.to_csv(output_path, index=False)
    
    logger.info(f"Saved {len(trades)} trades to {output_path}")
    
    # Print summary
    if len(trades_df) > 0:
        wins = (trades_df['outcome'] == 'WIN').sum()
        losses = (trades_df['outcome'] == 'LOSS').sum()
        win_rate = wins / len(trades_df) * 100 if len(trades_df) > 0 else 0
        
        logger.info(f"=== Backtest Summary ===")
        logger.info(f"Total Trades: {len(trades_df)}")
        logger.info(f"Wins: {wins}, Losses: {losses}")
        logger.info(f"Win Rate: {win_rate:.1f}%")
        logger.info(f"Final Balance: ${balance:.2f}")
        logger.info(f"Total PnL: ${balance - 10000:.2f}")
    
    return trades_df


def main():
    """Main entry point."""
    logger.info("=== Gold Research Strategy Backtest ===")
    
    # Load data
    df = load_or_generate_data()
    
    logger.info(f"Loaded {len(df)} bars of data")
    logger.info(f"Date range: {df['time'].min()} to {df['time'].max()}")
    
    # Run backtest
    signals_df = run_backtest(df, train_ratio=0.8)
    
    if signals_df is None:
        logger.error("Backtest failed")
        return
    
    # Save raw signals
    signals_path = "data/gold_research_signals.csv"
    signals_df.to_csv(signals_path, index=False)
    logger.info(f"Raw signals saved to {signals_path}")
    
    # Convert to Hedge EA format
    hedge_path = "data/gold_research_trades.csv"
    trades_df = convert_to_hedge_format(signals_df, hedge_path)
    
    logger.info("=== Backtest Complete ===")
    logger.info(f"Output files:")
    logger.info(f"  - Signals: {signals_path}")
    logger.info(f"  - Trades:  {hedge_path}")


if __name__ == "__main__":
    main()
