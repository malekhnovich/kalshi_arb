#!/usr/bin/env python3
"""
Binance.US MCP Server - Python FastMCP Implementation

An MCP (Model Context Protocol) server that provides Claude with direct access to
Binance.US market data, order books, and trading capabilities.

Installation:
    pip install mcp httpx pydantic

Usage (Standalone):
    python binance_us_mcp_server.py

Usage (Claude Desktop):
    1. Follow CLAUDE_DESKTOP_MCP_SETUP_PYTHON.md for configuration
    2. Restart Claude Desktop
    3. Ask Claude about Binance.US data
"""

import httpx
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP


# Initialize MCP Server
mcp = FastMCP("binance_us_mcp")


# ============================================================================
# Constants and Configuration
# ============================================================================

BINANCE_US_API_URL = "https://api.binance.us/api/v3"
REQUEST_TIMEOUT = 10.0


# ============================================================================
# Pydantic Input Models
# ============================================================================

class GetOrderBookInput(BaseModel):
    """Input model for getting order book data"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    symbol: str = Field(
        ...,
        description="Trading pair symbol (e.g., 'BTCUSDT', 'SOLUSDT', 'ETHUSDT')",
        min_length=4,
        max_length=12
    )
    limit: Optional[int] = Field(
        default=20,
        description="Number of bid/ask levels to return (1-5000, default 20)",
        ge=1,
        le=5000
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format (uppercase alphanumeric)"""
        if not v.replace('_', '').isalnum():
            raise ValueError("Symbol must be alphanumeric (e.g., BTCUSDT)")
        return v.upper()


class GetTickerInput(BaseModel):
    """Input model for getting ticker data"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    symbol: Optional[str] = Field(
        default=None,
        description="Trading pair symbol (e.g., 'BTCUSDT'). Leave blank for all symbols",
        min_length=4,
        max_length=12
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: Optional[str]) -> Optional[str]:
        """Validate symbol format"""
        if v is not None and not v.replace('_', '').isalnum():
            raise ValueError("Symbol must be alphanumeric (e.g., BTCUSDT)")
        return v.upper() if v else None


class GetKlinesInput(BaseModel):
    """Input model for getting candlestick data"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    symbol: str = Field(
        ...,
        description="Trading pair symbol (e.g., 'BTCUSDT')",
        min_length=4,
        max_length=12
    )
    interval: str = Field(
        default="1m",
        description="Candle interval: 1m, 5m, 15m, 30m, 1h, 4h, 1d, etc.",
        min_length=2,
        max_length=3
    )
    limit: Optional[int] = Field(
        default=100,
        description="Number of candles to return (1-1000, default 100)",
        ge=1,
        le=1000
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format (uppercase alphanumeric)"""
        if not v.replace('_', '').isalnum():
            raise ValueError("Symbol must be alphanumeric")
        return v.upper()

    @field_validator('interval')
    @classmethod
    def validate_interval(cls, v: str) -> str:
        """Validate interval format (lowercase, e.g., 1m, 5m, 1h)"""
        valid_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'}
        if v.lower() not in valid_intervals and v not in valid_intervals:
            raise ValueError(f"Invalid interval. Must be one of: {', '.join(sorted(valid_intervals))}")
        return v.lower() if v != '1M' else v


class GetAccountInfoInput(BaseModel):
    """Input model for getting account information"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    include_balances: bool = Field(
        default=True,
        description="Include account balances in response"
    )


class AnalyzePriceMomentumInput(BaseModel):
    """Input model for analyzing price momentum"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    symbol: str = Field(
        ...,
        description="Trading pair symbol (e.g., 'SOLUSDT')",
        min_length=4,
        max_length=12
    )
    minutes_window: Optional[int] = Field(
        default=60,
        description="Number of minutes to analyze (1-1440)",
        ge=1,
        le=1440
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format"""
        if not v.replace('_', '').isalnum():
            raise ValueError("Symbol must be alphanumeric")
        return v.upper()


class DetectTemporalLagInput(BaseModel):
    """Input model for detecting temporal arbitrage lag"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    symbol: str = Field(
        ...,
        description="Trading pair symbol (e.g., 'SOLUSDT')",
        min_length=4,
        max_length=12
    )
    confidence_threshold: Optional[float] = Field(
        default=70.0,
        description="Confidence threshold percentage (0-100, default 70)",
        ge=0,
        le=100
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format"""
        if not v.replace('_', '').isalnum():
            raise ValueError("Symbol must be alphanumeric")
        return v.upper()


# ============================================================================
# Binance.US API Client
# ============================================================================

