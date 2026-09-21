# -*- coding: utf-8 -*-
"""解出学习通登录二维码里真正编码的内容，并测过期时间。"""
import sys, io, time
sys.path.insert(0, r"<repo>\app")
import numpy as np, cv2
from cx_client import Chaoxing

for attempt in range(3):
    cx = Chaoxing()
    info = cx.start_qr()
    raw = np.frombuffer(info["qr"], np.uint8)
    img = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
    # 放大再解，提高识别率
    big = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    d = cv2.QRCodeDetector()
    ok, pts = d.detect(big)
    txt, pts2, _ = d.detectAndDecode(big)
    print("try", attempt, "size", img.shape, "detect", ok, "payload:", repr(txt))
    if txt:
        cx2 = cx
        print("uuid from page:", info["uuid"])
        break
    time.sleep(1)
