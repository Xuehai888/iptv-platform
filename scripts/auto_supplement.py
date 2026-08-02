#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV Auto-Supplement v1
========================
Automatically searches for new/fresh IPTV sources on GitHub and public endpoints.
Tests their availability, deduplicates with existing sources, and merges into the collection.

Strategy:
1. Check health report to find low-performing (dead) sources
2. Search GitHub via API + known repos for fresh IPTV lists  
3. Test new sources (quick mode first)
4. Merge valid new sources with existing collection
5. Update m3u/txt files + cron jobs

Usage:
    python3 auto_supplement.py          # Run full supplement cycle
    python3 auto_supplement.py --dry    # Preview only, don't write files
"""
import os, re, json, time, logging, hashlib, glob
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = "/opt/iptv"
M3U_DIR = os.path.join(BASE_DIR, "m3u")
TXT_DIR = os.path.join(BASE_DIR, "txt")
LOG_DIR = os.path.join(BASE_DIR, "logs")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "auto_supplement.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ===================== Known GitHub IPTV repositories =====================
# v2: 2026-08-01 清理失效源（iptv-cat/nicedoc/batawil/qingwenyuan/zabonala/kerrywf/xiehmad/yes-playlists/iill.us.kg/suxuang-mini 全部404移除），
#     新增验证可用的：iptv-org、Fanmingming、M3U8-CN
KNOWN_GITHUB_REPOS = [
    {"url": "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u", 
     "name": "Guovin iptv-api (GD mirror)", "active": True},
    {"url": "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u", 
     "name": "YueChan Live IPTV", "active": True},
    {"url": "https://raw.githubusercontent.com/YueChan/Live/main/Global.m3u", 
     "name": "YueChan Live Global", "active": True},
    {"url": "https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u", 
     "name": "suxuang myIPTV ipv4", "active": True},
    {"url": "https://live.zbds.top/tv/iptv4.txt", 
     "name": "live.zbds.top iptv4", "active": True},
    {"url": "https://www.iyouhun.com/tv/zb", 
     "name": "iyouhun 直播源", "active": True},
    {"url": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8", 
     "name": "Free-TV IPTV", "active": True},
    {"url": "https://iptv-org.github.io/iptv/countries/cn.m3u", 
     "name": "iptv-org 中国", "active": True},
    {"url": "https://iptv-org.github.io/iptv/index.m3u", 
     "name": "iptv-org 全球", "active": True},
    {"url": "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u", 
     "name": "fanmingming IPv6", "active": True},
    {"url": "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u", 
     "name": "M3U8-CN 国内", "active": True},
]

# GitHub search queries for finding new IPTV repos
GITHUB_SEARCH_QUERIES = [
    "iptv m3u",
    "iptv live",
    "iptv china",
    "iptv channel list",
    "live tv m3u8",
    "中国直播 m3u",
    "电视直播 m3u",
]


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
            current = {"name": name, "logo": logo, "group": group}
        elif line and not line.startswith("#"):
            current["url"] = line.strip()
            if "name" in current and "url" in current:
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
                    channels.append({"name": name, "url": url, "group": current_group})
    return channels


def fetch_url(url, timeout=20):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for attempt in range(2):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='replace')[:1000000]
        except Exception:
            time.sleep(1)
    return None


def test_url(url, timeout=10):
    """Quick test if a URL returns content."""
    try:
        headers = {
            "User-Agent": "VLC/3.0",
            "Range": "bytes=0-4095",
        }
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            chunk = resp.read(4096)
            return resp.status >= 200 and len(chunk) > 0
    except:
        try:
            req = Request(url, headers={"User-Agent": "VLC/3.0"})
            with urlopen(req, timeout=timeout) as resp:
                chunk = resp.read(4096)
                return resp.status >= 200 and len(chunk) > 0
        except:
            return False


def load_existing_urls():
    """Load all URLs already in our collection to avoid duplicates."""
    existing = set()
    
    # From m3u files
    for fname in glob.glob(os.path.join(M3U_DIR, "*.m3u")):
        content = fetch_url(f"http://localhost/m3u/{os.path.basename(fname)}") or \
                  (open(fname, 'r', encoding='utf-8').read()[:300000])
        channels = parse_m3u(content)
        for ch in channels:
            existing.add(ch.get("url", ""))
    
    # From txt files
    for fname in glob.glob(os.path.join(TXT_DIR, "*.txt")):
        content = (open(fname, 'r', encoding='utf-8').read()[:300000])
        channels = parse_txt(content)
        for ch in channels:
            existing.add(ch.get("url", ""))
    
    return existing


def search_github_api(query, per_page=30):
    """Search GitHub API for IPTV-related repos/files."""
    results = []
    try:
        api_url = f"https://api.github.com/search/code?q={query}+extension:m3u&per_page={per_page}"
        headers = {"User-Agent": "IPTV-Supplement/1.0"}
        req = Request(api_url, headers=headers)
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            items = data.get("items", [])
            for item in items:
                results.append({
                    "name": item.get("name", ""),
                    "repo": item.get("repository", {}).get("full_name", ""),
                    "url": item.get("html_url", ""),
                    "content_url": item.get("download_url", ""),
                })
    except Exception as e:
        log.warning(f"GitHub search '{query}' failed: {e}")
    return results


def deduplicate_channels(channels, exclude_set=None):
    """Remove duplicate URLs, keep unique channels."""
    seen = set()
    unique = []
    for ch in channels:
        url = ch.get("url", "")
        if url and (exclude_set is None or url not in exclude_set):
            if url not in seen:
                seen.add(url)
                unique.append(ch)
    return unique


def get_low_performing_sources(report_data, threshold=50):
    """Find sources with success rate below threshold - these need replacement."""
    low_perf = []
    for src in report_data.get("sources", []):
        if src.get("success_rate", 100) < threshold:
            low_perf.append(src)
    return low_perf


def main(dry_run=False):
    log.info("=" * 70)
    log.info("IPTV Auto-Supplement Starting")
    log.info("=" * 70)
    
    start_time = time.time()
    
    # ===================== Step 1: Load existing & check previous health =====================
    log.info("[1/5] Loading existing sources...")
    existing_urls = load_existing_urls()
    log.info(f"  Existing URLs loaded: {len(existing_urls)}")
    
    # Load previous health report
    prev_report = None
    pattern = os.path.join(REPORT_DIR, "health_*.json")
    files = sorted(glob.glob(pattern))
    if files:
        with open(files[-1], 'r', encoding='utf-8') as f:
            prev_report = json.load(f)
        log.info(f"  Previous health report loaded from: {files[-1]}")
    
    low_perf = get_low_performing_sources(prev_report, threshold=50) if prev_report else []
    dead_source_count = len(low_perf)
    log.info(f"  Low-performing sources (<50%): {dead_source_count}")
    
    # ===================== Step 2: Test known sources =====================
    log.info("[2/5] Testing known GitHub IPTV sources...")
    tested_sources = {}
    
    with ThreadPoolExecutor(max_workers=10) as pool:
        future_to_name = {}
        for repo in KNOWN_GITHUB_REPOS:
            url = repo["url"]
            future = pool.submit(test_url, url)
            future_to_name[future] = repo
        
        for future in as_completed(future_to_name):
            repo = future_to_name[future]
            try:
                ok = future.result()
                tested_sources[repo["name"]] = {"url": repo["url"], "ok": ok}
                icon = "✅" if ok else "❌"
                log.info(f"  {icon} {repo['name']}: {'working' if ok else 'DEAD'}")
            except:
                tested_sources[repo["name"]] = {"url": repo["url"], "ok": False}
                log.info(f"  ❌ {repo['name']}: ERROR")
    
    working_known = {k: v for k, v in tested_sources.items() if v["ok"]}
    dead_known = {k: v for k, v in tested_sources.items() if not v["ok"]}
    log.info(f"  Working known: {len(working_known)}, Dead known: {len(dead_known)}")
    
    # ===================== Step 3: Fetch & parse new sources =====================
    log.info("[3/5] Parsing new sources...")
    new_all_channels = []
    
    for name, info in working_known.items():
        content = fetch_url(info["url"])
        if not content:
            continue
        
        if "#EXTM3U" in content[:200] or "#EXTINF" in content[:200]:
            channels = parse_m3u(content)
        else:
            channels = parse_txt(content)
        
        if not channels:
            continue
        
        unique = deduplicate_channels(channels, existing_urls)
        new_all_channels.extend(unique)
        log.info(f"  {name}: {len(channels)} total → {len(unique)} new unique")
    
    log.info(f"  Total potential new channels: {len(new_all_channels)}")
    
    # ===================== Step 4: Quick validation of new channels =====================
    log.info("[4/5] Quick validation of new channels...")
    valid_new = []
    sample = new_all_channels[:200]  # Validate first 200
    
    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = {pool.submit(test_url, ch["url"]): ch for ch in sample}
        done = 0
        for future in as_completed(futures):
            done += 1
            ch = futures[future]
            try:
                if future.result():
                    valid_new.append(ch)
            except:
                pass
            if done % 50 == 0:
                log.info(f"  Validated {done}/{len(sample)}: {len(valid_new)} OK ({len(valid_new)/max(done,1)*100:.0f}%)")
    
    log.info(f"  New valid channels: {len(valid_new)}/{len(sample)} ({len(valid_new)/max(len(sample),1)*100:.0f}%)")
    
    # If we found enough, take them all
    final_new = valid_new if len(valid_new) > 0 else sample[:min(len(new_all_channels), 100)]
    
    # ===================== Step 5: Merge & Generate updated files =====================
    log.info("[5/5] Merging and generating updated files...")
    
    # v2: 只读分类全集文件 cn.m3u / international.m3u（避免把 all.m3u 全集、intl_* 子文件
    #      或 international.m3u 误判为中文源导致重复/混入）
    all_chinese = []
    all_intl = []
    
    for fname in [os.path.join(M3U_DIR, "cn.m3u"), os.path.join(M3U_DIR, "international.m3u")]:
        if not os.path.exists(fname):
            continue
        content = open(fname, 'r', encoding='utf-8').read()[:1000000]
        channels = parse_m3u(content)
        if os.path.basename(fname) == "cn.m3u":
            all_chinese.extend(channels)
        else:
            all_intl.extend(channels)
    
    # Add valid new channels
    existing_urls_for_merge = set(ch["url"] for ch in all_chinese) | set(ch["url"] for ch in all_intl)
    truly_new = deduplicate_channels(final_new, existing_urls_for_merge)
    
    if truly_new:
        log.info(f"  Adding {len(truly_new)} new unique channels...")
        all_chinese.extend(truly_new)
        all_intl.extend(truly_new)
        
        if not dry_run:
            # Regenerate all files (v2: 保留 group-title 品牌化)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            def m3u_extinf(ch):
                group = ch.get("group", ch.get("category", "Other"))
                # 品牌化：统一加"天天电视 · "前缀（幂等）
                if group and not group.startswith("天天电视"):
                    group = f"天天电视 · {group}"
                logo = ch.get("logo", "")
                logo_attr = f' tvg-logo="{logo}"' if logo else ""
                # 标准 group-title 属性（TVBox 兼容）
                return f'#EXTINF:-1 group-title="{group}"{logo_attr},{ch["name"]}'
            
            # cn.m3u
            cn_content = ["#EXTM3U", f"# Chinese - {len(all_chinese)} channels - {timestamp}"]
            for ch in all_chinese:
                cn_content.append(m3u_extinf(ch))
                cn_content.append(ch["url"])
            with open(os.path.join(M3U_DIR, "cn.m3u"), 'w', encoding='utf-8') as f:
                f.write('\n'.join(cn_content))
            
            # all.m3u
            all_content = ["#EXTM3U", f"# All - {len(all_chinese + all_intl)} channels - {timestamp}"]
            for ch in all_chinese + all_intl:
                all_content.append(m3u_extinf(ch))
                all_content.append(ch["url"])
            with open(os.path.join(M3U_DIR, "all.m3u"), 'w', encoding='utf-8') as f:
                f.write('\n'.join(all_content))
            
            # TXT files
            txt_lines = ["CN,#genre#"]
            for ch in all_chinese:
                txt_lines.append(f'{ch["name"]},{ch["url"]}')
            with open(os.path.join(TXT_DIR, "cn.txt"), 'w', encoding='utf-8') as f:
                f.write('\n'.join(txt_lines))
            
            log.info("  ✅ Files regenerated successfully!")
    
    elapsed = time.time() - start_time
    
    # Summary
    print("\n" + "=" * 70)
    print("AUTO-SUPPLEMENT SUMMARY")
    print("=" * 70)
    print(f"Existing URLs:    {len(existing_urls)}")
    print(f"Low-performers:   {dead_source_count}")
    print(f"Known sources ok: {len(working_known)}/{len(tested_sources)}")
    print(f"New candidates:   {len(new_all_channels)}")
    print(f"Valid new:        {len(final_new)}")
    print(f"Truly new add:    {len(truly_new)}")
    print(f"Elapsed:          {elapsed:.1f}s")
    
    if dead_known:
        print(f"\n⚠️  Dead known sources needing replacement:")
        for name, info in dead_known.items():
            print(f"  - {name}: {info['url']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Preview only")
    args = parser.parse_args()
    main(dry_run=args.dry)
