#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test and add new sources from ngo5/IPTV"""
import json
import time
import concurrent.futures
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError


def encode_url(url):
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


# New sources from ngo5/IPTV that we don't have yet
NEW_URLS = [
    # === Live sources (直播源) ===
    {"name": "📺 YanG-1989集合源", "url": "https://tv.iill.top/m3u/Gather", "type": "live"},
    {"name": "📺 IPTV总部(世界杯)", "url": "http://82.156.243.185:33389/fwc.m3u", "type": "live"},
    {"name": "📺 vbskycn IPv6", "url": "https://live.zbds.org/tv/iptv6.m3u", "type": "live"},
    {"name": "📺 Guovin IPv6", "url": "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv6/result.m3u", "type": "live"},
    {"name": "📺 范明明IPv6", "url": "https://live.fanmingming.cn/tv/m3u/ipv6.m3u", "type": "live"},
    {"name": "📺 Kimentanm源", "url": "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u", "type": "live"},
    {"name": "📺 BurningC4源", "url": "https://raw.githubusercontent.com/BurningC4/Chinese-IPTV/master/TV-IPV4.m3u", "type": "live"},
    {"name": "📺 zwc456baby源", "url": "https://raw.githubusercontent.com/zwc456baby/iptv_alive/refs/heads/master/live.m3u", "type": "live"},
    {"name": "📺 ChinaIPTV自动更新", "url": "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8", "type": "live"},
    {"name": "📺 ibert IPv6", "url": "https://m3u.ibert.me/fmml_ipv6.m3u", "type": "live"},
    
    # === VOD sources (点播源) ===
    {"name": " 饭太硬(.cc)", "url": "http://www.饭太硬.cc/tv", "type": "single"},
    {"name": "🎬 饭太硬(cf)", "url": "http://fty.xxooo.cf/tv", "type": "single"},
    {"name": "🎬 王小二(wex)", "url": "https://9280.kstore.space/wex.json", "type": "single"},
    {"name": "🎬 讴歌(api)", "url": "https://xn--xkkx-rp5imh.v.nxog.top/api.php?id=1", "type": "single"},
    {"name": "🎬 盒子迷", "url": "https://盒子迷.top/禁止贩卖", "type": "single"},
    {"name": "🎬 唐三", "url": "http://6080.eu.org/", "type": "single"},
    {"name": "🎬 FongMi导航", "url": "https://fongmi.eu.org/", "type": "single"},
    
    # === EPG (节目单) ===
    {"name": "📅 EPG 112114", "url": "https://epg.112114.xyz/pp.xml", "type": "epg"},
    {"name": "📅 EPG 范明明(镜像)", "url": "https://live.fanmingming.com/e.xml", "type": "epg"},
    {"name": "📅 EPG 范明明(国内)", "url": "https://live.fanmingming.cn/e.xml", "type": "epg"},
    {"name": "📅 EPG ERW", "url": "https://e.erw.cc/e.xml", "type": "epg"},
]


def test_url(item):
    url = encode_url(item["url"])
    name = item["name"]
    try:
        req = Request(url, method="HEAD", headers={
            "User-Agent": "TVBox/1.0 Mozilla/5.0",
            "Accept": "*/*"
        })
        with urlopen(req, timeout=15) as resp:
            return name, item["url"], resp.status, "OK", item["type"]
    except HTTPError as e:
        try:
            req = Request(url, method="GET", headers={
                "User-Agent": "TVBox/1.0 Mozilla/5.0",
                "Accept": "*/*"
            })
            with urlopen(req, timeout=15) as resp:
                return name, item["url"], resp.status, "OK", item["type"]
        except Exception:
            return name, item["url"], e.code, "HTTP Error", item["type"]
    except Exception as e:
        return name, item["url"], 0, str(e)[:80], item["type"]


