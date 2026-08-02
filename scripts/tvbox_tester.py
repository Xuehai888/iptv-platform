#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Server-side TVBox URL tester - run on 207.246.102.108"""
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


URLS_TO_TEST = [
    # 中文域名接口
    {"name": " 饭太硬", "url": "http://www.饭太硬.com/tv", "type": "single"},
    {"name": "🎬 肥猫", "url": "http://肥猫.com/", "type": "single"},
    {"name": " 摸鱼", "url": "http://我不是.摸鱼儿.com", "type": "single"},
    {"name": "🎬 王小二", "url": "http://tvbox.王二小放牛娃.top", "type": "single"},
    {"name": " 开心", "url": "http://kxrj.site:55/天天开心", "type": "single"},
    {"name": " 云星日记", "url": "http://itvbox.cc/云星日记", "type": "single"},
    {"name": " 巧记", "url": "http://cdn.qiaoji8.com/tvbox.json", "type": "single"},
    {"name": " 喵影视", "url": "http://meowtv.cn/tv", "type": "single"},
    {"name": "🎬 OK线路", "url": "http://ok321.top/ok", "type": "single"},
    {"name": " 荷城茶秀", "url": "http://rihou.cc:88/荷城茶秀", "type": "single"},
    
    # 普通接口
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
    {"name": " 宝盒mzjk", "url": "http://mzjk.top/禁止贩卖", "type": "single"},
    
    # tvyuan
    {"name": " tvyuan聚合源", "url": "https://tv.cc0cd.cc.cd/jj", "type": "single"},
    {"name": " tvyuan全量版", "url": "https://tv.cc0cd.cc.cd", "type": "single"},
    {"name": "🏬 tvyuan多仓版", "url": "https://tv.cc0cd.cc.cd/multi", "type": "multi"},
    
    # GitHub 代理接口
    {"name": " qist0707", "url": "https://github.moeyy.xyz/https://raw.githubusercontent.com/qist/tvbox/master/0707.json", "type": "single"},
    {"name": " qist0821", "url": "https://github.moeyy.xyz/https://raw.githubusercontent.com/qist/tvbox/master/0821.json", "type": "single"},
    {"name": " qist0822", "url": "https://github.moeyy.xyz/https://raw.githubusercontent.com/qist/tvbox/master/0822.json", "type": "single"},
    {"name": " jinenge", "url": "https://github.moeyy.xyz/https://raw.githubusercontent.com/jinenge/tvbox/main/tvbox.json", "type": "single"},
    {"name": " scovis", "url": "https://github.moeyy.xyz/https://raw.githubusercontent.com/scovis/TVBox/main/tvbox.json", "type": "single"},
    {"name": " 南风", "url": "https://github.moeyy.xyz/https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json", "type": "single"},
    {"name": " 香雅情", "url": "https://github.moeyy.xyz/https://raw.githubusercontent.com/xyq254245/xyqonlinerule/main/XYQTVBox.json", "type": "single"},
    
    # GitHub raw
    {"name": " 金虎", "url": "https://raw.githubusercontent.com/Zhou-Li-Bin/Tvbox-QingNing/main/%E6%8E%A5%E5%8F%A3.json", "type": "single"},
    {"name": " 饭太硬(GH)", "url": "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json", "type": "single"},
    
    # 多仓
    {"name": " 欧歌多仓", "url": "http://ww.weidonglong.com/ysc50311.json", "type": "multi"},
    {"name": "🏬 西夏影视", "url": "https://d.kstore.space/download/2912/xx888.json", "type": "multi"},
    {"name": "🏬 无邪多仓", "url": "https://gitee.com/wxej/wxrj/raw/master/wx.json", "type": "multi"},
    {"name": " 天微", "url": "https://qixing.myhkw.com/DC.txt", "type": "multi"},
    {"name": "🏬 挺好分享(多仓)", "url": "http://ztha.top/TVBox/FLCK.json", "type": "multi"},
    {"name": " 业余打发", "url": "https://ghproxy.net/https://raw.githubusercontent.com/yyfxz/qqtv/main/qq.json", "type": "multi"},
    {"name": "🏬 蓝色影视", "url": "https://raw.gitcode.com/yydg/ggdx/raw/main/Xboxb.json", "type": "multi"},
    {"name": "🏬 宝盒(多仓)", "url": "http://mzjk.top/DC", "type": "multi"},
    {"name": "🏬 天天秒播", "url": "http://tv.laohu.cool/tvbox.json", "type": "multi"},
    {"name": " 飞哥传奇", "url": "https://chuanshuo.77blog.cn/dc.json", "type": "multi"},
    {"name": "🏬 电视盒子集", "url": "http://120.79.4.185/dc.json", "type": "multi"},
    
    # 直播源
    {"name": " YueChan IPTV", "url": "https://raw.githubusercontent.com/YueChan/Live/refs/heads/main/IPTV.m3u", "type": "live"},
    {"name": " YueChan Global", "url": "https://raw.githubusercontent.com/YueChan/Live/refs/heads/main/Global.m3u", "type": "live"},
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
    print("TVBox 接口可用性测试（服务器端）")
    print("=" * 60)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
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

    single_ok = [r for r in ok_results if r[4] == "single"]
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

    # Build new repo JSON
    urls = []

    for r in multi_ok:
        urls.append({"name": r[0], "url": r[1]})

    for r in single_ok:
        urls.append({"name": r[0], "url": r[1]})

    # Add self-hosted live sources
    urls.append({"name": "🇨🇳 自建中文直播（565频道）", "url": "http://207.246.102.108/m3u/cn.m3u"})
    urls.append({"name": "📺 自建CCTV央视（228频道）", "url": "http://207.246.102.108/m3u/cctv.m3u"})
    urls.append({"name": " 自建卫视频道（217频道）", "url": "http://207.246.102.108/m3u/weishi.m3u"})
    urls.append({"name": "🌍 自建全球频道（15000+）", "url": "http://207.246.102.108/m3u/all.m3u"})

    repo_json = {
        "name": "IPTV Source Station - TVBox Multi Repo (Auto-Tested)",
        "description": "TVBox多仓配置，自动测试筛选可用线路，每6小时更新",
        "version": time.strftime("%Y-%m-%d"),
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "urls": urls
    }

    with open("/opt/iptv/tvbox/repo.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(repo_json, ensure_ascii=False, indent=2))

    # Update HTML update time
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
    print(f"\n多仓地址: http://207.246.102.108/tvbox/repo.json")


if __name__ == "__main__":
    main()
