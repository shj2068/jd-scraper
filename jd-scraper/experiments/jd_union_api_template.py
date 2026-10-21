# 京东联盟 API 调用步骤:
# 1. 访问 https://media.jd.com/ 注册账号
# 2. 完成个人实名认证
# 3. 进入「开发者管理」→「我的 API」→ 领取授权 Key
# 4. 创建应用 → 获取 AppKey 和 AppSecret
# 5. 申请接口权限（填写用途：选品/比价/数据采集）
# 6. 使用以下代码调用

import hashlib
import time
import httpx
import json

APP_KEY = "你的AppKey"       # 替换为实际值
APP_SECRET = "你的AppSecret"  # 替换为实际值
GATEWAY = "https://router.jd.com/api"

def jd_union_sign(params, app_secret):
    """京东联盟签名算法"""
    sorted_params = sorted(params.items())
    sign_str = app_secret
    for k, v in sorted_params:
        sign_str += str(k) + str(v)
    sign_str += app_secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()

def query_jingfen_goods(elite_id=1, page=1, page_size=20):
    """查询京粉精选商品（无需额外申请）"""
    params = {
        "method": "jd.union.open.goods.jingfen.query",
        "app_key": APP_KEY,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "1.0",
        "sign_method": "md5",
        "goods_req": json.dumps({
            "eliteId": elite_id,  # 1=好券商品, 2=精选卖场, 10=9.9包邮...
            "pageIndex": page,
            "pageSize": page_size,
        }),
    }
    params["sign"] = jd_union_sign(params, APP_SECRET)

    r = httpx.post(GATEWAY, data=params, timeout=10)
    return r.json()

# 调用示例:
# result = query_jingfen_goods(elite_id=1, page=1, page_size=10)
# print(json.dumps(result, ensure_ascii=False, indent=2))