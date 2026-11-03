package com.datnt.gtpush

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationManagerCompat
import org.json.JSONObject

/**
 * Fallback path that needs no Wear Engine approval: post an ordinary Android notification,
 * and Huawei Health mirrors it to the watch (if AppNote is enabled in Health's notification settings).
 * One fixed notification id: each push replaces the previous one, so the watch only keeps the latest.
 */
class WatchNotifier(private val context: Context) {

    private val manager = context.getSystemService(NotificationManager::class.java)

    init {
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Dữ liệu cho đồng hồ", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "Huawei Health chuyển các thông báo này lên đồng hồ"
            },
        )
    }

    /** False when the user denied POST_NOTIFICATIONS or turned notifications off for the app. */
    fun canPost(): Boolean = manager.areNotificationsEnabled()

    /** Huawei Health can only mirror notifications if it has notification-listener access. */
    fun isHealthListening(): Boolean =
        NotificationManagerCompat.getEnabledListenerPackages(context).contains(WatchLink.HEALTH_PACKAGE)

    /** Posts [payload] (our {"title","value","sub"} JSON or plain text). Returns false if not allowed. */
    @SuppressLint("MissingPermission") // guarded by canPost()
    fun post(payload: String): Boolean {
        if (!canPost()) return false
        val (title, text) = toTitleAndText(payload)
        val openApp = PendingIntent.getActivity(
            context, 0,
            Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = Notification.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setContentIntent(openApp)
            .setAutoCancel(true)
            .build()
        // cancel + notify (not just update): Health treats it as a new notification and pushes it again.
        manager.cancel(NOTIFICATION_ID)
        manager.notify(NOTIFICATION_ID, notification)
        return true
    }

    private fun toTitleAndText(payload: String): Pair<String, String> {
        val json = runCatching { JSONObject(payload) }.getOrNull() ?: return DEFAULT_TITLE to payload
        val title = json.optString("title").ifBlank { DEFAULT_TITLE }
        val card = listOf(json.optString("value"), json.optString("sub"))
            .filter { it.isNotBlank() }
            .joinToString(" · ")
        val text = listOf(card, json.optString("text"))
            .filter { it.isNotBlank() }
            .joinToString("\n")
            .ifBlank { title }
        return title to text
    }

    private companion object {
        const val CHANNEL_ID = "watch_data"
        const val NOTIFICATION_ID = 1
        const val DEFAULT_TITLE = "AppNote"
    }
}
