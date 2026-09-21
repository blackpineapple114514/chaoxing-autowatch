# -*- coding: utf-8 -*-
"""
学习通刷课 App —— Flask 后端。

启动：  python app.py     然后浏览器打开 http://127.0.0.1:8760
一个进程可服务多人；每个人的登录 cookie 存在各自的服务端会话里。
"""
import io
import os
import sys
import time
import json
import platform
import threading
import uuid as _uuid

# 平台探测：Windows 桌面版走 DPAPI；Android（Chaquopy）走 Java 侧 Keystore。
# CPython 的 Android 构建会提供 sys.getandroidapilevel()，这是最可靠的判据。
IS_ANDROID = hasattr(sys, "getandroidapilevel")
IS_WINDOWS = (not IS_ANDROID) and platform.system() == "Windows"

if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes as _wt

from flask import Flask, request, jsonify, session, send_from_directory, render_template

from cx_client import Chaoxing

# 打包成 exe 后模板被解包到 sys._MEIPASS
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = "chaoxing-autowatch-" + _uuid.uuid4().hex  # 重启后旧会话失效，重新扫码即可

# 学习通登录二维码的真实寿命：官方登录页是 3 秒轮询一次、轮满 50 次就显示"二维码已失效"
# => 150 秒。过期后必须调 refreshQRCode 换一对新的 uuid/enc。
QR_TTL_SECONDS = 150
LOGPATH = os.path.join(os.path.expanduser("~"), "chaoxing-autowatch.log")

# 本机令牌：Android 前台服务（常驻通知的「停止」、进度轮询）不带浏览器会话，
# 用这个令牌才能操作后端。服务只监听 127.0.0.1，但同机其他应用也能连回环，
# 所以令牌必须有（每次启动 Python 都重新生成）。
LOCAL_TOKEN = _uuid.uuid4().hex


def local_token():
    """供 Java 侧（Java 调用）取令牌。"""
    return LOCAL_TOKEN


def alog(msg):
    """把登录/刷新等关键事件写进实体日志文件（打包后也在本机可见）。"""
    try:
        with open(LOGPATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


TPL_DIR = os.path.join(BASE_DIR, "templates")


def _load_index_html():
    """读首页模板。
    桌面/exe：直接读盘。Android(Chaquopy)：源码与数据文件打包在 APK 里，
    文件系统未必认得到，读不到就退回构建期内嵌的副本（sync_python.py 生成）。"""
    try:
        with open(os.path.join(TPL_DIR, "index.html"), "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        alog("template read failed: %s" % e)
    try:
        from ui_html import INDEX_HTML
        alog("template fallback: ui_html")
        return INDEX_HTML
    except Exception as e:
        alog("template fallback failed: %s" % e)
        return ("<!doctype html><meta charset='utf-8'>"
                "<h2 style='font-family:sans-serif'>界面模板缺失</h2>"
                "<pre>templates/index.html 与 ui_html.py 都读不到</pre>")


try:
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(TPL_DIR),
        DictLoader({"index.html": _load_index_html()}),
    ])
except Exception as e:
    alog("jinja loader setup failed: %s" % e)


# ---------------------------------------------------------------- 记住登录（平台加密）
# cookie = 凭据。明文落盘绝不允许。
#   Windows：DPAPI（crypt32）——密文只能被「同一台机器 + 同一个 Windows 用户」解开。
#   Android：Java 侧 Creds（Android Keystore AES/GCM）——密钥在硬件/系统密钥库，拷走文件没用。
CRED_PATH = os.path.join(os.path.expanduser("~"), ".chaoxing-autowatch.cred")

if IS_WINDOWS:

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", _wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(data):
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        return _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    def _dpapi(data, unprotect=False):
        """CryptProtectData / CryptUnprotectData。失败抛 OSError。"""
        src, keep = _blob(data)
        out = _BLOB()
        fn = ctypes.windll.crypt32.CryptUnprotectData if unprotect else ctypes.windll.crypt32.CryptProtectData
        ok = fn(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out))
        if not ok:
            raise OSError("DPAPI %s failed (err %s)" % ("unprotect" if unprotect else "protect",
                                                         ctypes.GetLastError()))
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)


def _android_creds():
    """Android：拿 Java 侧 com.hpp.chaoxingwatch.Creds（Keystore AES/GCM）。不可用返回 None。"""
    try:
        from java import jclass
        return jclass("com.hpp.chaoxingwatch.Creds")
    except Exception as e:
        alog("android creds unavailable: %s" % e)
        return None


