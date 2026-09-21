package com.hpp.chaoxingwatch;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** 常驻通知上的「停止刷课」按钮：打本机令牌接口停任务。 */
public class StopReceiver extends BroadcastReceiver {

    public static final String ACTION = "com.hpp.chaoxingwatch.STOP";

    @Override
    public void onReceive(Context context, Intent intent) {
        final Context app = context.getApplicationContext();
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    Http.get("http://127.0.0.1:" + Server.PORT + "/api/brush/cancel?token=" + Server.token, 6000);
                } catch (Throwable ignored) {
                    // 后端不在了就算了
                }
            }
        });
        t.setDaemon(true);
        t.start();
    }
}
