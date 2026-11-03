package com.datnt.gtpush

import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import com.huawei.hmf.tasks.Task
import com.huawei.wearengine.HiWear
import com.huawei.wearengine.WearEngineException
import com.huawei.wearengine.auth.AuthCallback
import com.huawei.wearengine.auth.Permission
import com.huawei.wearengine.device.Device
import com.huawei.wearengine.p2p.Message
import com.huawei.wearengine.p2p.Receiver
import com.huawei.wearengine.p2p.SendCallback
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Coroutine wrapper over the Wear Engine phone SDK, bound to our single watch app
 * ([BuildConfig.WATCH_PACKAGE] signed with the key behind [BuildConfig.WATCH_FINGERPRINT]).
 * Every call goes phone app -> Huawei Health -> Bluetooth -> watch.
 */
class WatchLink(private val context: Context) {

    private val deviceClient = HiWear.getDeviceClient(context)
    private val p2pClient = HiWear.getP2pClient(context).apply {
        setPeerPkgName(BuildConfig.WATCH_PACKAGE)
        setPeerFingerPrint(BuildConfig.WATCH_FINGERPRINT)
    }
    private var receiver: Receiver? = null

    fun isHealthInstalled(): Boolean = try {
        context.packageManager.getPackageInfo(HEALTH_PACKAGE, 0)
        true
    } catch (_: PackageManager.NameNotFoundException) {
        false
    }

    suspend fun hasPermission(): Boolean =
        HiWear.getAuthClient(context).checkPermission(Permission.DEVICE_MANAGER).await() == true

    /** Opens Huawei Health's authorization screen. Returns true when DEVICE_MANAGER was granted. */
    suspend fun requestPermission(activity: Activity): Boolean = suspendCancellableCoroutine { cont ->
        HiWear.getAuthClient(activity).requestPermission(object : AuthCallback {
            override fun onOk(granted: Array<out Permission>?) {
                if (cont.isActive) {
                    cont.resume(granted.orEmpty().any { it.name == Permission.DEVICE_MANAGER.name })
                }
            }

            override fun onCancel() {
                if (cont.isActive) cont.resume(false)
            }
        }, Permission.DEVICE_MANAGER).addOnFailureListener { e ->
            if (cont.isActive) cont.resumeWithException(e)
        }
    }

    /** First bonded watch that Huawei Health currently has a connection to, or null. */
    suspend fun connectedDevice(): Device? =
        deviceClient.bondedDevices.await().orEmpty().firstOrNull { it.isConnected }

    suspend fun isWatchAppInstalled(device: Device): Boolean =
        p2pClient.isAppInstalled(device, BuildConfig.WATCH_PACKAGE).await() == true

    /** Returns a ping code, see [describePing]. */
    suspend fun ping(device: Device): Int = suspendCancellableCoroutine { cont ->
        p2pClient.ping(device) { code -> if (cont.isActive) cont.resume(code) }
            .addOnFailureListener { e -> if (cont.isActive) cont.resumeWithException(e) }
    }

    /** Sends [text] to the watch app and returns the Wear Engine result code ([SEND_SUCCESS] = delivered). */
    suspend fun send(device: Device, text: String): Int {
        val bytes = text.toByteArray(Charsets.UTF_8)
        require(bytes.size <= MAX_PAYLOAD_BYTES) {
            "Payload ${bytes.size} bytes > $MAX_PAYLOAD_BYTES bytes (giới hạn của đồng hồ Lite)"
        }
        val message = Message.Builder().setPayload(bytes).build()
        return suspendCancellableCoroutine { cont ->
            p2pClient.send(device, message, object : SendCallback {
                override fun onSendResult(resultCode: Int) {
                    if (cont.isActive) cont.resume(resultCode)
                }

                override fun onSendProgress(progress: Long) = Unit
            }).addOnFailureListener { e ->
                if (cont.isActive) cont.resumeWithException(e)
            }
        }
    }

    /** Receives messages the watch app sends with FeatureAbility.sendMsg. */
    suspend fun listen(device: Device, onMessage: (String) -> Unit) {
        stopListening()
        val r = Receiver { message -> message.data?.let { onMessage(String(it, Charsets.UTF_8)) } }
        p2pClient.registerReceiver(device, r).await()
        receiver = r
    }

    suspend fun stopListening() {
        val r = receiver ?: return
        receiver = null
        p2pClient.unregisterReceiver(r).await()
    }

    companion object {
        const val HEALTH_PACKAGE = "com.huawei.health"
        const val MAX_PAYLOAD_BYTES = 1024
        const val SEND_SUCCESS = 207

        fun describePing(code: Int): String = when (code) {
            200 -> "chưa cài app trên đồng hồ"
            201 -> "đã cài, chưa chạy"
            202 -> "đã cài, đang chạy"
            203 -> "lỗi khác"
            else -> "mã $code"
        }

        fun describeError(e: Throwable): String =
            (e as? WearEngineException)?.let { "WearEngine ${it.errorCode}: ${it.message}" }
                ?: (e.message ?: e.toString())
    }
}

/** Awaits a Huawei hmf [Task] without blocking. */
suspend fun <T> Task<T>.await(): T = suspendCancellableCoroutine { cont ->
    addOnCompleteListener { task ->
        if (!cont.isActive) return@addOnCompleteListener
        when {
            task.isCanceled -> cont.cancel()
            task.isSuccessful -> cont.resume(task.result)
            else -> cont.resumeWithException(task.exception ?: IllegalStateException("Wear Engine task failed"))
        }
    }
}
