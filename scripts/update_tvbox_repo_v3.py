# -*- coding: utf-8 -*-
"""
TVBox 仓库全量更新 v3 —— 【天天电视】品牌版
============================================
- 加入成人点播源（🔞 极乐 / 悦动）
- 所有线路（点播+直播）统一添加 "天天电视 ·" 品牌前缀
- 自建直播源品牌化命名
- 直接连接服务器更新 /opt/iptv/tvbox/repo.json
"""
import paramiko
import json
import time
import concurrent.futures
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError

# ===================== 品牌设置 =====================
BRAND_NAME = "天天电视"

def get_branded_name(raw_name):
    """将原始名称统一包装为 天天电视 · xxx"""
    clean_name = raw_name.strip()
    if BRAND_NAME in clean_name:
        return clean_name
    return f"{BRAND_NAME} · {clean_name}"

# ===================== 服务器配置 =====================
host = "207.246.102.108"
user = "root"
password = "dF4=cc[xPME[t_y8"

def run_cmd(client, cmd, timeout=120):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

# ===================== 待测资源列表 =====================
URLS_TO_TEST = [
    # --- 【1. 成人 VIP 点播源】 ---
    {"name": "🔞 极乐点播", "url": "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/xxx.m3u8", "type": "single"},
    {"name": "🔞 悦动点播", "url": "https://gist.github.com/639936/ee108ef4fc3eadcc23c41408fa0d107e", "type": "single"},

    # --- 【2. 普通点播源】 ---
    {"name": "🎬 肥猫", "url": "http://肥猫.com/", "type": "single"},
    {"name": "🎬 饭太硬", "url": "http://www.饭太硬.com/tv", "type": "single"},
    {"name": "🎬 饭太硬(备用)", "url": "http://www.饭太硬.com/tv/", "type": "single"},
    {"name": "🎬 小米", "url": "https://www.mpanso.com/小米/DEMO.json", "type": "single"},
    {"name": "🎬 OK线路", "url": "http://ok321.top/ok", "type": "single"},
    {"name": "🎬 王小二", "url": "http://tvbox.王二小放牛娃.top", "type": "single"},
    {"name": "🎬 摸鱼", "url": "http://我不是.摸鱼儿.com", "type": "single"},
    {"name": "🎬 开心", "url": "http://kxrj.site:55/天天开心", "type": "single"},
    {"name": "🎬 巧记", "url": "http://cdn.qiaoji8.com/tvbox.json", "type": "single"},
    {"name": "🎬 喵影视", "url": "http://meowtv.cn/tv", "type": "single"},
    {"name": "🎬 挺好分享", "url": "http://ztha.top/TVBox/thdjk.json", "type": "single"},
    {"name": "🎬 驸马", "url": "http://fmys.top/fmys.json", "type": "single"},
    {"name": "🎬 龙伊", "url": "https://xn--qoqw77q.top/", "type": "single"},
    {"name": "🎬 传说", "url": "https://chuanshuo.77blog.cn/tv.json", "type": "single"},
    {"name": "🎬 西夏", "url": "https://2912.kstore.space/0506.json", "type": "single"},
    {"name": "🎬 非凡", "url": "https://g.3344550.xyz/https://raw.githubusercontent.com/jigedos/1024/master/jsm.json", "type": "single"},
    {"name": "🎬 英雄", "url": "https://cdn.githubraw.com/xuexuguang/tvbox_spider/main/tv/kk/heroaku_dtes.json", "type": "single"},
    {"name": "🎬 短剧", "url": "http://74.120.175.78/JK/XYQTVBox/dj.json", "type": "single"},
    {"name": "🎬 白龙", "url": "http://124.71.189.194/a.json", "type": "single"},
    {"name": "🎬 菜妮丝", "url": "https://tv.xn--yhqu5zs87a.top", "type": "single"},
    {"name": "🎬 云星日记", "url": "http://itvbox.cc/云星日记", "type": "single"},
    {"name": "🎬 俊佬", "url": "http://home.jundie.top:81/top98.json", "type": "single"},
    {"name": "🎬 荷城茶秀", "url": "http://rihou.cc:88/荷城茶秀", "type": "single"},
    {"name": "🎬 运输车", "url": "https://weixine.net/ysc.json", "type": "single"},
    {"name": "🎬 爱TV吧", "url": "https://hub.gitmirror.com/https://raw.githubusercontent.com/txtvv/txtv/main/tvbox/0326.json", "type": "single"},
    {"name": "🎬 南风", "url": "https://github.moeyy.xyz/https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json", "type": "single"},
    {"name": "🎬 刘备", "url": "https://raw.liucn.cc/box/m.json", "type": "single"},
    {"name": "🎬 dxawi", "url": "https://dxawi.github.io/0/0.json", "type": "single"},
    {"name": "🎬 香雅情", "url": "https://github.moeyy.xyz/https://raw.githubusercontent.com/xyq254245/xyqonlinerule/main/XYQTVBox.json", "type": "single"},
    {"name": "🎬 道长", "url": "https://pastebin.com/raw/5NHaxyGR", "type": "single"},
    {"name": "🎬 小马影视", "url": "https://szyyds.cn/tv/x.json", "type": "single"},
    {"name": "🎬 PG线路", "url": "http://ztha.top/PG/jsm.json", "type": "single"},
    {"name": "🎬 吾爱", "url": "http://52bsj.vip:98/wuai", "type": "single"},
    {"name": "🎬 高天流云", "url": "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json", "type": "single"},
    {"name": "🎬 小屋", "url": "https://git.acwing.com/shhentu/lzxw/-/raw/main/Monster.json", "type": "single"},

    # --- 【3. 多仓源】 ---
    {"name": "🏬 全网影视", "url": "http://ww.weidonglong.com/ysc50311.json", "type": "multi"},
    {"name": "🏬 西夏影视", "url": "https://d.kstore.space/download/2912/xx888.json", "type": "multi"},
    {"name": "🏬 无邪多仓", "url": "https://gitee.com/wxej/wxrj/raw/master/wx.json", "type": "multi"},
    {"name": "🌐 天微", "url": "https://qixing.myhkw.com/DC.txt", "type": "multi"},
    {"name": "🏬 挺好分享(多仓)", "url": "http://ztha.top/TVBox/FLCK.json", "type": "multi"},
    {"name": "🏬 业余打发", "url": "https://ghproxy.net/https://raw.githubusercontent.com/yyfxz/qqtv/main/qq.json", "type": "multi"},
    {"name": "🏬 蓝色影视", "url": "https://raw.gitcode.com/yydg/ggdx/raw/main/Xboxb.json", "type": "multi"},
    {"name": "🏬 宝盒(多仓)", "url": "http://mzjk.top/DC", "type": "multi"},
    {"name": "🏬 天天秒播", "url": "http://tv.laohu.cool/tvbox.json", "type": "multi"},
    {"name": "🏬 飞哥传奇", "url": "https://chuanshuo.77blog.cn/dc.json", "type": "multi"},
    {"name": "🏬 电视盒子集", "url": "http://120.79.4.185/dc.json", "type": "multi"},

    # --- 【4. 外部直播源】 ---
    {"name": "📺 悦然直播", "url": "https://raw.githubusercontent.com/YueChan/Live/refs/heads/main/IPTV.m3u", "type": "live"},
    {"name": "🌍 悦然全球", "url": "https://raw.githubusercontent.com/YueChan/Live/refs/heads/main/Global.m3u", "type": "live"},
]

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

