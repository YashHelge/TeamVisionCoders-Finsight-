package com.finsight.finsight.capture

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import java.security.MessageDigest

/**
 * SMS Broadcast Receiver — Captures incoming bank SMS in real-time.
 *
 * Filters: Only processes SMS from known Indian bank senders.
 * Computes SHA-256 fingerprint and forwards to SyncOrchestrator.
 */
class SmsBroadcastReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "FinSight.SMS"

        // Indian bank & financial SMS sender patterns
        private val BANK_SENDERS = setOf(
            "HDFCBK", "SBIINB", "ICICIB", "AXISBK", "KOTAKB",
            "YESBK", "PNBSMS", "BOIIND", "UBOI", "CANBNK",
            "IDBIBNK", "INDBNK", "BOBIBANK", "RBLBNK", "FEDBK",
            "SCBANK", "CITIBNK", "HSBCBK", "DEUTBK",
            "PYTM", "PAYTM", "PhonePe", "GPAY", "AMAZONPAY",
            "JIOMNY", "CREDCLUB", "RAZRPAY",
            "HDFC", "SBI", "ICICI", "AXIS", "KOTAK",
            "AIRTEL", "JIOFI", "VODAFO",
        )

        fun isBankSms(sender: String): Boolean {
            val upper = sender.uppercase()
            return BANK_SENDERS.any { upper.contains(it) } ||
                upper.matches(Regex("^[A-Z]{2}-[A-Z]{6}$")) // Standard Indian bank SMS format
        }

        fun computeFingerprint(sender: String, body: String, timestamp: Long): String {
            val input = "$sender|$body|$timestamp"
            val digest = MessageDigest.getInstance("SHA-256")
            val hash = digest.digest(input.toByteArray())
            return hash.joinToString("") { "%02x".format(it) }
        }
    }

    override fun onReceive(context: Context?, intent: Intent?) {
        if (intent?.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return

        for (sms in messages) {
            val sender = sms.originatingAddress ?: continue
            val body = sms.messageBody ?: continue
            val timestamp = sms.timestampMillis

            if (!isBankSms(sender)) {
                Log.d(TAG, "Skipping non-bank SMS from: $sender")
                continue
            }

            val fingerprint = computeFingerprint(sender, body, timestamp)
            Log.i(TAG, "Bank SMS captured: sender=$sender fp=${fingerprint.take(16)}...")

            // Store in local queue for batch sync
            val prefs = context?.getSharedPreferences("finsight_sms_queue", Context.MODE_PRIVATE)
            val queue = prefs?.getStringSet("pending_sms", mutableSetOf()) ?: mutableSetOf()
            val entry = "$fingerprint|$sender|$timestamp|$body"
            queue.add(entry)
            prefs?.edit()?.putStringSet("pending_sms", queue)?.apply()

            // Notify Flutter via MethodChannel (if activity is running)
            // This is handled by the MethodChannelBridge in MainActivity
        }
    }
}
