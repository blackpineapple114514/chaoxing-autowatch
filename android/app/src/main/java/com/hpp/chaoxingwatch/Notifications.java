package com.hpp.chaoxingwatch;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.Build;

/** 通知通道与两种通知：常驻的「正在刷课」和跑完的提醒。 */
public final class Notifications {

    public static final String CH_SERVICE = "brush_service";
    public static final String CH_DONE = "brush_done";
    public static final int ID_SERVICE = 1001;
    public static final int ID_DONE = 1002;
    private static final int REQ = 2001;

    private Notifications() {
    }

    public static void createChannels(Context c) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) {
            return;
        }
        NotificationChannel a = new NotificationChannel(CH_SERVICE,
                c.getString(R.string.ch_service), NotificationManager.IMPORTANCE_LOW);
        a.setShowBadge(false);
        a.setSound(null, null);
        a.setVibrationPattern(null);
        NotificationChannel b = new NotificationChannel(CH_DONE,
                c.getString(R.string.ch_done), NotificationManager.IMPORTANCE_HIGH);
        b.enableVibration(true);
        nm.createNotificationChannel(a);
        nm.createNotificationChannel(b);
    }

    private static Notification.Builder builder(Context c, String ch) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            return new Notification.Builder(c, ch);
        }
        return new Notification.Builder(c);
    }

    private static int piFlags() {
        int f = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            f |= PendingIntent.FLAG_IMMUTABLE;
        }
        return f;
    }

    private static PendingIntent openApp(Context c) {
        Intent i = new Intent(c, MainActivity.class);
        i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(c, REQ, i, piFlags());
    }

    /** 常驻通知：带「停止刷课」按钮。 */
    public static Notification service(Context c, String title, String text) {
        Intent stop = new Intent(c, StopReceiver.class).setAction(StopReceiver.ACTION);
        PendingIntent ps = PendingIntent.getBroadcast(c, REQ + 1, stop, piFlags());
        return builder(c, CH_SERVICE)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(openApp(c))
                .addAction(new Notification.Action.Builder(
                        Icon.createWithResource(c, R.drawable.ic_stat), "停止刷课", ps).build())
                .build();
    }

    /** 刷完/停止提醒（有声）。 */
    public static void done(Context c, String title, String body) {
        Notification n = builder(c, CH_DONE)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setContentIntent(openApp(c))
                .build();
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) {
            nm.notify(ID_DONE, n);
        }
    }
}
