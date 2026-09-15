# -*- coding: utf-8 -*-
"""
每日早报插件 v5.0.0（通用版）
用户对机器人说"早/早上好/早安/早报/morning"等，机器人分三条自然语言回复：
- 第一条（秒发）：问候
- 第二条（快，约0.2s）：城市天气（含与昨天冷热对比 + 明后天 + 增减衣/带伞提示）
- 第三条（慢，约2-3s）：新闻（今日头条热榜）+ 加密货币行情（币安）+ 每日一言

特性：
- 零第三方依赖，仅 AstrBot 核心 API
- 零 key：所有数据源均为免费公开 API
- 城市/经纬度/币种均可配置（见 _conf_schema.json）
"""
import asyncio
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

PLUGIN_NAME = "astrbot_plugin_daily_report"
PLUGIN_AUTHOR = "小康助手"
PLUGIN_DESC = "每日早报：说'早'即收到天气+新闻+加密货币+每日一言，全部免费API零key"
PLUGIN_VERSION = "5.0.0"

# ===== 默认配置（可被 _conf_schema.json 覆盖） =====
DEFAULT_CONFIG = {
    "city_name": "北京市",
    "latitude": 39.90,
    "longitude": 116.40,
    "enable_crypto": True,
    "crypto_symbols": ["BTCUSDT", "ETHUSDT", "DOGEUSDT"],
}

# ===== 加密货币价格数据源（多源自动切换，全部免费无key，国内可达） =====
# 主源：Binance Vision 官方数据域名（国内可访问，数据格式与币安一致）
# 备用：Gate.io 公开API（国内可访问；ETH 偶发超时，自动重试）
BINANCE_API_HOST = "https://data-api.binance.vision"
GATE_API_HOST = "https://api.gateio.ws"

# 币种显示名（内置映射，未列出的币种显示原符号）
CRYPTO_DISPLAY = {
    "BTCUSDT": "比特币🟠",
    "ETHUSDT": "以太坊💎",
    "DOGEUSDT": "狗狗币🐶",
    "SOLUSDT": "Solana🟣",
    "BNBUSDT": "币安币🟡",
    "XRPUSDT": "瑞波币🔷",
    "ADAUSDT": "艾达币🔵",
    "LTCUSDT": "莱特币⚪",
    "AVAXUSDT": "雪崩币🔺",
}

NEWS_COUNT = 6

# WMO 天气代码 -> 中文
WMO_MAP = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "雾", 48: "冻雾",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
    56: "冻毛毛雨", 57: "冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "强阵雨", 82: "暴雨",
    85: "阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "雷暴伴冰雹",
}


def fetch_url(url, timeout=15, ua=None):
    headers = {"User-Agent": ua or "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_weather(city_name, latitude, longitude):
    """城市天气：昨天+今明后天（0.2s快源），完全由配置决定"""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode,precipitation_probability_max"
        f"&timezone=Asia%2FShanghai&past_days=1&forecast_days=3"
    )
    try:
        data = json.loads(fetch_url(url, timeout=12))
        daily = data["daily"]
        result = []
        for i in range(min(4, len(daily["time"]))):
            code = daily["weathercode"][i]
            desc = WMO_MAP.get(code, "多云")
            tmax = round(float(daily["temperature_2m_max"][i]))
            tmin = round(float(daily["temperature_2m_min"][i]))
            prob = daily.get("precipitation_probability_max", [None] * 4)[i]
            result.append({
                "date": daily["time"][i],
                "desc": desc,
                "tmax": tmax,
                "tmin": tmin,
                "rain_prob": int(prob) if prob is not None else None,
            })
        return result
    except Exception as e:
        logger.error(f"天气获取失败: {e}")
        return None


