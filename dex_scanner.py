"""
DEX Scanner - شناسایی شت‌کوین‌های جدید با پتانسیل پامپ
از DexScreener API (رایگان)
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEXSCREENER_BASE = "https://api.dexscreener.com/latest"

# شبکه‌های پشتیبانی‌شده
CHAINS = {
    "solana": "Solana",
    "bsc": "BSC",
    "ethereum": "Ethereum",
    "base": "Base",
    "arbitrum": "Arbitrum",
}

# لینک خرید برای هر شبکه
BUY_LINKS = {
    "solana": "https://raydium.io/swap/?inputCurrency=sol&outputCurrency={address}",
    "bsc": "https://pancakeswap.finance/swap?outputCurrency={address}",
    "ethereum": "https://app.uniswap.org/#/swap?outputCurrency={address}",
    "base": "https://app.uniswap.org/#/swap?chain=base&outputCurrency={address}",
    "arbitrum": "https://app.uniswap.org/#/swap?chain=arbitrum&outputCurrency={address}",
}

EXPLORER_LINKS = {
    "solana": "https://solscan.io/token/{address}",
    "bsc": "https://bscscan.com/token/{address}",
    "ethereum": "https://etherscan.io/token/{address}",
    "base": "https://basescan.org/token/{address}",
    "arbitrum": "https://arbiscan.io/token/{address}",
}


class DexScanner:
    def __init__(self):
        self.session = None

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "CryptoPumpBot/2.0"},
                timeout=aiohttp.ClientTimeout(total=20)
            )
        return self.session

    async def _get(self, url, params=None):
        try:
            session = await self._get_session()
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error(f"DEX request error: {e}")
        return None

    # ── Fetch New Tokens ───────────────────────────────────────────────────────

    async def get_new_tokens(self, chain: str = "solana", max_age_hours: int = 24) -> list:
        """توکن‌های جدید روی یک شبکه"""
        url = f"{DEXSCREENER_BASE}/dex/tokens/new"
        # DexScreener latest pairs endpoint
        url = f"https://api.dexscreener.com/token-profiles/latest/v1"
        data = await self._get(url)
        tokens = []
        if not data:
            return tokens
        items = data if isinstance(data, list) else data.get('pairs', [])
        for item in items[:50]:
            if isinstance(item, dict):
                c = item.get('chainId', '')
                if chain != 'all' and c != chain:
                    continue
                tokens.append(item)
        return tokens

    async def search_new_pairs(self, chain: str = "solana") -> list:
        """جستجوی پیر‌های جدید روی DexScreener"""
        url = f"https://api.dexscreener.com/latest/dex/search"
        params = {"q": "new"}
        data = await self._get(url, params)
        if not data:
            return []
        pairs = data.get('pairs', []) or []
        result = []
        now = datetime.now(timezone.utc).timestamp() * 1000
        for p in pairs:
            if chain != 'all' and p.get('chainId', '') != chain:
                continue
            # فیلتر: کمتر از max_age_hours ساعت
            created = p.get('pairCreatedAt', 0) or 0
            age_hours = (now - created) / (1000 * 3600) if created > 0 else 999
            if age_hours <= 48:
                result.append(p)
        return result[:30]

    async def get_boosted_tokens(self) -> list:
        """توکن‌های بوست‌شده (ترند) در DexScreener"""
        url = "https://api.dexscreener.com/token-boosts/top/v1"
        data = await self._get(url)
        if not data:
            return []
        return data if isinstance(data, list) else []

    async def get_pair_data(self, chain: str, address: str) -> dict:
        """اطلاعات کامل یک پیر"""
        url = f"{DEXSCREENER_BASE}/dex/pairs/{chain}/{address}"
        data = await self._get(url)
        if data and data.get('pairs'):
            return data['pairs'][0]
        return {}

    async def search_token(self, query: str) -> list:
        """جستجوی توکن با اسم یا آدرس"""
        url = f"{DEXSCREENER_BASE}/dex/search"
        data = await self._get(url, {"q": query})
        if data:
            return data.get('pairs', [])[:10]
        return []

    # ── Pump Score for Shitcoins ───────────────────────────────────────────────

    def calc_shitcoin_pump_score(self, pair: dict) -> dict:
        """
        امتیاز پامپ برای شت‌کوین‌های DEX
        فاکتورها: حجم، نقدینگی، تعداد تراکنش، تغییر قیمت، سن
        """
        score = 0
        details = {}

        # 1. حجم ۲۴ ساعته (0-25)
        vol_24h = float((pair.get('volume') or {}).get('h24', 0) or 0)
        if vol_24h > 1_000_000: s = 25
        elif vol_24h > 500_000: s = 22
        elif vol_24h > 100_000: s = 18
        elif vol_24h > 50_000: s = 14
        elif vol_24h > 10_000: s = 10
        elif vol_24h > 1_000: s = 5
        else: s = 1
        score += s
        details['volume'] = s

        # 2. نقدینگی (0-20)
        liq = float((pair.get('liquidity') or {}).get('usd', 0) or 0)
        if liq > 500_000: s = 20
        elif liq > 100_000: s = 17
        elif liq > 50_000: s = 14
        elif liq > 10_000: s = 10
        elif liq > 1_000: s = 6
        elif liq > 100: s = 3
        else: s = 0
        score += s
        details['liquidity'] = s

        # 3. تعداد خریدار ۱ ساعته (0-20)
        txns_h1 = pair.get('txns', {}).get('h1', {}) or {}
        buys = int(txns_h1.get('buys', 0) or 0)
        sells = int(txns_h1.get('sells', 0) or 0)
        buy_pressure = buys / (buys + sells + 1)
        if buys > 200: s = 20
        elif buys > 100: s = 17
        elif buys > 50: s = 13
        elif buys > 20: s = 9
        elif buys > 5: s = 5
        else: s = 1
        # فشار خرید بیشتر از فروش = بهتر
        if buy_pressure > 0.7: s = min(20, s + 3)
        score += s
        details['buy_pressure'] = s

        # 4. تغییر قیمت (0-20)
        price_change = pair.get('priceChange', {}) or {}
        ch_1h = float(price_change.get('h1', 0) or 0)
        ch_6h = float(price_change.get('h6', 0) or 0)
        ch_24h = float(price_change.get('h24', 0) or 0)
        if 5 < ch_1h < 50: s = 20      # پامپ در حال شروع
        elif 0 < ch_1h < 5: s = 15     # شروع حرکت
        elif ch_1h > 50: s = 8         # شاید دیر شده
        elif ch_1h < -20: s = 3        # دامپ
        else: s = 6
        score += s
        details['price_momentum'] = s

        # 5. سن توکن (جدیدتر = ریسک بیشتر ولی شانس بیشتر) (0-15)
        now = datetime.now(timezone.utc).timestamp() * 1000
        created = pair.get('pairCreatedAt', 0) or 0
        age_h = (now - created) / (1000 * 3600) if created > 0 else 999
        if 1 < age_h < 6: s = 15       # خیلی جدید
        elif 6 < age_h < 12: s = 13
        elif 12 < age_h < 24: s = 10
        elif 24 < age_h < 48: s = 7
        else: s = 3
        score += s
        details['freshness'] = s

        # verdict
        if score >= 75: verdict = '🚀 پتانسیل بالا'
        elif score >= 60: verdict = '📈 امیدوارکننده'
        elif score >= 45: verdict = '🟡 متوسط'
        elif score >= 30: verdict = '🔶 ضعیف'
        else: verdict = '⚠️ ریسک بالا'

        # ریسک‌ها
        risks = []
        if liq < 10_000: risks.append('نقدینگی کم')
        if age_h < 2: risks.append('خیلی جدید')
        if vol_24h < 5_000: risks.append('حجم پایین')
        if buy_pressure < 0.4: risks.append('فشار فروش')

        return {
            'score': min(100, score),
            'verdict': verdict,
            'details': details,
            'risks': risks,
            'age_hours': round(age_h, 1),
            'buy_pressure_pct': round(buy_pressure * 100, 1),
            'buys_1h': buys,
            'sells_1h': sells,
        }

    def get_buy_link(self, chain: str, address: str) -> str:
        template = BUY_LINKS.get(chain, "")
        return template.format(address=address) if template else ""

    def get_explorer_link(self, chain: str, address: str) -> str:
        template = EXPLORER_LINKS.get(chain, "")
        return template.format(address=address) if template else ""

    # ── Top New Pumps ──────────────────────────────────────────────────────────

    async def get_top_new_pumps(self, chain: str = "solana", limit: int = 8) -> list:
        """برترین شت‌کوین‌های جدید با پتانسیل پامپ"""
        # چند endpoint را امتحان کن
        all_pairs = []

        # 1. Boosted tokens
        boosted = await self.get_boosted_tokens()
        for b in boosted[:20]:
            addr = b.get('tokenAddress', '')
            c = b.get('chainId', '')
            if chain != 'all' and c != chain:
                continue
            if addr:
                pair_data = await self.get_pair_data(c, addr)
                if pair_data:
                    all_pairs.append(pair_data)
            await asyncio.sleep(0.3)

        # 2. Search new pairs
        new_pairs = await self.search_new_pairs(chain)
        all_pairs.extend(new_pairs)

        # Score and sort
        scored = []
        seen = set()
        for pair in all_pairs:
            addr = (pair.get('baseToken') or {}).get('address', '')
            if addr in seen or not addr:
                continue
            seen.add(addr)

            pump_info = self.calc_shitcoin_pump_score(pair)
            if pump_info['score'] >= 30:  # فقط امتیاز بالاتر از 30
                scored.append({**pair, 'pump_info': pump_info})

        scored.sort(key=lambda x: x['pump_info']['score'], reverse=True)
        return scored[:limit]

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
