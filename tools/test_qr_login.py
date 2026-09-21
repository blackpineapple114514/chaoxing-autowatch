# -*- coding: utf-8 -*-
"""验证：学习通扫码登录能否纯 HTTP 完成（不需要浏览器）。
输出：QR 图片 + 轮询状态日志。"""
import re, sys, time, json, io
import requests

LOGIN_URL = "https://passport2.chaoxing.com/login?fid=12&refer=http%3A%2F%2Fi.chaoxing.com%2Fbase&space=2"
BASE = "https://passport2.chaoxing.com"

def main():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Referer": LOGIN_URL,
    })
    r = s.get(LOGIN_URL, timeout=20)
    print("login page:", r.status_code, len(r.text), flush=True)
    uuid = re.search(r'id="uuid"\s+value="([^"]+)"', r.text) or re.search(r'value="([^"]+)"\s+id="uuid"', r.text)
    enc = re.search(r'id="enc"\s+value="([^"]+)"', r.text) or re.search(r'value="([^"]+)"\s+id="enc"', r.text)
    print("uuid:", uuid and uuid.group(1), "enc:", enc and enc.group(1), flush=True)
    if not uuid or not enc:
        print("PARSE FAIL"); return
    uuid_v, enc_v = uuid.group(1), enc.group(1)

    qr = s.get(f"{BASE}/createqr?uuid={uuid_v}&fid=-1", timeout=20)
    print("qr:", qr.status_code, qr.headers.get("content-type"), len(qr.content), flush=True)
    with open(r"<tmp>\qr_login.png", "wb") as f:
        f.write(qr.content)

    print("cookies after page:", s.cookies.get_dict(), flush=True)
    for i in range(40):
        try:
            st = s.post(f"{BASE}/getauthstatus/v2", data={
                "enc": enc_v, "uuid": uuid_v, "doubleFactorLogin": "0", "forbidotherlogin": "0",
            }, timeout=20, headers={"X-Requested-With": "XMLHttpRequest"})
            print(f"[{i}] status={st.status_code} body={st.text[:300]}", flush=True)
            try:
                j = st.json()
            except Exception:
                j = {}
            if j.get("status") is True or j.get("status") == 1:
                print("LOGIN OK, cookies:", s.cookies.get_dict(), flush=True)
                io.open(r"<tmp>\login_ok.json", "w", encoding="utf-8").write(
                    json.dumps({"uuid": uuid_v, "enc": enc_v, "body": st.text, "cookies": s.cookies.get_dict()}, ensure_ascii=False, indent=2))
                return
            # refresh QR if expired
            if "二维码" in st.text and ("过期" in st.text or "失效" in st.text):
                rr = s.post(f"{BASE}/refreshQRCode", timeout=20)
                print("refresh:", rr.status_code, rr.text[:200], flush=True)
                try:
                    d = rr.json(); uuid_v = d.get("uuid", uuid_v); enc_v = d.get("enc", enc_v)
                    qr = s.get(f"{BASE}/createqr?uuid={uuid_v}&fid=-1", timeout=20)
                    open(r"<tmp>\qr_login.png", "wb").write(qr.content)
                except Exception as e:
                    print("refresh err", e, flush=True)
        except Exception as e:
            print("poll err", e, flush=True)
        time.sleep(3)
    print("TIMEOUT no login", flush=True)

if __name__ == "__main__":
    main()
