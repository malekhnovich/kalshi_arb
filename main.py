#!/usr/bin/env python3
"""
Binance.US Bot Trade Analyzer
Fetches historical Binance.US candle data and correlates with Polymarket bot trades
to detect temporal arbitrage patterns.

Usage:
    python3 binance_bot_analyzer.py --symbol SOLUSDT --date 2026-01-12 --hour 22
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import argparse
from typing import List, Dict, Tuple

class BinanceAnalyzer:
    """Analyze Binance.US price movements vs Polymarket trading patterns"""
    
    BASE_URL = "https://api.binance.us/api/v3"
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_klines(self, symbol: str, interval: str = "1m", limit: int = 120) -> List[List]:
        """
        Fetch klines (candlestick data) from Binance
        
        Args:
            symbol: Trading pair (e.g., "SOLUSDT", "BTCUSDT")
            interval: Candle interval (1m, 5m, 1h)
            limit: Number of candles to fetch
        
        Returns:
            List of klines with OHLCV data
        """
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        try:
            response = self.session.get(f"{self.BASE_URL}/klines", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching klines: {e}")
            return []
    
    def get_historical_klines(self, symbol: str, start_time: int, end_time: int, 
                             interval: str = "1m") -> List[List]:
        """
        Fetch historical klines for a specific time range
        
        Args:
            symbol: Trading pair
            start_time: Unix timestamp in milliseconds
            end_time: Unix timestamp in milliseconds
            interval: Candle interval
        
        Returns:
            List of klines within the time range
        """
        all_klines = []
        current_time = start_time
        
        while current_time < end_time:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_time,
                "endTime": end_time,
                "limit": 1000
            }
            
            try:
                response = self.session.get(f"{self.BASE_URL}/klines", params=params)
                response.raise_for_status()
                klines = response.json()
                
                if not klines:
                    break
                
                all_klines.extend(klines)
                current_time = klines[-1][0] + 60000  # Move to next minute
                
            except requests.exceptions.RequestException as e:
                print(f"❌ Error fetching historical klines: {e}")
                break
        
        return all_klines
    
    def analyze_price_momentum(self, symbol: str, minutes_before_trade: int = 10,
                               minutes_after_trade: int = 5) -> Dict:
        """
        Analyze price momentum in the critical window before/after bot trade
        
        Args:
            symbol: Trading pair
            minutes_before_trade: How many minutes before trade to analyze
            minutes_after_trade: How many minutes after trade to analyze
        
        Returns:
            Dict with analysis results
        """
        # Fetch 1-minute candles
        klines = self.get_klines(symbol, interval="1m", limit=minutes_before_trade + minutes_after_trade + 10)
        
        if not klines:
            return {"error": "Could not fetch candle data"}
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        # Convert to numeric
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        
        # Convert timestamps
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        
        return {
            "symbol": symbol,
            "total_candles": len(df),
            "time_range": f"{df['timestamp'].min()} to {df['timestamp'].max()}",
            "latest_price": float(df['close'].iloc[-1]),
            "latest_volume": float(df['volume'].iloc[-1]),
            "data": df.to_dict('records')
        }
    
    def detect_price_confirmation(self, symbol: str, direction: str = "UP") -> Dict:
        """
        Detect if price has "confirmed" momentum (moved decisively in one direction)
        
        Args:
            symbol: Trading pair
            direction: "UP" or "DOWN"
        
        Returns:
            Dict with confirmation analysis
        """
        klines = self.get_klines(symbol, interval="1m", limit=60)
        
        if not klines:
            return {"error": "Could not fetch data"}
        
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        df['open'] = pd.to_numeric(df['open'])
        df['close'] = pd.to_numeric(df['close'])
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        
        # Calculate momentum metrics
        candles_up = (df['close'] >= df['open']).sum()
        candles_down = (df['close'] < df['open']).sum()
        total_candles = len(df)
        
        # Check if direction is confirmed
        if direction.upper() == "UP":
            confirmation = (candles_up / total_candles) > 0.6
            confidence = (candles_up / total_candles) * 100
        else:
            confirmation = (candles_down / total_candles) > 0.6
            confidence = (candles_down / total_candles) * 100
        
        return {
            "symbol": symbol,
            "direction": direction,
            "candles_up": candles_up,
            "candles_down": candles_down,
            "up_percentage": (candles_up / total_candles) * 100,
            "down_percentage": (candles_down / total_candles) * 100,
            "is_confirmed": confirmation,
            "confidence_percentage": confidence,
            "latest_price": float(df['close'].iloc[-1]),
            "time_range": f"{df['timestamp'].min()} to {df['timestamp'].max()}"
        }
    
    def calculate_lag_window(self, symbol: str, polymarket_entry_time: str) -> Dict:
        """
        Calculate if there's a lag between spot price confirmation and market pricing
        
        Args:
            symbol: Trading pair
            polymarket_entry_time: ISO format time of Polymarket entry
        
        Returns:
            Analysis of the lag window
        """
        analysis = self.detect_price_confirmation(symbol)
        
        return {
            "symbol": symbol,
            "polymarket_entry_time": polymarket_entry_time,
            "spot_confirmation": analysis,
            "lag_analysis": {
                "description": "If spot price confirmed direction but Polymarket still offering 50/50 odds, there's exploitable lag",
                "confirmed": analysis.get("is_confirmed", False),
                "confidence": analysis.get("confidence_percentage", 0)
            }
        }

def format_output(data: Dict) -> str:
    """Pretty print analysis results"""
    return json.dumps(data, indent=2, default=str)

def main():
    parser = argparse.ArgumentParser(
        description="Analyze Binance price movements vs bot trading patterns"
    )
    parser.add_argument("--symbol", default="SOLUSDT", help="Trading pair (default: SOLUSDT)")
    parser.add_argument("--date", help="Date for analysis (YYYY-MM-DD)")
    parser.add_argument("--hour", type=int, help="Hour for analysis (0-23)")
    parser.add_argument("--detect-lag", action="store_true", help="Detect temporal arbitrage lag")
    
    args = parser.parse_args()
    
    analyzer = BinanceAnalyzer()
    
    print(f"\n🤖 Binance.US Bot Trade Analyzer")
    print(f"{'='*50}")
    print(f"Symbol: {args.symbol}")
    
    # Fetch current price momentum
    print(f"\n📊 Analyzing current price momentum...")
    momentum = analyzer.analyze_price_momentum(args.symbol, minutes_before_trade=10)
    print(f"Total candles: {momentum['total_candles']}")
    print(f"Latest price: ${momentum['latest_price']}")
    print(f"Time range: {momentum['time_range']}")
    
    # Detect if price is confirmed
    print(f"\n🔍 Detecting price confirmation...")
    up_analysis = analyzer.detect_price_confirmation(args.symbol, direction="UP")
    down_analysis = analyzer.detect_price_confirmation(args.symbol, direction="DOWN")
    
    print(f"\nUP direction:")
    print(f"  - Candles up: {up_analysis['candles_up']} ({up_analysis['up_percentage']:.1f}%)")
    print(f"  - Confirmed: {up_analysis['is_confirmed']}")
    
    print(f"\nDOWN direction:")
    print(f"  - Candles down: {down_analysis['candles_down']} ({down_analysis['down_percentage']:.1f}%)")
    print(f"  - Confirmed: {down_analysis['is_confirmed']}")
    
    # Temporal lag analysis
    if args.detect_lag:
        print(f"\n⏱️  Analyzing temporal arbitrage lag...")
        lag_window = analyzer.calculate_lag_window(args.symbol, datetime.now().isoformat())
        print(f"\nLag Analysis:")
        print(f"  - Spot price confirmed: {lag_window['lag_analysis']['confirmed']}")
        print(f"  - Confidence: {lag_window['lag_analysis']['confidence']:.1f}%")
        if lag_window['lag_analysis']['confirmed'] and lag_window['lag_analysis']['confidence'] > 70:
            print(f"  ✅ EXPLOITABLE LAG DETECTED: Spot has confirmed direction, market may still be mispriced")
        else:
            print(f"  ❌ No clear lag detected")
    
    print(f"\n{'='*50}\n")

if __name__ == "__main__":
    main()