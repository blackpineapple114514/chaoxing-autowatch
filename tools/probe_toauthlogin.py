# -*- coding: utf-8 -*-
"""模拟"手机扫到二维码后"那一步：GET toauthlogin，看过期/有效分别返回什么。
用 3 种身份：全新会话 / 已登录会话(相当于自己扫码) / 旧二维码(已放置很久)。
只 GET，不改任何东西。"""
import sys, os, json, time
sys.path.insert(0, r"<repo>\app")
import requests
from cx_client import Chaoxing, UA

OLD_UUID = "4ee4a1590fa94cbab7a3d8d7816f16d9"
OLD_ENC = "ba95d8676171729bb1c87f121fb09418"

def show(tag, r):
    print("---", tag, "status", r.status_code, "len", len(r.text))
    print("    loc:", r.headers.get("Location", ""))
    print("    body:", r.text[:400].replace("\n", " "))

# 1) 全新会话 + 旧二维码（很久以前创建的）
s = requests.Session(); s.headers.update({"User-Agent": UA})
u = "https://passport2.chaoxing.com/toauthlogin?uuid=%s&enc=%s&xxtrefer=&clientid=&type=0&mobiletip=" % (OLD_UUID, OLD_ENC)
show("匿名+旧QR", s.get(u, timeout=25, allow_redirects=False))

# 2) 已登录会话 + 旧二维码
ck = json.load(open(os.path.join(os.path.expanduser("~"), ".chaoxing-cookies.json"), encoding="utf-8"))
s2 = requests.Session(); s2.headers.update({"User-Agent": UA})
for k, v in ck["base"].items():
    s2.cookies.set(k, v, domain=".chaoxing.com")
show("已登录+旧QR", s2.get(u, timeout=25, allow_redirects=False))

# 3) 刚创建的二维码
cx = Chaoxing()
info = cx.start_qr()
fresh = "https://passport2.chaoxing.com/toauthlogin?uuid=%s&enc=%s&xxtrefer=&clientid=&type=0&mobiletip=" % (info["uuid"], info["enc"])
print("\n新鲜 uuid:", info["uuid"])
show("匿名+新QR", s.get(fresh, timeout=25, allow_redirects=False))

# 4) 等服务端可能翻转，再轮询几次
for i in range(3):
    time.sleep(3)
    st = cx.poll_login()
    print("   poll", st["status"], str(st.get("raw"))[:120])
