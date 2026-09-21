package com.hpp.chaoxingwatch;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.PowerManager;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 刷课期间的前台服务 —— 抗系统杀后台的主力。
 * <p>
 * 三重保险：
 * 1) 前台服务 + 常驻通知（系统不会随便收走带前台服务的进程）
 * 2) PARTIAL_WAKE_LOCK（熄屏后 CPU 继续跑，否则夜间滴灌会停摆）
 * 3) WIFI_LOCK（不让 WiFi 在休眠时掉线）
 * <p>
 * 另外它每 5 秒查一次后端任务状态，把进度写进通知；任务结束就自动收工，
 * 免得刷完了还一直占着 WakeLock 耗电。
 */
public class BrushService extends Service {

    public static final String ACTION_START = "com.hpp.chaoxingwatch.SVC_START";
    public static final String ACTION_STOP = "com.hpp.chaoxingwatch.SVC_STOP";

    private static final long WAKE_CAP_MS = 12L * 60 * 60 * 1000;   // 12 小时上限，防意外长占
    private static final int FAIL_LIMIT = 36;       // 连续 36 次(约 3 分钟)读不到后端就收工，别白占 WakeLock

    private static final Pattern P_PHASE = Pattern.compile("\"phase\"\\s*:\\s*\"([^\"]*)\"");
    private static final Pattern P_PERCENT = Pattern.compile("\"percent\"\\s*:\\s*([0-9.]+)");
    private static final Pattern P_INDEX = Pattern.compile("\"videos_index\"\\s*:\\s*([0-9]+)");
    private static final Pattern P_TOTAL = Pattern.compile("\"videos_total\"\\s*:\\s*([0-9]+)");
    private static final Pattern P_POS = Pattern.compile("\"cur_pos\"\\s*:\\s*([0-9.]+)");
    private static final Pattern P_DUR = Pattern.compile("\"cur_dur\"\\s*:\\s*([0-9.]+)");
    private static final Pattern P_NAME = Pattern.compile("\"current_video\"\\s*:\\s*\"([^\"]*)\"");

    private PowerManager.WakeLock wake;
    private WifiManager.WifiLock wifi;
    // 轮询必须放在自己的线程上。主线程发 HTTP 会直接抛 NetworkOnMainThreadException，
    // 而且会被下面的 catch 吞掉 —— 表症是「通知进度永远不动 + 服务永不自停」(2026-09-21 实测踩过)。
    private HandlerThread poller;
    private Handler handler;
    private boolean polling;
    private boolean sawRunning;
    private int readFails;

