# -*- coding: utf-8 -*-
"""长测：一个二维码从创建到过期的真实寿命（最长 10 分钟），并看过期时服务端返回什么。"""
import sys, time, json
sys.path.insert(0, r"<repo>\app")
from cx_client import Chaoxing

cx = Chaoxing()
info = cx.start_qr()
print("uuid:", info["uuid"], flush=True)
t0 = time.time()
last = None
while time.time() - t0 < 600:
    st = cx.poll_login()
    el = time.time() - t0
    key = st["status"]
    if key != last or last is None or int(el) % 30 == 0:
        print("t=%6.1fs status=%s raw=%s" % (el, st["status"], json.dumps(st.get("raw"), ensure_ascii=False)[:200]), flush=True)
        last = key
    if st["status"] in ("expired", "ok"):
        print(">>> STOP at %.1fs status=%s" % (el, st["status"]), flush=True)
        break
    time.sleep(5)
else:
    print(">>> 10 分钟内没变过期（仍有效）", flush=True)
