#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""幂等地为 /opt/iptv/m3u/*.m3u 的 group-title 添加「天天电视 ·」前缀"""
import os, re, glob

M3U_DIR = "/opt/iptv/m3u"
PREFIX = "天天电视 · "

# 排除文件：all.m3u / international.m3u 也要处理？——先全部处理，但跳过已加过的
files = sorted(glob.glob(os.path.join(M3U_DIR, "*.m3u")))
total_groups = 0
for fp in files:
    with open(fp, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    orig = content
    
    def add_prefix(m):
        gt = m.group(1)
        if gt.startswith(PREFIX) or gt.startswith("天天电视"):
            return m.group(0)
        return f'tvg-group="{PREFIX}{gt}"'
    
    content = re.sub(r'tvg-group="([^"]*)"', add_prefix, content)
    
    if content != orig:
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        groups_added = len(re.findall(r'tvg-group="', content))
        total_groups += groups_added
        print(f"✅ {os.path.basename(fp)}: group-title 已品牌化")
    else:
        print(f"⏭️  {os.path.basename(fp)}: 无需修改（可能已加前缀或无分组）")

print(f"\n完成！共处理 {len(files)} 个文件")
