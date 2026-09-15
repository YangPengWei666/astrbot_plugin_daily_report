# 每日早报插件 (astrbot_plugin_daily_report)

对机器人说「**早**」，自动收到三条自然语言早报：

1. **问候**（秒发）—— 早上好呀☀️
2. **天气**（约0.2秒）—— 城市天气 + 与昨天冷热对比（增减衣提示）+ 降水带伞提示 + 明后天
3. **新闻 + 加密货币 + 每日一言**（约2-3秒）—— 今日头条热榜6条 + 币安行情（当前价/24h/本月走势）+ 诗词一言 + 结尾祝福

## ✨ 特性

- **零依赖**：仅使用 AstrBot 核心 API，无任何第三方包
- **零 key**：天气(open-meteo)、新闻(头条热榜)、币价(币安Vision+Gate.io双源)、一言(hitokoto) 全部为免费公开 API
- **全平台兼容**：微信 / Telegram / QQ / 飞书 等所有 AstrBot 支持平台
- **国内直连友好**：币价数据源选择国内可直连的官方域名，无需代理
- **可配置**：城市与经纬度、加密货币开关、币种列表均可自定义

## 📦 安装

### 方法一：AstrBot 插件商店安装（推荐）
在 AstrBot 管理面板 → 插件商店 → 搜索 `每日早报` → 一键安装。

### 方法二：手动安装
将本仓库克隆/下载到 AstrBot 的 `data/plugins/` 目录：

```bash
cd ~/astrbot/AstrBot/data/plugins
git clone https://github.com/YangPengWei666/astrbot_plugin_daily_report.git
```

然后在 AstrBot 管理面板重启或热重载插件。

## ⚙️ 配置

在 AstrBot 管理面板 → 插件管理 → 每日早报 → 配置：

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `city_name` | 天气播报中的城市显示名称 | 原平市 |
| `latitude` | 天气查询纬度 | 38.73 |
| `longitude` | 天气查询经度 | 112.71 |
| `enable_crypto` | 是否播报加密货币行情 | true |
| `crypto_symbols` | 币种交易对（逗号分隔） | BTCUSDT,ETHUSDT,DOGEUSDT |

**自定义币种示例**：`BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT`（支持所有币安现货交易对，格式为 `币种+USDT`）

## 🚀 使用

对机器人发送以下任一触发词：

```
早 / 早上好 / 早安 / 早报 / morning / Morning / 早呀 / 早啊
```

## 📄 数据源

| 数据 | 来源 | 是否需要key |
|---|---|---|
| 天气 | open-meteo.com（全球开源天气API） | 否 |
| 新闻 | 今日头条官方热榜（备用：澎湃RSS） | 否 |
| 加密货币 | 币安 Vision 数据域名（主，国内可访问）+ Gate.io（备用，自动切换） | 否 |
| 每日一言 | hitokoto.cn（诗词类型） | 否 |

> **加密货币兼容说明**：主源使用币安官方数据域名 `data-api.binance.vision`（国内可直连），若主源故障自动切换 Gate.io，保证国内/海外用户都能正常收到币价。

## 🗓️ 版本历史

- **v5.0.0**（2026-09）：通用化改造——城市/经纬度/币种可配置、加密货币开关、删除调试命令、标准插件包结构
- v4.7.0：三条消息定型（问候/天气/新闻+货币+一言），并行抓取优化
- v1.0.0~v4.x：内部迭代版本

## 📜 开源协议

MIT License
