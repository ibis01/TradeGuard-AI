"""
TradeGuard AI - Market Intelligence MCP.
Simple, reliable market data fetching with debugging.
"""

import time
import json
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

REQUEST_TIMEOUT = 3.0  # seconds
CACHE_TTL = 3  # seconds

# ============================================================================
# SIMPLE CACHE
# ============================================================================

_cache = {}
_cache_timestamps = {}

def _get_cached(key: str) -> Optional[Any]:
    if key in _cache and key in _cache_timestamps:
        age = time.time() - _cache_timestamps[key]
        if age < CACHE_TTL:
            return _cache[key]
    return None

def _set_cache(key: str, value: Any) -> None:
    _cache[key] = value
    _cache_timestamps[key] = time.time()

def clear_cache():
    _cache.clear()
    _cache_timestamps.clear()
    logger.info("Cache cleared")

# ============================================================================
# BINANCE API - PRIMARY SOURCE
# ============================================================================

def get_binance_price(symbol: str) -> Optional[float]:
    """
    Get price from Binance API.
    This is the PRIMARY source.
    """
    cache_key = f"binance_{symbol}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.info(f"Binance cache hit for {symbol}: ${cached:,.2f}")
        return cached
    
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
        logger.info(f"Fetching Binance price for {symbol}...")
        
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            price = float(data['price'])
            _set_cache(cache_key, price)
            logger.info(f"✅ Binance {symbol}: ${price:,.2f}")
            return price
        else:
            logger.warning(f"Binance returned status {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning(f"⏰ Binance timeout for {symbol}")
        return None
    except requests.exceptions.ConnectionError:
        logger.warning(f"🔌 Binance connection error for {symbol}")
        return None
    except Exception as e:
        logger.warning(f"❌ Binance error: {e}")
        return None

# ============================================================================
# COINBASE API - FALLBACK
# ============================================================================

def get_coinbase_price(symbol: str) -> Optional[float]:
    """
    Get price from Coinbase API.
    FALLBACK source.
    """
    cache_key = f"coinbase_{symbol}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.info(f"Coinbase cache hit for {symbol}: ${cached:,.2f}")
        return cached
    
    try:
        url = f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"
        logger.info(f"Fetching Coinbase price for {symbol}...")
        
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            price = float(data['data']['amount'])
            _set_cache(cache_key, price)
            logger.info(f"✅ Coinbase {symbol}: ${price:,.2f}")
            return price
        else:
            logger.warning(f"Coinbase returned status {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning(f"⏰ Coinbase timeout for {symbol}")
        return None
    except Exception as e:
        logger.warning(f"❌ Coinbase error: {e}")
        return None

# ============================================================================
# KUCOIN API - SECOND FALLBACK
# ============================================================================

def get_kucoin_price(symbol: str) -> Optional[float]:
    """
    Get price from KuCoin API.
    SECOND FALLBACK source.
    """
    cache_key = f"kucoin_{symbol}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.info(f"KuCoin cache hit for {symbol}: ${cached:,.2f}")
        return cached
    
    try:
        url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}-USDT"
        logger.info(f"Fetching KuCoin price for {symbol}...")
        
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == '200000':
                price = float(data['data']['price'])
                _set_cache(cache_key, price)
                logger.info(f"✅ KuCoin {symbol}: ${price:,.2f}")
                return price
        return None
            
    except Exception as e:
        logger.warning(f"❌ KuCoin error: {e}")
        return None

# ============================================================================
# BYBIT API - THIRD FALLBACK
# ============================================================================

def get_bybit_price(symbol: str) -> Optional[float]:
    """
    Get price from Bybit API.
    THIRD FALLBACK source.
    """
    cache_key = f"bybit_{symbol}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.info(f"Bybit cache hit for {symbol}: ${cached:,.2f}")
        return cached
    
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}USDT"
        logger.info(f"Fetching Bybit price for {symbol}...")
        
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('retCode') == 0:
                result_list = data.get('result', {}).get('list', [])
                if result_list:
                    price = float(result_list[0]['lastPrice'])
                    _set_cache(cache_key, price)
                    logger.info(f"✅ Bybit {symbol}: ${price:,.2f}")
                    return price
        return None
            
    except Exception as e:
        logger.warning(f"❌ Bybit error: {e}")
        return None

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def get_live_market_data(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get live market data with fallbacks.
    Returns None if all providers fail.
    """
    cache_key = f"live_{symbol}"
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    # Try providers in order
    providers = [
        ("Binance", get_binance_price),
        ("Coinbase", get_coinbase_price),
        ("KuCoin", get_kucoin_price),
        ("Bybit", get_bybit_price),
    ]
    
    for name, fetcher in providers:
        price = fetcher(symbol)
        if price is not None:
            result = {
                "ok": True,
                "last_close": price,
                "exchange": name,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "source": "live"
            }
            _set_cache(cache_key, result)
            logger.info(f"✅ Got {symbol} price from {name}: ${price:,.2f}")
            return result
    
    # All providers failed
    logger.error(f"❌ All providers failed for {symbol}")
    return None

# ============================================================================
# TECHNICAL ANALYSIS
# ============================================================================

def analyze_technicals_fast(symbol: str) -> Dict[str, Any]:
    """Fast technical analysis using real data."""
    cache_key = f"tech_{symbol}"
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    price_data = get_live_market_data(symbol)
    
    if not price_data:
        result = {
            "ok": False,
            "symbol": symbol,
            "error": "No market data available",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        _set_cache(cache_key, result)
        return result
    
    # Try to get klines
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1h&limit=20"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            closes = [float(candle[4]) for candle in data]
            
            if len(closes) >= 10:
                last = closes[-1]
                sma_10 = sum(closes[-10:]) / 10
                
                if last > sma_10 * 1.01:
                    trend = "Bullish"
                elif last < sma_10 * 0.99:
                    trend = "Bearish"
                else:
                    trend = "Neutral"
                
                result = {
                    "ok": True,
                    "symbol": symbol,
                    "last_close": last,
                    "trend": trend,
                    "signal": "Buy" if trend == "Bullish" else "Sell" if trend == "Bearish" else "Neutral",
                    "rsi": 50.0,
                    "exchange": "Binance",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                _set_cache(cache_key, result)
                return result
    except Exception as e:
        logger.warning(f"Technical analysis error: {e}")
    
    # Fallback: just return price
    result = {
        "ok": True,
        "symbol": symbol,
        "last_close": price_data.get("last_close", 0),
        "trend": "Neutral",
        "signal": "Neutral",
        "rsi": 50.0,
        "exchange": price_data.get("exchange", "Unknown"),
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }
    
    _set_cache(cache_key, result)
    return result

async def analyze_technicals(symbol: str, **kwargs) -> Dict[str, Any]:
    """Async wrapper."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_technicals_fast, symbol)

# ============================================================================
# HEALTH CHECK
# ============================================================================

def check_market_data_health() -> Dict[str, Any]:
    """Check if market data is available."""
    result = get_live_market_data("BTC")
    
    if result:
        return {
            "status": "healthy",
            "price": result.get("last_close"),
            "exchange": result.get("exchange"),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
    else:
        return {
            "status": "unhealthy",
            "price": None,
            "exchange": None,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

def diagnose_connection() -> Dict[str, Any]:
    """Diagnose connection issues."""
    results = {}
    
    # Test each provider
    providers = [
        ("Binance", "https://api.binance.com/api/v3/ping"),
        ("Coinbase", "https://api.coinbase.com/v2/prices/BTC-USD/spot"),
        ("KuCoin", "https://api.kucoin.com/api/v1/timestamp"),
        ("Bybit", "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT"),
    ]
    
    for name, url in providers:
        try:
            start = time.time()
            response = requests.get(url, timeout=2.0)
            elapsed = (time.time() - start) * 1000
            
            results[name] = {
                "reachable": response.status_code == 200,
                "status_code": response.status_code,
                "latency_ms": round(elapsed, 2)
            }
        except Exception as e:
            results[name] = {
                "reachable": False,
                "status_code": None,
                "latency_ms": None,
                "error": str(e)
            }
    
    reachable = [n for n, r in results.items() if r.get("reachable")]
    
    return {
        "internet_connection": bool(reachable),
        "reachable_providers": reachable,
        "providers": results,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

# ============================================================================
# SELF-TEST
# ============================================================================

if __name__ == "__main__":
    print("🧪 Testing Market Intelligence...")
    print("=" * 50)
    
    # First run diagnostics
    print("\n📡 Connection Diagnostics:")
    diag = diagnose_connection()
    print(f"  Internet: {'✅' if diag['internet_connection'] else '❌'}")
    print(f"  Reachable providers: {diag['reachable_providers']}")
    
    for provider, data in diag['providers'].items():
        if data.get('reachable'):
            print(f"    ✅ {provider}: {data.get('latency_ms', 0)}ms")
        else:
            print(f"    ❌ {provider}: {data.get('error', 'unreachable')}")
    
    # Test each symbol
    print("\n" + "=" * 50)
    print("Testing price fetch...")
    
    for symbol in ["BTC", "ETH", "SOL"]:
        print(f"\n📊 Fetching {symbol}...")
        result = get_live_market_data(symbol)
        
        if result:
            print(f"  ✅ ${result['last_close']:,.2f} from {result['exchange']}")
        else:
            print(f"  ❌ No data available")
    
    print("\n✅ Tests complete!")