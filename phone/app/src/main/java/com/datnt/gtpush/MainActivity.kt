package com.datnt.gtpush

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle

class MainActivity : ComponentActivity() {

    private val viewModel: MainViewModel by viewModels()

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { viewModel.refreshNotificationStatus() }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null &&
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        setContent {
            MaterialTheme(colorScheme = if (isSystemInDarkTheme()) darkColorScheme() else lightColorScheme()) {
                Surface(Modifier.fillMaxSize()) {
                    val state by viewModel.state.collectAsStateWithLifecycle()
                    MainScreen(
                        state = state,
                        onRefresh = viewModel::refresh,
                        onRequestPermission = { viewModel.requestPermission(this) },
                        onPing = viewModel::ping,
                        onNotifyChange = viewModel::setNotifyEnabled,
                        payloadBytes = { t, v, s, x -> viewModel.buildPayload(t, v, s, x)?.let(viewModel::payloadBytes) ?: 0 },
                        onSend = viewModel::sendManual,
                        onClearLog = viewModel::clearLog,
                    )
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        viewModel.refresh() // the watch may have connected / the app may have been installed meanwhile
    }
}

@Composable
private fun MainScreen(
    state: MainViewModel.UiState,
    onRefresh: () -> Unit,
    onRequestPermission: () -> Unit,
    onPing: () -> Unit,
    onNotifyChange: (Boolean) -> Unit,
    payloadBytes: (String, String, String, String) -> Int,
    onSend: (String, String, String, String) -> Unit,
    onClearLog: () -> Unit,
) {
    var title by rememberSaveable { mutableStateOf("") }
    var value by rememberSaveable { mutableStateOf("") }
    var sub by rememberSaveable { mutableStateOf("") }
    var text by rememberSaveable { mutableStateOf("") }
    val bytes = payloadBytes(title, value, sub, text)
    val tooLong = bytes > WatchLink.MAX_PAYLOAD_BYTES

    LazyColumn(
        Modifier
            .fillMaxSize()
            .safeDrawingPadding(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("AppNote", style = MaterialTheme.typography.headlineSmall)
            if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 8.dp))
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    StatusRow("App ID (AGC)", state.appIdSet.mark(), if (state.appIdSet) "đã đặt" else "chưa đặt")
                    StatusRow("Huawei Health", state.healthInstalled.mark(), if (state.healthInstalled) "đã cài" else "chưa cài")
                    StatusRow(
                        "Quyền Wear Engine",
                        state.permission?.mark() ?: "…",
                        when (state.permission) { true -> "đã cấp"; false -> "chưa cấp"; null -> "chưa rõ" },
                    )
                    StatusRow("Đồng hồ", (state.deviceName != null).mark(), state.deviceName ?: "không kết nối")
                    StatusRow("App trên đồng hồ", "⌚", state.watchApp ?: "chưa rõ")
                    StatusRow("Cho phép thông báo", state.notificationsAllowed.mark(), if (state.notificationsAllowed) "có" else "không")
                    StatusRow("Health đọc thông báo", state.healthListening.mark(), if (state.healthListening) "có" else "không")
                }
            }
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onRefresh) { Text("Làm mới") }
                OutlinedButton(onClick = onRequestPermission) { Text("Cấp quyền") }
                OutlinedButton(onClick = onPing) { Text("Ping") }
            }
        }

        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Gửi kèm thông báo")
                    Text(
                        "Health chuyển thông báo lên đồng hồ — chạy được khi chưa duyệt Wear Engine",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.padding(4.dp))
                Switch(checked = state.notifyEnabled, onCheckedChange = onNotifyChange)
            }
        }

        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(title, { title = it }, Modifier.fillMaxWidth(), label = { Text("title") }, singleLine = true)
                OutlinedTextField(value, { value = it }, Modifier.fillMaxWidth(), label = { Text("value") }, singleLine = true)
                OutlinedTextField(sub, { sub = it }, Modifier.fillMaxWidth(), label = { Text("sub") }, singleLine = true)
                OutlinedTextField(
                    text, { text = it },
                    Modifier.fillMaxWidth().heightIn(min = 120.dp),
                    label = { Text("text (đoạn văn — có text thì đồng hồ hiện dạng đọc)") },
                    minLines = 4,
                    maxLines = 10,
                )
                Text(
                    "$bytes / ${WatchLink.MAX_PAYLOAD_BYTES} byte",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (tooLong) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.align(Alignment.End),
                )
                Button(onClick = { onSend(title, value, sub, text) }, Modifier.fillMaxWidth(), enabled = !tooLong) {
                    Text("Gửi lên đồng hồ")
                }
            }
        }

        item {
            Text(
                "Từ Mac: adb forward tcp:${BuildConfig.HTTP_PORT} tcp:${BuildConfig.HTTP_PORT}\n" +
                    "curl -X POST localhost:${BuildConfig.HTTP_PORT}/push -d '{\"title\":\"Ghi chú\",\"text\":\"...\"}'",
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        item {
            HorizontalDivider()
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Log", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 12.dp))
                TextButton(onClick = onClearLog) { Text("Xoá") }
            }
        }

        items(state.log) { line ->
            Text(line, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
        }
    }
}

@Composable
private fun StatusRow(label: String, mark: String, detail: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text("$mark  $label")
        Text(detail, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

private fun Boolean.mark() = if (this) "✅" else "❌"
