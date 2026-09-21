# -*- coding: utf-8 -*-
"""压力轮询 getauthstatus，看有没有哪次响应里带"过期/失效"（会导致 App 误刷新二维码）。"""
import sys, time
sys.path.insert(0, r"<repo>\app")
from cx_client import Chaoxing, PASSPORT

cx = Chaoxing()
info = cx.start_qr()
print("uuid:", info["uuid"], flush=True)
hit = 0
codes = {}
t0 = time.time()
i = 0
while time.time() - t0 < 90:
    i += 1
    st = cx.s.post("%s/getauthstatus/v2" % PASSPORT, timeout=20,
                   data={"enc": cx.enc, "uuid": cx.uuid,
                         "doubleFactorLogin": "0", "forbidotherlogin": "0"},
                   headers={"X-Requested-With": "XMLHttpRequest"})
    codes[st.status_code] = codes.get(st.status_code, 0) + 1
    b = st.text
    if "过期" in b or "失效" in b:
        hit += 1
        print("!!! 第 %d 次出现关键字: %s" % (i, b[:300]), flush=True)
    time.sleep(0.4)
print("轮询 %d 次，状态码分布 %s，命中关键字 %d 次" % (i, codes, hit), flush=True)
