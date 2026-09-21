package com.hpp.chaoxingwatch;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.PowerManager;
import android.provider.Settings;
import android.webkit.JavascriptInterface;

/**
 * WebView ⇄ Java 的桥（前端里叫 window.AndroidBridge）。
 * <p>
 * 注意：方法运行在 JavaBridge 线程，不是 UI 线程；涉及窗口/服务操作一律封送到主线程。
 */
public class Bridge {

    private final Activity act;

    public Bridge(Activity a) {
        this.act = a;
    }

    /** 前端用它判断「我是不是在 Android 里」。 */
    @JavascriptInterface
    public boolean isAndroid() {
        return true;
    }

    /** 开始/结束刷课：开刷时拉起前台服务保住进程，跑完就撤。 */
    @JavascriptInterface
    public void setKeepAlive(final boolean on) {
        act.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (on) {
                    BrushService.start(act);
                } else {
                    BrushService.stop(act);
                }
            }
        });
    }

    /** 刷完提醒（对应桌面的 js_api.notify_done）。 */
    @JavascriptInterface
    public void notifyDone(final String title, final String body) {
        act.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                Notifications.done(act,
                        title == null || title.isEmpty() ? "刷课完成" : title,
                        body == null ? "" : body);
            }
        });
    }

    @JavascriptInterface
    public boolean isIgnoringBatteryOptimizations() {
        try {
            PowerManager pm = (PowerManager) act.getSystemService(Activity.POWER_SERVICE);
            return pm != null && pm.isIgnoringBatteryOptimizations(act.getPackageName());
        } catch (Throwable t) {
            return false;
        }
    }

    @JavascriptInterface
    public void requestIgnoreBatteryOptimizations() {
        act.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    Intent i = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                    i.setData(Uri.parse("package:" + act.getPackageName()));
                    act.startActivity(i);
                } catch (Throwable t) {
                    try {
                        act.startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
                    } catch (Throwable ignored) {
                        // 厂商 ROM 可能两者都拦，那就只剩手动路径了
                    }
                }
            }
        });
    }

    /** 跳到本应用的系统详情页（国产 ROM 的自启动/后台管理入口都在这里）。 */
    @JavascriptInterface
    public void openAppSettings() {
        act.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                    i.setData(Uri.parse("package:" + act.getPackageName()));
                    act.startActivity(i);
                } catch (Throwable ignored) {
                    // 忽略
                }
            }
        });
    }
}
