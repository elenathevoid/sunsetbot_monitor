"""
火烧云预报推送脚本
数据来源: sunsetbot.top
推送渠道: PushPlus -> 微信

使用方式:
  python main.py morning    # 早晨推送: 今日日落 + 明日日出 + 明日日落
  python main.py afternoon  # 下午复查: 仅当今日日落达到小烧及以上时推送
"""

import os
import sys
import json
import time
import random
import requests
from datetime import datetime, timezone, timedelta

# ============== 配置 ==============
CITY = os.environ.get("SB_CITY", "上海")          # 查询城市
MODEL = os.environ.get("SB_MODEL", "EC")          # 预报模型: EC 或 GFS
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")  # PushPlus Token
BASE_URL = "https://sunsetbot.top"

# 上海时区 UTC+8
CST = timezone(timedelta(hours=8))

# 火烧云等级排序 (从低到高)
BURN_LEVELS = ["不烧", "微烧", "小烧", "中烧", "大烧", "超大烧"]
# 小烧及以上的等级索引
SMALL_BURN_INDEX = BURN_LEVELS.index("小烧")


def now_cst():
    """获取当前上海时间"""
    return datetime.now(CST)


def fetch_forecast(city, event, model=MODEL):
    """
    从 sunsetbot.top 获取火烧云预报数据

    参数:
        city:  城市名, 如 "上海"
        event: 事件类型
               set_1  = 今天日落
               rise_1 = 今天日出
               set_2  = 明天日落
               rise_2 = 明天日出
        model: 预报模型, "EC" 或 "GFS"

    返回:
        dict 或 None (请求失败时)
    """
    params = {
        "query_id": str(random.randint(1, 99999999)),
        "intend": "select_city",
        "query_city": city,
        "event_date": "None",
        "event": event,
        "times": "None",
        "model": model,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL + "/",
    }

    try:
        resp = requests.get(BASE_URL + "/", params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            print(f"[WARNING] {city} {event} 返回状态: {data.get('status')}")
            return None

        return data

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 请求失败 {city} {event}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON解析失败 {city} {event}: {e}")
        return None


def parse_quality(tb_quality):
    """
    解析鲜艳度字段, 提取数值和等级

    输入示例: "0.077（小烧）"
    返回: (0.077, "小烧")
    """
    if not tb_quality:
        return 0.0, "未知"

    # 提取括号中的等级
    value = 0.0
    level = "未知"

    # 尝试提取数值
    parts = tb_quality.split("（")
    if len(parts) >= 1:
        try:
            value = float(parts[0])
        except ValueError:
            pass

    # 提取等级文字
    if "（" in tb_quality:
        level_part = tb_quality.split("（")[1].replace("）", "").strip()
        level = level_part
    elif "(" in tb_quality:
        level_part = tb_quality.split("(")[1].replace(")", "").strip()
        level = level_part

    return value, level


def is_small_burn_or_above(level):
    """判断是否达到小烧及以上"""
    for i, bl in enumerate(BURN_LEVELS):
        if bl in level:
            return i >= SMALL_BURN_INDEX
    return False


def get_emoji_for_level(level):
    """根据等级返回对应emoji"""
    if "超大烧" in level:
        return "🔥🔥🔥🔥🔥"
    elif "大烧" in level:
        return "🔥🔥🔥🔥"
    elif "中烧" in level:
        return "🔥🔥🔥"
    elif "小烧" in level:
        return "🔥🔥"
    elif "微烧" in level:
        return "🔥"
    else:
        return "☁️"


def format_forecast_item(label, data):
    """格式化单条预报信息"""
    if data is None:
        return f"📌 {label}\n   ⚠️ 数据获取失败\n"

    city = data.get("display_city_name", "未知")
    event_name = data.get("display_event_name_cn", "")
    event_time = data.get("tb_event_time", "未知")
    quality = data.get("tb_quality", "未知")
    aod = data.get("tb_aod", "未知")
    model = data.get("display_model", "")
    times_name = data.get("display_times_name", "")
    times_str = data.get("display_times_str", "")

    value, level = parse_quality(quality)
    emoji = get_emoji_for_level(level)

    text = (
        f"📌 {label}\n"
        f"   📍 {city} {event_name}\n"
        f"   🕐 {event_time}\n"
        f"   {emoji} 鲜艳度: {quality}\n"
        f"   🌫️ 气溶胶: {aod}\n"
        f"   📊 模型: {model} | {times_name}({times_str})\n"
    )
    return text, value, level


def send_pushplus(title, content):
    """
    通过 PushPlus 推送消息到微信

    参数:
        title:   消息标题
        content: 消息内容 (支持 HTML)
    """
    if not PUSHPLUS_TOKEN:
        print("[ERROR] 未配置 PUSHPLUS_TOKEN 环境变量")
        return False

    url = "http://www.pushplus.plus/send"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html",
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        if result.get("code") == 200:
            print(f"[OK] PushPlus 推送成功: {result.get('msg', '')}")
            return True
        else:
            print(f"[ERROR] PushPlus 推送失败: {result}")
            return False

    except Exception as e:
        print(f"[ERROR] PushPlus 请求异常: {e}")
        return False


# ============== 早晨推送 ==============
def run_morning():
    """
    早晨推送逻辑:
    获取今日日落、明日日出、明日日落的预报, 组合成一条消息推送
    """
    now = now_cst()
    date_str = now.strftime("%Y年%m月%d日")
    print(f"[INFO] 早晨推送启动 - {date_str} {now.strftime('%H:%M:%S')} CST")

    # 抓取三项数据
    print("[INFO] 正在获取今日日落...")
    today_sunset = fetch_forecast(CITY, "set_1")
    time.sleep(0.5)

    print("[INFO] 正在获取明日日出...")
    tomorrow_sunrise = fetch_forecast(CITY, "rise_2")
    time.sleep(0.5)

    print("[INFO] 正在获取明日日落...")
    tomorrow_sunset = fetch_forecast(CITY, "set_2")

    # 组装消息
    lines = []
    lines.append(f"<h2>🌅 火烧云日报 | {date_str}</h2>")
    lines.append(f"<p>📍 城市: {CITY} | 📊 模型: {MODEL}</p>")
    lines.append("<hr>")

    # 今日日落
    if today_sunset:
        quality = today_sunset.get("tb_quality", "")
        _, level = parse_quality(quality)
        emoji = get_emoji_for_level(level)
        lines.append(f"<h3>{emoji} 今日日落</h3>")
        lines.append("<ul>")
        lines.append(f"<li>📍 {today_sunset.get('display_city_name', '')} {today_sunset.get('display_event_name_cn', '')}</li>")
        lines.append(f"<li>🕐 {today_sunset.get('tb_event_time', '未知')}</li>")
        lines.append(f"<li>🔥 鲜艳度: <b>{quality}</b></li>")
        lines.append(f"<li>🌫️ 气溶胶: {today_sunset.get('tb_aod', '未知')}</li>")
        lines.append(f"<li>📊 {today_sunset.get('display_model', '')} | {today_sunset.get('display_times_name', '')}({today_sunset.get('display_times_str', '')})</li>")
        lines.append("</ul>")
    else:
        lines.append("<h3>☁️ 今日日落</h3><p>⚠️ 数据获取失败</p>")

    # 明日日出
    if tomorrow_sunrise:
        quality = tomorrow_sunrise.get("tb_quality", "")
        _, level = parse_quality(quality)
        emoji = get_emoji_for_level(level)
        lines.append(f"<h3>{emoji} 明日日出</h3>")
        lines.append("<ul>")
        lines.append(f"<li>📍 {tomorrow_sunrise.get('display_city_name', '')} {tomorrow_sunrise.get('display_event_name_cn', '')}</li>")
        lines.append(f"<li>🕐 {tomorrow_sunrise.get('tb_event_time', '未知')}</li>")
        lines.append(f"<li>🔥 鲜艳度: <b>{quality}</b></li>")
        lines.append(f"<li>🌫️ 气溶胶: {tomorrow_sunrise.get('tb_aod', '未知')}</li>")
        lines.append(f"<li>📊 {tomorrow_sunrise.get('display_model', '')} | {tomorrow_sunrise.get('display_times_name', '')}({tomorrow_sunrise.get('display_times_str', '')})</li>")
        lines.append("</ul>")
    else:
        lines.append("<h3>☁️ 明日日出</h3><p>⚠️ 数据获取失败</p>")

    # 明日日落
    if tomorrow_sunset:
        quality = tomorrow_sunset.get("tb_quality", "")
        _, level = parse_quality(quality)
        emoji = get_emoji_for_level(level)
        lines.append(f"<h3>{emoji} 明日日落</h3>")
        lines.append("<ul>")
        lines.append(f"<li>📍 {tomorrow_sunset.get('display_city_name', '')} {tomorrow_sunset.get('display_event_name_cn', '')}</li>")
        lines.append(f"<li>🕐 {tomorrow_sunset.get('tb_event_time', '未知')}</li>")
        lines.append(f"<li>🔥 鲜艳度: <b>{quality}</b></li>")
        lines.append(f"<li>🌫️ 气溶胶: {tomorrow_sunset.get('tb_aod', '未知')}</li>")
        lines.append(f"<li>📊 {tomorrow_sunset.get('display_model', '')} | {tomorrow_sunset.get('display_times_name', '')}({tomorrow_sunset.get('display_times_str', '')})</li>")
        lines.append("</ul>")
    else:
        lines.append("<h3>☁️ 明日日落</h3><p>⚠️ 数据获取失败</p>")

    lines.append("<hr>")
    lines.append(f"<p style='color:gray;font-size:12px;'>数据来源: sunsetbot.top | 推送时间: {now.strftime('%Y-%m-%d %H:%M:%S')} CST</p>")

    content = "\n".join(lines)

    # 判断今日日落是否达到小烧及以上
    today_level = "未知"
    if today_sunset:
        _, today_level = parse_quality(today_sunset.get("tb_quality", ""))

    title = f"🌅 火烧云日报 {date_str}"
    if is_small_burn_or_above(today_level):
        title = f"今日日落{today_level}{get_emoji_for_level(today_level)} | {title}"


    print(f"[INFO] 今日日落等级: {today_level}")
    print(f"[INFO] 小烧及以上: {is_small_burn_or_above(today_level)}")
    print(f"[INFO] 消息标题: {title}")

    # 推送
    success = send_pushplus(title, content)
    if success:
        print("[INFO] 早晨推送完成")
    else:
        print("[ERROR] 早晨推送失败")
        sys.exit(1)


# ============== 下午复查 ==============
def run_afternoon():
    """
    下午复查逻辑:
    重新获取今日日落预报, 仅当达到小烧及以上时推送
    """
    now = now_cst()
    date_str = now.strftime("%Y年%m月%d日")
    print(f"[INFO] 下午复查启动 - {date_str} {now.strftime('%H:%M:%S')} CST")

    print("[INFO] 正在复查今日日落...")
    today_sunset = fetch_forecast(CITY, "set_1")

    if today_sunset is None:
        print("[WARNING] 数据获取失败, 跳过推送")
        return

    quality = today_sunset.get("tb_quality", "")
    value, level = parse_quality(quality)
    emoji = get_emoji_for_level(level)

    print(f"[INFO] 今日日落复查结果: {quality} (等级: {level})")

    if not is_small_burn_or_above(level):
        print(f"[INFO] 今日日落等级为「{level}」, 未达到小烧及以上, 不推送")
        return

    print(f"[INFO] 今日日落等级为「{level}」, 达到小烧及以上, 开始推送")

    # 组装消息
    lines = []
    lines.append(f"<h2>🔥 火烧云下午复查 | {date_str}</h2>")
    lines.append(f"<p>📍 城市: {CITY} | 📊 模型: {MODEL}</p>")
    lines.append("<hr>")
    lines.append(f"<h3>{emoji} 今日日落（复查）</h3>")
    lines.append("<ul>")
    lines.append(f"<li>📍 {today_sunset.get('display_city_name', '')} {today_sunset.get('display_event_name_cn', '')}</li>")
    lines.append(f"<li>🕐 {today_sunset.get('tb_event_time', '未知')}</li>")
    lines.append(f"<li>🔥 鲜艳度: <b style='color:red;font-size:18px;'>{quality}</b></li>")
    lines.append(f"<li>🌫️ 气溶胶: {today_sunset.get('tb_aod', '未知')}</li>")
    lines.append(f"<li>📊 {today_sunset.get('display_model', '')} | {today_sunset.get('display_times_name', '')}({today_sunset.get('display_times_str', '')})</li>")
    lines.append("</ul>")
    lines.append("<hr>")
    lines.append(f"<p style='color:gray;font-size:12px;'>数据来源: sunsetbot.top | 复查时间: {now.strftime('%Y-%m-%d %H:%M:%S')} CST</p>")

    content = "\n".join(lines)
        title = f"今日日落{level}{emoji} | 🔥 火烧云Recheck {date_str}"

    success = send_pushplus(title, content)
    if success:
        print("[INFO] 下午复查推送完成")
    else:
        print("[ERROR] 下午复查推送失败")
        sys.exit(1)


# ============== 主入口 ==============
def main():
    if len(sys.argv) < 2:
        print("用法: python main.py [morning|afternoon]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "morning":
        run_morning()
    elif mode == "afternoon":
        run_afternoon()
    else:
        print(f"未知模式: {mode}")
        print("用法: python main.py [morning|afternoon]")
        sys.exit(1)


if __name__ == "__main__":
    main()
