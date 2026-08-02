#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV Source Collector v3 - Categorized & Sorted
Auto-classifies channels into: CCTV, Weishi, Local, HK-TW-MO, International, etc.
"""
import os, re, json, time, logging
from datetime import datetime
from urllib.request import urlopen, Request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = "/opt/iptv"
M3U_DIR = os.path.join(BASE_DIR, "m3u")
TXT_DIR = os.path.join(BASE_DIR, "txt")
LOG_DIR = os.path.join(BASE_DIR, "logs")
TIMEOUT = 8
MAX_WORKERS = 30

SOURCES = [
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://iptv-org.github.io/iptv/languages/zho.m3u",
    "https://iptv-org.github.io/iptv/countries/cn.m3u",
    "https://iptv-org.github.io/iptv/countries/hk.m3u",
    "https://iptv-org.github.io/iptv/countries/tw.m3u",
    "https://iptv-org.github.io/iptv/countries/mo.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
    "https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_all.m3u8",
]

# CCSH/IPTV：每日自动测速筛选的国内直播源（央视/卫视/地方台/港澳台），
# 含大量国内运营商源。该源由 GitHub Actions 每日 04:00 自动更新+测速，
# 因此跳过本脚本的服务器验证（海外服务器会误杀国内源）。
# vbskycn/iptv：服务器自动扫描验证的 IPTV4 国内直连源，每 6 小时更新，
# 同样跳过验证（iptv6 大部分已失效，不收录）。
TRUSTED_SOURCES = [
    "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.m3u",          # CCSH 完整版（含地方台）
    "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live_lite.m3u",     # CCSH 精简版（无地方台）
    "https://live.zbds.top/tv/iptv4.txt",                                            # vbskycn IPTV4 TXT（已扫描验证）
    "https://raw.githubusercontent.com/vbskycn/iptv/refs/heads/master/tv/iptv4.txt", # vbskycn GitHub 备用
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "collect_v3.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ==================== Classification Rules ====================

# CCTV keywords (in priority order)
CCTV_KEYWORDS = [
    "CCTV", "央视", "CGTN", "中央电视", "中央电视台",
    "CCTV-1", "CCTV-2", "CCTV-3", "CCTV-4", "CCTV-5",
    "CCTV-6", "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10",
    "CCTV-11", "CCTV-12", "CCTV-13", "CCTV-14", "CCTV-15",
    "CCTV-16", "CCTV-17", "CCTV5+", "CCTV4K", "CCTV8K",
]

# Weishi (satellite TV) keywords
WEISHI_KEYWORDS = [
    "卫视", "东方卫视", "湖南卫视", "浙江卫视", "江苏卫视", "北京卫视",
    "广东卫视", "深圳卫视", "四川卫视", "湖北卫视", "辽宁卫视",
    "山东卫视", "河南卫视", "福建卫视", "安徽卫视", "天津卫视",
    "重庆卫视", "陕西卫视", "河北卫视", "山西卫视", "吉林卫视",
    "黑龙江卫视", "江西卫视", "广西卫视", "云南卫视", "贵州卫视",
    "甘肃卫视", "内蒙古卫视", "新疆卫视", "西藏卫视", "青海卫视",
    "宁夏卫视", "海南卫视", "厦门卫视", "东南卫视", "海峡卫视",
    "凤凰卫视", "旅游卫视", "金鹰卡通", "嘉佳卡通", "卡酷少儿",
    "哈哈炫动", "优漫卡通",
]

# Province/City for local TV
PROVINCES = [
    "广东", "广州", "深圳", "东莞", "佛山", "珠海", "中山", "惠州",
    "上海", "浙江", "杭州", "宁波", "温州",
    "江苏", "南京", "苏州", "无锡", "常州", "徐州",
    "北京", "天津", "重庆",
    "湖南", "长沙", "湖北", "武汉", "四川", "成都",
    "山东", "济南", "青岛", "河南", "郑州",
    "福建", "福州", "安徽", "合肥",
    "辽宁", "沈阳", "大连", "吉林", "长春", "黑龙江", "哈尔滨",
    "陕西", "西安", "山西", "太原", "河北", "石家庄",
    "江西", "南昌", "广西", "南宁", "云南", "昆明",
    "贵州", "贵阳", "甘肃", "兰州", "内蒙古", "呼和浩特",
    "新疆", "乌鲁木齐", "西藏", "拉萨", "青海", "西宁",
    "宁夏", "银川", "海南", "海口", "三亚",
]

# HK-TW-MO keywords
HKTWMO_KEYWORDS = [
    "TVB", "ATV", "Viu", "RTHK", "凤凰", "香港",
    "中天", "三立", "民视", "华视", "台视", "大爱",
    "东森", "纬来", "壹电视", "年代", "TVBS", "中视", "公视",
    "原住", "客家", "澳门", "澳亚", "澳视", "莲花",
    "八大", "非凡", "国兴", "高点",
    "CCTV4",  # International
]

# International keywords by region
INTL_REGIONS = {
    "🇺🇸 USA": ["CNN", "Fox", "NBC", "CBS", "ABC", "ESPN", "HBO", "Bloomberg",
                  "USA", "American", "US "],
    "🇬🇧 UK": ["BBC", "Sky", "ITV", "Channel 4", "Channel 5", "UK"],
    "🇯🇵 Japan": ["NHK", "TBS", "Fuji", "TV Asahi", "NTV", "日本", "Japan"],
    "🇰🇷 Korea": ["KBS", "MBC", "SBS", "Korea", "Arirang"],
    "🇫🇷 France": ["France", "TF1", "M6", "Arte"],
    "🇩🇪 Germany": ["ARD", "ZDF", "DW", "German", "Deutsche"],
    "🇪🇸 Spain": ["TVE", "Antena 3", "Spanish", "Telecinco"],
    "🇷🇺 Russia": ["Russia", "RT ", "Первый", "Россия", "Russian"],
    "🇮🇳 India": ["India", "Bollywood", "Hindi", "Tamil"],
    "🇧🇷 Brazil": ["Brazil", "Globo", "SBT", "Record", "Portuguese"],
    "🌍 Africa": ["Africa", "Nigeria", "Kenya", "South Africa", "Ghana"],
    "🌏 Asia": ["Thailand", "Vietnam", "Philippines", "Indonesia", "Malaysia",
                 "Singapore", "Myanmar", "Cambodia", "Laos"],
    "🌎 Americas": ["Mexico", "Argentina", "Colombia", "Chile", "Canada",
                      "Canadian", "CBC"],
    "🌍 Middle East": ["Al Jazeera", "Arab", "Turkey", "Iran", "Iraq",
                        "Saudi", "UAE", "Dubai"],
}


def classify_channel(name, group, url):
    """Classify a channel into a category"""
    text = (name + " " + group).upper()
    name_clean = name.strip()
    
    # 1. CCTV
    for kw in CCTV_KEYWORDS:
        if kw.upper() in text:
            return "📺 CCTV央视"
    
    # 2. Weishi (Satellite TV)
    for kw in WEISHI_KEYWORDS:
        if kw in name_clean or kw.upper() in text:
            return "📡 卫视频道"
    
    # 3. HK-TW-MO
    for kw in HKTWMO_KEYWORDS:
        if kw in name_clean or kw.upper() in text:
            return "🇭🇰 港澳台"
    
    # 4. Chinese local TV (by province)
    for prov in PROVINCES:
        if prov in name_clean:
            return f"🏠 地方台"
    
    # 5. Other Chinese channels
    CN_KEYWORDS = [
        "CHC", "体育", "新闻", "电影", "电视剧", "纪录", "少儿", "卡通",
        "动画", "音乐", "财经", "军事", "教育", "科技", "文化", "旅游",
        "生活", "健康", "法治", "综合", "公共", "都市", "经济", "民生",
        "娱乐", "影视", "戏剧", "戏曲", "经典", "怀旧", "咪咕",
        "珠江", "南方", "轮播", "华数", "百视", "NewTV", "SiTV", "CIBN",
        "斗鱼", "虎牙", "哔哩哔哩", "B站",
    ]
    for kw in CN_KEYWORDS:
        if kw in name_clean:
            return "📺 国内其他"
    
    # 6. International (by region)
    for region, keywords in INTL_REGIONS.items():
        for kw in keywords:
            if kw.upper() in text:
                return f"🌍 {region}"
    
    # 7. If URL or name has country codes
    country_patterns = {
        "🇺🇸 USA": [".us", "USA", "United States"],
        "🇬🇧 UK": [".uk", ".gb", "United Kingdom"],
        "🇯🇵 Japan": [".jp", "Japan", "日本"],
        "🇰🇷 Korea": [".kr", "Korea", "韩国"],
        "🇫🇷 France": [".fr", "France", "法国"],
        "🇩🇪 Germany": [".de", "Germany", "德国"],
        "🇷🇺 Russia": [".ru", "Russia", "俄罗斯"],
        "🇮🇳 India": [".in", "India", "印度"],
        "🇧🇷 Brazil": [".br", "Brazil", "巴西"],
        "🇹🇷 Turkey": [".tr", "Turkey", "土耳其"],
        "🇲🇽 Mexico": [".mx", "Mexico", "墨西哥"],
        "🇨🇦 Canada": [".ca", "Canada", "加拿大"],
        "🇦🇺 Australia": [".au", "Australia", "澳大利亚"],
        "🇮🇹 Italy": [".it", "Italy", "意大利"],
        "🇵🇹 Portugal": [".pt", "Portugal", "葡萄牙"],
        "🇳🇱 Netherlands": [".nl", "Netherlands", "荷兰"],
        "🇸🇪 Sweden": [".se", "Sweden", "瑞典"],
        "🇵🇱 Poland": [".pl", "Poland", "波兰"],
    }
    for region, patterns in country_patterns.items():
        for p in patterns:
            if p.lower() in url.lower() or p.upper() in text:
                return f"🌍 {region}"
    
    # Default: uncategorized international
    return "🌍 其他国际"


def fetch_url(url, timeout=20):
    headers = {"User-Agent": "Mozilla/5.0 IPTV-Collector/3.0"}
    for attempt in range(3):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == 2:
                log.warning(f"Failed: {url}: {e}")
                return None
            time.sleep(2)
    return None


def parse_m3u(content):
    channels = []
    if not content:
        return channels
    lines = content.strip().split("\n")
    current = {}
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            match = re.search(r'#EXTINF:-?\d+\s*(?:[a-z-]+="[^"]*"\s*)*,(.+)', line)
            name = match.group(1).strip() if match else "Unknown"
            logo_m = re.search(r'tvg-logo="([^"]*)"', line)
            logo = logo_m.group(1) if logo_m else ""
            group_m = re.search(r'(?:group-title|tvg-group)="([^"]*)"', line)
            group = group_m.group(1) if group_m else "Other"
            country_m = re.search(r'tvg-country="([^"]*)"', line)
            country = country_m.group(1) if country_m else ""
            current = {"name": name, "logo": logo, "group": group, "country": country}
        elif line and not line.startswith("#"):
            current["url"] = line
            if "name" in current:
                channels.append(current)
            current = {}
    return channels


def parse_txt(content):
    channels = []
    if not content:
        return channels
    current_group = "Other"
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ",#genre#" in line:
            current_group = line.replace(",#genre#", "").strip()
        elif "," in line:
            parts = line.split(",", 1)
            if len(parts) == 2:
                name, url = parts[0].strip(), parts[1].strip()
                if url.startswith("http"):
                    channels.append({"name": name, "url": url, "group": current_group, "logo": "", "country": ""})
    return channels


def validate_channel(channel):
    url = channel.get("url", "")
    if not url:
        return False
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "VLC/3.0"})
        with urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status in (200, 301, 302)
    except:
        try:
            req = Request(url, headers={"User-Agent": "VLC/3.0", "Range": "bytes=0-1024"})
            with urlopen(req, timeout=TIMEOUT) as resp:
                return resp.status in (200, 206, 301, 302)
        except:
            return False


def generate_m3u(channels, title="IPTV"):
    # 注意：不含 #EXTM3U 头，由调用方拼接（避免重复头导致 TVBox 解析失败）
    lines = []
    for ch in channels:
        logo = ch.get("logo", "")
        group = ch.get("category", ch.get("group", "Other"))
        # 品牌化：统一加"天天电视 · "前缀（幂等，避免重复）
        if group and not group.startswith("天天电视"):
            group = f"天天电视 · {group}"
        name = ch.get("name", "Unknown")
        url = ch.get("url", "")
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        # 使用标准 group-title 属性（TVBox 兼容）
        lines.append(f'#EXTINF:-1 group-title="{group}"{logo_attr},{name}')
        lines.append(url)
    return "\n".join(lines)


def dedupe_by_name(channels, max_per_name=3):
    """
    按频道名去重限流：同一频道名最多保留 max_per_name 个源。
    解决 TVBox 菜单里同一频道（如 CCTV1）出现几十个重复源的问题。
    清洗逻辑：去掉常见的分辨率/清晰度后缀，使 "CCTV1"、"CCTV1 高清"、"CCTV1 (1080p)" 归并为同一频道名。
    """
    import re as _re
    cleaned = []
    for ch in channels:
        name = ch.get("name", "")
        # 清洗：去掉 括号后缀/分辨率/清晰度标记
        base = _re.sub(r'\s*[（(]\s*[^）)]*[）)]\s*$', '', name)          # 去 (1080p) （高清）
        base = _re.sub(r'\s*(高清|超清|标清|流畅|原画|蓝光|4K|8K|1080P?|720P?|480P?|60FPS?|VIP|极速|备用)\s*$', '', base, flags=_re.I)  # 去清晰度词
        base = base.strip()
        ch["_base_name"] = base if base else name
        cleaned.append(ch)

    by_name = {}
    for ch in cleaned:
        key = ch["_base_name"]
        by_name.setdefault(key, []).append(ch)

    result = []
    for key, chs in by_name.items():
        # 同一频道名：优先保留 trusted（已验证），再保留其他，最多 max_per_name 个
        chs_sorted = sorted(chs, key=lambda c: (0 if c.get("trusted") else 1, c.get("url", "")))
        result.extend(chs_sorted[:max_per_name])
    return result


def generate_txt(channels):
    lines = []
    groups = {}
    for ch in channels:
        g = ch.get("category", ch.get("group", "Other"))
        if g not in groups:
            groups[g] = []
        groups[g].append(ch)
    # Sort groups
    group_order = [
        "📺 CCTV央视", "📡 卫视频道", "🇭🇰 港澳台", "🏠 地方台",
        "📺 国内其他",
    ]
    intl_groups = sorted([g for g in groups if g.startswith("🌍")])
    sorted_groups = group_order + intl_groups + [g for g in groups if g not in group_order and not g.startswith("🌍")]
    
    for group in sorted_groups:
        if group in groups:
            lines.append(f"{group},#genre#")
            for ch in groups[group]:
                lines.append(f"{ch['name']},{ch['url']}")
            lines.append("")
    return "\n".join(lines)


def sort_channels(channels):
    """Sort channels within each category"""
    category_order = {
        "📺 CCTV央视": 1,
        "📡 卫视频道": 2,
        "🇭🇰 港澳台": 3,
        "🏠 地方台": 4,
        "📺 国内其他": 5,
    }
    
    def sort_key(ch):
        cat = ch.get("category", "")
        cat_num = category_order.get(cat, 10 if cat.startswith("🌍") else 6)
        # Within category, sort by name
        name = ch.get("name", "")
        # Try to extract channel number for CCTV
        cctv_num = 0
        if cat == "📺 CCTV央视":
            m = re.search(r'CCTV[-\s]?(\d+)', name, re.I)
            if m:
                cctv_num = int(m.group(1))
            elif "5+" in name:
                cctv_num = 50
            elif "4K" in name:
                cctv_num = 90
            elif "8K" in name:
                cctv_num = 91
            elif "CGTN" in name:
                cctv_num = 100
        return (cat_num, cctv_num, name)
    
    return sorted(channels, key=sort_key)


def main():
    start_time = time.time()
    log.info("=" * 60)
    log.info("IPTV Collection v3 - Categorized & Sorted")
    log.info("=" * 60)

    # Fetch sources
    all_channels = []
    for src_url in SOURCES:
        log.info(f"Fetching: {src_url}")
        content = fetch_url(src_url, timeout=25)
        if content:
            if "#EXTM3U" in content[:500] or "#EXTINF" in content[:500]:
                channels = parse_m3u(content)
            else:
                channels = parse_txt(content)
            log.info(f"  Parsed {len(channels)} channels")
            all_channels.extend(channels)

    # Fetch trusted sources (CCSH/vbskycn: 已测速筛选，跳过本脚本验证)
    for src_url in TRUSTED_SOURCES:
        log.info(f"Fetching trusted: {src_url}")
        content = fetch_url(src_url, timeout=30)
        if content:
            if "#EXTM3U" in content[:500] or "#EXTINF" in content[:500]:
                channels = parse_m3u(content)
            else:
                channels = parse_txt(content)
            for ch in channels:
                ch["trusted"] = True  # 跳过服务器验证，避免误杀国内源
            log.info(f"  Parsed {len(channels)} channels (trusted)")
            all_channels.extend(channels)

    log.info(f"Total raw: {len(all_channels)}")

    # Deduplicate by URL
    seen = set()
    unique = []
    for ch in all_channels:
        url = ch.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(ch)
    log.info(f"Unique: {len(unique)}")

    # Classify all channels
    for ch in unique:
        ch["category"] = classify_channel(
            ch.get("name", ""),
            ch.get("group", ""),
            ch.get("url", "")
        )
    
    # Count by category
    cat_counts = {}
    for ch in unique:
        cat = ch["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    
    log.info("Category distribution:")
    for cat in sorted(cat_counts.keys()):
        log.info(f"  {cat}: {cat_counts[cat]}")

    # Chinese vs International
    cn_cats = ["📺 CCTV央视", "📡 卫视频道", "🇭🇰 港澳台", "🏠 地方台", "📺 国内其他"]
    cn_channels = [ch for ch in unique if ch["category"] in cn_cats]
    intl_channels = [ch for ch in unique if ch["category"] not in cn_cats]
    
    log.info(f"Chinese channels: {len(cn_channels)}")
    log.info(f"International channels: {len(intl_channels)}")

    # Validate Chinese channels (more strict)
    # 注意：CCSH 的 trusted 频道跳过验证（其自身每日测速，且含国内运营商源，
    # 海外服务器 HEAD 会误杀）。其他频道照常验证。
    trusted_cn = [ch for ch in cn_channels if ch.get("trusted")]
    untrusted_cn = [ch for ch in cn_channels if not ch.get("trusted")]

    log.info(f"Validating {len(untrusted_cn)} Chinese channels (skip {len(trusted_cn)} trusted)...")
    valid_cn = list(trusted_cn)  # trusted 全部保留
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(validate_channel, ch): ch for ch in untrusted_cn}
        done = 0
        for future in as_completed(futures):
            done += 1
            ch = futures[future]
            try:
                if future.result():
                    valid_cn.append(ch)
            except:
                pass
            if done % 100 == 0:
                log.info(f"  {done}/{len(untrusted_cn)}, valid: {len(valid_cn)}")
    
    log.info(f"Valid Chinese: {len(valid_cn)}")

    # International: no validation (too many, too slow)
    # Just keep all
    valid_intl = intl_channels

    # Sort
    valid_cn = sort_channels(valid_cn)
    valid_intl = sort_channels(valid_intl)

    # 去重限流：同一频道名最多保留 3 个源（避免 TVBox 菜单重复爆炸）
    # 注意：cctv/weishi/local/hktwmo 等分类文件内再各自限流一次
    valid_cn = dedupe_by_name(valid_cn, max_per_name=3)
    valid_intl = dedupe_by_name(valid_intl, max_per_name=3)
    log.info(f"After dedupe - Chinese: {len(valid_cn)} | International: {len(valid_intl)}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # === Generate categorized files ===

    # 1. CCTV only
    cctv = [ch for ch in valid_cn if ch["category"] == "📺 CCTV央视"]
    m3u = f"#EXTM3U\n# CCTV - {len(cctv)} channels - {timestamp}\n" + generate_m3u(cctv)
    with open(os.path.join(M3U_DIR, "cctv.m3u"), "w", encoding="utf-8") as f:
        f.write(m3u)

    # 2. Weishi only
    weishi = [ch for ch in valid_cn if ch["category"] == "📡 卫视频道"]
    m3u = f"#EXTM3U\n# Weishi - {len(weishi)} channels - {timestamp}\n" + generate_m3u(weishi)
    with open(os.path.join(M3U_DIR, "weishi.m3u"), "w", encoding="utf-8") as f:
        f.write(m3u)

    # 3. HK-TW-MO
    hktwmo = [ch for ch in valid_cn if ch["category"] == "🇭🇰 港澳台"]
    m3u = f"#EXTM3U\n# HK-TW-MO - {len(hktwmo)} channels - {timestamp}\n" + generate_m3u(hktwmo)
    with open(os.path.join(M3U_DIR, "hktwmo.m3u"), "w", encoding="utf-8") as f:
        f.write(m3u)

    # 4. Local TV
    local = [ch for ch in valid_cn if ch["category"] == "🏠 地方台"]
    m3u = f"#EXTM3U\n# Local TV - {len(local)} channels - {timestamp}\n" + generate_m3u(local)
    with open(os.path.join(M3U_DIR, "local.m3u"), "w", encoding="utf-8") as f:
        f.write(m3u)

    # 5. All Chinese (categorized)
    all_cn = valid_cn
    m3u = f"#EXTM3U\n# Chinese - {len(all_cn)} channels - {timestamp}\n" + generate_m3u(all_cn)
    with open(os.path.join(M3U_DIR, "cn.m3u"), "w", encoding="utf-8") as f:
        f.write(m3u)
    txt = generate_txt(all_cn)
    with open(os.path.join(TXT_DIR, "cn.txt"), "w", encoding="utf-8") as f:
        f.write(txt)

    # 6. International by region
    intl_cats = {}
    for ch in valid_intl:
        cat = ch["category"]
        if cat not in intl_cats:
            intl_cats[cat] = []
        intl_cats[cat].append(ch)
    
    # Write each region as separate file
    for cat, chs in sorted(intl_cats.items()):
        safe_name = re.sub(r'[^\w]', '_', cat).strip('_')
        m3u = f"#EXTM3U\n# {cat} - {len(chs)} channels - {timestamp}\n" + generate_m3u(chs)
        with open(os.path.join(M3U_DIR, f"intl_{safe_name}.m3u"), "w", encoding="utf-8") as f:
            f.write(m3u)

    # 7. All international
    m3u = f"#EXTM3U\n# International - {len(valid_intl)} channels - {timestamp}\n" + generate_m3u(valid_intl)
    with open(os.path.join(M3U_DIR, "international.m3u"), "w", encoding="utf-8") as f:
        f.write(m3u)

    # 8. Everything
    all_channels_sorted = valid_cn + valid_intl
    m3u = f"#EXTM3U\n# All - {len(all_channels_sorted)} channels - {timestamp}\n" + generate_m3u(all_channels_sorted)
    with open(os.path.join(M3U_DIR, "all.m3u"), "w", encoding="utf-8") as f:
        f.write(m3u)
    txt = generate_txt(all_channels_sorted)
    with open(os.path.join(TXT_DIR, "all.txt"), "w", encoding="utf-8") as f:
        f.write(txt)

    # === Generate index page ===
    cat_summary = {}
    for ch in all_channels_sorted:
        cat = ch["category"]
        cat_summary[cat] = cat_summary.get(cat, 0) + 1

    cat_rows = ""
    for cat in sorted(cat_summary.keys(), key=lambda x: (0 if x in cn_cats else 1, x)):
        cnt = cat_summary[cat]
        is_cn = cat in cn_cats
        tag = "国内" if is_cn else "国际"
        cat_rows += f"""        <tr>
            <td>{cat}</td>
            <td>{cnt}</td>
            <td>{tag}</td>
        </tr>\n"""

    tvbox_guide = """
    <div class="card" style="border: 2px solid #e94560; background: #fffaf0;">
        <h2>🚀 TVBox / 影视仓 使用（推荐）</h2>
        <p><strong>📺 直播（一个源看全部，不走线路）：</strong>TVBox 直播页 → 添加直播源 → 粘贴：</p>
        <div class="url">天天电视直播总源（16324 频道 · 央视/卫视/地方台/港澳台/各国 29 分类）：<br>http://207.246.102.108/m3u/all.m3u</div>
        <div class="url">国内精简版（央视/卫视/地方台/港澳台 1588 频道）：<br>http://207.246.102.108/m3u/cn.m3u</div>
        <p><strong>🔞 成人直播（成人频道，请自行斟酌）：</strong>同样在直播页添加直播源：</p>
        <div class="url">天天电视成人直播（776 频道）：<br>http://207.246.102.108/m3u/adult.m3u</div>
        <p><strong>🎬 点播（线路只用于点播）：</strong>TVBox 设置 → 配置地址 → 粘贴仓库 → 保存后选一条线路：</p>
        <div class="url">天天电视点播仓库（27 条点播线路，每 6 小时自动筛选更新）：<br>http://207.246.102.108/tvbox/repo.json</div>
    </div>
    """

    index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>📺 天天电视 - IPTV 直播源站</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, 'PingFang SC', sans-serif; max-width: 960px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1 {{ text-align: center; color: #1a1a2e; }}
        .subtitle {{ text-align: center; color: #666; margin-bottom: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat {{ background: white; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .stat .num {{ font-size: 2em; font-weight: bold; color: #e94560; }}
        .stat .label {{ color: #666; margin-top: 5px; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .card h2 {{ color: #16213e; border-bottom: 2px solid #e94560; padding-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .tag {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }}
        .tag-cn {{ background: #fff3cd; color: #856404; }}
        .tag-intl {{ background: #d1ecf1; color: #0c5460; }}
        .url {{ background: #f0f0f0; padding: 8px 12px; border-radius: 6px; font-family: monospace; font-size: 0.85em; word-break: break-all; display: block; margin: 5px 0; }}
        a {{ color: #0066cc; }}
    </style>
</head>
<body>
    <h1>📺 天天电视 IPTV 源站</h1>
    <p class="subtitle">Last updated: {timestamp} | Auto-refresh every 6 hours</p>

    <div class="stats">
        <div class="stat">
            <div class="num">{len(valid_cn)}</div>
            <div class="label">🇨🇳 国内频道</div>
        </div>
        <div class="stat">
            <div class="num">{len(valid_intl)}</div>
            <div class="label">🌍 国际频道</div>
        </div>
        <div class="stat">
            <div class="num">{len(all_channels_sorted)}</div>
            <div class="label">📺 总频道数</div>
        </div>
        <div class="stat">
            <div class="num">{len(cat_summary)}</div>
            <div class="label">📂 分类数</div>
        </div>
    </div>

    {tvbox_guide}

    <div class="card">
        <h2>🇨🇳 国内频道（已验证可用）</h2>
        <div class="url">M3U: http://207.246.102.108/m3u/cn.m3u ({len(valid_cn)}频道)</div>
        <div class="url">TXT: http://207.246.102.108/txt/cn.txt ({len(valid_cn)}频道)</div>
        <table>
            <tr><th>分类</th><th>数量</th><th>链接</th></tr>
            <tr><td>📺 CCTV央视</td><td>{len(cctv)}</td><td><a href="/m3u/cctv.m3u">cctv.m3u</a></td></tr>
            <tr><td>📡 卫视频道</td><td>{len(weishi)}</td><td><a href="/m3u/weishi.m3u">weishi.m3u</a></td></tr>
            <tr><td>🇭🇰 港澳台</td><td>{len(hktwmo)}</td><td><a href="/m3u/hktwmo.m3u">hktwmo.m3u</a></td></tr>
            <tr><td>🏠 地方台</td><td>{len(local)}</td><td><a href="/m3u/local.m3u">local.m3u</a></td></tr>
        </table>
    </div>

    <div class="card">
        <h2>🌍 国际频道</h2>
        <div class="url">M3U: http://207.246.102.108/m3u/international.m3u ({len(valid_intl)}频道)</div>
        <table>
            <tr><th>地区</th><th>数量</th><th>链接</th></tr>"""

    for cat in sorted(intl_cats.keys()):
        cnt = len(intl_cats[cat])
        safe_name = re.sub(r'[^\w]', '_', cat).strip('_')
        index_html += f"""
            <tr><td>{cat}</td><td>{cnt}</td><td><a href="/m3u/intl_{safe_name}.m3u">intl_{safe_name}.m3u</a></td></tr>"""

    index_html += f"""
        </table>
    </div>

    <div class="card">
        <h2>📺 全部频道（{len(all_channels_sorted)}）</h2>
        <div class="url">M3U: http://207.246.102.108/m3u/all.m3u</div>
        <div class="url">TXT: http://207.246.102.108/txt/all.txt</div>
    </div>

    <div class="card">
        <h2>📂 完整分类统计</h2>
        <table>
            <tr><th>分类</th><th>数量</th><th>类型</th></tr>
{cat_rows}        </table>
    </div>

    <div class="card">
        <h2>📖 使用方法</h2>
        <p><strong>TVBox / 影视仓 · 点播：</strong>设置 → 配置地址 → 粘贴 http://207.246.102.108/tvbox/repo.json → 保存 → 选线路（欧歌/驸马/真心等）</p>
        <p><strong>TVBox / 影视仓 · 直播：</strong>直播页 → 添加直播源 → 粘贴 http://207.246.102.108/m3u/all.m3u（或国内版 cn.m3u）</p>
        <p><strong>VLC/PotPlayer：</strong>媒体 → 打开网络串流 → 粘贴 M3U 链接</p>
        <p><strong>TiviMate：</strong>添加播放列表 → M3U 链接</p>
    </div>
</body>
</html>"""

    with open(os.path.join(BASE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    elapsed = time.time() - start_time
    log.info(f"Done in {elapsed:.1f}s")
    log.info(f"Chinese: {len(valid_cn)} | International: {len(valid_intl)} | Total: {len(all_channels_sorted)}")


if __name__ == "__main__":
    main()
