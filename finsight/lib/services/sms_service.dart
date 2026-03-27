import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';

/// SMS Service — Reads bank SMS from the device inbox via MethodChannel
/// and syncs them to the FinSight backend for ML classification.
class SmsService {
  static const _channel = MethodChannel('com.finsight/sms');
  static const _lastSyncKeyPrefix = 'sms_last_sync_';

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
  /// Uses a per-user sync key so different accounts don't share sync state.
  Future<SyncResult> syncSmsToBackend({int months = 6, String? userId}) async {
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

    // Filter only new SMS (after last sync) — per-user key
    final prefs = await SharedPreferences.getInstance();
    final syncKey = userId != null ? '$_lastSyncKeyPrefix$userId' : '${_lastSyncKeyPrefix}default';
    final lastSync = prefs.getInt(syncKey) ?? 0;
    final newSms = allSms.where((sms) {
      final ts = sms['timestamp'] as int? ?? 0;
      return ts > lastSync;
    }).toList();

    if (newSms.isEmpty) {
      return SyncResult(total: allSms.length, synced: 0, error: null);
    }

    // Convert SMS to correct format for /sms/ingest endpoint
    final messages = newSms.map((sms) {
      final body = sms['body'] as String? ?? '';
      final sender = sms['sender'] as String? ?? '';
      final timestamp = sms['timestamp'] as int? ?? DateTime.now().millisecondsSinceEpoch;
      final date = sms['date'] as String? ?? DateTime.now().toIso8601String();

      return {
        'sender': sender,
        'body': body,
        'timestamp': timestamp,
        'date': date,
      };
    }).toList();

    // Send to backend in batches of 50
    int totalSynced = 0;
    try {
      for (var i = 0; i < messages.length; i += 50) {
        final batch = messages.skip(i).take(50).toList();
        await _api.ingestSms(batch);
        totalSynced += batch.length;
      }

      // Save the latest timestamp (per-user)
      final latestTs = newSms.map((s) => s['timestamp'] as int? ?? 0).reduce((a, b) => a > b ? a : b);
      await prefs.setInt(syncKey, latestTs);

      // Invalidate analytics cache on backend so fresh data is computed
      await _api.invalidateAnalyticsCache();
    } catch (e) {
      return SyncResult(total: allSms.length, synced: totalSynced, error: e.toString());
    }

    return SyncResult(total: allSms.length, synced: totalSynced, error: null);
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
