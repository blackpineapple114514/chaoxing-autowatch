# -*- coding: utf-8 -*-
"""量一下学习通登录二维码的有效期：多久变 expired，refreshQRCode 是否换 uuid。"""
import sys, os, time, hashlib
sys.path.insert(0, r"<repo>\app")
from cx_client import Chaoxing

cx = Chaoxing()
info = cx.start_qr()
qr = info["qr"]
print("uuid:", info["uuid"])
print("enc :", info["enc"])
print("qr bytes:", len(qr), "sha1:", hashlib.sha1(qr).hexdigest()[:12],
      "ctype:", info["content_type"])
try:
    import qrcode, io
    from PIL import Image
    img = Image.open(io.BytesIO(qr))
    print("qr image size:", img.size, img.mode)
except Exception as e:
    print("decode qr failed:", e)

t0 = time.time()
for i in range(40):
    st = cx.poll_login()
    el = time.time() - t0
    print("t=%5.1fs  status=%s  raw=%s" % (el, st["status"], str(st.get("raw"))[:160]))
    if st["status"] == "expired":
        print(">>> QR 存活 %.1f 秒" % el)
        break
    time.sleep(5)

print("--- 试 refreshQRCode ---")
old_uuid = cx.uuid
r = cx.s.post("https://passport2.chaoxing.com/refreshQRCode", timeout=25,
              headers={"X-Requested-With": "XMLHttpRequest"})
print("status:", r.status_code, "body:", r.text[:300])
print("uuid before:", old_uuid, " after:", cx.uuid, " same:", old_uuid == cx.uuid)
