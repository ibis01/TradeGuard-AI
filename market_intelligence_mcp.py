"""
TradeGuard AI - Market Intelligence MCP (Enhanced with Recommendation Reasons).
Accurate technical analysis with 100 candles and detailed reasoning.
"""

import time
import logging
import requests
import concurrent.futures
from typing import Dict, Any, Optional, List
from datetime import datetime
import math

# Import risk management constants and balance fetcher
from risk_management_mcp import (
    get_portfolio_balance,
    MAX_RISK_PERCENT,
    MAX_POSITION_PCT,
    MIN_STOP_DISTANCE,
    evaluate_trade_risk
)
# Import guardrails for exposure check
from guardrails_mcp import check_exposure_limit, MAX_OPEN_EXPOSURE

# ============================================================================
# CONFIGURATION
# ============================================================================

REQUEST_TIMEOUT = 2.0
CACHE_TTL = 30
KLINES_LIMIT = 100

# ---- Use a slightly larger minimum stop to avoid floating-point issues ----
STOP_BUFFER = 0.006  # 0.6% (safety margin above risk engine's 0.5%)

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ============================================================================
# CACHE
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

# ============================================================================
# PRICE FETCHERS (parallel)
# ============================================================================

def _fetch_binance(symbol: str) -> Optional[float]:
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return float(resp.json()['price'])
    except:
        pass
    return None

def _fetch_coinbase(symbol: str) -> Optional[float]:
    try:
        url = f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return float(resp.json()['data']['amount'])
    except:
        pass
    return None

def _fetch_kraken(symbol: str) -> Optional[float]:
    try:
        kraken_symbol = "XBT" if symbol == "BTC" else symbol
        url = f"https://api.kraken.com/0/public/Ticker?pair={kraken_symbol}USD"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            pair_key = list(data['result'].keys())[0]
            return float(data['result'][pair_key]['c'][0])
    except:
        pass
    return None

def _fetch_kucoin(symbol: str) -> Optional[float]:
    try:
        url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}-USDT"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == '200000':
                return float(data['data']['price'])
    except:
        pass
    return None

def _fetch_bybit(symbol: str) -> Optional[float]:
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}USDT"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('retCode') == 0:
                lst = data.get('result', {}).get('list', [])
                if lst:
                    return float(lst[0]['lastPrice'])
    except:
        pass
    return None

def _fetch_coingecko(symbol: str) -> Optional[float]:
    ids = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
    coin_id = ids.get(symbol.upper())
    if not coin_id:
        return None
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            return float(data[coin_id]["usd"])
    except:
        pass
    return None

def get_live_market_data(symbol: str) -> Optional[Dict[str, Any]]:
    cache_key = f"price_{symbol}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    fetchers = [
        _fetch_binance,
        _fetch_coinbase,
        _fetch_kraken,
        _fetch_kucoin,
        _fetch_bybit,
        _fetch_coingecko,
    ]

    price = None
    exchange = "Unknown"

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        future_to_name = {
            executor.submit(f, symbol): f.__name__.replace('_fetch_', '').capitalize()
            for f in fetchers
        }
        for future in concurrent.futures.as_completed(future_to_name, timeout=REQUEST_TIMEOUT + 0.5):
            try:
                p = future.result()
                if p is not None:
                    price = p
                    exchange = future_to_name[future]
                    break
            except:
                continue

    if price is None:
        return None

    result = {
        "ok": True,
        "last_close": price,
        "exchange": exchange,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "source": "live"
    }
    _set_cache(cache_key, result)
    return result

# ============================================================================
# ACCURATE INDICATORS
# ============================================================================

def _sma(data: list, period: int) -> float:
    if len(data) < period:
        return 0.0
    return sum(data[-period:]) / period

def _ema(data: list, period: int) -> float:
    if len(data) < period:
        return 0.0
    multiplier = 2.0 / (period + 1)
    ema = data[-period]
    for p in data[-period + 1:]:
        ema = (p * multiplier) + (ema * (1 - multiplier))
    return ema

