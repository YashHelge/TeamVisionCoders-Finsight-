package com.finsight.finsight

import android.Manifest
import android.content.pm.PackageManager
import android.database.Cursor
import android.net.Uri
import android.util.Log
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.text.SimpleDateFormat
import java.util.*

class MainActivity : FlutterActivity() {
    companion object {
        private const val CHANNEL = "com.finsight/sms"
        private const val TAG = "FinSight.MainActivity"
        private const val SMS_PERMISSION_CODE = 1001

        // Indian bank & financial SMS sender prefixes
        private val BANK_SENDERS = setOf(
            "HDFCBK", "SBIINB", "ICICIB", "AXISBK", "KOTAKB",
            "YESBK", "PNBSMS", "BOIIND", "UBOI", "CANBNK",
            "IDBIBNK", "INDBNK", "BOBIBANK", "RBLBNK", "FEDBK",
            "SCBANK", "CITIBNK", "HSBCBK", "DEUTBK",
            "PYTM", "PAYTM", "PhonePe", "GPAY", "AMAZONPAY",
            "JIOMNY", "CREDCLUB", "RAZRPAY",
            "HDFC", "SBI", "ICICI", "AXIS", "KOTAK",
            "AIRTEL", "JIOFI", "VODAFO", "IDFCFB", "INDUSB",
            "CENTBK", "SYNB", "MAHABK", "IOBA", "UCOBNK",
        )
    }

    private var pendingResult: MethodChannel.Result? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "readSmsInbox" -> {
                    val months = call.argument<Int>("months") ?: 6
                    if (hasSmsPermission()) {
                        val smsData = readBankSms(months)
                        result.success(smsData)
                    } else {
                        pendingResult = result
                        requestSmsPermission()
                    }
                }
                "hasSmsPermission" -> {
                    result.success(hasSmsPermission())
                }
                "requestSmsPermission" -> {
                    if (hasSmsPermission()) {
                        result.success(true)
                    } else {
                        pendingResult = result
                        requestSmsPermission()
                    }
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun hasSmsPermission(): Boolean {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.READ_SMS) == PackageManager.PERMISSION_GRANTED
    }

    private fun requestSmsPermission() {
        ActivityCompat.requestPermissions(
            this,
            arrayOf(Manifest.permission.READ_SMS, Manifest.permission.RECEIVE_SMS),
            SMS_PERMISSION_CODE
        )
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == SMS_PERMISSION_CODE) {
            val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
            if (granted) {
                // If pending from readSmsInbox call
                pendingResult?.let {
                    val smsData = readBankSms(6)
                    it.success(smsData)
                    pendingResult = null
                } ?: run {
                    // From requestSmsPermission call
                    pendingResult?.success(true)
                    pendingResult = null
                }
            } else {
                pendingResult?.success(if (pendingResult != null) emptyList<Map<String, Any>>() else false)
                pendingResult = null
            }
        }
    }

    /**
     * Read bank/financial SMS from the device inbox.
     * Filters by known Indian bank sender patterns and financial keywords.
     * Goes back [months] months from now.
     */
    private fun readBankSms(months: Int): List<Map<String, Any>> {
        val smsList = mutableListOf<Map<String, Any>>()
        val dateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault())

        // Calculate cutoff date
        val calendar = Calendar.getInstance()
        calendar.add(Calendar.MONTH, -months)
        val cutoffMs = calendar.timeInMillis.toString()

        val uri = Uri.parse("content://sms/inbox")
        val projection = arrayOf("_id", "address", "body", "date", "date_sent")
        val selection = "date > ?"
        val selectionArgs = arrayOf(cutoffMs)
        val sortOrder = "date DESC"

        var cursor: Cursor? = null
        try {
            cursor = contentResolver.query(uri, projection, selection, selectionArgs, sortOrder)
            cursor?.let {
                val addressIdx = it.getColumnIndexOrThrow("address")
                val bodyIdx = it.getColumnIndexOrThrow("body")
                val dateIdx = it.getColumnIndexOrThrow("date")

                while (it.moveToNext()) {
                    val address = it.getString(addressIdx) ?: continue
                    val body = it.getString(bodyIdx) ?: continue
                    val dateMs = it.getLong(dateIdx)

                    // Filter: only bank/financial SMS
                    if (!isBankSms(address, body)) continue

                    val smsMap = mapOf<String, Any>(
                        "sender" to address,
                        "body" to body,
                        "timestamp" to dateMs,
                        "date" to dateFormat.format(Date(dateMs)),
                    )
                    smsList.add(smsMap)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error reading SMS inbox: ${e.message}", e)
        } finally {
            cursor?.close()
        }

        Log.i(TAG, "Read ${smsList.size} bank SMS from last $months months")
        return smsList
    }

    private fun isBankSms(sender: String, body: String): Boolean {
        val upper = sender.uppercase()
        // Check sender matches known bank patterns
        val senderMatch = BANK_SENDERS.any { upper.contains(it) } ||
            upper.matches(Regex(".*[A-Z]{2}-[A-Z]{4,6}.*"))

        if (senderMatch) return true

        // Fallback: check body for financial keywords (catches UPI app SMS)
        val lowerBody = body.lowercase()
        val financialKeywords = listOf(
            "debited", "credited", "a/c", "acct", "account",
            "upi", "neft", "imps", "rtgs", "bal ",
            "rs.", "rs ", "inr", "₹",
            "transaction", "transferred",
        )
        return financialKeywords.count { lowerBody.contains(it) } >= 2
    }
}
