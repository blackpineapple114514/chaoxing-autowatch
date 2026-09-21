# -*- coding: utf-8 -*-
"""扒官方 login.js：看 getauthstatus 返回的 type 码含义（2/4/6…）和隐藏输入值。"""
import re, io, sys
sys.path.insert(0, r"<repo>\app")
import requests
from cx_client import UA, LOGIN_URL

r = requests.get(LOGIN_URL, headers={"User-Agent": UA}, timeout=25)
h = r.text
print("=== 隐藏输入 ===")
for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', h):
    t = m.group(0)
    if any(k in t for k in ("doubleFactor", "forbidotherlogin", "refer", "_blank", "uuid", "enc", "fid")):
        print("  ", t.replace("\n", " ")[:200])

js = requests.get("https://passport2-static.chaoxing.com/js/fanya/login.js?v=20260908",
                  headers={"User-Agent": UA}, timeout=25).text
io.open(r"<tmp>\login.js", "w", encoding="utf-8").write(js)
print("\nlogin.js len:", len(js))

for kw in ["toauthlogin", "refreshQRCode", "ewmDisable", "type ==", "type==", "type == ", "已失效", "qrlogin", "qrcode"]:
    idxs = [m.start() for m in re.finditer(re.escape(kw), js)][:4]
    for i in idxs:
        seg = js[max(0, i - 220):i + 320].replace("\n", " ")
        print("\n### %s @%d\n%s" % (kw, i, seg))
