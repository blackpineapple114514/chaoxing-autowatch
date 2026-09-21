package com.hpp.chaoxingwatch;

import android.util.Log;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

/**
 * 在后台线程里跑 Flask（复用桌面的 app.py，一行业务代码没动）。
 * <p>
 * local_token 是从 Python 侧取出来的一次性本机令牌：常驻通知上的「停止」按钮、
 * 以及服务轮询进度，都要带这个令牌才能操作后端（服务只监听 127.0.0.1，但同一台
 * 手机上的其他应用也能连本机回环，所以加一道令牌）。
 */
public final class Server {

    public static final int PORT = 8760;
    private static final String TAG = "ChaoxingWatch";

    public static volatile String token = "";
    public static volatile String lastError = "";
    private static volatile boolean started = false;

    private Server() {
    }

    public static synchronized void start(final android.content.Context ctx) {
        if (started) {
            return;
        }
        started = true;
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    PyObject app = Python.getInstance().getModule("app");
                    token = String.valueOf(app.callAttr("local_token"));
                    Log.i(TAG, "flask starting on 127.0.0.1:" + PORT + " token=" + token.substring(0, 6) + "...");
                    app.callAttr("serve", "127.0.0.1", PORT);   // 阻塞
                } catch (Throwable e) {
                    lastError = String.valueOf(e);
                    Log.e(TAG, "flask start failed", e);
                    started = false;
                }
            }
        }, "flask-server");
        t.setDaemon(true);
        t.start();
    }

    /** 轮询 /api/me，起来了返回 true。 */
    public static boolean waitReady(int timeoutMs) {
        long end = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < end) {
            try {
                Http.get("http://127.0.0.1:" + PORT + "/api/me", 2500);
                return true;
            } catch (Throwable ignored) {
                try {
                    Thread.sleep(250);
                } catch (InterruptedException e) {
                    return false;
                }
            }
        }
        return false;
    }
}
