import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';

/// SMS Service — Reads bank SMS from the device inbox via MethodChannel
/// and syncs them to the FinSight backend for ML classification.
class SmsService {
  static const _channel = MethodChannel('com.finsight/sms');
  static const _lastSyncKey = 'sms_last_sync_timestamp';

  final ApiService _api;

  SmsService(this._api);

  /// Check if SMS permission has been granted.
  Future<bool> hasPermission() async {
    try {
      return await _channel.invokeMethod<bool>('hasSmsPermission') ?? false;
    } catch (e) {
      return false;
    }
  }

  /// Request SMS permission from the user.
  Future<bool> requestPermission() async {
    try {
      return await _channel.invokeMethod<bool>('requestSmsPermission') ?? false;
    } catch (e) {
      return false;
    }
  }

  /// Read bank SMS from the device inbox (last [months] months).
  /// Returns a list of SMS maps with: sender, body, timestamp, date.
  Future<List<Map<String, dynamic>>> readSmsInbox({int months = 6}) async {
    try {
      final result = await _channel.invokeMethod<List>('readSmsInbox', {'months': months});
      if (result == null) return [];
      return result.map((item) => Map<String, dynamic>.from(item as Map)).toList();
    } catch (e) {
      return [];
    }
  }

  /// Sync SMS from the device to the FinSight backend.
  /// Only syncs SMS that haven't been synced before (based on timestamp).
  /// Returns the number of new SMS synced.
  Future<SyncResult> syncSmsToBackend({int months = 6}) async {
    // Check permission first
    final hasPerms = await hasPermission();
    if (!hasPerms) {
      final granted = await requestPermission();
      if (!granted) {
        return SyncResult(total: 0, synced: 0, error: 'SMS permission denied');
      }
    }

    // Read SMS from inbox
    final allSms = await readSmsInbox(months: months);
    if (allSms.isEmpty) {
      return SyncResult(total: 0, synced: 0, error: 'No bank SMS found');
    }

    // Filter only new SMS (after last sync)
    final prefs = await SharedPreferences.getInstance();
    final lastSync = prefs.getInt(_lastSyncKey) ?? 0;
    final newSms = allSms.where((sms) {
      final ts = sms['timestamp'] as int? ?? 0;
      return ts > lastSync;
    }).toList();

    if (newSms.isEmpty) {
      return SyncResult(total: allSms.length, synced: 0, error: null);
    }

    // Convert SMS to dataset format for the backend
    final transactions = newSms.map((sms) {
      final body = sms['body'] as String? ?? '';
      final sender = sms['sender'] as String? ?? '';
      final date = sms['date'] as String? ?? DateTime.now().toIso8601String();
      final amount = _extractAmount(body);
      final direction = _detectDirection(body);

      return {
        'date': date,
        'description': body,
        'amount': amount,
        'type': direction,
        'bank': sender,
        'payment_method': _detectPaymentMethod(body),
      };
    }).toList();

    // Send to backend in batches of 50
    int totalSynced = 0;
    try {
      for (var i = 0; i < transactions.length; i += 50) {
        final batch = transactions.skip(i).take(50).toList();
        await _api.ingestDataset(batch);
        totalSynced += batch.length;
      }

      // Save the latest timestamp
      final latestTs = newSms.map((s) => s['timestamp'] as int? ?? 0).reduce((a, b) => a > b ? a : b);
      await prefs.setInt(_lastSyncKey, latestTs);
    } catch (e) {
      return SyncResult(total: allSms.length, synced: totalSynced, error: e.toString());
    }

    return SyncResult(total: allSms.length, synced: totalSynced, error: null);
  }

  /// Extract amount from SMS body using regex patterns.
  double _extractAmount(String body) {
    // Match patterns like: Rs.5000, Rs 5,000.00, INR 1000, ₹500
    final patterns = [
      RegExp(r'(?:Rs\.?|INR|₹)\s*([\d,]+\.?\d*)', caseSensitive: false),
      RegExp(r'([\d,]+\.?\d*)\s*(?:Rs\.?|INR|₹)', caseSensitive: false),
      RegExp(r'(?:amount|amt)\s*(?:of|:)?\s*(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)', caseSensitive: false),
    ];

    for (final pattern in patterns) {
      final match = pattern.firstMatch(body);
      if (match != null) {
        final amountStr = match.group(1)!.replaceAll(',', '');
        final amount = double.tryParse(amountStr);
        if (amount != null && amount > 0 && amount < 10000000) {
          return amount;
        }
      }
    }
    return 0.0;
  }

  /// Detect transaction direction from SMS body.
  String _detectDirection(String body) {
    final lower = body.toLowerCase();
    final debitKeywords = ['debited', 'debit', 'withdrawn', 'sent', 'paid', 'purchase', 'spent', 'charged'];
    final creditKeywords = ['credited', 'credit', 'received', 'deposited', 'refund', 'cashback'];

    for (final kw in creditKeywords) {
      if (lower.contains(kw)) return 'credit';
    }
    for (final kw in debitKeywords) {
      if (lower.contains(kw)) return 'debit';
    }
    return 'debit';
  }

  /// Detect payment method from SMS body.
  String _detectPaymentMethod(String body) {
    final lower = body.toLowerCase();
    if (lower.contains('upi')) return 'upi';
    if (lower.contains('neft')) return 'neft';
    if (lower.contains('imps')) return 'imps';
    if (lower.contains('rtgs')) return 'rtgs';
    if (lower.contains('nach') || lower.contains('ecs')) return 'nach';
    if (lower.contains('atm')) return 'atm';
    if (lower.contains('card') || lower.contains('pos')) return 'card';
    if (lower.contains('netbank')) return 'netbanking';
    return 'other';
  }
}

/// Result of an SMS sync operation.
class SyncResult {
  final int total;
  final int synced;
  final String? error;

  SyncResult({required this.total, required this.synced, this.error});

  bool get success => error == null;
  bool get hasNewData => synced > 0;
}