def save_creds(u):
    """登录成功后加密落盘。失败不影响使用。"""
    try:
        payload = {"cookies": u["cx"].cookies_list(), "userid": u.get("userid"),
                   "name": u.get("name"), "saved": int(time.time())}
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if IS_WINDOWS:
            with open(CRED_PATH, "wb") as f:
                f.write(_dpapi(raw))
        else:
            C = _android_creds()
            if C is None:
                return
            if not C.save(raw.decode("utf-8")):
                alog("creds save failed (android)")
                return
        alog("creds saved")
    except Exception as e:
        alog("creds save failed: %s" % e)


def has_creds():
    """是否存在可用的已保存凭据（不解密，只看有没有）。"""
    if IS_WINDOWS:
        return os.path.exists(CRED_PATH)
    C = _android_creds()
    try:
        return bool(C is not None and C.has())
    except Exception:
        return False


def load_creds():
    try:
        if IS_WINDOWS:
            if not os.path.exists(CRED_PATH):
                return None
            raw = _dpapi(open(CRED_PATH, "rb").read(), unprotect=True)
        else:
            C = _android_creds()
            if C is None:
                return None
            s = C.load()
            if not s:
                return None
            raw = s.encode("utf-8")
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        alog("creds load failed: %s" % e)
        return None


def drop_creds():
    try:
        if IS_WINDOWS:
            if os.path.exists(CRED_PATH):
                os.remove(CRED_PATH)
        else:
            C = _android_creds()
            if C is not None:
                C.drop()
        alog("creds dropped")
    except Exception:
        pass

USERS = {}          # sid -> {"cx": Chaoxing, "userid": str, "name": str}
JOBS = {}           # sid -> brush job state
LOCK = threading.Lock()


def get_user():
    sid = session.get("sid")
    if not sid or sid not in USERS:
        return None
    return USERS[sid]


def get_job():
    sid = session.get("sid")
    return JOBS.get(sid)


def finish_login(u):
    """登录成功后统一收尾：抬用户信息 + 标已登录 + 立刻拉一次课程做验证。
    整段包 try，任何小毛病都不允许再让登录接口挂掉（曾经因为一个不存在的
    cookies_dict() 把“登录成功”分支摔成 500，界面就一直卡在扫码页）。"""
    try:
        ck = u["cx"].cookies_dict()
        u["userid"] = ck.get("_uid") or ck.get("UID")
        u["name"] = (ck.get("uname", "") or "").strip('"') or u["userid"]
    except Exception as e:
        alog("finish_login cookie read failed: %s" % e)
        u["userid"] = u.get("userid") or "?"
    u["logged_in"] = True
    alog("login OK userid=%s name=%s" % (u.get("userid"), u.get("name")))
    try:
        cs = u["cx"].get_courses()
        u["verify"] = len(cs)
        alog("verify OK courses=%d %s" % (len(cs), [c.get("name") for c in cs][:4]))
    except Exception as e:
        u["verify"] = -1
        alog("verify FAILED: %s" % e)
    save_creds(u)          # 记住登录（DPAPI 加密落盘），下次开应用免扫码
    return u.get("userid")


@app.post("/api/login/auto")
def api_login_auto():
    """用上次保存的凭据自动登录。失败（过期/换机器/换 Windows 用户）就悄悄返回 ok:false。"""
    if not has_creds():
        return jsonify({"ok": False, "reason": "no_creds"})
    saved = load_creds()
    if not saved:
        return jsonify({"ok": False, "reason": "undecryptable"})
    try:
        cx = Chaoxing.from_cookies(saved.get("cookies") or [])
        cs = cx.get_courses()
        if not cs:
            raise RuntimeError("cookies 已失效")
    except Exception as e:
        alog("auto login failed: %s" % e)
        drop_creds()          # 失效凭据立刻清掉，不留垃圾
        return jsonify({"ok": False, "reason": "expired"})
    sid = _uuid.uuid4().hex
    session["sid"] = sid
    u = {"cx": cx, "userid": saved.get("userid"), "name": saved.get("name"),
         "qr_born": 0, "last_state": "auto"}
    USERS[sid] = u
    finish_login(u)
    alog("auto login OK userid=%s" % u.get("userid"))
    return jsonify({"ok": True, "userid": u.get("userid"), "name": u.get("name"),
                    "courses": len(cs)})


