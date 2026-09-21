# -*- coding: utf-8 -*-
"""
学习通自动刷视频 v1.0 (by hpp) —— 桌面版启动器。

在后台线程里跑 Flask，再开一个原生窗口（Edge WebView2）加载界面。
窗口不可用时自动回退到系统浏览器。

行为：
  * 单实例 —— 重复双击 exe 不会开出第二个窗口，只会把已在运行的那个抬到前台；
  * 点 X 不退出，收进托盘继续后台刷；托盘图标双击 / 菜单「打开主界面」可召回；
  * 真要退出：托盘右键 → 退出（或在窗口可见时关闭……见下，X 一律进托盘）。

打包：  python build_exe.py      产物 dist/学习通自动刷视频v1.0.exe
"""
import os
import sys
import ctypes
import socket
import threading
import time
import traceback
from ctypes import wintypes

# 打包后模块与模板都在 sys._MEIPASS
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

LOG = os.path.join(os.path.expanduser("~"), "chaoxing-autowatch.log")

TITLE = "学习通自动刷视频 v1.0  ·  hpp"

# ---------------------------------------------------------------- 单实例（纯 ctypes，不依赖 CLR）
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateMutexW.restype = wintypes.HANDLE
_k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_k32.CreateEventW.restype = wintypes.HANDLE
_k32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_k32.OpenEventW.restype = wintypes.HANDLE
_k32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_k32.SetEvent.argtypes = [wintypes.HANDLE]
_k32.SetEvent.restype = wintypes.BOOL
_k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_k32.WaitForSingleObject.restype = wintypes.DWORD
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL

MUTEX_NAME = "Local\\ChaoxingAutoWatch_v1"
SHOW_EVENT = "Local\\ChaoxingAutoWatch_Show"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
INFINITE = 0xFFFFFFFF

_h_show = None

# GUI 侧句柄（只能由建窗线程碰）
_ui = {"form": None, "wf": None, "tray": None, "ready": False, "really_exit": False}


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_port(port, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.4):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def claim_single_instance():
    """True = 本进程成为主实例；False = 已有实例在跑（已发信号请它浮出窗口），本进程应退出。"""
    global _h_show
    h = _k32.CreateMutexW(None, True, MUTEX_NAME)
    if h and ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        ev = _k32.OpenEventW(EVENT_MODIFY_STATE, False, SHOW_EVENT)
        if ev:
            _k32.SetEvent(ev)
            _k32.CloseHandle(ev)
        return False
    _h_show = _k32.CreateEventW(None, False, False, SHOW_EVENT)
    return True


def watch_show_signal():
    """主实例后台守着：有人再次双击 exe 就把窗口抬出来。"""
    while True:
        try:
            if _k32.WaitForSingleObject(_h_show, INFINITE) == 0:
                log("收到唤起信号（又被点了一次 exe）")
                show_main_window()
        except Exception:
            log("watch_show_signal failed:\n" + traceback.format_exc())
            return


# ---------------------------------------------------------------- 窗口/托盘（全部经 GUI 线程）
def on_ui_thread(fn, *args):
    """把 fn 排到建窗线程上执行。

    铁律：WinForms 控件只能由创建它的线程碰；跨线程直接调 Show/Hide 是同步消息，
    对方没抽消息就永久阻塞（真发生过）。所以一律 Invoke 过去。
    """
    form = _ui.get("form")
    if form is None:
        return False
    try:
        from System import Func, Type
        form.Invoke(Func[Type](lambda: fn(*args)))
        return True
    except Exception:
        log("on_ui_thread failed:\n" + traceback.format_exc())
        return False


def _show_window_ui():
    """（GUI 线程）把窗口从托盘/最小化状态抬到最前。"""
    form = _ui["form"]
    WF = _ui["wf"]
    form.Show()
    if form.WindowState == WF.FormWindowState.Minimized:
        form.WindowState = WF.FormWindowState.Normal
    form.Activate()
    # TopMost 借一下再还，是把它顶到最前的可靠土办法
    form.TopMost = True
    form.TopMost = False


def show_main_window():
    on_ui_thread(_show_window_ui)


def _notify_ui(title, body):
    """（GUI 线程）刷完提醒：托盘气泡；窗口本来就开着才顺手抬到前面。"""
    tray = _ui.get("tray")
    if tray is not None:
        try:
            tray.ShowBalloonTip(6000, title, body, _ui["wf"].ToolTipIcon.Info)
        except Exception:
            pass
    form = _ui["form"]
    if form is not None and form.Visible:
        _show_window_ui()


def _quit_ui():
    """（GUI 线程）真退出：摘掉托盘图标 + 放行关闭。"""
    _ui["really_exit"] = True
    tray = _ui.get("tray")
    if tray is not None:
        try:
            tray.Visible = False
        except Exception:
            pass
    form = _ui["form"]
    if form is not None:
        form.Close()


