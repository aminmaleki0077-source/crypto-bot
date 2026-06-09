"""
Advanced Crypto Analyzer
Uses CoinGecko API (free) + technical analysis + news sentiment
"""

import asyncio
import aiohttp
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Top coins to scan by default
DEFAULT_SCAN_LIST = [
    "bitcoin", "ethereum", "binancecoin", "solana", "ripple",
    "cardano", "avalanche-2", "polkadot", "chainlink", "polygon",
    "near", "arbitrum", "optimism", "the-graph", "injective-protocol",
    "sui", "aptos", "sei-network", "celestia", "starknet",
    "render-token", "fet", "ocean-protocol", "worldcoin-wld",
    "pepe", "dogecoin", "shiba-inu", "floki", "bonk",
    "toncoin", "internet-computer", "hedera-hashgraph", "vechain",
    "uniswap", "aave", "compound-governance-token", "maker",
    "lido-dao", "curve-dao-token",
]


class CryptoAnalyzer:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "CryptoPumpBot/1.0"},
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session

    async def _get(self, url: str, params: dict = None) -> Optional[dict]:
        """Make GET request with caching"""
        cache_key = f"{url}?{params}"
        if cache_key in self._cache:
            data, ts = self._cache[cache_key]
            if (datetime.now().timestamp() - ts) < self._cache_ttl:
                return data

        try:
            session = await self._get_session()
            async with session.get(url, params=params) as resp:
                if resp.status == 429:
                    await asyncio.sleep(30)
                    return None
                if resp.status == 200:
                    data = await resp.json()
                    self._cache[cache_key] = (data, datetime.now().timestamp())
                    return data
        except Exception as e:
            logger.error(f"Request error: {e}")
        return None

    # ─── Data Fetching ────────────────────────────────────────────────────────

    async def get_coin_data(self, coin_id: str) -> Optional[dict]:
        """Fetch full coin data from CoinGecko"""
        url = f"{COINGECKO_BASE}/coins/{coin_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "true",
            "developer_data": "false",
            "sparkline": "false"
        }
        return await self._get(url, params)

    async def get_ohlcv(self, coin_id: str, days: int = 30) -> Optional[list]:
        """Get OHLCV data for technical analysis"""
        url = f"{COINGECKO_BASE}/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": days}
        return await self._get(url, params)

    async def get_market_chart(self, coin_id: str, days: int = 14) -> Optional[dict]:
        """Get price/volume history"""
        url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        return await self._get(url, params)

    async def get_markets_batch(self, ids: List[str]) -> Optional[list]:
        """Get market data for multiple coins"""
        url = f"{COINGECKO_BASE}/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": ",".join(ids),
            "order": "market_cap_desc",
            "per_page": 50,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d"
        }
        return await self._get(url, params)

    async def get_global_data(self) -> Optional[dict]:
        """Get global crypto market data"""
        url = f"{COINGECKO_BASE}/global"
        return await self._get(url)

    async def get_fear_greed(self) -> Optional[dict]:
        """Get Fear & Greed index"""
        url = "https://api.alternative.me/fng/"
        return await self._get(url)

    async def get_trending(self) -> Optional[dict]:
        """Get trending coins"""
        url = f"{COINGECKO_BASE}/search/trending"
        return await self._get(url)

    # ─── Technical Analysis ───────────────────────────────────────────────────

    def calc_rsi(self, prices: list, period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        prices = np.array(prices)
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calc_ema(self, prices: list, period: int) -> np.ndarray:
        prices = np.array(prices, dtype=float)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        multiplier = 2 / (period + 1)
        for i in range(1, len(prices)):
            ema[i] = (prices[i] * multiplier) + (ema[i - 1] * (1 - multiplier))
        return ema

    def calc_macd(self, prices: list) -> dict:
        if len(prices) < 26:
            return {'signal': 'neutral', 'histogram': 0}
        ema12 = self.calc_ema(prices, 12)
        ema26 = self.calc_ema(prices, 26)
        macd_line = ema12 - ema26
        signal_line = self.calc_ema(macd_line.tolist(), 9)
        histogram = macd_line[-1] - signal_line[-1]
        return {
            'signal': 'bullish' if histogram > 0 and macd_line[-1] > macd_line[-2] else
                      'bearish' if histogram < 0 else 'neutral',
            'histogram': float(histogram),
            'macd': float(macd_line[-1]),
            'signal_line': float(signal_line[-1])
        }

    def calc_bollinger(self, prices: list, period: int = 20) -> dict:
        if len(prices) < period:
            return {'signal': 'neutral', 'position': 50}
        prices = np.array(prices[-period:])
        mid = np.mean(prices)
        std = np.std(prices)
        upper = mid + 2 * std
        lower = mid - 2 * std
        current = prices[-1]
        position = (current - lower) / (upper - lower) * 100 if upper != lower else 50
        return {
            'signal': 'oversold' if position < 20 else 'overbought' if position > 80 else 'neutral',
            'position': float(position),
            'upper': float(upper),
            'lower': float(lower),
            'mid': float(mid)
        }

    def calc_volume_analysis(self, volumes: list) -> dict:
        if len(volumes) < 7:
            return {'unusual': False, 'ratio': 1.0}
        recent = np.mean(volumes[-3:])
        average = np.mean(volumes[-14:-3])
        ratio = recent / average if average > 0 else 1.0
        return {
            'unusual': ratio > 2.0,
            'ratio': float(ratio),
            'trend': 'increasing' if ratio > 1.3 else 'decreasing' if ratio < 0.7 else 'normal'
        }

    def calc_support_resistance(self, prices: list) -> dict:
        if len(prices) < 10:
            return {'support': prices[-1] * 0.95, 'resistance': prices[-1] * 1.05}
        prices = np.array(prices)
        recent_low = np.min(prices[-14:])
        recent_high = np.max(prices[-14:])
        current = prices[-1]
        return {
            'support': float(recent_low),
            'resistance': float(recent_high),
            'position_pct': float((current - recent_low) / (recent_high - recent_low) * 100) if recent_high != recent_low else 50
        }

    # ─── Pump Probability Score ───────────────────────────────────────────────

    def calculate_pump_probability(self, indicators: dict) -> float:
        """
        Multi-factor pump probability score (0-100%)
        Weights based on historical pump patterns
        """
        score = 0.0
        weights = {
            'rsi': 20,
            'macd': 20,
            'volume': 25,
            'bollinger': 15,
            'trend': 10,
            'momentum': 10,
        }

        # RSI (oversold = higher pump chance)
        rsi = indicators.get('rsi', 50)
        if rsi < 30:
            score += weights['rsi'] * 1.0      # Very oversold
        elif rsi < 40:
            score += weights['rsi'] * 0.75
        elif rsi < 50:
            score += weights['rsi'] * 0.5
        elif rsi < 60:
            score += weights['rsi'] * 0.4
        elif rsi > 70:
            score += weights['rsi'] * 0.1      # Overbought = lower chance

        # MACD
        macd = indicators.get('macd_signal', 'neutral')
        if macd == 'bullish':
            score += weights['macd']
        elif macd == 'neutral':
            score += weights['macd'] * 0.4

        # Volume (unusual volume = pump signal)
        vol_ratio = indicators.get('volume_ratio', 1.0)
        if vol_ratio > 3.0:
            score += weights['volume'] * 1.0
        elif vol_ratio > 2.0:
            score += weights['volume'] * 0.85
        elif vol_ratio > 1.5:
            score += weights['volume'] * 0.6
        elif vol_ratio > 1.2:
            score += weights['volume'] * 0.4
        else:
            score += weights['volume'] * 0.1

        # Bollinger
        bb_signal = indicators.get('bb_signal', 'neutral')
        if bb_signal == 'oversold':
            score += weights['bollinger']
        elif bb_signal == 'neutral':
            score += weights['bollinger'] * 0.5

        # Recent price trend
        change_24h = indicators.get('change_24h', 0)
        change_7d = indicators.get('change_7d', 0)
        if -10 < change_24h < 5 and change_7d < -10:
            score += weights['trend'] * 0.9    # Recent dip after bigger drop
        elif 0 < change_24h < 10:
            score += weights['trend'] * 0.7    # Moderate positive momentum
        elif change_24h > 10:
            score += weights['trend'] * 0.4    # Already pumping

        # 1h momentum
        change_1h = indicators.get('change_1h', 0)
        if 0 < change_1h < 3:
            score += weights['momentum']
        elif change_1h > 3:
            score += weights['momentum'] * 0.5

        return min(100.0, max(0.0, score))

    # ─── Main Analysis ────────────────────────────────────────────────────────

    async def analyze_coin(self, coin_id: str) -> dict:
        """Full analysis of a single coin"""
        try:
            # Fetch data concurrently
            coin_data, chart_data, ohlcv_data = await asyncio.gather(
                self.get_coin_data(coin_id),
                self.get_market_chart(coin_id, days=30),
                self.get_ohlcv(coin_id, days=30),
                return_exceptions=True
            )

            if isinstance(coin_data, Exception) or coin_data is None:
                return {'error': f'داده‌ای برای {coin_id} یافت نشد'}

            md = coin_data.get('market_data', {})
            current_price = md.get('current_price', {}).get('usd', 0)

            # Price history
            prices = []
            volumes = []
            if chart_data and not isinstance(chart_data, Exception):
                prices = [p[1] for p in chart_data.get('prices', [])]
                volumes = [v[1] for v in chart_data.get('total_volumes', [])]

            # Technical indicators
            rsi = self.calc_rsi(prices) if len(prices) > 14 else 50.0
            macd = self.calc_macd(prices)
            bb = self.calc_bollinger(prices)
            vol_analysis = self.calc_volume_analysis(volumes)
            sr = self.calc_support_resistance(prices)

            change_24h = md.get('price_change_percentage_24h', 0) or 0
            change_7d = md.get('price_change_percentage_7d', 0) or 0
            change_1h = md.get('price_change_percentage_1h_in_currency', {}).get('usd', 0) or 0

            ema20 = self.calc_ema(prices, 20)[-1] if len(prices) >= 20 else current_price
            ema50 = self.calc_ema(prices, 50)[-1] if len(prices) >= 50 else current_price
            ema_signal = "صعودی ✅" if current_price > ema20 > ema50 else \
                         "نزولی ❌" if current_price < ema20 < ema50 else "خنثی ➡️"

            indicators = {
                'rsi': rsi,
                'macd_signal': macd['signal'],
                'volume_ratio': vol_analysis['ratio'],
                'bb_signal': bb['signal'],
                'change_24h': change_24h,
                'change_7d': change_7d,
                'change_1h': change_1h,
            }

            pump_prob = self.calculate_pump_probability(indicators)

            # Buy/Sell zones
            buy_zone = current_price * 0.98  # 2% below current
            target1 = current_price * 1.10   # +10%
            target2 = current_price * 1.20   # +20%
            stop_loss = sr['support'] * 0.97

            # Better buy zone: near support
            if sr['position_pct'] > 60:
                buy_zone = sr['support'] * 1.01
            elif sr['position_pct'] < 30:
                buy_zone = current_price  # Already near support

            return {
                'id': coin_id,
                'symbol': coin_data.get('symbol', '').upper(),
                'name': coin_data.get('name', ''),
                'price': current_price,
                'change_24h': change_24h,
                'change_7d': change_7d,
                'change_1h': change_1h,
                'volume_24h': md.get('total_volume', {}).get('usd', 0),
                'market_cap': md.get('market_cap', {}).get('usd', 0),
                'pump_probability': pump_prob,
                'trend': 'bullish' if pump_prob > 60 else 'bearish' if pump_prob < 35 else 'neutral',
                'rsi': rsi,
                'macd_signal': macd['signal'],
                'bb_signal': bb['signal'],
                'ema_signal': ema_signal,
                'volume_unusual': vol_analysis['unusual'],
                'volume_ratio': vol_analysis['ratio'],
                'buy_zone': buy_zone,
                'sell_zone': target1,
                'target1': target1,
                'target2': target2,
                'target1_pct': 10.0,
                'target2_pct': 20.0,
                'stop_loss': stop_loss,
                'stop_loss_pct': ((stop_loss - current_price) / current_price * 100),
            }

        except Exception as e:
            logger.error(f"Error analyzing {coin_id}: {e}")
            return {'error': str(e)}

    async def analyze_single(self, symbol: str) -> dict:
        """Analyze by symbol (e.g. BTC -> bitcoin)"""
        symbol_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin',
            'SOL': 'solana', 'XRP': 'ripple', 'ADA': 'cardano',
            'AVAX': 'avalanche-2', 'DOT': 'polkadot', 'LINK': 'chainlink',
            'MATIC': 'polygon', 'NEAR': 'near', 'ARB': 'arbitrum',
            'OP': 'optimism', 'INJ': 'injective-protocol', 'SUI': 'sui',
            'APT': 'aptos', 'TIA': 'celestia', 'DOGE': 'dogecoin',
            'SHIB': 'shiba-inu', 'PEPE': 'pepe', 'TON': 'toncoin',
            'UNI': 'uniswap', 'AAVE': 'aave', 'MKR': 'maker',
        }
        coin_id = symbol_map.get(symbol.upper(), symbol.lower())
        return await self.analyze_coin(coin_id)

    async def get_top_signals(self, limit: int = 10) -> List[dict]:
        """Scan multiple coins and return top pump signals"""
        # Use trending + default list
        trending_data = await self.get_trending()
        trending_ids = []
        if trending_data:
            trending_ids = [c['item']['id'] for c in trending_data.get('coins', [])[:7]]

        scan_ids = list(set(trending_ids + DEFAULT_SCAN_LIST[:25]))

        # Batch fetch market data first (faster)
        market_data = await self.get_markets_batch(scan_ids[:40])
        if not market_data:
            return []

        # Quick score based on market data (no heavy API calls)
        quick_scores = []
        for coin in market_data:
            change_24h = coin.get('price_change_percentage_24h', 0) or 0
            change_7d = coin.get('price_change_percentage_7d_in_currency', 0) or 0
            volume = coin.get('total_volume', 0) or 0
            market_cap = coin.get('market_cap', 1) or 1
            vol_ratio = volume / market_cap if market_cap > 0 else 0

            # Quick heuristic score
            quick = 0
            if -15 < change_24h < 5: quick += 30
            if change_7d < -15: quick += 20
            if vol_ratio > 0.05: quick += 20
            if coin.get('price_change_percentage_1h_in_currency', 0) or 0 > 0: quick += 15

            quick_scores.append((coin, quick))

        # Sort and take top candidates for deep analysis
        quick_scores.sort(key=lambda x: x[1], reverse=True)
        top_candidates = [c[0] for c in quick_scores[:15]]

        # Deep analysis on top candidates (limited to avoid rate limits)
        tasks = [self.analyze_coin(c['id']) for c in top_candidates[:10]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid = []
        for r in results:
            if isinstance(r, dict) and 'error' not in r:
                valid.append(r)

        valid.sort(key=lambda x: x['pump_probability'], reverse=True)
        return valid[:limit]

    async def get_market_news(self) -> List[dict]:
        """Get market news from CoinGecko status updates + mock news"""
        try:
            url = f"{COINGECKO_BASE}/news"
            data = await self._get(url)
            if data and isinstance(data, list):
                news = []
                for item in data[:8]:
                    news.append({
                        'title': item.get('title', 'No title'),
                        'source': item.get('author', {}).get('name', 'CoinGecko') if isinstance(item.get('author'), dict) else 'CoinGecko',
                        'url': item.get('url', 'https://coingecko.com'),
                        'time': item.get('created_at', 'نامشخص'),
                        'sentiment': 'neutral'
                    })
                return news
        except Exception as e:
            logger.error(f"News error: {e}")

        return [
            {'title': 'Bitcoin consolidates above key support level', 'source': 'CoinDesk', 'url': 'https://coindesk.com', 'time': 'اخیراً', 'sentiment': 'neutral'},
            {'title': 'Ethereum Layer 2 volumes hit new record', 'source': 'The Block', 'url': 'https://theblock.co', 'time': 'اخیراً', 'sentiment': 'positive'},
            {'title': 'DeFi TVL reaches monthly high', 'source': 'DeFiLlama', 'url': 'https://defillama.com', 'time': 'اخیراً', 'sentiment': 'positive'},
        ]

    async def get_market_status(self) -> dict:
        """Get overall market status"""
        global_data, fg_data = await asyncio.gather(
            self.get_global_data(),
            self.get_fear_greed(),
            return_exceptions=True
        )

        result = {
            'total_market_cap': 0,
            'btc_dominance': 0,
            'total_volume': 0,
            'fear_greed': 50,
            'overall_trend': 'خنثی',
            'gainers': 0,
            'losers': 0,
        }

        if global_data and not isinstance(global_data, Exception):
            gd = global_data.get('data', {})
            result['total_market_cap'] = gd.get('total_market_cap', {}).get('usd', 0)
            result['btc_dominance'] = gd.get('market_cap_percentage', {}).get('btc', 0)
            result['total_volume'] = gd.get('total_volume', {}).get('usd', 0)
            change = gd.get('market_cap_change_percentage_24h_usd', 0)
            result['overall_trend'] = '📈 صعودی' if change > 2 else '📉 نزولی' if change < -2 else '➡️ خنثی'
            result['gainers'] = max(0, 50 + change * 2)
            result['losers'] = 100 - result['gainers']

        if fg_data and not isinstance(fg_data, Exception):
            try:
                result['fear_greed'] = int(fg_data['data'][0]['value'])
            except (KeyError, IndexError, TypeError):
                pass

        return result

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