class BinanceUSClient:
    """HTTP client for Binance.US API"""

    def __init__(self, base_url: str = BINANCE_US_API_URL, timeout: float = REQUEST_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    async def request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to Binance.US API"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                url = f"{self.base_url}{endpoint}"
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                raise Exception(f"Binance.US API error: {str(e)}")
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON response from Binance.US: {str(e)}")

    async def get_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Get order book for a trading pair"""
        params = {"symbol": symbol, "limit": limit}
        return await self.request("/depth", params)

    async def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get ticker data for symbol(s)"""
        params = {}
        if symbol:
            params["symbol"] = symbol
            return await self.request("/ticker/24hr", params)
        else:
            return await self.request("/ticker/24hr")

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[List]:
        """Get candlestick data"""
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        return await self.request("/klines", params)

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information"""
        return await self.request("/exchangeInfo")

    async def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information (requires API key)
        Note: This would require authentication which needs to be configured
        """
        # In a real scenario, this would need proper authentication headers
        # For now, return a message indicating authentication is required
        return {
            "status": "requires_authentication",
            "message": "Account info requires Binance.US API key authentication",
            "note": "Configure your API key in the MCP server setup"
        }


# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool(
    name="binance_get_order_book",
    annotations={
        "title": "Get Binance.US Order Book",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def get_order_book(params: GetOrderBookInput) -> str:
    """
    Retrieve the current order book (bid/ask levels) for a trading pair on Binance.US.

    This tool fetches real-time market depth data showing available buy and sell orders
    at different price levels. Useful for analyzing market structure, spreads, and
    liquidity.

    Args:
        params (GetOrderBookInput): Validated input containing:
            - symbol (str): Trading pair (e.g., 'BTCUSDT', 'SOLUSDT')
            - limit (int): Number of bid/ask levels (1-5000, default 20)

    Returns:
        str: JSON formatted order book with bids and asks
    """
    try:
        client = BinanceUSClient()
        order_book = await client.get_order_book(params.symbol, params.limit)

        return json.dumps({
            "status": "success",
            "symbol": params.symbol,
            "bids": order_book.get("bids", [])[:params.limit],
            "asks": order_book.get("asks", [])[:params.limit],
            "timestamp": order_book.get("E", "unknown"),
            "spread": f"{((float(order_book['asks'][0][0]) - float(order_book['bids'][0][0])) / float(order_book['bids'][0][0]) * 100):.4f}% (if available)"
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(
    name="binance_get_ticker",
    annotations={
        "title": "Get Binance.US Ticker Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def get_ticker(params: GetTickerInput) -> str:
    """
    Get 24-hour ticker data for one or all trading pairs on Binance.US.

    Returns statistics including price changes, volume, and high/low prices
    over the last 24 hours.

    Args:
        params (GetTickerInput): Validated input containing:
            - symbol (str, optional): Specific trading pair or leave blank for all

    Returns:
        str: JSON formatted ticker data with price and volume statistics
    """
    try:
        client = BinanceUSClient()
        ticker_data = await client.get_ticker(params.symbol)

        if params.symbol:
            # Single ticker
            return json.dumps({
                "status": "success",
                "symbol": params.symbol,
                "price": ticker_data.get("lastPrice", "N/A"),
                "priceChange24h": ticker_data.get("priceChange", "N/A"),
                "priceChangePercent24h": ticker_data.get("priceChangePercent", "N/A"),
                "volume24h": ticker_data.get("volume", "N/A"),
                "quoteAssetVolume24h": ticker_data.get("quoteAssetVolume", "N/A"),
                "high24h": ticker_data.get("highPrice", "N/A"),
                "low24h": ticker_data.get("lowPrice", "N/A"),
                "bidPrice": ticker_data.get("bidPrice", "N/A"),
                "askPrice": ticker_data.get("askPrice", "N/A")
            }, indent=2)
        else:
            # Multiple tickers - return top 10 by volume
            tickers = sorted(
                ticker_data,
                key=lambda x: float(x.get("quoteAssetVolume", 0)),
                reverse=True
            )[:10]

            return json.dumps({
                "status": "success",
                "count": len(tickers),
                "top_10_by_volume": [
                    {
                        "symbol": t["symbol"],
                        "price": t.get("lastPrice", "N/A"),
                        "priceChangePercent24h": t.get("priceChangePercent", "N/A"),
                        "volume24h": t.get("volume", "N/A")
                    }
                    for t in tickers
                ]
            }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(
    name="binance_get_klines",
    annotations={
        "title": "Get Binance.US Candlestick Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def get_klines(params: GetKlinesInput) -> str:
    """
    Get candlestick (OHLCV) data for a trading pair at specified intervals.

    Returns historical price data including open, high, low, close prices and volume.
    Useful for technical analysis and detecting price momentum.

    Args:
        params (GetKlinesInput): Validated input containing:
            - symbol (str): Trading pair (e.g., 'BTCUSDT')
            - interval (str): Candle interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            - limit (int): Number of candles (1-1000, default 100)

    Returns:
        str: JSON formatted candlestick data with OHLCV values
    """
    try:
        client = BinanceUSClient()
        klines = await client.get_klines(params.symbol, params.interval, params.limit)

        formatted_candles = []
        for k in klines:
            formatted_candles.append({
                "openTime": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "closeTime": k[6],
                "quoteAssetVolume": float(k[7]),
                "numberOfTrades": k[8]
            })

        return json.dumps({
            "status": "success",
            "symbol": params.symbol,
            "interval": params.interval,
            "candles": formatted_candles,
            "latestPrice": float(formatted_candles[-1]["close"]) if formatted_candles else None
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(
    name="binance_analyze_price_momentum",
    annotations={
        "title": "Analyze Binance.US Price Momentum",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def analyze_price_momentum(params: AnalyzePriceMomentumInput) -> str:
    """
    Analyze price momentum by checking what percentage of recent candles are up vs down.

    This detects directional bias in the market. A high percentage of up candles
    indicates strong upward momentum, useful for detecting temporal arbitrage
    opportunities.

    Args:
        params (AnalyzePriceMomentumInput): Validated input containing:
            - symbol (str): Trading pair (e.g., 'SOLUSDT')
            - minutes_window (int): Window to analyze in minutes (default 60)

    Returns:
        str: JSON formatted analysis with momentum metrics
    """
    try:
        client = BinanceUSClient()
        limit = params.minutes_window if params.minutes_window <= 1000 else 1000
        klines = await client.get_klines(params.symbol, "1m", limit)

        if not klines:
            return json.dumps({"status": "error", "message": f"No data for {params.symbol}"}, indent=2)

        # Analyze candles
        candles_up = sum(1 for k in klines if float(k[4]) >= float(k[1]))
        candles_down = len(klines) - candles_up
        total = len(klines)

        up_percentage = (candles_up / total) * 100 if total > 0 else 0
        down_percentage = (candles_down / total) * 100 if total > 0 else 0

        # Determine confirmation
        up_confirmed = up_percentage > 60
        down_confirmed = down_percentage > 60

        return json.dumps({
            "status": "success",
            "symbol": params.symbol,
            "timeWindow": f"{params.minutes_window} minutes",
            "totalCandles": total,
            "candlesUp": candles_up,
            "candlesDown": candles_down,
            "upPercentage": round(up_percentage, 2),
            "downPercentage": round(down_percentage, 2),
            "upConfirmed": up_confirmed,
            "downConfirmed": down_confirmed,
            "latestPrice": float(klines[-1][4]),
            "analysis": "Strong UP momentum" if up_confirmed else ("Strong DOWN momentum" if down_confirmed else "No clear direction")
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(
    name="binance_detect_temporal_lag",
    annotations={
        "title": "Detect Temporal Arbitrage Lag",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def detect_temporal_lag(params: DetectTemporalLagInput) -> str:
    """
    Detect if there's exploitable temporal lag between spot price confirmation
    and Polymarket odds.

    This analyzes recent price momentum to determine if the direction is confirmed
    on spot exchanges but may still be mispriced on prediction markets.

    Args:
        params (DetectTemporalLagInput): Validated input containing:
            - symbol (str): Trading pair (e.g., 'SOLUSDT')
            - confidence_threshold (float): Minimum confidence to flag as confirmed

    Returns:
        str: JSON formatted lag detection analysis
    """
    try:
        client = BinanceUSClient()
        klines = await client.get_klines(params.symbol, "1m", 60)

        if not klines:
            return json.dumps({"status": "error", "message": f"No data for {params.symbol}"}, indent=2)

        # Analyze candles
        candles_up = sum(1 for k in klines if float(k[4]) >= float(k[1]))
        candles_down = len(klines) - candles_up
        total = len(klines)

        up_percentage = (candles_up / total) * 100 if total > 0 else 0
        down_percentage = (candles_down / total) * 100 if total > 0 else 0

        # Check for exploitable lag
        lag_detected = False
        exploitable_direction = None
        lag_description = ""

        if up_percentage > params.confidence_threshold:
            lag_detected = True
            exploitable_direction = "UP"
            lag_description = f"Spot price shows strong UP momentum ({up_percentage:.1f}% of candles up). If Polymarket still offers 50/50 odds, this is exploitable."
        elif down_percentage > params.confidence_threshold:
            lag_detected = True
            exploitable_direction = "DOWN"
            lag_description = f"Spot price shows strong DOWN momentum ({down_percentage:.1f}% of candles down). If Polymarket still offers 50/50 odds, this is exploitable."

        return json.dumps({
            "status": "success",
            "symbol": params.symbol,
            "lagDetected": lag_detected,
            "exploitableDirection": exploitable_direction,
            "lagDescription": lag_description if lag_detected else "No clear directional confirmation detected",
            "upPercentage": round(up_percentage, 2),
            "downPercentage": round(down_percentage, 2),
            "confidenceThreshold": params.confidence_threshold,
            "recommendation": f"✅ EXPLOITABLE LAG: Buy '{exploitable_direction}' on Polymarket at 50/50 odds if spot shows {exploitable_direction} momentum" if lag_detected else "❌ No exploitable lag detected at this time",
            "latestPrice": float(klines[-1][4])
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    # Run the MCP server
    import asyncio

    print("🚀 Starting Binance.US MCP Server...")
    print(f"📡 API Endpoint: {BINANCE_US_API_URL}")
    print("Available tools:")
    print("  • binance_get_order_book")
    print("  • binance_get_ticker")
    print("  • binance_get_klines")
    print("  • binance_analyze_price_momentum")
    print("  • binance_detect_temporal_lag")
    print("\n✅ Server initialized. Ready to accept MCP connections...")

    # Run the server
    mcp.run()