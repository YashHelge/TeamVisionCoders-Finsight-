package com.finsight.finsight.capture

import android.app.Notification
import android.content.Context
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log

/**
 * UPI Notification Listener — Captures payment notifications from UPI apps.
 *
 * Monitored apps: PhonePe, Google Pay, Paytm, CRED, Amazon Pay, WhatsApp Pay, BHIM
 */
class UpiNotificationListener : NotificationListenerService() {

    companion object {
        private const val TAG = "FinSight.Notification"

        private val UPI_PACKAGES = setOf(
            "com.phonepe.app",
            "com.google.android.apps.nbu.paisa.user",  // Google Pay
            "net.one97.paytm",
            "com.dreamplug.androidapp",  // CRED
            "in.amazon.mShop.android.shopping",
            "com.whatsapp",
            "in.org.npci.upiapp",  // BHIM
            "com.upi.axispay",
            "com.csam.icici.bank.imobile",
            "com.sbi.SBIFreedomPlus",
        )

        private val FINANCIAL_KEYWORDS = setOf(
            "paid", "received", "debited", "credited", "sent",
            "₹", "inr", "rs.", "rs ", "rupee",
            "upi", "neft", "imps", "rtgs",
            "transaction", "payment", "transfer",
        )
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        val notification = sbn?.notification ?: return
        val packageName = sbn.packageName ?: return

        if (packageName !in UPI_PACKAGES) return

        val extras = notification.extras ?: return
        val title = extras.getString(Notification.EXTRA_TITLE, "")
        val text = extras.getString(Notification.EXTRA_TEXT, "")
        val bigText = extras.getString(Notification.EXTRA_BIG_TEXT, text)

        val fullText = "$title $bigText".lowercase()

        // Check if it's a financial notification
        if (FINANCIAL_KEYWORDS.none { fullText.contains(it) }) {
            return
        }

        val timestamp = sbn.postTime
        val fingerprint = SmsBroadcastReceiver.computeFingerprint(packageName, fullText, timestamp)

        Log.i(TAG, "UPI notification captured: pkg=$packageName fp=${fingerprint.take(16)}...")

        // Store in local queue
        val prefs = getSharedPreferences("finsight_sms_queue", Context.MODE_PRIVATE)
        val queue = prefs.getStringSet("pending_notifications", mutableSetOf()) ?: mutableSetOf()
        val entry = "$fingerprint|$packageName|$timestamp|$fullText"
        queue.add(entry)
        prefs.edit().putStringSet("pending_notifications", queue).apply()
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        // No action needed
    }
}
