"""
Advanced Crypto Analyzer v2
Technical: RSI, MACD, Bollinger, EMA, Ichimoku
Fundamental: Market cap, volume ratio, dominance, dev activity
"""

import asyncio
import aiohttp
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

DEFAULT_SCAN_LIST = [
    "bitcoin","ethereum","binancecoin","solana","ripple",
    "cardano","avalanche-2","polkadot","chainlink","polygon",
    "near","arbitrum","optimism","injective-protocol","sui",
    "aptos","celestia","render-token","fetch-ai","ocean-protocol",
    "pepe","dogecoin","shiba-inu","floki","bonk",
    "toncoin","internet-computer","hedera-hashgraph",
    "uniswap","aave","maker","lido-dao","curve-dao-token",
]


class CryptoAnalyzer:
    def __init__(self):
        self.session = None
        self._cache = {}
        self._cache_ttl = 300

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "CryptoPumpBot/2.0"},
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session

    async def _get(self, url, params=None):
        cache_key = f"{url}{params}"
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

    # ── Data Fetching ──────────────────────────────────────────────────────────

    async def get_coin_data(self, coin_id):
        return await self._get(f"{COINGECKO_BASE}/coins/{coin_id}", {
            "localization": "false", "tickers": "false",
            "market_data": "true", "community_data": "true",
            "developer_data": "true", "sparkline": "false"
        })

    async def get_market_chart(self, coin_id, days=60):
        return await self._get(f"{COINGECKO_BASE}/coins/{coin_id}/market_chart", {
            "vs_currency": "usd", "days": days, "interval": "daily"
        })

    async def get_markets_batch(self, ids):
        return await self._get(f"{COINGECKO_BASE}/coins/markets", {
            "vs_currency": "usd", "ids": ",".join(ids),
            "order": "market_cap_desc", "per_page": 50, "page": 1,
            "sparkline": "false", "price_change_percentage": "1h,24h,7d,30d"
        })

    async def get_global_data(self):
        return await self._get(f"{COINGECKO_BASE}/global")

    async def get_fear_greed(self):
        return await self._get("https://api.alternative.me/fng/")

    async def get_trending(self):
        return await self._get(f"{COINGECKO_BASE}/search/trending")

    # ── Technical Indicators ───────────────────────────────────────────────────

    def calc_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        prices = np.array(prices, dtype=float)
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            return 100.0
        return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)

    def calc_ema(self, prices, period):
        prices = np.array(prices, dtype=float)
        if len(prices) < period:
            return prices
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        k = 2 / (period + 1)
        for i in range(1, len(prices)):
            ema[i] = prices[i] * k + ema[i-1] * (1 - k)
        return ema

    def calc_macd(self, prices):
        if len(prices) < 26:
            return {'signal': 'neutral', 'histogram': 0, 'macd': 0, 'strength': 0}
        ema12 = self.calc_ema(prices, 12)
        ema26 = self.calc_ema(prices, 26)
        macd_line = ema12 - ema26
        signal_line = self.calc_ema(macd_line.tolist(), 9)
        hist = macd_line[-1] - signal_line[-1]
        hist_prev = macd_line[-2] - signal_line[-2] if len(macd_line) > 1 else 0
        # Strength: is histogram growing?
        strength = abs(hist) / (abs(macd_line[-1]) + 1e-10)
        if hist > 0 and hist > hist_prev:
            signal = 'bullish_strong'
        elif hist > 0:
            signal = 'bullish'
        elif hist < 0 and hist < hist_prev:
            signal = 'bearish_strong'
        elif hist < 0:
            signal = 'bearish'
        else:
            signal = 'neutral'
        return {'signal': signal, 'histogram': float(hist),
                'macd': float(macd_line[-1]), 'strength': float(strength)}

    def calc_bollinger(self, prices, period=20):
        if len(prices) < period:
            return {'signal': 'neutral', 'position': 50, 'width': 0}
        arr = np.array(prices[-period:], dtype=float)
        mid = np.mean(arr)
        std = np.std(arr)
        upper = mid + 2 * std
        lower = mid - 2 * std
        current = prices[-1]
        pos = (current - lower) / (upper - lower) * 100 if upper != lower else 50
        width = (upper - lower) / mid * 100  # band width %
        if pos < 15:
            signal = 'strong_oversold'
        elif pos < 30:
            signal = 'oversold'
        elif pos > 85:
            signal = 'strong_overbought'
        elif pos > 70:
            signal = 'overbought'
        else:
            signal = 'neutral'
        return {'signal': signal, 'position': float(pos),
                'upper': float(upper), 'lower': float(lower),
                'mid': float(mid), 'width': float(width)}

    def calc_ichimoku(self, prices):
        """Ichimoku Cloud - simplified daily version"""
        if len(prices) < 52:
            return {'signal': 'neutral', 'above_cloud': None, 'tk_cross': 'neutral'}
        arr = np.array(prices, dtype=float)
        # Tenkan-sen (9)
        tenkan = (np.max(arr[-9:]) + np.min(arr[-9:])) / 2
        # Kijun-sen (26)
        kijun = (np.max(arr[-26:]) + np.min(arr[-26:])) / 2
        # Senkou A (avg of tenkan+kijun)
        senkou_a = (tenkan + kijun) / 2
        # Senkou B (52)
        senkou_b = (np.max(arr[-52:]) + np.min(arr[-52:])) / 2
        current = arr[-1]
        cloud_top = max(senkou_a, senkou_b)
        cloud_bottom = min(senkou_a, senkou_b)

        if current > cloud_top:
            cloud_signal = 'above_cloud'  # bullish
        elif current < cloud_bottom:
            cloud_signal = 'below_cloud'  # bearish
        else:
            cloud_signal = 'inside_cloud'  # neutral

        # TK cross
        if tenkan > kijun:
            tk = 'bullish'
        elif tenkan < kijun:
            tk = 'bearish'
        else:
            tk = 'neutral'

        return {
            'signal': cloud_signal,
            'tenkan': float(tenkan),
            'kijun': float(kijun),
            'senkou_a': float(senkou_a),
            'senkou_b': float(senkou_b),
            'tk_cross': tk,
            'above_cloud': current > cloud_top
        }

    def calc_volume_analysis(self, volumes):
        if len(volumes) < 7:
            return {'unusual': False, 'ratio': 1.0, 'trend': 'normal'}
        recent = np.mean(volumes[-3:])
        avg = np.mean(volumes[-14:-3]) if len(volumes) >= 14 else np.mean(volumes[:-3])
        ratio = recent / avg if avg > 0 else 1.0
        if ratio > 3.0: trend = 'explosive'
        elif ratio > 2.0: trend = 'very_high'
        elif ratio > 1.5: trend = 'high'
        elif ratio > 1.2: trend = 'above_avg'
        elif ratio < 0.5: trend = 'very_low'
        else: trend = 'normal'
        return {'unusual': ratio > 2.0, 'ratio': float(ratio), 'trend': trend}

    def calc_support_resistance(self, prices):
        if len(prices) < 10:
            p = prices[-1] if prices else 1
            return {'support': p * 0.95, 'resistance': p * 1.05, 'position_pct': 50}
        arr = np.array(prices, dtype=float)
        low14 = float(np.min(arr[-14:]))
        high14 = float(np.max(arr[-14:]))
        low30 = float(np.min(arr[-30:])) if len(arr) >= 30 else low14
        high30 = float(np.max(arr[-30:])) if len(arr) >= 30 else high14
        current = float(arr[-1])
        pos = (current - low14) / (high14 - low14) * 100 if high14 != low14 else 50
        return {
            'support': low14, 'resistance': high14,
            'support_30': low30, 'resistance_30': high30,
            'position_pct': float(pos)
        }

    # ── Fundamental Score ──────────────────────────────────────────────────────

    def calc_fundamental_score(self, coin_data) -> dict:
        """Score fundamental factors 0-100"""
        score = 0
        details = {}
        md = coin_data.get('market_data', {})

        # 1. Volume/MarketCap ratio (liquidity)
        vol = md.get('total_volume', {}).get('usd', 0) or 0
        mcap = md.get('market_cap', {}).get('usd', 1) or 1
        vol_ratio = vol / mcap
        if vol_ratio > 0.15: s = 25
        elif vol_ratio > 0.08: s = 20
        elif vol_ratio > 0.04: s = 15
        elif vol_ratio > 0.02: s = 10
        else: s = 5
        score += s
        details['liquidity'] = {'score': s, 'ratio': round(vol_ratio * 100, 2)}

        # 2. Market cap rank (lower = bigger = more trusted)
        rank = coin_data.get('market_cap_rank', 999) or 999
        if rank <= 10: s = 25
        elif rank <= 50: s = 20
        elif rank <= 100: s = 15
        elif rank <= 200: s = 10
        else: s = 5
        score += s
        details['rank'] = {'score': s, 'rank': rank}

        # 3. Community (reddit, twitter followers)
        community = coin_data.get('community_data', {}) or {}
        reddit = community.get('reddit_subscribers', 0) or 0
        twitter = community.get('twitter_followers', 0) or 0
        total_community = reddit + twitter
        if total_community > 1_000_000: s = 25
        elif total_community > 500_000: s = 20
        elif total_community > 100_000: s = 15
        elif total_community > 10_000: s = 10
        else: s = 5
        score += s
        details['community'] = {'score': s, 'followers': total_community}

        # 4. Developer activity
        dev = coin_data.get('developer_data', {}) or {}
        commits = (dev.get('commit_count_4_weeks', 0) or 0)
        prs = (dev.get('pull_requests_merged', 0) or 0)
        dev_score_raw = commits + prs
        if dev_score_raw > 200: s = 25
        elif dev_score_raw > 100: s = 20
        elif dev_score_raw > 50: s = 15
        elif dev_score_raw > 10: s = 10
        else: s = 5
        score += s
        details['dev_activity'] = {'score': s, 'commits_4w': commits}

        return {'total': score, 'max': 100, 'details': details}

    # ── Final Pump Probability ─────────────────────────────────────────────────

    def calculate_pump_probability(self, tech: dict, fundamental: dict) -> dict:
        """
        Combined technical + fundamental pump probability
        Returns score 0-100 with breakdown
        """
        tech_score = 0
        tech_max = 60  # technical = 60% weight

        # RSI (0-15)
        rsi = tech.get('rsi', 50)
        if rsi < 25: r = 15
        elif rsi < 35: r = 12
        elif rsi < 45: r = 8
        elif rsi < 55: r = 5
        elif rsi > 75: r = 1
        else: r = 3
        tech_score += r

        # MACD (0-15)
        macd_sig = tech.get('macd_signal', 'neutral')
        if macd_sig == 'bullish_strong': r = 15
        elif macd_sig == 'bullish': r = 10
        elif macd_sig == 'neutral': r = 5
        elif macd_sig == 'bearish': r = 2
        else: r = 0
        tech_score += r

        # Volume (0-15)
        vol_ratio = tech.get('volume_ratio', 1.0)
        if vol_ratio > 4.0: r = 15
        elif vol_ratio > 3.0: r = 13
        elif vol_ratio > 2.0: r = 10
        elif vol_ratio > 1.5: r = 7
        elif vol_ratio > 1.2: r = 4
        else: r = 1
        tech_score += r

        # Bollinger (0-10)
        bb_sig = tech.get('bb_signal', 'neutral')
        if bb_sig == 'strong_oversold': r = 10
        elif bb_sig == 'oversold': r = 7
        elif bb_sig == 'neutral': r = 4
        elif bb_sig == 'overbought': r = 1
        else: r = 0
        tech_score += r

        # Ichimoku (0-10)
        ichi_sig = tech.get('ichimoku_signal', 'neutral')
        ichi_tk = tech.get('ichimoku_tk', 'neutral')
        if ichi_sig == 'above_cloud' and ichi_tk == 'bullish': r = 10
        elif ichi_sig == 'above_cloud': r = 7
        elif ichi_sig == 'inside_cloud' and ichi_tk == 'bullish': r = 5
        elif ichi_sig == 'inside_cloud': r = 3
        else: r = 1
        tech_score += r

        # Price trend (0-5)
        c24 = tech.get('change_24h', 0)
        c7d = tech.get('change_7d', 0)
        if -8 < c24 < 3 and c7d < -15: r = 5
        elif 0 < c24 < 8: r = 4
        elif c24 > 8: r = 2
        else: r = 2
        tech_score += r

        # Fundamental score (40% weight → 0-40)
        fund_raw = fundamental.get('total', 50)
        fund_score = fund_raw * 0.4

        total = min(100, tech_score + fund_score)

        # Verdict
        if total >= 80: verdict = '🚀 بسیار قوی'
        elif total >= 65: verdict = '📈 قوی'
        elif total >= 50: verdict = '🟡 متوسط'
        elif total >= 35: verdict = '🔶 ضعیف'
        else: verdict = '🔴 منفی'

        return {
            'total': round(total, 1),
            'technical': round(tech_score, 1),
            'fundamental': round(fund_score, 1),
            'verdict': verdict
        }

    # ── Main Analysis ──────────────────────────────────────────────────────────

    async def analyze_coin(self, coin_id: str) -> dict:
        try:
            coin_data, chart_data = await asyncio.gather(
                self.get_coin_data(coin_id),
                self.get_market_chart(coin_id, days=60),
                return_exceptions=True
            )
            if isinstance(coin_data, Exception) or not coin_data:
                return {'error': f'داده‌ای برای {coin_id} یافت نشد'}

            md = coin_data.get('market_data', {})
            current_price = md.get('current_price', {}).get('usd', 0) or 0

            prices, volumes = [], []
            if chart_data and not isinstance(chart_data, Exception):
                prices = [p[1] for p in chart_data.get('prices', [])]
                volumes = [v[1] for v in chart_data.get('total_volumes', [])]

            rsi = self.calc_rsi(prices)
            macd = self.calc_macd(prices)
            bb = self.calc_bollinger(prices)
            ichi = self.calc_ichimoku(prices)
            vol_a = self.calc_volume_analysis(volumes)
            sr = self.calc_support_resistance(prices)
            fund = self.calc_fundamental_score(coin_data)

            change_24h = md.get('price_change_percentage_24h', 0) or 0
            change_7d = md.get('price_change_percentage_7d', 0) or 0
            change_30d = md.get('price_change_percentage_30d', 0) or 0
            change_1h = md.get('price_change_percentage_1h_in_currency', {}).get('usd', 0) or 0

            ema20 = float(self.calc_ema(prices, 20)[-1]) if len(prices) >= 20 else current_price
            ema50 = float(self.calc_ema(prices, 50)[-1]) if len(prices) >= 50 else current_price
            if current_price > ema20 > ema50: ema_signal = '✅ صعودی'
            elif current_price < ema20 < ema50: ema_signal = '❌ نزولی'
            else: ema_signal = '➡️ خنثی'

            tech = {
                'rsi': rsi,
                'macd_signal': macd['signal'],
                'volume_ratio': vol_a['ratio'],
                'bb_signal': bb['signal'],
                'ichimoku_signal': ichi['signal'],
                'ichimoku_tk': ichi['tk_cross'],
                'change_24h': change_24h,
                'change_7d': change_7d,
            }

            pump = self.calculate_pump_probability(tech, fund)

            # Buy/Sell zones
            buy_zone = sr['support'] * 1.005 if sr['position_pct'] > 40 else current_price * 0.99
            target1 = current_price * 1.10
            target2 = current_price * 1.22
            target3 = current_price * 1.40
            stop_loss = sr['support'] * 0.96

            return {
                'id': coin_id,
                'symbol': coin_data.get('symbol', '').upper(),
                'name': coin_data.get('name', ''),
                'price': current_price,
                'change_1h': change_1h,
                'change_24h': change_24h,
                'change_7d': change_7d,
                'change_30d': change_30d,
                'volume_24h': md.get('total_volume', {}).get('usd', 0) or 0,
                'market_cap': md.get('market_cap', {}).get('usd', 0) or 0,
                'market_cap_rank': coin_data.get('market_cap_rank', 0),
                'pump_probability': pump['total'],
                'pump_technical': pump['technical'],
                'pump_fundamental': pump['fundamental'],
                'pump_verdict': pump['verdict'],
                'trend': 'bullish' if pump['total'] > 60 else 'bearish' if pump['total'] < 35 else 'neutral',
                'rsi': rsi,
                'macd_signal': macd['signal'],
                'macd_histogram': macd['histogram'],
                'bb_signal': bb['signal'],
                'bb_position': bb['position'],
                'bb_width': bb['width'],
                'ichimoku_signal': ichi['signal'],
                'ichimoku_tk': ichi['tk_cross'],
                'ema_signal': ema_signal,
                'volume_unusual': vol_a['unusual'],
                'volume_ratio': vol_a['ratio'],
                'volume_trend': vol_a['trend'],
                'fundamental_score': fund['total'],
                'fund_liquidity': fund['details']['liquidity']['score'],
                'fund_rank': fund['details']['rank']['score'],
                'fund_community': fund['details']['community']['score'],
                'fund_dev': fund['details']['dev_activity']['score'],
                'buy_zone': buy_zone,
                'sell_zone': target1,
                'target1': target1,
                'target2': target2,
                'target3': target3,
                'stop_loss': stop_loss,
                'support': sr['support'],
                'resistance': sr['resistance'],
            }
        except Exception as e:
            logger.error(f"Error analyzing {coin_id}: {e}")
            return {'error': str(e)}

    async def analyze_single(self, symbol: str) -> dict:
        symbol_map = {
            'BTC':'bitcoin','ETH':'ethereum','BNB':'binancecoin',
            'SOL':'solana','XRP':'ripple','ADA':'cardano',
            'AVAX':'avalanche-2','DOT':'polkadot','LINK':'chainlink',
            'MATIC':'polygon','NEAR':'near','ARB':'arbitrum',
            'OP':'optimism','INJ':'injective-protocol','SUI':'sui',
            'APT':'aptos','TIA':'celestia','DOGE':'dogecoin',
            'SHIB':'shiba-inu','PEPE':'pepe','TON':'toncoin',
            'UNI':'uniswap','AAVE':'aave','MKR':'maker',
            'LDO':'lido-dao','CRV':'curve-dao-token',
            'RENDER':'render-token','FET':'fetch-ai',
        }
        coin_id = symbol_map.get(symbol.upper(), symbol.lower())
        return await self.analyze_coin(coin_id)

    async def get_top_signals(self, limit=10) -> List[dict]:
        trending_data = await self.get_trending()
        trending_ids = []
        if trending_data:
            trending_ids = [c['item']['id'] for c in trending_data.get('coins', [])[:7]]
        scan_ids = list(set(trending_ids + DEFAULT_SCAN_LIST[:25]))
        market_data = await self.get_markets_batch(scan_ids[:40])
        if not market_data:
            return []
        quick_scores = []
        for coin in market_data:
            c24 = coin.get('price_change_percentage_24h', 0) or 0
            c7d = coin.get('price_change_percentage_7d_in_currency', 0) or 0
            vol = coin.get('total_volume', 0) or 0
            mcap = coin.get('market_cap', 1) or 1
            vr = vol / mcap
            q = 0
            if -15 < c24 < 5: q += 30
            if c7d < -15: q += 20
            if vr > 0.05: q += 20
            if (coin.get('price_change_percentage_1h_in_currency') or 0) > 0: q += 15
            quick_scores.append((coin, q))
        quick_scores.sort(key=lambda x: x[1], reverse=True)
        top = [c[0] for c in quick_scores[:12]]
        results = await asyncio.gather(*[self.analyze_coin(c['id']) for c in top[:10]], return_exceptions=True)
        valid = [r for r in results if isinstance(r, dict) and 'error' not in r]
        valid.sort(key=lambda x: x['pump_probability'], reverse=True)
        return valid[:limit]

    async def get_market_news(self) -> List[dict]:
        try:
            data = await self._get(f"{COINGECKO_BASE}/news")
            if data and isinstance(data, list):
                return [{'title': i.get('title',''),'source': i.get('author',{}).get('name','CoinGecko') if isinstance(i.get('author'),dict) else 'CoinGecko','url': i.get('url','https://coingecko.com'),'time': i.get('created_at','اخیراً'),'sentiment':'neutral'} for i in data[:8]]
        except: pass
        return [
            {'title':'Bitcoin consolidates above key support','source':'CoinDesk','url':'https://coindesk.com','time':'اخیراً','sentiment':'neutral'},
            {'title':'Ethereum Layer 2 volumes hit new record','source':'The Block','url':'https://theblock.co','time':'اخیراً','sentiment':'positive'},
        ]

    async def get_market_status(self) -> dict:
        gd, fg = await asyncio.gather(self.get_global_data(), self.get_fear_greed(), return_exceptions=True)
        result = {'total_market_cap':0,'btc_dominance':0,'total_volume':0,'fear_greed':50,'overall_trend':'خنثی','gainers':50,'losers':50}
        if gd and not isinstance(gd, Exception):
            d = gd.get('data', {})
            result['total_market_cap'] = d.get('total_market_cap',{}).get('usd',0)
            result['btc_dominance'] = d.get('market_cap_percentage',{}).get('btc',0)
            result['total_volume'] = d.get('total_volume',{}).get('usd',0)
            ch = d.get('market_cap_change_percentage_24h_usd', 0)
            result['overall_trend'] = '📈 صعودی' if ch > 2 else '📉 نزولی' if ch < -2 else '➡️ خنثی'
            result['gainers'] = max(0, min(100, 50 + ch * 2))
            result['losers'] = 100 - result['gainers']
        if fg and not isinstance(fg, Exception):
            try: result['fear_greed'] = int(fg['data'][0]['value'])
            except: pass
        return result

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