# ---------------------------------------------------------------- 登录
@app.post("/api/login/qr")
def api_login_qr():
    cx = Chaoxing()
    info = cx.start_qr()
    sid = _uuid.uuid4().hex
    session["sid"] = sid
    USERS[sid] = {"cx": cx, "userid": None, "name": None, "qr_born": time.time(),
                  "uuid": info["uuid"], "last_state": None}
    alog("qr issued uuid=%s" % info["uuid"])
    return jsonify({"ok": True, "ttl": QR_TTL_SECONDS,
                    "qr": "data:%s;base64,%s" % (info["content_type"],
                                                 __import__("base64").b64encode(info["qr"]).decode())})


@app.post("/api/login/refresh")
def api_login_refresh():
    u = get_user()
    if not u:
        return jsonify({"ok": False, "error": "no session"}), 400
    # 登录成功后不再换码（那个码已经被消费，换了也没意义，还会把界面拨回扫码页）
    if u.get("logged_in"):
        return jsonify({"ok": False, "error": "已登录，无需换码"}), 400
    try:
        info = u["cx"].refresh_qr()
    except Exception as e:
        alog("qr refresh FAILED: %s" % e)
        return jsonify({"ok": False, "error": str(e)}), 500
    u["qr_born"] = time.time()
    u["uuid"] = info["uuid"]
    u["last_state"] = None
    alog("qr rotated uuid=%s" % info["uuid"])
    import base64
    return jsonify({"ok": True, "ttl": QR_TTL_SECONDS,
                    "qr": "data:%s;base64,%s" % (info["content_type"],
                                                 base64.b64encode(info["qr"]).decode())})


@app.post("/api/login/password")
def api_login_password():
    """学号/手机号 + 密码登录。密码只在内存里过一手，绝不写日志、不回显。"""
    body = request.get_json(silent=True) or {}
    uname = (body.get("uname") or "").strip()
    pwd = body.get("password") or ""
    if not uname or not pwd:
        return jsonify({"ok": False, "error": "账号和密码都要填"}), 400
    cx = Chaoxing()
    try:
        res = cx.password_login(uname, pwd)
    except Exception as e:
        alog("password login EXCEPTION uname=%s: %s" % (uname, e))
        return jsonify({"ok": False, "error": "请求异常：%s" % e}), 500
    alog("password login uname=%s -> %s (mes=%s)" % (uname, res["status"], res.get("mes")))
    if res["status"] != "ok":
        return jsonify({"ok": False, "status": res["status"],
                        "error": res.get("mes") or res["status"]})
    sid = _uuid.uuid4().hex
    session["sid"] = sid
    USERS[sid] = {"cx": cx, "userid": None, "name": None, "qr_born": time.time(),
                  "uuid": None, "last_state": None}
    finish_login(USERS[sid])
    u = USERS[sid]
    return jsonify({"ok": True, "userid": u.get("userid"), "name": u.get("name"),
                    "verify": u.get("verify")})


@app.get("/api/login/status")
def api_login_status():
    u = get_user()
    if not u:
        return jsonify({"ok": False, "error": "no session"}), 400
    # 已登录就直接返回，绝不再去问状态：扫码成功后那个码已被服务端消费，
    # 再问只会回"已失效"，前端就会把界面拨回扫码页（曾经的真凶）。
    if u.get("logged_in"):
        return jsonify({"ok": True, "status": "ok", "userid": u.get("userid"),
                        "name": u.get("name"), "verify": u.get("verify"),
                        "left": QR_TTL_SECONDS})
    res = u["cx"].poll_login()
    raw = res.get("raw") or {}
    # 扫码那一步（type=4）服务端会把昵称一起发下来，顺手存下，界面显示真名而不是 uid
    if raw.get("nickname"):
        u["name"] = raw["nickname"]
    # 每一次状态跳变都写日志（type/mes 都记），下次扫码失败能一眼看出卡在哪一步
    key = (res["status"], str(raw.get("type")), str(raw.get("mes")))
    if key != u.get("last_state"):
        u["last_state"] = key
        alog("state %s uuid=%s raw=%s" % (res["status"], u.get("uuid"), json.dumps(raw, ensure_ascii=False)[:200]))
    if res["status"] == "ok":
        finish_login(u)
    return jsonify({"ok": True, "status": res["status"],
                    "type": raw.get("type"), "mes": raw.get("mes"),
                    "uuid": u.get("uuid"),
                    "left": max(0, int(QR_TTL_SECONDS - (time.time() - u.get("qr_born", 0))))})


