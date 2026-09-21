# -*- coding: utf-8 -*-
"""深挖 refresh_qr：刷新后 createqr 到底返回了什么（字节数/类型/尺寸/内容）。"""
import sys, io, hashlib
sys.path.insert(0, r"<repo>\app")
import numpy as np, cv2
from cx_client import Chaoxing, PASSPORT

cx = Chaoxing()
info = cx.start_qr()
print("初始 uuid:", info["uuid"], "qr bytes:", len(info["qr"]), "ctype:", info["content_type"])

rr = cx.s.post("%s/refreshQRCode" % PASSPORT, timeout=25, headers={"X-Requested-With": "XMLHttpRequest"})
print("refreshQRCode http:", rr.status_code, "body:", rr.text[:200])
import json
try:
    d = rr.json()
except Exception:
    d = {}
new_uuid = d.get("uuid")
print("新 uuid:", new_uuid, "新 enc:", d.get("enc"))

for tag, u in (("新uuid", new_uuid), ("旧uuid", info["uuid"])):
    q = cx.s.get("%s/createqr?uuid=%s&fid=-1" % (PASSPORT, u), timeout=25)
    b = q.content
    print("\n--- createqr(%s) http=%s len=%d ctype=%s sha1=%s" % (tag, q.status_code, len(b), q.headers.get("content-type"), hashlib.sha1(b).hexdigest()[:12]))
    print("    前 120 字节:", b[:120])
    if b[:3] == b"\xff\xd8\xff" or b[:4] == b"\x89PNG":
        img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_GRAYSCALE)
        big = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        txt, _, _ = cv2.QRCodeDetector().detectAndDecode(big)
        print("    image shape:", None if img is None else img.shape, "decode:", (txt or "(空)")[:110])
