#!/usr/bin/env python3
"""深入分析 category-h5 子应用的 JS，提取真实 functionId 和 API 配置"""
import httpx, re, json, sys
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"

print("=" * 70)
print("  深入分析 category-h5 子应用 JS")
print("=" * 70)

client = httpx.Client(timeout=15.0, headers={"User-Agent": UA}, follow_redirects=True)

# 1. 获取 category-h5 主页
print("\n[1] 获取 category-h5 主页...")
r = client.get("https://zhaoshang.jd.com/category-h5/")
print(f"  status={r.status_code}, size={len(r.text)}")

# 提取所有 JS URL
js_urls = re.findall(r'(?:src|href)=["\']([^"\']+\.js)["\']', r.text)
js_urls2 = re.findall(r'((?:https?:)?//[^\s"<>]+\.js)', r.text)
all_js = list(set(js_urls + js_urls2))
print(f"  JS 文件: {len(all_js)} 个")

# 补全 URL
resolved = []
for u in all_js:
    if u.startswith("//"):
        resolved.append("https:" + u)
    elif u.startswith("/"):
        resolved.append("https://zhaoshang.jd.com" + u)
    elif u.startswith("http"):
        resolved.append(u)
    else:
        resolved.append("https://zhaoshang.jd.com/category-h5/" + u)

# 2. 下载每个 JS 并搜索 functionId 和 API 配置
print("\n[2] 逐个分析 JS 文件...")
all_function_ids = set()
all_api_patterns = []

for js_url in sorted(resolved):
    try:
        js_r = client.get(js_url)
        js_text = js_r.text
        fname = js_url.split("/")[-1][:40]
        
        # 搜索 functionId 赋值
        # 模式: functionId = "xxx" 或 functionId: "xxx" 或 B.functionId=x
        fid_assigns = re.findall(r'functionId\s*[=:]\s*["\']([^"\']+)["\']', js_text)
        for fid in fid_assigns:
            all_function_ids.add(fid)
            print(f"  [{fname}] functionId = '{fid}'")
        
        # 搜索字符串中的 functionId 值（更广泛）
        # 在 functionId 附近搜索
        for m in re.finditer(r'functionId', js_text):
            ctx = js_text[max(0, m.start()-100):m.end()+200]
            # 提取引号内的字符串值
            vals = re.findall(r'["\']([a-zA-Z][a-zA-Z0-9_]+\.[a-zA-Z][a-zA-Z0-9_.]+)["\']', ctx)
            for v in vals:
                all_function_ids.add(v)
                print(f"  [{fname}] 上下文发现: '{v}'")
        
        # 搜索 API URL 构建模式
        for kw in ["appendParams", "api.m.jd", "functionId", "baseURL", "/api/", "getJson"]:
            if kw in js_text:
                count = js_text.count(kw)
                # 获取第一个匹配的上下文
                idx = js_text.index(kw)
                ctx = js_text[max(0, idx-60):idx+120]
                all_api_patterns.append({"file": fname, "keyword": kw, "count": count, "context": ctx})
                
        # 搜索所有引号字符串中的点分路径（可能是 mtop API）
        dot_paths = re.findall(r'["\']([a-z]+\.[a-z]+\.[a-z]+(?:\.[a-z]+)+)["\']', js_text)
        interesting = [p for p in dot_paths if not any(x in p for x in [".js", ".com", ".css", ".png", ".svg"])]
        for p in interesting:
            if len(p) > 10:
                all_function_ids.add(p)
                
    except Exception as e:
        print(f"  {js_url.split('/')[-1][:40]}: ERROR {str(e)[:60]}")

# 3. 汇总发现
print("\n[3] 汇总发现")
print(f"  所有 functionId / API 名称 ({len(all_function_ids)}):")
for fid in sorted(all_function_ids):
    print(f"    {fid}")

print(f"\n  API 模式 ({len(all_api_patterns)}):")
for p in all_api_patterns:
    print(f"    [{p['file']}] '{p['keyword']}' x{p['count']}")
    print(f"      ctx: ...{p['context'][:150]}...")

# 4. 重点分析 app.2045.js 中的 getJson 和 appendParams
print("\n[4] 重点分析 API 调用构建逻辑...")
for js_url in sorted(resolved):
    if "app" in js_url.split("/")[-1]:
        try:
            js_r = client.get(js_url)
            js_text = js_r.text
            fname = js_url.split("/")[-1][:40]
            
            # 搜索 getJson 调用
            for m in re.finditer(r'getJson\s*\(', js_text):
                ctx = js_text[max(0, m.start()-200):m.end()+300]
                print(f"\n  [{fname}] getJson 调用上下文:")
                print(f"    {ctx[:400]}")
            
            # 搜索 appendParams 调用
            for m in re.finditer(r'appendParams', js_text):
                ctx = js_text[max(0, m.start()-100):m.end()+200]
                print(f"\n  [{fname}] appendParams 上下文:")
                print(f"    {ctx[:300]}")
                
            # 搜索所有硬编码的字符串参数
            for m in re.finditer(r'["\']((?:jd|pop|sell|shop|industry|gong|zhaoshang)[a-zA-Z0-9_.]*)["\']', js_text, re.IGNORECASE):
                val = m.group(1)
                if len(val) > 5 and not val.endswith(".js"):
                    print(f"  [{fname}] 京东相关字符串: '{val}'")
                    
        except Exception as e:
            print(f"  ERROR: {e}")

# 5. 用发现的 functionId 尝试调用
print("\n[5] 尝试调用发现的 functionId...")
sys.path.insert(0, str(Path(__file__).parent))
try:
    from python.sign import generate_sign
    from python.fingerprint import FingerprintGenerator
    from python.anti_detect import AntiDetect
    
    fp = FingerprintGenerator(platform="desktop")
    uuid = fp.get_or_create_uuid()
    anti = AntiDetect(random_delay_range=(0.2, 0.5))
    
    test_fids = sorted(all_function_ids)
    for fid in test_fids[:20]:  # 最多测 20 个
        body_str = "{}"
        sign, t = generate_sign(function_id=fid, body=body_str, uuid=uuid)
        params = {
            "functionId": fid, "appid": "ebf5a3c8", "client": "h5",
            "clientVersion": "1.0.0", "t": t, "uuid": uuid, "sign": sign, "body": body_str,
        }
        headers = anti.build_stealth_headers()
        r = client.get("https://api.m.jd.com/", params=params, headers=headers)
        try:
            data = r.json()
            code = data.get("code", "?")
            echo = data.get("echo", data.get("message", ""))
            has_data = bool(data.get("data") or data.get("result"))
            status = "✓" if has_data else "✗"
            print(f"  {status} {fid}: code={code} echo={str(echo)[:50]}")
            if has_data:
                print(f"    DATA: {json.dumps(data, ensure_ascii=False)[:300]}")
        except:
            print(f"  ? {fid}: non-JSON ({r.text[:80]})")
except ImportError as e:
    print(f"  无法导入签名模块: {e}")

client.close()
print("\n" + "=" * 70)
print("  分析完成")
print("=" * 70)