def _setup_tray_ui():
    """（GUI 线程）建托盘图标，并把「X 关窗」改成收进托盘。"""
    import clr
    clr.AddReference("System.Windows.Forms")
    clr.AddReference("System.Drawing")
    import System.Windows.Forms as WF
    from System.Drawing import Icon, SystemIcons

    form = _ui["form"]
    _ui["wf"] = WF

    def on_form_closing(sender, args):
        # X 按钮 = 收进托盘继续后台刷；只有托盘菜单「退出」才真的关
        if not _ui["really_exit"]:
            args.Cancel = True
            form.Hide()

    form.FormClosing += on_form_closing

    # 图标直接用 exe 自己的（冻结后 sys.executable 就是本 exe）
    ico = None
    try:
        ico = Icon.ExtractAssociatedIcon(sys.executable)
    except Exception:
        ico = None
    if ico is None:
        ico = SystemIcons.Application

    tray = WF.NotifyIcon()
    tray.Icon = ico
    tray.Text = "学习通自动刷视频 v1.0"
    tray.Visible = True

    menu = WF.ContextMenuStrip()
    mi_show = WF.ToolStripMenuItem("打开主界面")
    mi_quit = WF.ToolStripMenuItem("退出")
    mi_show.Click += lambda s, e: _show_window_ui()
    mi_quit.Click += lambda s, e: _quit_ui()
    menu.Items.Add(mi_show)
    menu.Items.Add(WF.ToolStripSeparator())
    menu.Items.Add(mi_quit)
    tray.ContextMenuStrip = menu
    tray.DoubleClick += lambda s, e: _show_window_ui()

    _ui["tray"] = tray
    _ui["ready"] = True
    log("tray ready（X 关窗 = 收进托盘）")


def _post_start():
    """webview.start() 之后在这个线程里跑：拿到 Form，再到 GUI 线程上装托盘。"""
    time.sleep(0.3)
    try:
        import webview
        if not webview.windows:
            log("no window object; tray disabled")
            return
        form = webview.windows[0].native
        _ui["form"] = form
        if form is None:
            log("native form is None; tray disabled")
            return
        on_ui_thread(_setup_tray_ui)
    except Exception:
        log("post_start failed:\n" + traceback.format_exc())


def main():
    if not claim_single_instance():
        log("已有实例在运行，已通知它显示窗口；本进程退出")
        return
    threading.Thread(target=watch_show_signal, daemon=True).start()

    port = int(os.environ.get("CX_PORT") or free_port())
    from app import app

    threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, threaded=True,
                               debug=False, use_reloader=False),
        daemon=True).start()

    url = "http://127.0.0.1:%d/" % port
    if not wait_port(port):
        log("server did not come up on %s" % url)
    log("serving at %s" % url)

    class Api:
        """暴露给页面 JS 的本地接口（window.pywebview.api.*）。

        ⚠️ 句柄必须存成下划线开头的私有名：pywebview 会 dir() 反射 js_api，
        对非可调用属性一路递归（webview/util.py get_functions），遇到原生窗口对象
        就会递归进 .NET 的 AccessibilityObject.Bounds.Empty.Empty... 直到栈溢出，
        表现是窗口出来了但永远不响应（2026-09-21 事故）。下划线前缀会被跳过。
        """
        _window = None

        def notify_done(self, title, body):
            """刷课跑完：托盘气泡 + （窗口开着才）抬到前台。"""
            log("notify: %s | %s" % (title, body))
            try:
                if not on_ui_thread(_notify_ui, title, body) and self._window:
                    self._window.restore()
                    self._window.on_top = True
            except Exception:
                log("notify failed:\n" + traceback.format_exc())
            return True

    api = Api()
    # —— 埋点：20 秒后打一次全部线程栈（只会打这一次，窗口模式下 stderr 是空的必须显式给文件）。
    #    正常启动时它只是几条无害记录；真卡死时这几行就是定位根因的全部依据。
    try:
        import faulthandler
        _fh = open(os.path.join(os.path.expanduser("~"), "chaoxing-stacks.log"),
                   "w", encoding="utf-8", buffering=1)
        faulthandler.dump_traceback_later(20, repeat=False, file=_fh)
        log("faulthandler armed")
    except Exception as e:
        log("faulthandler failed: %r" % (e,))

    try:
        import webview
        log("importing webview ok; creating window")
        api._window = webview.create_window(TITLE, url, width=1020, height=860,
                                            min_size=(760, 620), text_select=True,
                                            confirm_close=False, js_api=api)
        log("window created; calling webview.start()")
        webview.start(_post_start)
        log("window closed")
    except Exception:
        log("native window failed:\n" + traceback.format_exc())
        import webbrowser
        webbrowser.open(url)
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
