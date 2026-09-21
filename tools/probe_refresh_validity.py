# -*- coding: utf-8 -*-
"""关键验证：refreshQRCode 换出来的新码，是不是"一出生就是死的"？
对比：登录页直接给的码 vs refreshQRCode 换的码，各轮询几次看服务端态度。"""
import sys, time
sys.path.insert(0, r"<repo>\app")
from cx_client import Chaoxing

def probe(cx, tag, n=4, gap=2.0):
    print("--- %s uuid=%s" % (tag, cx.uuid))
    for i in range(n):
        st = cx.poll_login()
        print("    t=%.0fs status=%-8s raw=%s" % (i * gap, st["status"], str(st.get("raw"))[:120]))
        time.sleep(gap)

cx = Chaoxing()
info = cx.start_qr()
print("登录页给的 uuid:", info["uuid"])
probe(cx, "【登录页原生码】")

print()
print(">>> 调 refreshQRCode 换码")
info2 = cx.refresh_qr()
print("换出来的 uuid:", info2["uuid"])
probe(cx, "【refreshQRCode 新码】")

time.sleep(5)
probe(cx, "【再等 5 秒后】", n=3)