def _rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def _macd_series(closes: list, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
    if len(closes) < slow:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    macd_vals = []
    for i in range(slow, len(closes)):
        ema_f = _ema(closes[:i+1], fast)
        ema_s = _ema(closes[:i+1], slow)
        macd_vals.append(ema_f - ema_s)
    if not macd_vals:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    macd_current = macd_vals[-1]
    signal_line = _ema(macd_vals, signal) if len(macd_vals) >= signal else macd_current
    histogram = macd_current - signal_line
    return {
        "macd": round(macd_current, 4),
        "signal": round(signal_line, 4),
        "histogram": round(histogram, 4)
    }

def _bollinger_bands(closes: list, period: int = 20, std_dev: float = 2.0) -> Dict[str, float]:
    if len(closes) < period:
        return {"upper": 0.0, "middle": 0.0, "lower": 0.0}
    mid = _sma(closes, period)
    variance = sum((x - mid) ** 2 for x in closes[-period:]) / period
    std = math.sqrt(variance)
    return {
        "upper": round(mid + std_dev * std, 2),
        "middle": round(mid, 2),
        "lower": round(mid - std_dev * std, 2)
    }

def _stochastic_rsi(closes: list, period: int = 14) -> Dict[str, float]:
    if len(closes) < period:
        return {"k": 50.0, "d": 50.0}
    rsi_vals = []
    for i in range(period, len(closes)):
        rsi_vals.append(_rsi(closes[:i+1], period))
    if len(rsi_vals) < period:
        return {"k": 50.0, "d": 50.0}
    high = max(rsi_vals[-period:])
    low = min(rsi_vals[-period:])
    if high == low:
        k = 50.0
    else:
        k = ((rsi_vals[-1] - low) / (high - low)) * 100
    d = _sma(rsi_vals[-3:], 3) if len(rsi_vals) >= 3 else k
    return {"k": round(k, 2), "d": round(d, 2)}

def _atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 0.0
    tr = []
    for i in range(1, len(closes)):
        h = highs[i]
        l = lows[i]
        prev_c = closes[i-1]
        tr.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return sum(tr[-period:]) / period if tr else 0.0

def _compute_indicators(klines: List[Dict]) -> Dict[str, Any]:
    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    length = len(closes)

    if length < 14:
        return {"error": "Insufficient data"}

    sma_10 = _sma(closes, 10)
    sma_20 = _sma(closes, 20)
    sma_50 = _sma(closes, 50) if length >= 50 else sma_20
    sma_200 = _sma(closes, 200) if length >= 200 else sma_50
    ema_9 = _ema(closes, 9)
    ema_21 = _ema(closes, 21)
    ema_50 = _ema(closes, 50) if length >= 50 else ema_21
    rsi = _rsi(closes)
    macd = _macd_series(closes)
    bb = _bollinger_bands(closes)
    stoch = _stochastic_rsi(closes)
    atr_val = _atr(highs, lows, closes)
    support = min(lows[-20:]) if len(lows) >= 20 else None
    resistance = max(highs[-20:]) if len(highs) >= 20 else None
    volatility = (max(highs[-20:]) - min(lows[-20:])) / sma_20 * 100 if sma_20 > 0 else 0.0

    return {
        "sma_10": round(sma_10, 2),
        "sma_20": round(sma_20, 2),
        "sma_50": round(sma_50, 2),
        "sma_200": round(sma_200, 2),
        "ema_9": round(ema_9, 2),
        "ema_21": round(ema_21, 2),
        "ema_50": round(ema_50, 2),
        "rsi": rsi,
        "macd": macd,
        "bollinger_bands": bb,
        "stochastic": stoch,
        "atr": round(atr_val, 2),
        "support": support,
        "resistance": resistance,
        "volatility": round(volatility, 2)
    }

# ============================================================================
# KLINES FETCHER
# ============================================================================

def _get_klines_binance(symbol: str) -> Optional[List[Dict]]:
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1h&limit={KLINES_LIMIT}"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            return [
                {
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5])
                }
                for c in data
            ]
    except:
        pass
    return None

