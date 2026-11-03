package com.datnt.gtpush

import android.app.Activity
import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject
import java.time.LocalTime
import java.time.format.DateTimeFormatter

class MainViewModel(app: Application) : AndroidViewModel(app) {

    data class UiState(
        val appIdSet: Boolean = BuildConfig.HUAWEI_APP_ID.isNotEmpty(),
        val healthInstalled: Boolean = false,
        val permission: Boolean? = null,
        val deviceName: String? = null,
        val watchApp: String? = null,
        val notifyEnabled: Boolean = true,
        val notificationsAllowed: Boolean = false,
        val healthListening: Boolean = false,
        val busy: Boolean = false,
        val log: List<String> = emptyList(),
    )

    /** Result of one push: Wear Engine (code or error) and the notification fallback. */
    private data class Delivery(val wearCode: Int?, val wearError: String?, val notified: Boolean) {
        val wearOk get() = wearCode == WatchLink.SEND_SUCCESS
        val delivered get() = wearOk || notified
    }

    private val link = WatchLink(app)
    private val notifier = WatchNotifier(app)
    private val wearEngine = Mutex() // one Wear Engine operation at a time (UI and HTTP share it)
    private val timeFormat = DateTimeFormatter.ofPattern("HH:mm:ss") // thread-safe; log() runs on binder/IO threads too

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private val server = PushServer(BuildConfig.HTTP_PORT, ::handleHttp)

    init {
        server.start(viewModelScope) { e -> log("HTTP server lỗi: ${e.message}") }
        log("HTTP server: 127.0.0.1:${BuildConfig.HTTP_PORT} (dùng adb forward)")
        if (BuildConfig.HUAWEI_APP_ID.isEmpty()) {
            log("Chưa có App ID của AppGallery Connect (gtpush.huaweiAppId) — Wear Engine sẽ từ chối")
        }
        // refresh() runs from MainActivity.onResume
    }

    fun refresh() {
        refreshNotificationStatus()
        runOp {
            val health = link.isHealthInstalled()
            _state.update { it.copy(healthInstalled = health) }
            if (!health) {
                log("Chưa cài Huawei Health")
                return@runOp
            }
            val granted = link.hasPermission()
            _state.update { it.copy(permission = granted) }
            if (!granted) {
                log("Chưa cấp quyền Wear Engine — bấm \"Cấp quyền\"")
                return@runOp
            }
            val device = link.connectedDevice()
            _state.update { it.copy(deviceName = device?.name) }
            if (device == null) {
                log("Không thấy đồng hồ nào đang kết nối với Huawei Health")
                return@runOp
            }
            val installed = link.isWatchAppInstalled(device)
            _state.update { it.copy(watchApp = if (installed) "đã cài" else "chưa cài") }
            log("Đồng hồ: ${device.name} (${device.model}), app ${if (installed) "đã cài" else "chưa cài"}")
            if (installed) {
                link.listen(device) { msg -> log("⌚→📱 $msg") }
            }
        }
    }

    fun refreshNotificationStatus() {
        _state.update {
            it.copy(notificationsAllowed = notifier.canPost(), healthListening = notifier.isHealthListening())
        }
    }

    fun setNotifyEnabled(enabled: Boolean) = _state.update { it.copy(notifyEnabled = enabled) }

    fun requestPermission(activity: Activity) = runOp {
        val granted = link.requestPermission(activity)
        log(if (granted) "Đã cấp quyền Wear Engine" else "Quyền Wear Engine bị từ chối")
        _state.update { it.copy(permission = granted) }
        if (granted) refresh()
    }

    fun ping() = runOp {
        val device = link.connectedDevice() ?: error("Không có đồng hồ đang kết nối")
        val code = link.ping(device)
        _state.update { it.copy(watchApp = WatchLink.describePing(code)) }
        log("Ping: $code — ${WatchLink.describePing(code)}")
    }

    fun sendManual(title: String, value: String, sub: String, text: String) {
        val payload = buildPayload(title, value, sub, text)
        if (payload == null) {
            log("Nhập ít nhất một ô")
            return
        }
        val bytes = payloadBytes(payload)
        if (bytes > WatchLink.MAX_PAYLOAD_BYTES) {
            log("Quá dài: $bytes/${WatchLink.MAX_PAYLOAD_BYTES} byte — rút ngắn đoạn văn")
            return
        }
        viewModelScope.launch { deliver(payload, source = "📱") }
    }

