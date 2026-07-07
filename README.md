# 🔥 火烧云预报推送

每天自动抓取 sunsetbot.top 的火烧云预报数据，通过 PushPlus 推送到微信。

## 功能

| 时间 | 动作 |
|------|------|
| 每天 08:05 | 推送今日日落 + 明日日出 + 明日日落的火烧云预报 |
| 每天 15:05 | 复查今日日落，仅当达到小烧及以上时才推送 |

## 配置

在仓库 Settings → Secrets and variables → Actions 中添加：

Secrets:
- PUSHPLUS_TOKEN: 你的 PushPlus Token

Variables (可选):
- SB_CITY: 上海 (默认上海)
- SB_MODEL: EC (默认 EC)