def get_international_news():
    """今日头条官方热榜（内容已过国内审核，各平台可正常送达）"""
    try:
        req = urllib.request.Request(
            "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        items = data.get("data", []) or []
        titles = []
        for it in items:
            title = str(it.get("Title", "")).strip()
            if title:
                titles.append(title)
            if len(titles) >= NEWS_COUNT:
                break
        if titles:
            return titles
        raise ValueError("头条热榜为空")
    except Exception as e:
        logger.error(f"头条热榜获取失败: {e}")
        try:
            # 备用：澎湃新闻
            data = fetch_url("https://feedx.net/rss/thepaper.xml")
            root = ET.fromstring(data)
            return [i.find('title').text.strip() for i in root.findall('.//item')[:NEWS_COUNT]
                    if i.find('title') is not None and i.find('title').text]
        except Exception as e2:
            logger.error(f"备用新闻源也失败: {e2}")
            return ["新闻源暂时不可用"]


def _binance_crypto(symbol):
    """币安 Vision 数据：当前价 + 24h涨跌 + 本月涨跌"""
    data = json.loads(fetch_url(f"{BINANCE_API_HOST}/api/v3/ticker/24hr?symbol={symbol}", timeout=10))
    price = float(data["lastPrice"])
    change_24h = float(data["priceChangePercent"])
    klines = json.loads(fetch_url(f"{BINANCE_API_HOST}/api/v3/klines?symbol={symbol}&interval=1M&limit=1", timeout=10))
    month_open = float(klines[-1][1])
    month_change = (price - month_open) / month_open * 100
    return price, change_24h, month_change


def _gate_crypto(symbol):
    """Gate.io 数据：当前价 + 24h涨跌 + 30天涨跌（Gate无1M K线，用30d近似）"""
    pair = symbol.replace("USDT", "_USDT")
    data = json.loads(fetch_url(f"{GATE_API_HOST}/api/v4/spot/tickers?currency_pair={pair}", timeout=10))
    if not isinstance(data, list) or not data:
        raise Exception(f"Gate.io {symbol} 返回为空")
    price = float(data[0]["last"])
    change_24h = float(data[0]["change_percentage"])
    klines = json.loads(fetch_url(f"{GATE_API_HOST}/api/v4/spot/candlesticks?currency_pair={pair}&interval=30d&limit=1", timeout=10))
    if isinstance(klines, list) and klines:
        month_open = float(klines[-1][5])  # [ts, quote_vol, close, high, low, open, vol, closed]
        month_change = (price - month_open) / month_open * 100
    else:
        month_change = 0
    return price, change_24h, month_change


def get_crypto(symbols):
    """多源自动切换：Binance Vision 主，Gate.io 备用，保证国内外用户都能用"""
    results = []
    for symbol in symbols:
        symbol = str(symbol).strip().upper()
        if not symbol:
            continue
        name = CRYPTO_DISPLAY.get(symbol, symbol.replace("USDT", ""))
        price, change_24h, month_change = 0, 0, 0
        try:
            price, change_24h, month_change = _binance_crypto(symbol)
        except Exception as e:
            logger.warning(f"{symbol} 币安源失败，尝试Gate: {e}")
            try:
                price, change_24h, month_change = _gate_crypto(symbol)
            except Exception as e2:
                logger.error(f"{symbol} 所有数据源均失败: {e2}")
        results.append((name, price, change_24h, month_change))
    return results


def get_quote():
    """每日一言（免费接口）"""
    try:
        req = urllib.request.Request("https://v1.hitokoto.cn/?c=i&encode=json", headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        hitokoto = data.get("hitokoto", "").strip()
        src = data.get("from", "").strip()
        if not hitokoto:
            raise ValueError("一言为空")
        if src:
            return f"{hitokoto}——{src}"
        return hitokoto
    except Exception as e:
        logger.error(f"每日一言获取失败: {e}")
        return None


def _change_str(c):
    if c >= 0:
        return f"上涨{c:.2f}%"
    return f"下跌{abs(c):.2f}%"


def _price_str(name, price):
    if price <= 0:
        return "价格获取失败"
    if "DOGE" in name or "狗狗" in name or "SHIB" in name:
        return f"${price:.4f}"
    return f"${price:,.2f}"


def build_weather_msg(weather, city_name):
    """第一条天气：冷热对比 + 明后天 + 增减衣/带伞"""
    if not weather:
        return f"{city_name}天气数据暂时获取失败，稍后为您播报其他内容。"
    yesterday = weather[0] if len(weather) > 0 else None
    today = weather[1] if len(weather) > 1 else None
    if today is None:
        return f"{city_name}天气数据暂时获取失败，稍后为您播报其他内容。"

    parts = []
    parts.append(f"今天{city_name}{today['desc']}，气温{today['tmin']}到{today['tmax']}度🌡️。")
    if yesterday is not None:
        diff = today["tmax"] - yesterday["tmax"]
        if diff > 0:
            parts.append(f"比昨天暖和了{diff}度，可以适当减件衣服👕。")
        elif diff < 0:
            parts.append(f"比昨天冷了{abs(diff)}度，记得多穿点别着凉🧥。")
        else:
            parts.append("和昨天差不多，穿着照旧就行。")
    if today.get("rain_prob") is not None and today["rain_prob"] >= 30:
        parts.append(f"今天降水概率{today['rain_prob']}%，出门记得带伞☔。")
    if len(weather) > 2:
        t1 = weather[2]
        d1 = f"{t1['desc']}，{t1['tmin']}到{t1['tmax']}度"
        parts.append(f"明天{d1}。")
        if t1.get("rain_prob") is not None and t1["rain_prob"] >= 30:
            parts.append(f"明天降水概率{t1['rain_prob']}%，提前留意☔。")
    if len(weather) > 3:
        t2 = weather[3]
        parts.append(f"后天{t2['desc']}，{t2['tmin']}到{t2['tmax']}度。")
    return "".join(parts)


def build_message(news_list, crypto_list, quote, enable_crypto):
    """第三条：新闻 + 货币（可开关） + 每日一言"""
    lines = []
    lines.append("然后呢，咱们看今天的新闻——")
    for news in news_list:
        lines.append(f"✨{news}。")
    lines.append("")
    if enable_crypto and crypto_list:
        lines.append("最后再看看数字货币💰——")
        for name, price, c24, cmonth in crypto_list:
            pstr = _price_str(name, price)
            if price > 0:
                lines.append(f"{name}今天{pstr}，比昨天{_change_str(c24)}，本月整体{_change_str(cmonth)}。")
            else:
                lines.append(f"{name}行情数据暂时获取失败。")
        lines.append("")
    if quote:
        lines.append(f"最后送你一句话：{quote}")
    lines.append("")
    lines.append("好啦，今天的信息就这些，祝你有愉快的一天😊")
    return "\n".join(lines)


@register(PLUGIN_NAME, PLUGIN_AUTHOR, PLUGIN_DESC, PLUGIN_VERSION)
class DailyReportPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or AstrBotConfig()

    def _cfg(self, key, default=None):
        """读配置，兼容缺失字段"""
        try:
            val = self.config.get(key)
            if val is None or (isinstance(val, str) and not val.strip()):
                return default
            return val
        except Exception:
            return default

    @filter.regex(r"^(早|早上好|早安|早报|morning|Morning|早呀|早啊)$")
    async def daily_report(self, event: AstrMessageEvent):
        try:
            logger.info(f"[早报插件] 收到触发: platform={event.get_platform_id()}, session={event.get_session_id()}")

            # 读取配置
            city_name = self._cfg("city_name", "北京市")
            latitude = float(self._cfg("latitude", 39.90))
            longitude = float(self._cfg("longitude", 116.40))
            enable_crypto = bool(self._cfg("enable_crypto", True))
            symbols_cfg = self._cfg("crypto_symbols", ["BTCUSDT", "ETHUSDT", "DOGEUSDT"])
            if isinstance(symbols_cfg, str):
                symbols = [s.strip() for s in symbols_cfg.replace("，", ",").split(",") if s.strip()]
            else:
                symbols = list(symbols_cfg)

            # 第一条：秒发问候
            await event.send(event.plain_result("早上好呀☀️"))
            logger.info("[早报插件] 第一条(问候)已发送")

            # 第二条：天气（快源，约0.2s）
            weather = await asyncio.to_thread(get_weather, city_name, latitude, longitude)
            weather_msg = build_weather_msg(weather, city_name)
            logger.info(f"[早报插件] 天气获取完成: {weather is not None}")
            await event.send(event.plain_result(weather_msg))
            logger.info("[早报插件] 第二条(天气)已发送")

            # 第三条：新闻+货币+一言（并行抓取）
            news_list, crypto_list, quote = await asyncio.gather(
                asyncio.to_thread(get_international_news),
                asyncio.to_thread(get_crypto, symbols),
                asyncio.to_thread(get_quote),
            )
            logger.info(f"[早报插件] 新闻获取完成: {len(news_list)}条")
            logger.info(f"[早报插件] 币价获取完成: {len(crypto_list)}条")
            logger.info(f"[早报插件] 每日一言获取完成: {quote is not None}")
            message = build_message(news_list, crypto_list, quote, enable_crypto)
            logger.info(f"[早报插件] 播报组装完成: {len(message)}字符")
            await event.send(event.plain_result(message))
            logger.info("[早报插件] 第三条(新闻+货币+一言)已发送")
        except Exception as e:
            logger.error(f"[早报插件] 生成早报失败: {e}")
            await event.send(event.plain_result("抱歉，播报生成遇到了一点问题，请稍后再试~"))