    /** JSON the watch understands; text keeps its line breaks. Null when every field is blank. */
    fun buildPayload(title: String, value: String, sub: String, text: String): String? {
        val json = JSONObject()
        if (title.isNotBlank()) json.put("title", title.trim())
        if (value.isNotBlank()) json.put("value", value.trim())
        if (sub.isNotBlank()) json.put("sub", sub.trim())
        if (text.isNotBlank()) json.put("text", text.trim())
        return if (json.length() == 0) null else json.toString()
    }

    fun payloadBytes(payload: String): Int = payload.toByteArray(Charsets.UTF_8).size

    fun clearLog() = _state.update { it.copy(log = emptyList()) }

    // ---- HTTP: GET /status, POST /push ----

    private suspend fun handleHttp(req: PushServer.Request): PushServer.Response {
        if (req.method == "GET" && req.path == "/status") {
            val s = _state.value
            val json = JSONObject()
                .put("appIdSet", s.appIdSet)
                .put("healthInstalled", s.healthInstalled)
                .put("permission", s.permission ?: JSONObject.NULL)
                .put("device", s.deviceName ?: JSONObject.NULL)
                .put("watchApp", s.watchApp ?: JSONObject.NULL)
                .put("notifyEnabled", s.notifyEnabled)
                .put("notificationsAllowed", s.notificationsAllowed)
                .put("healthListening", s.healthListening)
            return PushServer.Response(200, json.toString())
        }
        if (req.method == "POST" && req.path == "/push") {
            val payload = try {
                toPayload(req.body)
            } catch (e: Exception) {
                return PushServer.Response(400, PushServer.errorJson("Body không hợp lệ: ${e.message}"))
            }
            val d = deliver(payload, source = "HTTP")
            val wear = JSONObject().apply {
                d.wearCode?.let { put("code", it).put("ok", d.wearOk) }
                d.wearError?.let { put("ok", false).put("error", it) }
            }
            val json = JSONObject()
                .put("ok", d.delivered)
                .put("wearEngine", wear)
                .put("notification", d.notified)
                .put("payload", payload)
            return PushServer.Response(if (d.delivered) 200 else 502, json.toString())
        }
        return PushServer.Response(404, PushServer.errorJson("Dùng GET /status hoặc POST /push"))
    }

    /**
     * JSON bodies keep only title/value/sub/text (as strings) so the watch always gets the shape it parses;
     * any other body is forwarded as plain text (the watch shows it as a paragraph).
     */
    private fun toPayload(body: String): String {
        val trimmed = body.trim()
        require(trimmed.isNotEmpty()) { "body rỗng" }
        val payload = if (!trimmed.startsWith("{")) {
            trimmed
        } else {
            val input = JSONObject(trimmed)
            val out = JSONObject()
            for (key in PAYLOAD_KEYS) {
                if (input.has(key) && !input.isNull(key)) out.put(key, input.get(key).toString())
            }
            require(out.length() > 0) { "JSON cần ít nhất một trong ${PAYLOAD_KEYS.joinToString()}" }
            out.toString()
        }
        val bytes = payloadBytes(payload)
        require(bytes <= WatchLink.MAX_PAYLOAD_BYTES) {
            "payload $bytes byte > ${WatchLink.MAX_PAYLOAD_BYTES} byte (giới hạn của đồng hồ Lite)"
        }
        return payload
    }

    /** Notification first (instant, no approval needed), then Wear Engine to the watch app. */
    private suspend fun deliver(payload: String, source: String): Delivery {
        var notified = false
        if (_state.value.notifyEnabled) {
            notified = notifier.post(payload)
            log("$source→🔔 ${if (notified) "đã bắn thông báo" else "không bắn được (chưa cho phép thông báo)"}")
        }
        return wearEngine.withLock {
            try {
                val device = link.connectedDevice() ?: error("Không có đồng hồ đang kết nối")
                val code = link.send(device, payload)
                log("$source→⌚ ${if (code == WatchLink.SEND_SUCCESS) "OK" else "mã $code"}: $payload")
                Delivery(wearCode = code, wearError = null, notified = notified)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                val msg = WatchLink.describeError(e)
                log("$source→⌚ lỗi: $msg")
                Delivery(wearCode = null, wearError = msg, notified = notified)
            }
        }
    }

    private fun runOp(block: suspend () -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                wearEngine.withLock { block() }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                log("Lỗi: ${WatchLink.describeError(e)}")
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }

    private fun log(line: String) {
        val stamped = "${LocalTime.now().format(timeFormat)}  $line"
        _state.update { it.copy(log = (listOf(stamped) + it.log).take(MAX_LOG_LINES)) }
    }

    override fun onCleared() {
        server.stop()
        super.onCleared()
    }

    private companion object {
        val PAYLOAD_KEYS = listOf("title", "value", "sub", "text")
        const val MAX_LOG_LINES = 200
    }
}
