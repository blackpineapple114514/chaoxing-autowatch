# -*- coding: utf-8 -*-
"""拉学习通登录页，扒出它自己的二维码刷新/过期 JS 逻辑（只读）。"""
import re, sys, io
sys.path.insert(0, r"<repo>\app")
import requests
from cx_client import UA, LOGIN_URL

r = requests.get(LOGIN_URL, headers={"User-Agent": UA}, timeout=25)
html = r.text
print("status", r.status_code, "len", len(html))
io.open(r"<tmp>\login_page.html", "w", encoding="utf-8").write(html)

for kw in ["getauthstatus", "refreshQRCode", "createqr", "已失效", "过期", "setInterval", "setTimeout",
           "qrTime", "countdown", "expire"]:
    for m in re.finditer(re.escape(kw), html):
        s = max(0, m.start() - 160)
        seg = html[s:m.start() + 200].replace("\n", " ").replace("\r", " ")
        print("\n### %s @%d\n%s" % (kw, m.start(), seg))
        break

print("\n===== script src 列表 =====")
for m in re.finditer(r'<script[^>]+src="([^"]+)"', html):
    print(m.group(1))
