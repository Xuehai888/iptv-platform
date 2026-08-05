#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox 仓库全量更新 v4 —— 品牌版（服务器端纯版）
============================================================
- 在服务器上直接运行（无 paramiko 依赖）
- 测试所有接口可用性（含成人点播源）
- 所有线路统一添加 " ·" 品牌前缀
- 写入 /opt/iptv/tvbox/repo.json + 更新 index.html
"""
import json
import time
import concurrent.futures
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError

# ===================== 品牌设置 =====================
BRAND_NAME = ""

def get_branded_name(raw_name):
    """将原始名称统一包装为  · xxx"""
    clean_name = raw_name.strip()
    if BRAND_NAME in clean_name:
        return clean_name
    return f"{BRAND_NAME} · {clean_name}"


def encode_url(url):
    """处理中文域名（IDNA 编码）"""
    if '://' not in url:
        return url
    scheme, rest = url.split('://', 1)
    if '/' in rest:
        host_part, path = rest.split('/', 1)
        try:
            host_encoded = host_part.encode('idna').decode('ascii')
        except Exception:
            host_encoded = host_part
        path = quote(path, safe='/')
        return f"{scheme}://{host_encoded}/{path}"
    else:
        try:
            return f"{scheme}://{rest.encode('idna').decode('ascii')}"
        except Exception:
            return url


# ===================== 待测资源列表 =====================
# 说明：raw.githubusercontent.com 源加国内加速代理前缀（国内 TVBox 直接拉 GitHub 常失败）
# 代理：ghfast.top / ghproxy.net 双备选
GH = "https://ghfast.top/https://raw.githubusercontent.com/"
GH2 = "https://ghproxy.net/https://raw.githubusercontent.com/"

URLS_TO_TEST = [
    # --- 【1. 成人 VIP 点播源】 ---
    {"name": "🔞 极乐点播", "url": GH + "hujingguang/ChinaIPTV/main/xxx.m3u8", "type": "single"},
    {"name": "🔞 悦动成人", "url": "https://raw.bgithub.xyz/wwb521/live/refs/heads/main/video.json", "type": "single"},

    # --- 【2. 普通点播源】 ---
    {"name": "🎬 肥猫(.net)", "url": "http://肥猫.net", "type": "single"},
    {"name": "🎬 饭太硬(.net)", "url": "http://www.饭太硬.net/tv", "type": "single"},
    {"name": "🎬 王小二(新)", "url": "https://9280.kstore.vip/newwex.json", "type": "single"},
    {"name": "🎬 挺好分享", "url": "http://ztha.top/TVBox/thdjk.json", "type": "single"},
    {"name": "🎬 驸马", "url": "http://fmys.top/fmys.json", "type": "single"},
    {"name": "🎬 刘备", "url": "https://raw.liucn.cc/box/m.json", "type": "single"},
    {"name": "🎬 dxawi", "url": GH + "dxawi/0/main/0.json", "type": "single"},
    {"name": "🎬 香雅情", "url": GH + "xyq254245/xyqonlinerule/main/XYQTVBox.json", "type": "single"},
    {"name": "🎬 非凡", "url": "https://g.3344550.xyz/" + GH2 + "jigedos/1024/master/jsm.json", "type": "single"},
    {"name": "🎬 英雄", "url": GH + "xuexuguang/tvbox_spider/main/tv/kk/heroaku_dtes.json", "type": "single"},
    {"name": "🎬 高天流云", "url": GH2 + "gaotianliuyun/gao/master/js.json", "type": "single"},
    {"name": "🎬 小屋", "url": "https://git.acwing.com/shhentu/lzxw/-/raw/main/Monster.json", "type": "single"},
    {"name": "🎬 小盒子", "url": "http://xhztv.top/xhz", "type": "single"},
    {"name": "🎬 小盒子4K", "url": "http://xhztv.top/4k.json", "type": "single"},
    {"name": "🎬 哈基米", "url": "https://17264.kstore.space/哈基米.png", "type": "single"},
    {"name": "🎬 动漫城", "url": "https://www.yingm.cc/dm/dm.json", "type": "single"},
    {"name": "🎬 HG接口", "url": "https://api.hgyx.vip/hgyx.json", "type": "single"},
    {"name": "🎬 潇洒", "url": "https://9877.kstore.space/ONE/one.json", "type": "single"},
    {"name": "🎬 小苹果", "url": "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", "type": "single"},
    {"name": "🎬 宝盒VIP", "url": GH + "guot55/YGBH/main/vip2.json", "type": "single"},
    {"name": "🎬 欧歌", "url": "https://xn--anna-wn6lw489o.v.nxog.top/m/", "type": "single", "force": True},
    {"name": "🎬 真心", "url": "https://www.252035.xyz/z/FongMi.json", "type": "single"},
    {"name": "🎬 分享", "url": GH2 + "maoystv/6/main/000.json", "type": "single"},
    {"name": "🎬 短剧", "url": "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json", "type": "single"},
    {"name": "🎬 东篱线路", "url": GH + "chitue/dongliTV/main/api.json", "type": "single"},
    {"name": "🎬 嗷呜线路", "url": "https://cnb.cool/aooooowuuuuu/FreeSpider/-/git/raw/main/config", "type": "single"},
    {"name": "🎬 L佬线路", "url": "https://android.lushunming.qzz.io/json/index.json", "type": "single"},
    {"name": "🎬 苹果CMS", "url": "https://pastebin.com/raw/gtbKvnE1", "type": "single"},
    {"name": "🎬 CandyMuj", "url": "https://tv.520993.xyz/candymuj.json", "type": "single"},
    {"name": "🎬 CandyMuj(无福利)", "url": "https://tv.520993.xyz/candymuj1.json", "type": "single"},
    {"name": "🎬 tvyuan全量版", "url": "https://tv.cc0cd.cc.cd", "type": "single"},
    {"name": "🎬 菜妮丝", "url": "https://tv.xn--yhqu5zs87a.top", "type": "single"},
    {"name": "🎬 龙伊", "url": "https://xn--qoqw77q.top/", "type": "single"},

    # --- 【3. 多仓源】 ---
    {"name": "🏬 小盒子多仓", "url": "http://xhztv.top/dc/", "type": "multi"},
    {"name": "🏬 拾光多仓", "url": "http://xmbjm.fh4u.org/dc.txt", "type": "multi"},

    # --- 【4. 外部直播源】 ---
    {"name": "📺 悦然直播", "url": GH + "YueChan/Live/refs/heads/main/IPTV.m3u", "type": "live"},
    {"name": "🌍 悦然全球", "url": GH + "YueChan/Live/refs/heads/main/Global.m3u", "type": "live"},
    {"name": "📡 直播电视IPV4", "url": "https://live.zbds.top/tv/iptv4.txt", "type": "live"},
    {"name": "🛰️ 国云直播", "url": GH2 + "Guovin/iptv-api/gd/output/result.m3u", "type": "live"},
    {"name": "📺 苏翔直播", "url": GH + "suxuang/myIPTV/refs/heads/main/ipv4.m3u", "type": "live"},
]


def test_url(item):
    """严格校验：GET 内容 + 类型检查（TVBox 解析兼容性）"""
    url = encode_url(item["url"])
    name = item["name"]
    try:
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 TVBox/1.0",
            "Accept": "*/*"
        })
        with urlopen(req, timeout=12) as resp:
            content = resp.read(200000)
            status = resp.status
            text = content.decode('utf-8', errors='ignore')[:10000]
            low = text.lower()
            ct = resp.headers.get('Content-Type', '')
            if 'application/json' in ct or text.strip().startswith(('{', '[')):
                return name, item["url"], status, "OK-JSON", item["type"]
            elif low.startswith('#extm3u') or '#extinf' in low or '.m3u8' in low:
                return name, item["url"], status, "OK-M3U", item["type"]
            elif ',#' in low or '#genre#' in low:
                return name, item["url"], status, "OK-TXT", item["type"]
            else:
                return name, item["url"], status, f"BAD({ct[:20]})", item["type"]
    except HTTPError as e:
        return name, item["url"], e.code, "HTTP Error", item["type"]
    except Exception as e:
        return name, item["url"], 0, str(e)[:60], item["type"]


def main():
    print("=" * 70)
    print(f"📺 {BRAND_NAME} | TVBox 仓库全量更新 v4（服务器端）")
    print("=" * 70)
    print("正在测试所有接口可用性（含成人点播源）...")
    print()

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        future_to_url = {executor.submit(test_url, item): item for item in URLS_TO_TEST}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            results.append(result)
            status_icon = "✅" if result[3] in ("OK-JSON", "OK-M3U", "OK-TXT") else "❌"
            print(f"{status_icon} {result[0][:30]:<30} HTTP {result[2]:<4} {result[3]}")

    # 只保留内容类型校验通过（OK-JSON/OK-M3U/OK-TXT）的线路 + force 标记的（用户确认可用）
    force_names = {item["name"] for item in URLS_TO_TEST if item.get("force")}
    ok_results = [r for r in results if r[3] in ("OK-JSON", "OK-M3U", "OK-TXT") or r[0] in force_names]
    fail_results = [r for r in results if r[3] not in ("OK-JSON", "OK-M3U", "OK-TXT") and r[0] not in force_names]

    print("\n" + "=" * 70)
    print(f"✅ 可用: {len(ok_results)} / {len(results)}")
    print(f"❌ 不可用: {len(fail_results)} / {len(results)}")
    print("=" * 70)

    # 分类（famous 也归入 single）
    single_ok = [r for r in ok_results if r[4] in ("single", "famous")]
    multi_ok = [r for r in ok_results if r[4] == "multi"]
    live_ok = [r for r in ok_results if r[4] == "live"]

    # ===================== 构建品牌仓库 =====================
    urls = []

    # 1) 多仓源（品牌化）
    for r in multi_ok:
        urls.append({"name": get_branded_name(r[0]), "url": r[1]})

    # 2) 单仓源（品牌化，含成人点播）
    for r in single_ok:
        urls.append({"name": get_branded_name(r[0]), "url": r[1]})

    # 3) 外部直播源：不再加入仓库（"线路归线路，直播自己配"）
    #    直播请直接在 TVBox 直播页添加 m3u 源：
    #      http://YOUR_SERVER_IP/m3u/all.m3u   （直播总源，16324 频道 29 分组）
    #      http://YOUR_SERVER_IP/m3u/cn.m3u    （国内精简版，1588 频道）
    #    live_ok 仅保留统计用途

    # 4) 自建直播源（品牌化命名，频道数动态读取）
    # TVBox 多仓选线路时要求每个线路是【完整 TVBox 配置 JSON】。
    # 借鉴欧歌/主流线路的 lives 格式：每个 live 必须带 type/playerType/timeout 等字段，
    # 否则部分 TVBox 版本静默忽略，导致"选线路不报错但直播不显示"。
    def count_channels(m3u_name):
        try:
            with open(f"/opt/iptv/m3u/{m3u_name}", 'r', encoding='utf-8') as f:
                return sum(1 for line in f if line.startswith("#EXTINF:"))
        except Exception:
            return 0

    def make_live(name, m3u_path, epg_url=""):
        """构造 TVBox 标准 live 条目（模仿欧歌格式）"""
        live = {
            "name": name,
            "type": 0,
            "url": f"http://YOUR_SERVER_IP/m3u/{m3u_path}",
            "playerType": 2,
            "timeout": 10
        }
        if epg_url:
            live["epg"] = epg_url
        return live

    def write_live_config(json_name, lives, cfg_name="直播"):
        """写入完整 TVBox 直播配置 JSON。

        重要：必须以"欧歌基座"（spider 完整URL + 127个sites + parses）为模板，
        只替换 lives。实测影视仓多仓选线路时，若配置 sites 为空 / spider 为空，
        会判定配置无效而整体忽略（含 lives），导致"选线路不报错但直播不显示"。
        欧歌/驸马/饭太硬等能正常显示直播的配置，全部是 spider+sites+lives 齐全的。
        """
        try:
            with open("/opt/iptv/tvbox/ouge_base.json", "r", encoding="utf-8") as f:
                base = json.load(f)
        except Exception as e:
            print(f"  ⚠️ ouge_base.json 加载失败({e})，回退为最小结构")
            base = {"spider": "", "sites": [], "parses": []}
        cfg = dict(base)
        cfg["name"] = cfg_name
        cfg["lives"] = lives
        with open(f"/opt/iptv/tvbox/{json_name}", "w", encoding="utf-8") as f:
            f.write(json.dumps(cfg, ensure_ascii=False, indent=1))

    cn_count = count_channels("cn.m3u")
    cctv_count = count_channels("cctv.m3u")
    weishi_count = count_channels("weishi.m3u")
    local_count = count_channels("local.m3u")
    hktwmo_count = count_channels("hktwmo.m3u")
    all_count = count_channels("all.m3u")

    # 每个分类一个独立配置（选线路后只显示对应分类的直播源）
    write_live_config("live_cn.json", [make_live(f"{BRAND_NAME} · 🇨🇳 中国频道（{cn_count}）", "cn.m3u")], "中国频道")
    write_live_config("live_cctv.json", [make_live(f"{BRAND_NAME} · 📺 央视频道（{cctv_count}）", "cctv.m3u")], "央视")
    write_live_config("live_weishi.json", [make_live(f"{BRAND_NAME} · 📡 卫视频道（{weishi_count}）", "weishi.m3u")], "卫视")
    write_live_config("live_local.json", [make_live(f"{BRAND_NAME} · 🏠 地方台（{local_count}）", "local.m3u")], "地方台")
    write_live_config("live_hktwmo.json", [make_live(f"{BRAND_NAME} · 🇭🇰 港澳台（{hktwmo_count}）", "hktwmo.m3u")], "港澳台")
    write_live_config("live_all.json", [make_live(f"{BRAND_NAME} · 🌍 全球频道（{all_count}）", "all.m3u")], "全球")

    # 一站式配置：6 个直播源合成一个配置，选一条线路直播页就有全部 6 个源（最接近欧歌体验）
    all_lives = [
        make_live(f"{BRAND_NAME} · 🇨🇳 中国频道（{cn_count}）", "cn.m3u"),
        make_live(f"{BRAND_NAME} · 📺 央视频道（{cctv_count}）", "cctv.m3u"),
        make_live(f"{BRAND_NAME} · 📡 卫视频道（{weishi_count}）", "weishi.m3u"),
        make_live(f"{BRAND_NAME} · 🏠 地方台（{local_count}）", "local.m3u"),
        make_live(f"{BRAND_NAME} · 🇭🇰 港澳台（{hktwmo_count}）", "hktwmo.m3u"),
        make_live(f"{BRAND_NAME} · 🌍 全球频道（{all_count}）", "all.m3u"),
    ]
    write_live_config("live_all_in_one.json", all_lives, "直播总源")

    # 4) 自建直播配置：不再加入仓库（"线路归线路，直播自己配"）
    #    用户直接在 TVBox 直播页添加 m3u 总源即可：
    #      http://YOUR_SERVER_IP/m3u/all.m3u   （一个源看全部：央视/卫视/地方台/港澳台/各国）
    #      http://YOUR_SERVER_IP/m3u/cn.m3u    （国内精简版）
    #    live_*.json 仍保留生成（供配置方式备用），但不写入 repo.json

    repo_json = {
        "name": f"📺 {BRAND_NAME} - 全能影视直播仓库",
        "description": f"{BRAND_NAME}多仓配置（点播为主，直播请直接添加 m3u 直播源），自动测试筛选，每6小时更新",
        "version": time.strftime("%Y-%m-%d"),
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "urls": urls
    }

    # ===================== 直接写文件（服务器端） =====================
    with open("/opt/iptv/tvbox/repo.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(repo_json, ensure_ascii=False, indent=2))
    print("✅ repo.json 已更新")

    # 更新 HTML
    try:
        with open("/opt/iptv/tvbox/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace('Last updated:', f"Last updated: {repo_json['update_time']} |")
        with open("/opt/iptv/tvbox/index.html", "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print(f"HTML update error: {e}")

    # ===================== 汇总输出 =====================
    print("\n" + "=" * 70)
    print(f"✅ TVBox 仓库已更新（{BRAND_NAME} 品牌版）")
    print("=" * 70)
    print(f"📺 品牌名称: {BRAND_NAME}")
    print(f"📦 可用线路: {len(urls)} 条（均为点播线路）")
    print(f"  - 多仓: {len(multi_ok)} 条")
    print(f"  - 单仓(含成人): {len(single_ok)} 条")
    print(f"\n📺 直播源（TVBox 直播页直接添加，不走线路）:")
    print(f"  - 直播总源: http://YOUR_SERVER_IP/m3u/all.m3u")
    print(f"  - 国内精简版:      http://YOUR_SERVER_IP/m3u/cn.m3u")
    print(f"\n🔗 多仓地址: http://YOUR_SERVER_IP/tvbox/repo.json")
    print(f"🕐 更新时间: {repo_json['update_time']}")


if __name__ == "__main__":
    main()
