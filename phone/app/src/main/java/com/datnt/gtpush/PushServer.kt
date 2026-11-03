package com.datnt.gtpush

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException

/**
 * Tiny HTTP/1.1 server so the Mac can push data:
 *   adb forward tcp:8765 tcp:8765
 *   curl -X POST localhost:8765/push -d '{"title":"BTC","value":"68,420","sub":"+2.1%"}'
 *
 * Binds to 127.0.0.1 only, so other devices on the Wi-Fi cannot push to the watch;
 * adb forward reaches it over USB.
 */
class PushServer(
    private val port: Int,
    private val handler: suspend (Request) -> Response,
) {
    data class Request(val method: String, val path: String, val body: String)
    data class Response(val status: Int, val json: String)

    private var serverSocket: ServerSocket? = null
    private var job: Job? = null

    fun start(scope: CoroutineScope, onError: (Throwable) -> Unit) {
        if (job?.isActive == true) return
        job = scope.launch(Dispatchers.IO) {
            try {
                ServerSocket().use { ss ->
                    ss.reuseAddress = true
                    ss.bind(InetSocketAddress(InetAddress.getLoopbackAddress(), port))
                    serverSocket = ss
                    while (isActive) {
                        val client = try {
                            ss.accept()
                        } catch (_: SocketException) {
                            break // closed by stop()
                        }
                        launch { client.use { handle(it) } }
                    }
                }
            } catch (e: Exception) {
                onError(e)
            }
        }
    }

    fun stop() {
        runCatching { serverSocket?.close() }
        job?.cancel()
        serverSocket = null
        job = null
    }

    private suspend fun handle(socket: Socket) {
        socket.soTimeout = 5_000
        val input = BufferedInputStream(socket.getInputStream())
        val requestLine = readLine(input) ?: return
        val parts = requestLine.split(' ')
        if (parts.size < 2) return

        var contentLength = 0
        while (true) {
            val line = readLine(input) ?: break
            if (line.isEmpty()) break
            val colon = line.indexOf(':')
            if (colon > 0 && line.substring(0, colon).trim().equals("Content-Length", ignoreCase = true)) {
                contentLength = line.substring(colon + 1).trim().toIntOrNull() ?: 0
            }
        }
        if (contentLength > MAX_BODY_BYTES) {
            write(socket, Response(413, """{"ok":false,"error":"body > $MAX_BODY_BYTES bytes"}"""))
            return
        }

        val body = ByteArray(contentLength)
        var read = 0
        while (read < contentLength) {
            val n = input.read(body, read, contentLength - read)
            if (n < 0) break
            read += n
        }

        val request = Request(
            method = parts[0].uppercase(),
            path = parts[1].substringBefore('?'),
            body = String(body, 0, read, Charsets.UTF_8),
        )
        val response = try {
            handler(request)
        } catch (e: Exception) {
            Response(500, errorJson(e.message ?: e.toString()))
        }
        write(socket, response)
    }

    private fun readLine(input: InputStream): String? {
        val buf = ByteArrayOutputStream()
        while (true) {
            val b = input.read()
            if (b < 0) return if (buf.size() == 0) null else String(buf.toByteArray(), Charsets.UTF_8)
            if (b == '\n'.code) break
            if (b != '\r'.code) buf.write(b)
            if (buf.size() > MAX_LINE_BYTES) return null
        }
        return String(buf.toByteArray(), Charsets.UTF_8)
    }

    private fun write(socket: Socket, response: Response) {
        val bytes = response.json.toByteArray(Charsets.UTF_8)
        val head = buildString {
            append("HTTP/1.1 ${response.status} ${reason(response.status)}\r\n")
            append("Content-Type: application/json; charset=utf-8\r\n")
            append("Content-Length: ${bytes.size}\r\n")
            append("Connection: close\r\n\r\n")
        }
        socket.getOutputStream().apply {
            write(head.toByteArray(Charsets.US_ASCII))
            write(bytes)
            flush()
        }
    }

    private fun reason(status: Int) = when (status) {
        200 -> "OK"
        400 -> "Bad Request"
        404 -> "Not Found"
        413 -> "Payload Too Large"
        502 -> "Bad Gateway"
        503 -> "Service Unavailable"
        else -> "Error"
    }

    companion object {
        private const val MAX_BODY_BYTES = 8 * 1024
        private const val MAX_LINE_BYTES = 8 * 1024

        fun errorJson(message: String): String =
            org.json.JSONObject().put("ok", false).put("error", message).toString()
    }
}
