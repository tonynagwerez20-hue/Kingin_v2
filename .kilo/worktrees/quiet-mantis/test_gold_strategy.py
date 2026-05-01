"""Quick test script for Gold Research Strategy training."""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import strategy
from Engine.igof.layers.gold_research import GoldResearchStrategy

def load_data():
    """Load the XAUUSD data."""
    data_path = "data/XAUUSDm_H1_202401012300_202603032000.csv"
    
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path, sep='\t')
    
    # Parse date and time
    df['time'] = pd.to_datetime(df['<DATE>'] + ' ' + df['<TIME>'], format='%Y.%m.%d %H:%M:%S')
    df = df.rename(columns={
        '<OPEN>': 'open',
        '<HIGH>': 'high', 
        '<LOW>': 'low',
        '<CLOSE>': 'close',
        '<TICKVOL>': 'volume'
    })
    df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
    
    print(f"Loaded {len(df)} bars")
    return df

def main():
    print("=" * 50)
    print("Testing Gold Research Strategy")
    print("=" * 50)
    
    # Load data
    df = load_data()
    
    # Use smaller subset for quick test
    df = df.head(2000)
    print(f"Using {len(df)} bars for test")
    
    # Split: 80% train, 20% test
    train_size = int(len(df) * 0.8)
    train_df = df.iloc[:train_size].copy()
    test_df = df.iloc[train_size:].copy()
    
    print(f"Training on {len(train_df)} bars...")
    
    # Initialize strategy
    strategy = GoldResearchStrategy(lite_mode=True)
    
    # Train
    print("Training...")
    train_result = strategy.train(train_df)
    
    print(f"Train result: {train_result}")
    
    if train_result.get('status') == 'trained':
        print(f"Training R² High: {train_result.get('train_r2_high', 0):.4f}")
        print("Training SUCCESS!")
        
        # Generate a few signals
        print("\nGenerating test signals...")
        buffer_df = train_df.copy()
        
        for i in range(5):
            buffer_df = pd.concat([buffer_df, test_df.iloc[i:i+1]], ignore_index=True)
            if len(buffer_df) > 100:
                buffer_df = buffer_df.tail(100).reset_index(drop=True)
            
            signal, bounds = strategy.run_tick(buffer_df)
            print(f"  Bar {i}: signal={signal}, price={bounds.get('current_price', 0):.2f}")
        
        print("\nTest completed successfully!")
    else:
        print(f"Training failed: {train_result}")

if __name__ == "__main__":
    main()
