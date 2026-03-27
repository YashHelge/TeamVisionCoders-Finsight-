package com.finsight.finsight.capture

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * Boot Receiver — Restarts FinSight services after device reboot.
 */
class BootReceiver : BroadcastReceiver() {
    companion object {
        private const val TAG = "FinSight.Boot"
    }

    override fun onReceive(context: Context?, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED) {
            Log.i(TAG, "Device booted — FinSight services will be started by Flutter")
            // Services are started when the Flutter app launches
            // The UPI NotificationListenerService is managed by Android system settings
        }
    }
}
