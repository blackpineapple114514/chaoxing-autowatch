# -*- coding: utf-8 -*-
"""
学习通（超星）纯 HTTP 客户端 —— 扫码登录 / 读课程 / 读章节 / 读任务点 / 视频进度上报。

全部接口均已实测可用，不需要浏览器、不需要 Playwright。
"""
import re
import time
import json
import base64
import hashlib
import threading
from urllib.parse import urlparse

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

LOGIN_URL = "https://passport2.chaoxing.com/login?fid=12&refer=http%3A%2F%2Fi.chaoxing.com%2Fbase&space=2"
PASSPORT = "https://passport2.chaoxing.com"
VIDEO_SALT = "d_yHJ!$pdA~5"

# 账号密码登录用的 AES 密钥（从官方 login.js 的 encryptByAES 调用点扒出：key 同时当 IV）
AES_LOGIN_KEY = "u2oh6Vu^HWe4_AES"


def aes_b64(message, key=AES_LOGIN_KEY):
    """复刻官方 encryptByAES：AES/CBC/PKCS7，key=iv，输出 Base64。"""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as _padding
    k = key.encode("utf-8")
    padder = _padding.PKCS7(128).padder()
    data = padder.update(message.encode("utf-8")) + padder.finalize()
    enc = Cipher(algorithms.AES(k), modes.CBC(k)).encryptor()
    return base64.b64encode(enc.update(data) + enc.finalize()).decode()