def test_url(item):
    url = encode_url(item["url"])
    name = item["name"]
    try:
        req = Request(url, method="HEAD", headers={
            "User-Agent": "TVBox/1.0 Mozilla/5.0",
            "Accept": "*/*"
        })
        with urlopen(req, timeout=10) as resp:
            return name, item["url"], resp.status, "OK", item["type"]
    except HTTPError as e:
        try:
            req = Request(url, method="GET", headers={
                "User-Agent": "TVBox/1.0 Mozilla/5.0",
                "Accept": "*/*"
            })
            with urlopen(req, timeout=10) as resp:
                return name, item["url"], resp.status, "OK", item["type"]
        except Exception:
            return name, item["url"], e.code, "HTTP Error", item["type"]
    except Exception as e:
        return name, item["url"], 0, str(e)[:80], item["type"]

print("=" * 70)
print(f"📺 {BRAND_NAME} | TVBox 仓库全量更新 v3")
print("=" * 70)
print("正在测试所有接口可用性（含成人点播源）...")
print()

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

print("\n" + "=" * 70)
print(f"✅ 可用: {len(ok_results)} / {len(results)}")
print(f"❌ 不可用: {len(fail_results)} / {len(results)}")
print("=" * 70)

# 分类
single_ok = [r for r in ok_results if r[4] == "single"]
multi_ok = [r for r in ok_results if r[4] == "multi"]
live_ok = [r for r in ok_results if r[4] == "live"]

