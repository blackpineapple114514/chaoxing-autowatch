# -*- coding: utf-8 -*-
"""对着正在运行的 exe 自测：二维码接口 + /api/login/refresh 是否真能换新码。"""
import base64, io, time
import requests, numpy as np, cv2

B = "http://127.0.0.1:56918"
s = requests.Session()

def decode(dataurl):
    raw = base64.b64decode(dataurl.split(",", 1)[1])
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
    big = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    d = cv2.QRCodeDetector()
    txt, _, _ = d.detectAndDecode(big)
    return txt

j = s.post(B + "/api/login/qr", timeout=30).json()
print("qr ok:", j["ok"], "len:", len(j.get("qr", "")))
print("payload#1:", decode(j["qr"])[:110])
print("status  :", s.get(B + "/api/login/status", timeout=30).json())

t0 = time.time()
r = s.post(B + "/api/login/refresh", timeout=30)
print("refresh http:", r.status_code, "elapsed %.1fs" % (time.time() - t0))
try:
    rj = r.json()
except Exception as e:
    print("refresh NOT json:", r.text[:300]); raise SystemExit(0)
print("refresh ok:", rj.get("ok"), "err:", rj.get("error"))
if rj.get("ok"):
    print("payload#2:", decode(rj["qr"])[:110])
print("status after refresh:", s.get(B + "/api/login/status", timeout=30).json())