# ---------------------------------------------------------------- 工具函数
def enc_video(clazz_id, user_id, job_id, object_id, playing_ms, duration_ms, clip_time):
    """播放器进度上报的 enc 签名（已用真实抓包双样本对照验证）。"""
    s = "[%s][%s][%s][%s][%s][%s][%s][%s]" % (
        clazz_id, user_id, job_id, object_id, playing_ms, VIDEO_SALT, duration_ms, clip_time)
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _digest(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 客户端
class Chaoxing:
    def __init__(self, session=None):
        self.s = session or requests.Session()
        self.s.headers.update({"User-Agent": UA})

    # ---------------------------------------------------- 登录
    def start_qr(self):
        """拉登录页 -> 解析 uuid/enc -> 取二维码。返回 dict(qr=bytes, uuid=, enc=)。"""
        r = self.s.get(LOGIN_URL, timeout=25)
        uuid_m = re.search(r'id="uuid"\s+value="([^"]+)"', r.text) or \
            re.search(r'value="([^"]+)"\s+id="uuid"', r.text)
        enc_m = re.search(r'id="enc"\s+value="([^"]+)"', r.text) or \
            re.search(r'value="([^"]+)"\s+id="enc"', r.text)
        if not uuid_m or not enc_m:
            raise RuntimeError("登录页解析失败（uuid/enc 未找到）")
        self.uuid, self.enc = uuid_m.group(1), enc_m.group(1)
        qr = self.s.get("%s/createqr?uuid=%s&fid=-1" % (PASSPORT, self.uuid), timeout=25)
        return {"qr": qr.content, "uuid": self.uuid, "enc": self.enc,
                "content_type": qr.headers.get("content-type", "image/jpeg")}

    def refresh_qr(self):
        """二维码过期时刷新。返回新的二维码信息。"""
        rr = self.s.post("%s/refreshQRCode" % PASSPORT, timeout=25,
                         headers={"X-Requested-With": "XMLHttpRequest"})
        try:
            d = rr.json()
            self.uuid = d.get("uuid", self.uuid)
            self.enc = d.get("enc", self.enc)
        except Exception:
            pass
        qr = self.s.get("%s/createqr?uuid=%s&fid=-1" % (PASSPORT, self.uuid), timeout=25)
        return {"qr": qr.content, "uuid": self.uuid, "enc": self.enc,
                "content_type": qr.headers.get("content-type", "image/jpeg")}

    def poll_login(self):
        """轮询扫码状态。
        返回 status: 'waiting' | 'scanned'(已扫待确认) | 'cancelled'(手机取消) | 'expired' | 'ok'。
        类型码含义照抄官方登录页 JS：status=True 登录成功；type=4 已扫码待确认；type=6 客户端取消。
        """
        st = self.s.post("%s/getauthstatus/v2" % PASSPORT, timeout=25,
                         data={"enc": self.enc, "uuid": self.uuid,
                               "doubleFactorLogin": "0", "forbidotherlogin": "0"},
                         headers={"X-Requested-With": "XMLHttpRequest"})
        try:
            j = st.json()
        except Exception:
            j = {}
        if j.get("status") is True or j.get("status") == 1:
            self._warmup()
            return {"status": "ok", "raw": j}
        t = j.get("type")
        if t == 4:
            return {"status": "scanned", "raw": j}
        if t == 6:
            return {"status": "cancelled", "raw": j}
        body = st.text
        if "过期" in body or "失效" in body:
            return {"status": "expired", "raw": j}
        return {"status": "waiting", "raw": j}

    # ---------------------------------------------------- 账号密码登录
    def password_login(self, uname, password):
        """学号/手机号 + 密码 登录（复刻官方 fanyalogin）。
        返回 status: 'ok' | 'need_vcode'(需要图形验证码) | '2fa'(双因子) | 'fail'。
        注意：绝不要把 password 写进日志。
        """
        self.s.get(LOGIN_URL, timeout=25)          # 先拿会话 cookie
        data = {
            "fid": "-1",
            "uname": aes_b64(uname),
            "password": aes_b64(password),
            "refer": "http%3A%2F%2Fi.chaoxing.com%2Fbase",
            "t": "true",
            "forbidotherlogin": "0",
            "validate": "",
            "doubleFactorLogin": "0",
            "independentId": "0",
            "independentNameId": "0",
        }
        r = self.s.post("%s/fanyalogin" % PASSPORT, data=data, timeout=25,
                        headers={"X-Requested-With": "XMLHttpRequest",
                                 "Referer": LOGIN_URL})
        try:
            j = r.json()
        except Exception:
            return {"status": "fail", "mes": "服务端返回异常（%s）" % r.status_code, "raw": {}}
        if j.get("status") is True or j.get("status") == 1:
            if j.get("containTwoFactorLogin"):
                return {"status": "2fa", "mes": "需要双因子验证", "raw": j}
            self._warmup()
            return {"status": "ok", "raw": j}
        mes = j.get("mes") or j.get("msg2") or "登录失败"
        if "验证码" in mes or j.get("type") == 1:
            return {"status": "need_vcode", "mes": mes, "raw": j}
        return {"status": "fail", "mes": mes, "raw": j}

    def _warmup(self):
        """登录后访问若干页面，让服务端下发全套 cookie（含 HttpOnly 的 vc3/p_auth_token）。"""
        for u in ("https://i.chaoxing.com/base",
                  "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction"):
            try:
                self.s.get(u, timeout=25)
            except Exception:
                pass

    # ---------------------------------------------------- cookie 存取
    def cookies_dict(self):
        """{name: value} 形式（同名的 route 会按最后写入的域覆盖，够用）。"""
        return {c.name: c.value for c in self.s.cookies}

    def cookies_list(self):
        """带域的 cookie 列表（route 等同名 cookie 需要按域区分）。"""
        return [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
                for c in self.s.cookies]

    def cookie_header(self):
        return "; ".join("%s=%s" % (c.name, c.value) for c in self.s.cookies)

    @classmethod
    def from_cookies(cls, cookies):
        """cookies 可以是 {name: value}（视为 .chaoxing.com），
        也可以是 [{'name','value','domain','path'}] 列表。"""
        c = cls()
        if isinstance(cookies, dict):
            for k, v in cookies.items():
                c.s.cookies.set(k, v, domain=".chaoxing.com")
        else:
            for it in cookies:
                c.s.cookies.set(it["name"], it["value"],
                                domain=it.get("domain", ".chaoxing.com"),
                                path=it.get("path", "/"))
        return c

    # ---------------------------------------------------- 课程 / 章节 / 任务点
    def get_courses(self):
        body = ("courseType=1&courseFolderId=0&query=&pageHeader=-1&single=1"
                "&superstarClass=0&isFirefly=0&fid=&from=")
        r = self.s.post("https://mooc2-ans.chaoxing.com/mooc2-ans/visit/courselistdata",
                        data=body, timeout=25,
                        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                                 "X-Requested-With": "XMLHttpRequest",
                                 "Referer": "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction"})
        out = []
        for m in re.finditer(r'<div class="course clearfix[^"]*"[^>]*info="([^"]*)_([^"]*)"[^>]*id="c_(\d+)"', r.text):
            out.append({"clazzid": m.group(1), "cpi": m.group(2), "courseid": m.group(3)})
        names = re.findall(r'<span class="course-name overHidden2"[^>]*>\s*([^<]+)', r.text)
        for i, n in enumerate(names):
            if i < len(out):
                out[i]["name"] = n.strip()
        return out

    def get_chapters(self, courseid, clazzid, cpi):
        url = ("https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse"
               "?courseid=%s&clazzid=%s&cpi=%s&ut=s&t=%d" % (courseid, clazzid, cpi, int(time.time() * 1000)))
        r = self.s.get(url, timeout=25,
                       headers={"Referer": "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction"})
        out = []
        pat = re.compile(r'<div class="chapter_item" id="cur(\d+)"(.*?)</div>\s*</div>\s*</div>', re.S)
        for m in pat.finditer(r.text):
            kid, body = m.group(1), m.group(2)
            nm = re.search(r'class="catalog_name[^"]*"[^>]*>(.*?)</a>', body, re.S)
            name = re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else ''
            cnt = None
            for tag in re.findall(r'<input[^>]*knowledgeJobCount[^>]*>', body):
                m2 = re.search(r'value="(\d+)"', tag)
                if m2:
                    cnt = m2
                    break
            out.append({"knowledgeid": kid, "name": name,
                        "jobcount": int(cnt.group(1)) if cnt else 0})
        return out

    def get_jobs(self, courseid, clazzid, cpi, knowledgeid):
        url = ("https://mooc1.chaoxing.com/mooc-ans/knowledge/cards?clazzid=%s&courseid=%s"
               "&knowledgeid=%s&num=0&ut=s&cpi=%s&v=2025-0424-1038-3&mooc2=1"
               "&isMicroCourse=false&editorPreview=0" % (clazzid, courseid, knowledgeid, cpi))
        r = self.s.get(url, timeout=25, headers={
            "Referer": "https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=%s&courseId=%s&clazzid=%s&cpi=%s"
                       % (knowledgeid, courseid, clazzid, cpi)})
        m = re.search(r'mArg = (\{.*?\});', r.text, re.S)
        if not m:
            return {"defaults": {}, "attachments": []}
        d = json.loads(m.group(1))
        return {"defaults": d.get("defaults", {}), "attachments": d.get("attachments", [])}

    # ---------------------------------------------------- 视频上报
    def get_video_status(self, objectid):
        """拿 dtoken（上报路径密钥）和时长。"""
        url = "https://mooc1.chaoxing.com/ananas/status/%s?k=&flag=normal&ro=0&_dc=%d" % (
            objectid, int(time.time() * 1000))
        r = self.s.get(url, timeout=25,
                       headers={"Referer": "https://mooc1.chaoxing.com/mycourse/studentstudy"})
        j = r.json()
        return {"dtoken": j.get("dtoken"), "duration": j.get("duration"), "raw": j}

    def report_video(self, defaults, att, courseid, clazzid, userid, cpi,
                     playing_sec, isdrag=3, video_face_capture_enc=None):
        """上报一次视频进度。playing_sec = 当前播放秒数（**秒**，不是毫秒）。"""
        objectid = att.get("objectId")
        jobid = att.get("jobid")
        duration = int(att.get("ends") or att.get("attDuration") or defaults.get("duration") or 0)
        dtoken = defaults.get("_dtoken")
        clip = "0_%d" % duration
        e = enc_video(clazzid, userid, jobid, objectid, playing_sec * 1000, duration * 1000, clip)
        # otherInfo 必须去掉服务端附加的 "&courseId=..." 尾巴：带上会被服务端丢弃（403 或静默忽略）。
        otherinfo = (att.get("otherInfo") or "").split("&")[0]
        if video_face_capture_enc is None:
            video_face_capture_enc = att.get("videoFaceCaptureEnc", "") or ""
        q = {
            "clazzId": clazzid, "playingTime": str(playing_sec), "duration": str(duration),
            "clipTime": clip, "objectId": objectid,
            "otherInfo": otherinfo, "courseId": courseid, "jobid": jobid,
            "userid": userid, "isdrag": str(isdrag), "view": "pc", "enc": e, "rt": "0.9",
            "videoFaceCaptureEnc": video_face_capture_enc, "dtype": "Video",
            "_t": str(int(time.time() * 1000)), "attDuration": str(duration),
            "attDurationEnc": att.get("attDurationEnc", ""), "courseEngineInfo": "false",
        }
        url = "%s/%s" % (defaults.get("reportUrl"), dtoken)
        r = self.s.get(url, params=q, timeout=25, headers={
            "Referer": "https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=%s&courseId=%s&clazzid=%s&cpi=%s"
                       % (defaults.get("knowledgeid"), courseid, clazzid, cpi),
            "X-Requested-With": "XMLHttpRequest"})
        try:
            return {"ok": True, "data": r.json(), "status": r.status_code}
        except Exception:
            return {"ok": False, "status": r.status_code, "text": r.text[:200]}

    # ---------------------------------------------------- 视频弹题（InteractiveQuiz）
    def get_video_quiz(self, courseid, clazzid, cpi, mid):
        """取视频内嵌弹题。返回 [{resourceId, memberinfo, description, options, startTime, answered, ...}]"""
        url = "https://mooc1.chaoxing.com/mooc-ans/richvideo/initdatawithviewerV2"
        r = self.s.get(url, params={"mid": mid, "cpi": cpi, "classid": clazzid,
                                    "courseid": courseid, "_dc": str(int(time.time() * 1000))},
                       timeout=25, headers={
                           "Referer": "https://mooc1.chaoxing.com/ananas/modules/video/index.html",
                           "X-Requested-With": "XMLHttpRequest"})
        try:
            data = r.json()
        except Exception:
            return []
        out = []
        for grp in (data if isinstance(data, list) else []):
            for it in grp.get("datas", []):
                out.append(it)
        return out

    def submit_quiz(self, clazzid, cpi, objectid, eventid, memberinfo, answer):
        """提交一道弹题。answer = 选项 name 的逗号串，如 "B" 或 "A,C"。

        关键：**答错时服务端也会回传 rightContent（正确答案）**，所以可以先随便答一次再纠正。
        """
        r = self.s.get("https://mooc1.chaoxing.com/question/quiz-validation",
                       params={"classid": clazzid, "cpi": cpi, "objectid": objectid,
                               "eventid": eventid, "memberinfo": memberinfo,
                               "answerContent": answer},
                       timeout=25, headers={
                           "Referer": "https://mooc1.chaoxing.com/ananas/modules/video/index.html",
                           "X-Requested-With": "XMLHttpRequest"})
        try:
            return r.json()
        except Exception:
            return {"status": False, "raw": r.text[:200]}

    def answer_quiz(self, courseid, clazzid, cpi, objectid, mid, log=None):
        """自动答完一门视频的所有弹题（先试第一个选项，用 rightContent 纠错）。"""
        done = []
        for q in self.get_video_quiz(courseid, clazzid, cpi, mid):
            if not q.get("options"):
                continue
            if str(q.get("answered")).lower() == "true":
                done.append({"eventid": q.get("resourceId"), "ok": True, "already": True})
                continue
            guess = q["options"][0]["name"]
            res = self.submit_quiz(clazzid, cpi, objectid, q["resourceId"], q["memberinfo"], guess)
            if not res.get("isRight"):
                right = res.get("rightContent") or ""
                if right:
                    res = self.submit_quiz(clazzid, cpi, objectid, q["resourceId"], q["memberinfo"], right)
            ok = bool(res.get("isRight"))
            done.append({"eventid": q.get("resourceId"), "ok": ok, "answer": res.get("rightContent"),
                         "desc": (q.get("description") or "")[:60], "at": q.get("startTime")})
            if log:
                log("弹题 %s @%ss -> %s" % (done[-1]["desc"], q.get("startTime"), "通过" if ok else "失败"))
        return done