# ===================== 构建【天天电视】品牌仓库 =====================
urls = []

# 1) 多仓源（品牌化）
for r in multi_ok:
    urls.append({"name": get_branded_name(r[0]), "url": r[1]})

# 2) 单仓源（品牌化，含成人点播）
for r in single_ok:
    urls.append({"name": get_branded_name(r[0]), "url": r[1]})

# 3) 外部直播源（品牌化）
for r in live_ok:
    urls.append({"name": get_branded_name(r[0]), "url": r[1]})

# 4) 自建直播源（品牌化命名）
urls.append({"name": f"{BRAND_NAME} · 🇨🇳 中国频道", "url": "http://207.246.102.108/m3u/cn.m3u"})
urls.append({"name": f"{BRAND_NAME} · 📺 央视频道", "url": "http://207.246.102.108/m3u/cctv.m3u"})
urls.append({"name": f"{BRAND_NAME} · 📡 卫视频道", "url": "http://207.246.102.108/m3u/weishi.m3u"})
urls.append({"name": f"{BRAND_NAME} · 🌍 全球频道", "url": "http://207.246.102.108/m3u/all.m3u"})

repo_json = {
    "name": f"📺 {BRAND_NAME} - 全能影视直播仓库",
    "description": f"{BRAND_NAME}多仓配置：点播+直播+成人精选，自动测试筛选，每6小时更新",
    "version": time.strftime("%Y-%m-%d"),
    "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "urls": urls
}

# ===================== 连接服务器并部署 =====================
print("\n📡 正在连接服务器部署...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=22, username=user, password=password, timeout=30)

# 备份旧配置
run_cmd(client, "cp /opt/iptv/tvbox/repo.json /opt/iptv/tvbox/repo.json.bak 2>/dev/null; echo backup-done")

# 写入新 repo.json
sftp = client.open_sftp()
with sftp.file("/opt/iptv/tvbox/repo.json", "w") as f:
    f.write(json.dumps(repo_json, ensure_ascii=False, indent=2))
sftp.close()
print("✅ repo.json 已上传")

# 验证
out, _ = run_cmd(client, """
echo "=== 更新后的 repo.json 前600字符 ==="
curl -s http://localhost/tvbox/repo.json | head -c 600
echo ""
echo ""
echo "=== 线路总数 ==="
curl -s http://localhost/tvbox/repo.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['urls']), '条')"
""")
print(out)

client.close()

print("\n" + "=" * 70)
print("✅ TVBox 仓库已更新（天天电视品牌版）")
print("=" * 70)
print(f"📺 品牌名称: {BRAND_NAME}")
print(f"📦 可用线路: {len(urls)} 条")
print(f"  - 多仓: {len(multi_ok)} 条")
print(f"  - 单仓(含成人): {len(single_ok)} 条")
print(f"  - 直播: {len(live_ok) + 4} 条")
print(f"\n🔗 多仓地址: http://207.246.102.108/tvbox/repo.json")