def _get_klines_coingecko(symbol: str) -> Optional[List[Dict]]:
    ids = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
    coin_id = ids.get(symbol.upper())
    if not coin_id:
        return None
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=1"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            prices = data.get("prices", [])
            step = max(1, len(prices) // KLINES_LIMIT)
            sampled = prices[::step][:KLINES_LIMIT]
            return [
                {
                    "open": float(p[1]),
                    "high": float(p[1]),
                    "low": float(p[1]),
                    "close": float(p[1]),
                    "volume": 0
                }
                for p in sampled
            ]
    except:
        pass
    return None

def _get_klines(symbol: str) -> Optional[List[Dict]]:
    klines = _get_klines_binance(symbol)
    if klines and len(klines) >= 14:
        return klines
    return _get_klines_coingecko(symbol)

# ============================================================================
# MAIN TECHNICAL ANALYSIS WITH RECOMMENDATION REASON
# ============================================================================

def analyze_technicals(symbol: str) -> Dict[str, Any]:
    cache_key = f"tech_{symbol}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    price_data = get_live_market_data(symbol)
    if not price_data:
        result = {"ok": False, "symbol": symbol, "error": "No market data"}
        _set_cache(cache_key, result)
        return result

    klines = _get_klines(symbol)
    price = price_data["last_close"]

    if not klines or len(klines) < 14:
        result = {
            "ok": True,
            "symbol": symbol,
            "price": price,
            "exchange": price_data["exchange"],
            "trend": "Neutral",
            "signal": "Neutral",
            "rsi": 50.0,
            "confidence": 0,
            "summary": "Insufficient data for accurate analysis",
            "recommendation": "HOLD",
            "recommendation_reason": "Insufficient market data to generate a reliable recommendation."
        }
        _set_cache(cache_key, result)
        return result

    ind = _compute_indicators(klines)

    # ---- Trend Scoring ----
    score = 0
    if price > ind["sma_10"]: score += 1
    if price > ind["sma_20"]: score += 1
    if price > ind["sma_50"]: score += 1
    if price > ind["sma_200"]: score += 1
    if ind["sma_10"] > ind["sma_20"] > ind["sma_50"]: score += 2
    elif ind["sma_10"] < ind["sma_20"] < ind["sma_50"]: score -= 2
    if ind["ema_9"] > ind["ema_21"]: score += 1
    else: score -= 1
    if ind["ema_21"] > ind["ema_50"]: score += 1
    else: score -= 1
    if ind["macd"]["macd"] > ind["macd"]["signal"]: score += 1
    else: score -= 1
    if price > ind["bollinger_bands"]["middle"]: score += 1
    else: score -= 1

    if score >= 5: trend = "Strong Bullish"
    elif score >= 3: trend = "Bullish"
    elif score <= -5: trend = "Strong Bearish"
    elif score <= -3: trend = "Bearish"
    else: trend = "Neutral"

    # ---- Signal Generation ----
    buy, sell = 0.0, 0.0
    rsi_val = ind["rsi"]
    macd_obj = ind["macd"]
    bb = ind["bollinger_bands"]
    stoch_obj = ind["stochastic"]

    if rsi_val < 30: buy += 2
    elif rsi_val > 70: sell += 2
    elif rsi_val < 40: buy += 1
    elif rsi_val > 60: sell += 1
    elif rsi_val < 50: buy += 0.5
    else: sell += 0.5

    if macd_obj["macd"] > macd_obj["signal"] and macd_obj["histogram"] > 0:
        buy += 1.5
    elif macd_obj["macd"] < macd_obj["signal"] and macd_obj["histogram"] < 0:
        sell += 1.5

    if price < bb["lower"]: buy += 2
    elif price > bb["upper"]: sell += 2
    elif price < bb["lower"] * 1.005: buy += 1
    elif price > bb["upper"] * 0.995: sell += 1

    if stoch_obj["k"] < 20 and stoch_obj["d"] < 20: buy += 1.5
    elif stoch_obj["k"] > 80 and stoch_obj["d"] > 80: sell += 1.5
    elif stoch_obj["k"] < 30 and stoch_obj["d"] < 30: buy += 0.5
    elif stoch_obj["k"] > 70 and stoch_obj["d"] > 70: sell += 0.5

    if price > ind["sma_20"]: buy += 0.5
    else: sell += 0.5

    if buy > sell + 2: signal = "Strong Buy"
    elif buy > sell: signal = "Buy"
    elif sell > buy + 2: signal = "Strong Sell"
    elif sell > buy: signal = "Sell"
    else: signal = "Neutral"

    confidence = min(abs(buy - sell) / 6, 1.0) * 100

    # ---- Generate Recommendation Reason ----
    reasons = []
    if signal in ("Strong Buy", "Buy"):
        if rsi_val < 30:
            reasons.append(f"RSI is oversold at {rsi_val:.1f}, indicating potential reversal to the upside.")
        elif rsi_val < 50:
            reasons.append(f"RSI at {rsi_val:.1f} is below 50, suggesting bearish pressure is fading.")
        if macd_obj["histogram"] > 0:
            reasons.append("MACD histogram turned positive, showing increasing bullish momentum.")
        if price < bb["lower"]:
            reasons.append(f"Price is below the lower Bollinger Band (${bb['lower']:,.2f}), often a sign of oversold conditions.")
        if price > ind["sma_20"]:
            reasons.append(f"Price is above the 20-period SMA (${ind['sma_20']:,.2f}), confirming short-term strength.")
        if trend in ("Bullish", "Strong Bullish"):
            reasons.append("Overall trend is bullish, supporting a long position.")
        if reasons:
            recommendation = "BUY"
        else:
            recommendation = "HOLD (weak buy signal)"
    elif signal in ("Strong Sell", "Sell"):
        if rsi_val > 70:
            reasons.append(f"RSI is overbought at {rsi_val:.1f}, indicating potential reversal to the downside.")
        elif rsi_val > 50:
            reasons.append(f"RSI at {rsi_val:.1f} is above 50, suggesting bullish momentum is waning.")
        if macd_obj["histogram"] < 0:
            reasons.append("MACD histogram turned negative, showing increasing bearish momentum.")
        if price > bb["upper"]:
            reasons.append(f"Price is above the upper Bollinger Band (${bb['upper']:,.2f}), often a sign of overbought conditions.")
        if price < ind["sma_20"]:
            reasons.append(f"Price is below the 20-period SMA (${ind['sma_20']:,.2f}), confirming short-term weakness.")
        if trend in ("Bearish", "Strong Bearish"):
            reasons.append("Overall trend is bearish, supporting a short position.")
        if reasons:
            recommendation = "SELL"
        else:
            recommendation = "HOLD (weak sell signal)"
    else:
        if trend == "Bullish":
            reasons.append("Trend is bullish but signal is neutral; waiting for clearer entry.")
            recommendation = "HOLD (wait for dip)"
        elif trend == "Bearish":
            reasons.append("Trend is bearish but signal is neutral; waiting for clearer entry.")
            recommendation = "HOLD (wait for bounce)"
        else:
            reasons.append("No clear trend or signal; the market is in a consolidation phase.")
            recommendation = "HOLD (wait for breakout)"

    if not reasons:
        reasons.append("No strong technical signals detected. Markets are indecisive.")

    recommendation_reason = " • " + "\n • ".join(reasons)

    # ---- Align signal with recommendation to avoid UI contradiction ----
    if "BUY" in recommendation:
        signal = "Buy"
    elif "SELL" in recommendation:
        signal = "Sell"
    else:
        signal = "Hold"

    # ---- Detailed Report (without emojis for compatibility) ----
    report = (
        f"**Detailed Technical Analysis for {symbol}**\n\n"
        f"**Price:** ${price:,.2f}\n"
        f"**Trend:** {trend} (Score: {score})\n"
        f"**Signal:** {signal} (Confidence: {confidence:.1f}%)\n"
        f"**Recommendation:** {recommendation}\n\n"
        f"**Why {recommendation}?**\n{recommendation_reason}\n\n"
        f"**Moving Averages:**\n"
        f"  • SMA 10: ${ind['sma_10']:,.2f}\n"
        f"  • SMA 20: ${ind['sma_20']:,.2f}\n"
        f"  • SMA 50: ${ind['sma_50']:,.2f}\n"
        f"  • SMA 200: ${ind['sma_200']:,.2f}\n"
        f"  • EMA 9: ${ind['ema_9']:,.2f}\n"
        f"  • EMA 21: ${ind['ema_21']:,.2f}\n\n"
        f"**Oscillators:**\n"
        f"  • RSI (14): {rsi_val:.1f} "
        f"{'(Overbought)' if rsi_val > 70 else '(Oversold)' if rsi_val < 30 else '(Neutral)'}\n"
        f"  • MACD: {macd_obj['macd']:.4f} (Signal: {macd_obj['signal']:.4f})\n"
        f"  • MACD Histogram: {macd_obj['histogram']:.4f}\n"
        f"  • Stochastic RSI: K={stoch_obj['k']:.1f}, D={stoch_obj['d']:.1f}\n\n"
        f"**Volatility:**\n"
        f"  • ATR (14): ${ind['atr']:,.2f}\n"
        f"  • BB Upper: ${bb['upper']:,.2f}\n"
        f"  • BB Middle: ${bb['middle']:,.2f}\n"
        f"  • BB Lower: ${bb['lower']:,.2f}\n"
        f"  • Volatility: {ind['volatility']:.2f}%\n\n"
        f"**Key Levels:**\n"
        f"  • Support (20h): {f'${ind['support']:,.2f}' if ind['support'] else 'N/A'}\n"
        f"  • Resistance (20h): {f'${ind['resistance']:,.2f}' if ind['resistance'] else 'N/A'}\n\n"
        f"**Summary:** {trend} market with {signal} signal. RSI {rsi_val:.1f} indicates "
        f"{'overbought' if rsi_val > 70 else 'oversold' if rsi_val < 30 else 'neutral'} conditions. "
        f"MACD is {'bullish' if macd_obj['histogram'] > 0 else 'bearish'}.\n"
        f"Consider {recommendation.lower()} based on current setup."
    )

    result = {
        "ok": True,
        "symbol": symbol,
        "price": price,
        "exchange": price_data["exchange"],
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "sma_10": ind["sma_10"],
        "sma_20": ind["sma_20"],
        "sma_50": ind["sma_50"],
        "sma_200": ind["sma_200"],
        "ema_9": ind["ema_9"],
        "ema_21": ind["ema_21"],
        "ema_50": ind["ema_50"],
        "rsi": ind["rsi"],
        "macd": ind["macd"],
        "bollinger_bands": ind["bollinger_bands"],
        "stochastic": ind["stochastic"],
        "atr": ind["atr"],
        "trend": trend,
        "trend_score": score,
        "signal": signal,
        "confidence": round(confidence, 1),
        "buy_signals": round(buy, 1),
        "sell_signals": round(sell, 1),
        "support": ind["support"],
        "resistance": ind["resistance"],
        "volatility": ind["volatility"],
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
        "report": report,
        "summary": f"Trend: {trend} | Signal: {signal} | RSI: {rsi_val:.1f} | Conf: {confidence:.1f}%"
    }

    _set_cache(cache_key, result)
    return result
# Aliases
analyze_technicals_fast = analyze_technicals
analyze_technicals_advanced = analyze_technicals

# ============================================================================
# TRADE RECOMMENDATION (auto‑adjusts to always be executable)
# ============================================================================

def get_trade_recommendation(symbol: str) -> Dict[str, Any]:
    tech = analyze_technicals(symbol)
    if not tech.get("ok"):
        return {"ok": False, "error": tech.get("error", "No data")}

    price = tech["price"]
    signal = tech["signal"]
    trend = tech["trend"]
    rsi = tech["rsi"]
    atr = tech.get("atr", price * 0.01)
    recommendation = tech.get("recommendation", "HOLD")
    rec_reason = tech.get("recommendation_reason", "")

    # ---- Determine side and initial stop ----
    if "BUY" in recommendation:
        side = "long"
        stop_dist = atr * 1.5 if atr > 0 else price * 0.015
        stop = price - stop_dist
        min_stop = price - price * STOP_BUFFER
        if stop > min_stop:
            stop = min_stop
        risk = price - stop
        tp = price + risk * 3.0
        reason = f"📈 BUY: {rec_reason[:100]}..."
    elif "SELL" in recommendation:
        side = "short"
        stop_dist = atr * 1.5 if atr > 0 else price * 0.015
        stop = price + stop_dist
        max_stop = price + price * STOP_BUFFER
        if stop < max_stop:
            stop = max_stop
        risk = stop - price
        tp = price - risk * 3.0
        reason = f"📉 SELL: {rec_reason[:100]}..."
    else:
        side = "neutral"
        stop = price * 0.99
        risk = price - stop
        tp = price + risk * 3.0
        return {
            "ok": True,
            "side": "neutral",
            "entry_price": price,
            "stop_loss": stop,
            "take_profit": tp,
            "position_size": 0,
            "risk_amount": 0,
            "risk_percent": 0,
            "position_value": 0,
            "exposure_pct": 0,
            "rr_ratio": 3.0,
            "min_rr_ratio": 2.0,
            "ideal_rr_ratio": 3.0,
            "reasoning": f"➡️ HOLD: {rec_reason[:100]}...",
            "risk_reward_valid": False,
            "technical_indicators": tech,
            "account_size": 0
        }

    # ---- Get actual portfolio balance ----
    try:
        account_balance = get_portfolio_balance()
    except Exception as e:
        return {"ok": False, "error": f"Could not fetch portfolio balance: {e}"}

    # ---- Initial position sizing ----
    risk_per_trade = account_balance * MAX_RISK_PERCENT
    risk_per_unit = abs(price - stop)
    if risk_per_unit == 0:
        risk_per_unit = price * 0.01
    size = risk_per_trade / risk_per_unit

    # Cap at max position %
    max_position_value = account_balance * MAX_POSITION_PCT
    max_size = max_position_value / price
    if size > max_size:
        size = max_size
    size *= 0.995  # safety margin

    # Enforce minimum asset size
    min_size = {
        "BTC": 0.0001,
        "ETH": 0.001,
        "SOL": 0.01
    }.get(symbol, 0.0001)
    if size < min_size:
        size = min_size

    # ---- Adjust for exposure limit ----
    max_exposure_iterations = 25
    exposure_passed = False
    for _ in range(max_exposure_iterations):
        exposure_check = check_exposure_limit(size, price)
        if exposure_check["status"] == "PASSED":
            exposure_passed = True
            break
        size *= 0.90
        if size < min_size:
            size = min_size
            # Re-check with min size
            exposure_check = check_exposure_limit(size, price)
            if exposure_check["status"] == "PASSED":
                exposure_passed = True
            break

    if not exposure_passed:
        return {
            "ok": True,
            "side": "neutral",
            "entry_price": price,
            "stop_loss": stop,
            "take_profit": tp,
            "position_size": 0,
            "risk_amount": 0,
            "risk_percent": 0,
            "position_value": 0,
            "exposure_pct": 0,
            "rr_ratio": 3.0,
            "min_rr_ratio": 2.0,
            "ideal_rr_ratio": 3.0,
            "reasoning": f"⚠️ Cannot fit trade within exposure limit ({MAX_OPEN_EXPOSURE*100}%). Existing positions too large.",
            "risk_reward_valid": False,
            "technical_indicators": tech,
            "account_size": account_balance
        }

    # ---- Auto‑adjust to pass risk engine (risk and stop) ----
    max_iterations = 15
    for i in range(max_iterations):
        risk_result = evaluate_trade_risk(
            symbol=symbol,
            side=side,
            entry=price,
            stop=stop,
            size=size,
            take_profit=tp
        )
        if risk_result.get("status") == "PASSED":
            break

        reason_text = risk_result.get("reason", "")
        if "risk" in reason_text.lower() or "exceeds" in reason_text.lower():
            size *= 0.85
            if size < min_size:
                size = min_size
                break
        elif "stop" in reason_text.lower() and ("tight" in reason_text.lower() or "min" in reason_text.lower()):
            if side == "long":
                stop = price - (price - stop) * 1.15
            else:
                stop = price + (stop - price) * 1.15
            risk = abs(price - stop)
            if side == "long":
                tp = price + risk * 3.0
            else:
                tp = price - risk * 3.0
        else:
            size *= 0.9
            if side == "long":
                stop = price - (price - stop) * 1.05
            else:
                stop = price + (stop - price) * 1.05
            risk = abs(price - stop)
            if side == "long":
                tp = price + risk * 3.0
            else:
                tp = price - risk * 3.0
            if size < min_size:
                size = min_size
                break

    # ---- Final check against risk engine ----
    final_check = evaluate_trade_risk(symbol, side, price, stop, size, tp)
    if final_check.get("status") != "PASSED":
        return {
            "ok": True,
            "side": "neutral",
            "entry_price": price,
            "stop_loss": stop,
            "take_profit": tp,
            "position_size": 0,
            "risk_amount": 0,
            "risk_percent": 0,
            "position_value": 0,
            "exposure_pct": 0,
            "rr_ratio": 3.0,
            "min_rr_ratio": 2.0,
            "ideal_rr_ratio": 3.0,
            "reasoning": f"⚠️ Auto‑adjustment failed: {final_check.get('reason', 'Unknown')}",
            "risk_reward_valid": False,
            "technical_indicators": tech,
            "account_size": account_balance
        }

    # ---- Re-check exposure after risk adjustments ----
    final_exposure = check_exposure_limit(size, price)
    if final_exposure["status"] == "REJECTED":
        return {
            "ok": True,
            "side": "neutral",
            "entry_price": price,
            "stop_loss": stop,
            "take_profit": tp,
            "position_size": 0,
            "risk_amount": 0,
            "risk_percent": 0,
            "position_value": 0,
            "exposure_pct": 0,
            "rr_ratio": 3.0,
            "min_rr_ratio": 2.0,
            "ideal_rr_ratio": 3.0,
            "reasoning": f"⚠️ Auto‑adjustment failed: exposure would exceed {MAX_OPEN_EXPOSURE*100}% cap.",
            "risk_reward_valid": False,
            "technical_indicators": tech,
            "account_size": account_balance
        }

    # ---- Final parameters ----
    final_risk = abs(price - stop)
    pos_value = size * price
    exposure_pct = (pos_value / account_balance) * 100
    risk_amount = final_risk * size

    return {
        "ok": True,
        "symbol": symbol,
        "side": side,
        "entry_price": price,
        "stop_loss": stop,
        "take_profit": tp,
        "position_size": size,
        "risk_amount": risk_amount,
        "risk_percent": MAX_RISK_PERCENT * 100,
        "position_value": pos_value,
        "exposure_pct": round(exposure_pct, 2),
        "rr_ratio": 3.0,
        "min_rr_ratio": 2.0,
        "ideal_rr_ratio": 3.0,
        "reasoning": reason,
        "risk_reward_valid": True,
        "technical_indicators": tech,
        "account_size": account_balance
    }

# ============================================================================
# HEALTH CHECK & DIAGNOSTICS
# ============================================================================

def check_market_data_health() -> Dict[str, Any]:
    data = get_live_market_data("BTC")
    if data:
        return {
            "status": "healthy",
            "price": data["last_close"],
            "exchange": data["exchange"],
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
    else:
        return {
            "status": "unhealthy",
            "price": None,
            "exchange": None,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

def diagnose_connections() -> Dict[str, Any]:
    symbol = "BTC"
    fetchers = {
        "Binance": _fetch_binance,
        "Coinbase": _fetch_coinbase,
        "Kraken": _fetch_kraken,
        "KuCoin": _fetch_kucoin,
        "Bybit": _fetch_bybit,
        "CoinGecko": _fetch_coingecko,
    }
    results = {}
    for name, func in fetchers.items():
        try:
            start = time.time()
            price = func(symbol)
            elapsed = (time.time() - start) * 1000
            results[name] = {
                "reachable": price is not None,
                "price": price,
                "latency_ms": round(elapsed, 2)
            }
        except Exception as e:
            results[name] = {"reachable": False, "error": str(e)}
    return results

# ============================================================================
# SELF-TEST
# ============================================================================

if __name__ == "__main__":
    print("🔍 Testing Enhanced Market Intelligence...")
    diag = diagnose_connections()
    print("Provider status:")
    for name, info in diag.items():
        status = "✅" if info["reachable"] else "❌"
        price = f"${info['price']:,.2f}" if info.get("price") else "N/A"
        latency = f"{info.get('latency_ms', 0)}ms" if info.get("latency_ms") else "N/A"
        print(f"  {status} {name}: {price} ({latency})")

    for sym in ["BTC", "ETH", "SOL"]:
        t = analyze_technicals(sym)
        if t.get("ok"):
            print(f"\n{sym}: {t['recommendation']} - {t['summary']}")
        else:
            print(f"\n{sym}: Error - {t.get('error')}")
    print("✅ Done.")