@app.get("/api/me")
def api_me():
    u = get_user()
    if not u:
        return jsonify({"ok": False, "logged_in": False})
    return jsonify({"ok": True, "logged_in": u["userid"] is not None,
                    "userid": u["userid"], "name": u["name"]})


# ---------------------------------------------------------------- 课程
@app.get("/api/courses")
def api_courses():
    u = get_user()
    if not u or not u["userid"]:
        return jsonify({"ok": False, "error": "未登录"}), 401
    try:
        return jsonify({"ok": True, "courses": u["cx"].get_courses()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/api/chapters")
def api_chapters():
    u = get_user()
    if not u or not u["userid"]:
        return jsonify({"ok": False, "error": "未登录"}), 401
    courseid = request.args.get("courseid")
    clazzid = request.args.get("clazzid")
    cpi = request.args.get("cpi")
    try:
        chs = u["cx"].get_chapters(courseid, clazzid, cpi)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    # 自动识别「哪些章节含视频任务点」（只读）：给每个章节补 videos = 视频任务点数量
    #   videos = 0  -> 无视频，刷课时会跳过（前端置灰）
    #   videos = None -> 识别失败，当作“不确定”，仍允许勾选
    def _count_videos(ch):
        try:
            jobs = u["cx"].get_jobs(courseid, clazzid, cpi, ch["knowledgeid"])
            vids = [a for a in jobs.get("attachments", []) if a.get("type") == "video"]
            return {"videos": len(vids),
                    "videos_done": sum(1 for a in vids if a.get("isPassed")),
                    "videos_sec": sum(int(a.get("ends") or 0) for a in vids)}
        except Exception:
            return None

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as ex:
            counts = list(ex.map(_count_videos, chs))
        for ch, n in zip(chs, counts):
            if n is None:
                ch["videos"] = ch["videos_done"] = None
                ch["videos_sec"] = 0
            else:
                ch.update(n)
    except Exception:
        for ch in chs:
            ch.setdefault("videos", None)
            ch.setdefault("videos_done", None)
    return jsonify({"ok": True, "chapters": chs})


# ---------------------------------------------------------------- 刷课
def _mmss(sec):
    sec = int(sec or 0)
    return "%02d:%02d" % (sec // 60, sec % 60)


def _sleep_cancelable(st, secs):
    """可打断的等待：每 0.4 秒看一眼停止标志，点了“停止”立即生效（原来 sleep(30) 要等满 30 秒）。"""
    end = time.time() + max(0.0, float(secs))
    while True:
        if st.get("cancel"):
            raise KeyboardInterrupt
        left = end - time.time()
        if left <= 0:
            return
        time.sleep(min(0.4, left))


def _brush_worker(sid, tasks, opts):
    """tasks: [{courseid, clazzid, cpi, name, chapters:[{knowledgeid,name}|None]}]

    分两阶段：
      一、统计（planning）—— 只读不写，把章节/任务点列出来，得到总视频数；
      二、上报（brushing）—— 逐个视频按时间轴上报。
    这样界面一开始就有"共 N 个视频"，进度条才有分母。
    """
    st = JOBS[sid]
    u = USERS[sid]
    cx = u["cx"]
    userid = u["userid"]
    delay = float(opts.get("delay", 0) or 0)
    step = int(opts.get("step", 30) or 30)
    if step < 5:
        step = 30
    skip_done = bool(opts.get("skip_done", True))
    # 服务端有“不得快于实时”的限速：上报间隔必须 ≥ 视频推进秒数，否则静默丢弃
    if delay < step:
        delay = float(step)

    try:
        # ---------------- 阶段一：统计
        st["phase"] = "planning"
        st["courses_total"] = len(tasks)
        plan = []
        for ci, t in enumerate(tasks, 1):
            if st["cancel"]:
                raise KeyboardInterrupt
            st["current_course"] = t.get("name") or t["courseid"]
            st["courses_index"] = ci
            try:
                chapters = t.get("chapters") or cx.get_chapters(t["courseid"], t["clazzid"], t["cpi"])
            except Exception as e:
                st["errors"].append("取章节失败 %s: %s" % (st["current_course"], e))
                st["courses_done"] = ci
                continue
            st["chapters_total"] += len(chapters)
            for ch in chapters:
                if st["cancel"]:
                    raise KeyboardInterrupt
                st["current_chapter"] = ch.get("name") or ch["knowledgeid"]
                try:
                    jobs = cx.get_jobs(t["courseid"], t["clazzid"], t["cpi"], ch["knowledgeid"])
                except Exception as e:
                    st["errors"].append("%s: 取任务点失败 %s" % (st["current_chapter"], e))
                    st["chapters_done"] += 1
                    continue
                defaults = jobs.get("defaults", {})
                for att in jobs.get("attachments", []):
                    if att.get("type") != "video":
                        continue
                    plan.append((t, ch, att, defaults))
                    st["videos_total"] += 1
                st["chapters_done"] += 1
            st["courses_done"] = ci
        st["phase"] = "brushing"
        st["last"] = "统计完毕：共 %d 个视频任务点" % len(plan)
        # 已完成 / 预计剩余时间：跳过已完成的视频不计入 ETA
        done_idx = set()
        for i, (_t, _c, a, _d) in enumerate(plan):
            if a.get("isPassed"):
                done_idx.add(i)
        st["done_total"] = len(done_idx)
        st["skip_done"] = bool(skip_done)
        durs = [int(a.get("ends") or 0) for (_t, _c, a, _d) in plan]
        suf = [0] * (len(durs) + 1)
        for i in range(len(durs) - 1, -1, -1):
            suf[i] = suf[i + 1] + (0 if (skip_done and i in done_idx) else durs[i])
        st["suffix"] = suf
        st["eta_sec"] = suf[0] if suf else 0
        if st["done_total"]:
            st["last"] = ("统计完毕：共 %d 个视频，其中 %d 个已完成"
                          % (len(plan), st["done_total"]))

        def _brush_one(t, ch, att, defaults, prog=None, attempt_round=1):
            """刷一个视频。返回 True=成功，False=失败（交给重刷）。

            单次上报失败会**原地重试 3 次**（网络抖动不再直接丢掉这个视频）。
            """
            objectid = att.get("objectId")
            name = att.get("property", {}).get("name") or objectid
            st["current_video"] = name
            try:
                vs = cx.get_video_status(objectid)
            except Exception as e:
                st["errors"].append("dtoken 失败 %s: %s" % (name, e))
                return False
            defaults["_dtoken"] = vs.get("dtoken")
            duration = int(att.get("ends") or vs.get("duration") or 0)
            start_ms = int(att.get("headOffset") or att.get("playTime") or 0)
            st["cur_dur"] = duration
            st["cur_pos"] = max(0, start_ms // 1000)

            # 跳过已完成（默认开）：服务端已判通过的视频不再浪费时间重刷
            if skip_done and att.get("isPassed"):
                st["skipped"] += 1
                st["last"] = "跳过已完成：%s" % name
                return True

            t_cur = st["cur_pos"]
            idx = prog[0] if prog else 0
            total = prog[1] if prog else 0

            # 视频内嵌弹题（InteractiveQuiz）：必须在该秒数前答对，否则进度过不去。
            # 答错时服务端会回传 rightContent（正确答案），所以“先试第一个选项再纠正”即可。
            quizzes = []
            try:
                for q in cx.get_video_quiz(t["courseid"], t["clazzid"], t["cpi"], att.get("mid")):
                    if q.get("options") and str(q.get("answered")).lower() != "true":
                        q["_done"] = False
                        quizzes.append(q)
                quizzes.sort(key=lambda x: float(x.get("startTime") or 0))
            except Exception as e:
                st["errors"].append("取弹题失败 %s: %s" % (name, e))

            def _answer(q, _oid=objectid):
                try:
                    res = cx.submit_quiz(t["clazzid"], t["cpi"], _oid, q["resourceId"],
                                         q["memberinfo"], q["options"][0]["name"])
                    if not res.get("isRight") and res.get("rightContent"):
                        res = cx.submit_quiz(t["clazzid"], t["cpi"], _oid, q["resourceId"],
                                             q["memberinfo"], res["rightContent"])
                except Exception as e:
                    st["errors"].append("弹题提交异常 %s" % e)
                    return False
                q["_done"] = bool(res.get("isRight"))
                st["quiz_total"] = st.get("quiz_total", 0) + 1
                if q["_done"]:
                    st["quiz_done"] = st.get("quiz_done", 0) + 1
                return q["_done"]

            while t_cur < duration:
                if st["cancel"]:
                    raise KeyboardInterrupt
                t_cur = min(duration, t_cur + step)
                for q in quizzes:
                    if not q["_done"] and t_cur >= float(q.get("startTime") or 0):
                        _answer(q)
                res = None
                for k in range(3):                      # 单条上报重试 3 次
                    try:
                        res = cx.report_video(defaults, att, t["courseid"], t["clazzid"],
                                              userid, t["cpi"], t_cur, isdrag=3)
                    except Exception as e:
                        res = None
                        st["errors"].append("上报异常(第%d次) %s: %s" % (k + 1, name, e))
                    if res and res.get("ok"):
                        break
                    if st["cancel"]:
                        raise KeyboardInterrupt
                    if k < 2:
                        _sleep_cancelable(st, 2.0)
                if not (res and res.get("ok")):
                    st["errors"].append("上报失败(重试3次) %s pt=%s: %s"
                                        % (name, t_cur, (res or {}).get("text", "")))
                    return False
                st["reports"] += 1
                st["cur_pos"] = t_cur
                if prog:
                    _suf = st.get("suffix") or []
                    if 0 <= idx - 1 < len(_suf):
                        st["eta_sec"] = max(0, _suf[idx - 1] - t_cur)
                    if duration and total:
                        frac = min(1.0, t_cur / float(duration))
                        st["percent"] = int(((idx - 1 + frac) / float(total)) * 100)
                st["last"] = "%s%s  %s / %s" % ("[重刷]" if attempt_round > 1 else "",
                                                name, _mmss(t_cur), _mmss(duration))
                _sleep_cancelable(st, delay)

            # 收尾：回读服务端是否真的判定“已完成”
            try:
                j2 = cx.get_jobs(t["courseid"], t["clazzid"], t["cpi"], ch["knowledgeid"])
                for a2 in j2.get("attachments", []):
                    if a2.get("objectId") == objectid:
                        att["isPassed"] = a2.get("isPassed")
                        if a2.get("isPassed"):
                            st["passed"] = st.get("passed", 0) + 1
            except Exception:
                pass
            return True

        # ---------------- 阶段二：逐个上报
        total = len(plan)
        failed = []
        for idx, (t, ch, att, defaults) in enumerate(plan, 1):
            if st["cancel"]:
                raise KeyboardInterrupt
            st["current_course"] = t.get("name") or t["courseid"]
            st["current_chapter"] = ch.get("name") or ch["knowledgeid"]
            st["videos_index"] = idx
            st["videos_total"] = total
            if _brush_one(t, ch, att, defaults, prog=(idx, total), attempt_round=1):
                st["videos_done"] += 1
            else:
                failed.append((t, ch, att, defaults))
            st["failed"] = len(failed)
            st["percent"] = int((idx / float(max(1, total))) * 100)

        # ---------------- 阶段三：失败清单重刷一轮
        if failed and not st["cancel"]:
            st["phase"] = "retrying"
            st["last"] = "有 %d 个视频没刷成，正在重刷…" % len(failed)
            for ri, (t, ch, att, defaults) in enumerate(list(failed), 1):
                if st["cancel"]:
                    raise KeyboardInterrupt
                st["current_course"] = t.get("name") or t["courseid"]
                st["current_chapter"] = ch.get("name") or ch["knowledgeid"]
                st["retry_index"] = ri
                st["retry_total"] = len(failed)
                if _brush_one(t, ch, att, defaults, prog=None, attempt_round=2):
                    st["videos_done"] += 1
                    if (t, ch, att, defaults) in failed:
                        failed.remove((t, ch, att, defaults))
                st["failed"] = len(failed)
    except KeyboardInterrupt:
        st["phase"] = "cancelled"
        st["state"] = "cancelled"
        st["last"] = "已停止（停在第 %s/%s 个视频）" % (st.get("videos_index") or 0, st.get("videos_total") or 0)
        return
    except Exception as e:
        st["errors"].append("任务级错误: %s" % e)
    st["phase"] = "done"
    st["state"] = "done"
    st["percent"] = 100
    if not st.get("videos_total"):
        st["last"] = "没有找到视频任务点（可能是作业/测验类，暂不支持）"
    elif st.get("failed"):
        st["last"] = ("部分完成：成功 %d 个，仍有 %d 个没刷成（见错误列表），共上报 %d 次"
                      % (st["videos_done"], st["failed"], st["reports"]))
    else:
        st["last"] = "全部完成：%d 个视频，共上报 %d 次" % (st["videos_done"], st["reports"])


@app.post("/api/brush")
def api_brush():
    u = get_user()
    if not u or not u["userid"]:
        return jsonify({"ok": False, "error": "未登录"}), 401
    sid = session["sid"]
    body = request.get_json(force=True, silent=True) or {}
    tasks = body.get("tasks") or []
    if not tasks:
        return jsonify({"ok": False, "error": "没有选择任何课程/章节"}), 400
    opts = {"step": int(body.get("step", 30) or 30), "delay": float(body.get("delay", 0) or 0),
            "skip_done": bool(body.get("skip_done", True))}
    with LOCK:
        cur = JOBS.get(sid)
        if cur and cur.get("state") == "running":
            return jsonify({"ok": False, "error": "已有任务在跑"}), 409
        JOBS[sid] = {"state": "running", "phase": "planning", "cancel": False,
                     "reports": 0, "videos_done": 0, "done_videos": 0,
                     "videos_total": 0, "videos_index": 0,
                     "skipped": 0, "errors": [],
                     "courses_total": 0, "courses_done": 0, "courses_index": 0,
                     "chapters_total": 0, "chapters_done": 0,
                     "cur_pos": 0, "cur_dur": 0, "percent": 0,
                     "quiz_total": 0, "quiz_done": 0, "passed": 0,
                     "eta_sec": None, "suffix": [], "skip_done": True, "done_total": 0,
                     "failed": 0, "retry_index": 0, "retry_total": 0,
                     "current_course": "", "current_chapter": "", "current_video": "",
                     "last": "", "started": time.time()}
    threading.Thread(target=_brush_worker, args=(sid, tasks, opts), daemon=True).start()
    return jsonify({"ok": True})


@app.get("/api/brush/status")
def api_brush_status():
    j = get_job()
    if not j:
        return jsonify({"ok": True, "job": None})
    return jsonify({"ok": True, "job": {k: v for k, v in j.items() if k != "cancel"}})


@app.route("/api/brush/cancel", methods=["POST", "GET"])
def api_brush_cancel():
    # 本机令牌通道（Android 常驻通知的「停止刷课」）：停掉所有任务
    tok = request.args.get("token") or (request.get_json(silent=True) or {}).get("token")
    if tok and tok == LOCAL_TOKEN:
        for j in JOBS.values():
            j["cancel"] = True
        return jsonify({"ok": True, "stopped": len(JOBS)})
    j = get_job()
    if j:
        j["cancel"] = True
    return jsonify({"ok": True})


@app.get("/api/brush/status_all")
def api_brush_status_all():
    """本机令牌通道：不带浏览器会话也能读任务状态（单用户场景取唯一任务）。"""
    if (request.args.get("token") or "") != LOCAL_TOKEN:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    j = next(iter(JOBS.values()), None)
    if not j:
        return jsonify({"ok": True, "job": None})
    return jsonify({"ok": True, "job": {k: v for k, v in j.items() if k != "cancel"}})


@app.post("/api/logout")
def api_logout():
    sid = session.get("sid")
    if sid in USERS:
        del USERS[sid]
    if sid in JOBS:
        JOBS[sid]["cancel"] = True
        del JOBS[sid]
    session.clear()
    drop_creds()          # 退出 = 同时忘掉保存的登录
    return jsonify({"ok": True})


# ---------------------------------------------------------------- 页面
@app.get("/")
def index():
    return render_template("index.html")


def serve(host=None, port=None):
    """给外部启动器（桌面 gui.py / Android MainActivity）调用的入口。
    Android 上只监听回环，不对外暴露。"""
    if host is None:
        host = "127.0.0.1" if IS_ANDROID else "0.0.0.0"
    if port is None:
        port = int(os.environ.get("PORT", "8760"))
    alog("serving at http://%s:%d/" % (host, port))
    app.run(host=host, port=int(port), threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8760"))
    print("学习通自动刷视频 v1.0 (by hpp) -> http://127.0.0.1:%d" % port)
    serve(port=port)
