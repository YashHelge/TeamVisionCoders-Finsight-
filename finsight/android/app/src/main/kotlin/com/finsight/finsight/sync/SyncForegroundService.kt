package com.finsight.finsight.sync

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONArray
import org.json.JSONObject

/**
 * Foreground Service for batch SMS/notification sync.
 *
 * Drains the SharedPreferences queue and sends to backend /api/v1/sync/batch.
 */
class SyncForegroundService : Service() {

    companion object {
        private const val TAG = "FinSight.Sync"
        private const val CHANNEL_ID = "finsight_sync"
        private const val NOTIFICATION_ID = 1001
        private const val BASE_URL = "http://10.0.2.2:8080/api/v1"
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("FinSight Sync")
            .setContentText("Syncing financial data...")
            .setSmallIcon(android.R.drawable.ic_popup_sync)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()

        startForeground(NOTIFICATION_ID, notification)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Thread {
            try {
                syncPendingSms()
                syncPendingNotifications()
            } catch (e: Exception) {
                Log.e(TAG, "Sync failed", e)
            } finally {
                stopSelf()
            }
        }.start()

        return START_NOT_STICKY
    }

    private fun syncPendingSms() {
        val prefs = getSharedPreferences("finsight_sms_queue", Context.MODE_PRIVATE)
        val queue = prefs.getStringSet("pending_sms", mutableSetOf()) ?: return
        if (queue.isEmpty()) return

        Log.i(TAG, "Syncing ${queue.size} pending SMS")

        val signals = JSONArray()
        for (entry in queue) {
            val parts = entry.split("|", limit = 4)
            if (parts.size < 4) continue

            val obj = JSONObject()
            obj.put("fingerprint", parts[0])
            obj.put("sender", parts[1])
            obj.put("timestamp", parts[2].toLong())
            obj.put("body", parts[3])
            obj.put("source", "sms")
            signals.put(obj)
        }

        val success = postToBackend("/sync/batch", JSONObject().apply {
            put("signals", signals)
            put("mode", "REALTIME")
        })

        if (success) {
            prefs.edit().remove("pending_sms").apply()
            Log.i(TAG, "SMS sync complete: ${queue.size} signals sent")
        }
    }

    private fun syncPendingNotifications() {
        val prefs = getSharedPreferences("finsight_sms_queue", Context.MODE_PRIVATE)
        val queue = prefs.getStringSet("pending_notifications", mutableSetOf()) ?: return
        if (queue.isEmpty()) return

        Log.i(TAG, "Syncing ${queue.size} pending notifications")

        val signals = JSONArray()
        for (entry in queue) {
            val parts = entry.split("|", limit = 4)
            if (parts.size < 4) continue

            val obj = JSONObject()
            obj.put("fingerprint", parts[0])
            obj.put("sender", parts[1])
            obj.put("timestamp", parts[2].toLong())
            obj.put("body", parts[3])
            obj.put("source", "notification")
            signals.put(obj)
        }

        val success = postToBackend("/sync/batch", JSONObject().apply {
            put("signals", signals)
            put("mode", "REALTIME")
        })

        if (success) {
            prefs.edit().remove("pending_notifications").apply()
            Log.i(TAG, "Notification sync complete: ${queue.size} signals sent")
        }
    }

    private fun postToBackend(path: String, body: JSONObject): Boolean {
        try {
            val prefs = getSharedPreferences("finsight_config", Context.MODE_PRIVATE)
            val token = prefs.getString("auth_token", "demo-token") ?: "demo-token"

            val url = URL("$BASE_URL$path")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.doOutput = true
            conn.connectTimeout = 15000
            conn.readTimeout = 15000

            conn.outputStream.use { os ->
                os.write(body.toString().toByteArray())
            }

            val responseCode = conn.responseCode
            Log.d(TAG, "Backend response: $responseCode")

            return responseCode in 200..299
        } catch (e: Exception) {
            Log.e(TAG, "Backend post failed: ${e.message}")
            return false
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "FinSight Sync",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Background financial data synchronization"
            }
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(channel)
        }
    }
}