def main():
    print("=" * 60)
    print("测试 ngo5/IPTV 新增源")
    print("=" * 60)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        future_to_url = {executor.submit(test_url, item): item for item in NEW_URLS}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            results.append(result)
            status_icon = "✅" if result[2] in (200, 301, 302) else "❌"
            print(f"{status_icon} {result[0][:30]:<30} HTTP {result[2]:<4} {result[3]}")

    ok_results = [r for r in results if r[2] in (200, 301, 302)]
    fail_results = [r for r in results if r[2] not in (200, 301, 302)]

    print("\n" + "=" * 60)
    print(f"✅ 可用: {len(ok_results)} / {len(results)}")
    print(f"❌ 不可用: {len(fail_results)} / {len(results)}")
    print("=" * 60)

    live_ok = [r for r in ok_results if r[4] == "live"]
    single_ok = [r for r in ok_results if r[4] == "single"]
    epg_ok = [r for r in ok_results if r[4] == "epg"]

    print(f"\n📺 新增直播源: {len(live_ok)}")
    for r in live_ok:
        print(f"  - {r[0]}: {r[1]}")

    print(f"\n🎬 新增点播源: {len(single_ok)}")
    for r in single_ok:
        print(f"  - {r[0]}: {r[1]}")

    print(f"\n📅 新增EPG: {len(epg_ok)}")
    for r in epg_ok:
        print(f"  - {r[0]}: {r[1]}")

    # Read existing repo.json
    with open("/opt/iptv/tvbox/repo.json", "r", encoding="utf-8") as f:
        repo = json.load(f)
    
    existing_urls = {item["url"] for item in repo["urls"]}
    
    # Add new live sources
    for r in live_ok:
        if r[1] not in existing_urls:
            repo["urls"].append({"name": r[0], "url": r[1]})
            existing_urls.add(r[1])
    
    # Add new single sources
    for r in single_ok:
        if r[1] not in existing_urls:
            repo["urls"].append({"name": r[0], "url": r[1]})
            existing_urls.add(r[1])
    
    # Update metadata
    repo["update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    repo["description"] = "TVBox多仓配置，自动测试筛选可用线路，含点播+直播+EPG"
    
    # Save updated repo
    with open("/opt/iptv/tvbox/repo.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(repo, ensure_ascii=False, indent=2))
    
    # Update config.json with EPG and new live sources
    with open("/opt/iptv/tvbox/config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    # Add EPG to live sources
    if epg_ok:
        epg_url = epg_ok[0][1]  # Use first available EPG
        for live in config.get("lives", []):
            if "epg" not in live or not live["epg"]:
                live["epg"] = epg_url
    
    # Add new live sources to config
    for r in live_ok:
        # Check if already in config lives
        already = False
        for live in config.get("lives", []):
            if live.get("url") == r[1]:
                already = True
                break
        if not already:
            config["lives"].append({
                "name": r[0],
                "type": 0,
                "url": r[1],
                "epg": epg_ok[0][1] if epg_ok else "https://epg.112114.xyz/?ch={name}&date={date}",
                "logo": "https://epg.112114.xyz/logo/{name}.png"
            })
    
    with open("/opt/iptv/tvbox/config.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(config, ensure_ascii=False, indent=2))
    
    # Save EPG list for reference
    with open("/opt/iptv/tvbox/epg.txt", "w", encoding="utf-8") as f:
        f.write("可用EPG节目单地址:\n\n")
        for r in epg_ok:
            f.write(f"{r[0]}: {r[1]}\n")
    
    # Update HTML
    try:
        with open("/opt/iptv/tvbox/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace('Last updated:', f"Last updated: {repo['update_time']} |")
        with open("/opt/iptv/tvbox/index.html", "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print(f"HTML update error: {e}")

    total = len(repo["urls"])
    print("\n" + "=" * 60)
    print("✅ 仓库已更新")
    print("=" * 60)
    print(f"新增直播源: {len(live_ok)} 条")
    print(f"新增点播源: {len(single_ok)} 条")
    print(f"新增EPG: {len(epg_ok)} 条")
    print(f"仓库总线路: {total} 条")
    print(f"\n多仓地址: http://YOUR_SERVER_IP/tvbox/repo.json")
    print(f"配置地址: http://YOUR_SERVER_IP/tvbox/config.json")
    print(f"EPG列表:  http://YOUR_SERVER_IP/tvbox/epg.txt")


if __name__ == "__main__":
    main()