    public static void start(Context c) {
        Intent i = new Intent(c, BrushService.class).setAction(ACTION_START);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                c.startForegroundService(i);
            } else {
                c.startService(i);
            }
        } catch (Throwable ignored) {
            // Android 12+ 从后景启动前台服务会被拒（ForegroundServiceStartNotAllowedException）。
            // 正常流程是用户在前台点按钮，不会走到这里；但兜住异常，不能让 UI 线程崩。
        }
    }

    public static void stop(Context c) {
        Intent i = new Intent(c, BrushService.class).setAction(ACTION_STOP);
        try {
            c.startService(i);
        } catch (Throwable ignored) {
            // 忽略
        }
    }

    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            try {
                check();
            } catch (Throwable ignored) {
                // 单次失败不打断轮询
            }
            if (polling && handler != null) {
                handler.postDelayed(this, 5000);
            }
        }
    };

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? null : intent.getAction();
        if (ACTION_STOP.equals(action)) {
            finish("刷课已停止", "后台保活已撤下。");
            return START_NOT_STICKY;
        }

        acquire();
        try {
            startForeground(Notifications.ID_SERVICE,
                    Notifications.service(this, "正在刷课…", "保持后台运行中，别划掉这条通知"));
        } catch (Throwable ignored) {
            // 通知被系统拦（比如通知权限关闭）也不能让服务起不来
        }
        if (!polling) {
            polling = true;
            ensurePoller();
            handler.postDelayed(tick, 3000);
        }
        return START_STICKY;
    }

    /** 建轮询线程（只建一次）。 */
    private void ensurePoller() {
        if (handler == null) {
            poller = new HandlerThread("brush-poll");
            poller.start();
            handler = new Handler(poller.getLooper());
        }
    }

    private void stopPoller() {
        HandlerThread t = poller;
        poller = null;
        handler = null;
        if (t != null) {
            t.quitSafely();
        }
    }

    /** 查一次后端状态，更新通知；任务结束就自停。 */
    private void check() {
        if (Server.token == null || Server.token.isEmpty()) {
            return;
        }
        String body;
        try {
            body = Http.get("http://127.0.0.1:" + Server.PORT
                    + "/api/brush/status_all?token=" + Server.token, 5000);
            readFails = 0;
        } catch (Throwable e) {
            // 后端暂时不可达（比如还在启动），下一轮再说；但一直读不到就别再占着锁了。
            if (++readFails >= FAIL_LIMIT) {
                finish("刷课保活已停止", "连续读不到本机后端状态，已释放后台保活。");
            }
            return;
        }
        String phase = match(P_PHASE, body, "");
        boolean done = body.contains("\"job\":null") || "done".equals(phase)
                || "cancelled".equals(phase) || "error".equals(phase);

        if (done) {
            if (sawRunning) {
                if ("done".equals(phase)) {
                    finish("刷课完成 ✅", "全部任务已跑完，通知可以划掉了。");
                } else {
                    finish("刷课已结束", "任务状态：" + phase);
                }
            } else if (body.contains("\"job\":null")) {
                finish(null, null);      // 服务被系统拉起来了但并没有任务：安静收工
            }
            return;
        }

        sawRunning = true;
        StringBuilder sb = new StringBuilder();
        String name = match(P_NAME, body, "");
        if (!name.isEmpty()) {
            sb.append(name).append("　");
        }
        String idx = match(P_INDEX, body, "0");
        String total = match(P_TOTAL, body, "0");
        String pos = match(P_POS, body, "0");
        String dur = match(P_DUR, body, "0");
        sb.append("第 ").append(idx).append("/").append(total).append(" 个　")
                .append(fmt(pos)).append(" / ").append(fmt(dur));
        try {
            startForeground(Notifications.ID_SERVICE,
                    Notifications.service(this, "正在刷课 " + match(P_PERCENT, body, "0") + "%", sb.toString()));
        } catch (Throwable ignored) {
            // 忽略
        }
    }

    private static String fmt(String sec) {
        try {
            int s = (int) Double.parseDouble(sec);
            return String.format("%d:%02d", s / 60, s % 60);
        } catch (Throwable t) {
            return sec;
        }
    }

    private static String match(Pattern p, String s, String def) {
        Matcher m = p.matcher(s);
        return m.find() ? m.group(1) : def;
    }

    private void acquire() {
        try {
            if (wake == null) {
                PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
                if (pm != null) {
                    wake = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "chaoxingwatch:brush");
                    wake.setReferenceCounted(false);
                }
            }
            if (wake != null && !wake.isHeld()) {
                wake.acquire(WAKE_CAP_MS);
            }
        } catch (Throwable ignored) {
            // 忽略
        }
        try {
            if (wifi == null) {
                WifiManager wm = (WifiManager) getApplicationContext()
                        .getSystemService(Context.WIFI_SERVICE);
                if (wm != null) {
                    int mode = Build.VERSION.SDK_INT >= 29
                            ? WifiManager.WIFI_MODE_FULL_LOW_LATENCY
                            : WifiManager.WIFI_MODE_FULL;
                    wifi = wm.createWifiLock(mode, "chaoxingwatch:wifi");
                    wifi.setReferenceCounted(false);
                }
            }
            if (wifi != null && !wifi.isHeld()) {
                wifi.acquire();
            }
        } catch (Throwable ignored) {
            // 忽略
        }
    }

    private void release() {
        try {
            if (wake != null && wake.isHeld()) {
                wake.release();
            }
        } catch (Throwable ignored) {
            // 忽略
        }
        try {
            if (wifi != null && wifi.isHeld()) {
                wifi.release();
            }
        } catch (Throwable ignored) {
            // 忽略
        }
    }

    /** 收工：可选发一条提醒，然后停前台、释放锁、停服务。 */
    private void finish(String title, String body) {
        polling = false;
        if (handler != null) {
            handler.removeCallbacks(tick);
        }
        stopPoller();
        if (title != null) {
            Notifications.done(this, title, body == null ? "" : body);
        }
        release();
        stopForeground(true);
        stopSelf();
    }

    @Override
    public void onDestroy() {
        stopPoller();
        release();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
