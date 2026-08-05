#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enhanced TVBox URL tester with more sources"""
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


# Mix of tested + famous sources
URLS_TO_TEST = [
    # === Famous Chinese domain sources (keep even if test fails) ===
    {"name": " 饭太硬", "url": "http://www.饭太硬.com/tv", "type": "famous"},
    {"name": " 饭太硬(.net)", "url": "http://www.饭太硬.net/tv", "type": "single"},
    {"name": "🎬 肥猫", "url": "http://肥猫.com/", "type": "famous"},
    {"name": "🎬 肥猫(.net)", "url": "http://肥猫.net", "type": "single"},
    {"name": " 摸鱼", "url": "http://我不是.摸鱼儿.com", "type": "famous"},
    {"name": " 摸鱼(.top)", "url": "http://我不是.摸鱼儿.top", "type": "single"},
    {"name": "🎬 王小二", "url": "http://tvbox.王二小放牛娃.top", "type": "single"},
    {"name": " 王小二(新)", "url": "https://9280.kstore.vip/newwex.json", "type": "single"},
    {"name": "🎬 开心", "url": "http://kxrj.site:55/天天开心", "type": "single"},
    {"name": " 云星日记", "url": "http://itvbox.cc/云星日记", "type": "single"},
    {"name": " 巧记", "url": "http://cdn.qiaoji8.com/tvbox.json", "type": "single"},
    {"name": "🎬 喵影视", "url": "http://meowtv.cn/tv", "type": "single"},
    {"name": " 喵影视(.vip)", "url": "http://www.meowtv.vip/tvbox.json", "type": "single"},
    {"name": "🎬 OK线路", "url": "http://ok321.top/ok", "type": "single"},
    {"name": " 荷城茶秀", "url": "http://rihou.cc:88/荷城茶秀", "type": "single"},
    
    # === Existing working ones ===
    {"name": " 驸马", "url": "http://fmys.top/fmys.json", "type": "single"},
    {"name": " 龙伊", "url": "https://xn--qoqw77q.top/", "type": "single"},
    {"name": " 刘备", "url": "https://raw.liucn.cc/box/m.json", "type": "single"},
    {"name": " dxawi", "url": "https://dxawi.github.io/0/0.json", "type": "single"},
    {"name": " 非凡", "url": "https://g.3344550.xyz/https://raw.githubusercontent.com/jigedos/1024/master/jsm.json", "type": "single"},
    {"name": " 挺好分享", "url": "http://ztha.top/TVBox/thdjk.json", "type": "single"},
    {"name": " 英雄", "url": "https://cdn.githubraw.com/xuexuguang/tvbox_spider/main/tv/kk/heroaku_dtes.json", "type": "single"},
    {"name": " 小屋", "url": "https://git.acwing.com/shhentu/lzxw/-/raw/main/Monster.json", "type": "single"},
    {"name": " 高天流云", "url": "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json", "type": "single"},
    {"name": " 菜妮丝", "url": "https://tv.xn--yhqu5zs87a.top", "type": "single"},
    {"name": " 小盒子", "url": "http://xhztv.top/xhz", "type": "single"},
    {"name": " 小盒子4K", "url": "http://xhztv.top/4k.json", "type": "single"},
    
    # === More from youhunwl/TVAPP ===
    {"name": " 哈基米", "url": "https://17264.kstore.space/哈基米.png", "type": "single"},
    {"name": " 动漫城", "url": "https://www.yingm.cc/dm/dm.json", "type": "single"},
    {"name": " 俊佬", "url": "http://home.jundie.top:81/top98.json", "type": "single"},
    {"name": " 道长", "url": "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json", "type": "single"},
    {"name": " T4接口", "url": "https://gitee.com/free-kingdom/dc/raw/main/T4.json", "type": "single"},
    {"name": " 南风", "url": "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json", "type": "single"},
    {"name": " HG接口", "url": "https://api.hgyx.vip/hgyx.json", "type": "single"},
    {"name": " 潇洒", "url": "https://9877.kstore.space/ONE/one.json", "type": "single"},
    {"name": " 香雅情", "url": "https://raw.githubusercontent.com/xyq254245/xyqonlinerule/main/XYQTVBox.json", "type": "single"},
    {"name": " 小苹果", "url": "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", "type": "single"},
    {"name": " 宝盒VIP", "url": "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json", "type": "single"},
    {"name": " 欧歌", "url": "https://xn--anna-wn6lw489o.v.nxog.top/m/", "type": "single"},
    {"name": " 真心", "url": "https://www.252035.xyz/z/FongMi.json", "type": "single"},
    {"name": " 分享", "url": "https://raw.githubusercontent.com/maoystv/6/main/000.json", "type": "single"},
    {"name": " 短剧", "url": "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json", "type": "single"},
    {"name": " 东篱线路", "url": "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json", "type": "single"},
    {"name": " 嗷呜线路", "url": "https://cnb.cool/aooooowuuuuu/FreeSpider/-/git/raw/main/config", "type": "single"},
    {"name": " L佬线路", "url": "https://android.lushunming.qzz.io/json/index.json", "type": "single"},
    {"name": " 天神IY", "url": "https://gitee.com/cpu-iy/iy/raw/master/天神IY.json", "type": "single"},
    {"name": " 苹果CMS", "url": "https://pastebin.com/raw/gtbKvnE1", "type": "single"},
    
    # === CandyMuj ===
    {"name": " CandyMuj", "url": "https://tv.520993.xyz/candymuj.json", "type": "single"},
    {"name": " CandyMuj(无福利)", "url": "https://tv.520993.xyz/candymuj1.json", "type": "single"},
    
    # === Multi-repo sources ===
    {"name": "🏬 游魂多仓", "url": "https://www.iyouhun.com/tv/dc", "type": "multi"},
    {"name": "🏬 游魂多仓(备)", "url": "https://www.iyouhun.com/tv/yh", "type": "multi"},
    {"name": "🏬 潇洒单仓", "url": "https://9877.kstore.space/AnotherDS/api.json", "type": "multi"},
    {"name": "🏬 小盒子多仓", "url": "http://xhztv.top/dc/", "type": "multi"},
    {"name": "🏬 小盒子多仓(备)", "url": "http://xhztv.top/DC.txt", "type": "multi"},
    {"name": "🏬 拾光多仓", "url": "http://xmbjm.fh4u.org/dc.txt", "type": "multi"},
    
    # === tvyuan ===
    {"name": " tvyuan聚合源", "url": "https://tv.cc0cd.cc.cd/jj", "type": "single"},
    {"name": " tvyuan全量版", "url": "https://tv.cc0cd.cc.cd", "type": "single"},
    {"name": "🏬 tvyuan多仓版", "url": "https://tv.cc0cd.cc.cd/multi", "type": "multi"},
    
    # === Live sources ===
    {"name": "📺 YueChan IPTV", "url": "https://raw.githubusercontent.com/YueChan/Live/refs/heads/main/IPTV.m3u", "type": "live"},
    {"name": " YueChan Global", "url": "https://raw.githubusercontent.com/YueChan/Live/refs/heads/main/Global.m3u", "type": "live"},
    {"name": "📺 游魂直播源", "url": "https://www.iyouhun.com/tv/zb", "type": "live"},
    {"name": "📺 直播电视IPV4", "url": "https://live.zbds.top/tv/iptv4.txt", "type": "live"},
    {"name": "📺 Guovin IPTV", "url": "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u", "type": "live"},
    {"name": "📺 suxuang IPv4", "url": "https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv4.m3u", "type": "live"},
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
    print("TVBox 接口可用性测试 v2（更多源）")
    print("=" * 60)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=35) as executor:
        future_to_url = {executor.submit(test_url, item): item for item in URLS_TO_TEST}
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

    single_ok = [r for r in ok_results if r[4] in ("single", "famous")]
    multi_ok = [r for r in ok_results if r[4] == "multi"]
    live_ok = [r for r in ok_results if r[4] == "live"]

    print(f"\n 单仓可用: {len(single_ok)}")
    for r in single_ok:
        print(f"  - {r[0]}: {r[1]}")

    print(f"\n🏬 多仓可用: {len(multi_ok)}")
    for r in multi_ok:
        print(f"  - {r[0]}: {r[1]}")

    print(f"\n 直播源可用: {len(live_ok)}")
    for r in live_ok:
        print(f"  - {r[0]}: {r[1]}")

    # Build URLs list
    urls = []
    
    # Add multi-repo sources first
    for r in multi_ok:
        urls.append({"name": r[0], "url": r[1]})
    
    # Add single sources
    for r in single_ok:
        urls.append({"name": r[0], "url": r[1]})
    
    # Add self-hosted live sources
    urls.append({"name": "🇨🇳 自建中文直播（565频道）", "url": "http://YOUR_SERVER_IP/m3u/cn.m3u"})
    urls.append({"name": " 自建CCTV央视（228频道）", "url": "http://YOUR_SERVER_IP/m3u/cctv.m3u"})
    urls.append({"name": " 自建卫视频道（217频道）", "url": "http://YOUR_SERVER_IP/m3u/weishi.m3u"})
    urls.append({"name": "🌍 自建全球频道（15000+）", "url": "http://YOUR_SERVER_IP/m3u/all.m3u"})

    repo_json = {
        "name": "IPTV Source Station - TVBox Multi Repo (Auto-Tested)",
        "description": "TVBox多仓配置，自动测试筛选可用线路，每6小时更新",
        "version": time.strftime("%Y-%m-%d"),
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "urls": urls
    }

    with open("/opt/iptv/tvbox/repo.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(repo_json, ensure_ascii=False, indent=2))

    # Update HTML
    try:
        with open("/opt/iptv/tvbox/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace('Last updated:', f"Last updated: {repo_json['update_time']} |")
        with open("/opt/iptv/tvbox/index.html", "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print(f"HTML update error: {e}")

    print("\n" + "=" * 60)
    print("✅ TVBox 仓库已更新")
    print("=" * 60)
    print(f"可用线路: {len(urls)} 条")
    print(f"多仓: {len(multi_ok)} 条")
    print(f"单仓: {len(single_ok)} 条")
    print(f"自建直播源: 4 条")
    print(f"\n多仓地址: http://YOUR_SERVER_IP/tvbox/repo.json")


if __name__ == "__main__":
    main()
