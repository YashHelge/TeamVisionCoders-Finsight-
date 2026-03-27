import 'dart:convert';
import 'dart:async';
import 'package:http/http.dart' as http;
import '../core/constants.dart';

class ApiService {
  final String baseUrl;
  String _token;

  ApiService({String? baseUrl, String? token})
      : baseUrl = baseUrl ?? AppConstants.baseUrl,
        _token = token ?? '';

  void setToken(String token) => _token = token;

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer $_token',
  };

  /// Base URL without /api/v1 suffix for root-level endpoints
  String get _rootUrl {
    final idx = baseUrl.indexOf('/api/v1');
    return idx != -1 ? baseUrl.substring(0, idx) : baseUrl;
  }

  /// Safe GET with timeout and error handling
  Future<http.Response> _safeGet(Uri uri) async {
    return await http.get(uri, headers: _headers).timeout(
      const Duration(seconds: 15),
      onTimeout: () => throw TimeoutException('Request timed out'),
    );
  }

  /// Safe POST with timeout and error handling
  Future<http.Response> _safePost(Uri uri, {String? body}) async {
    return await http.post(uri, headers: _headers, body: body).timeout(
      const Duration(seconds: 15),
      onTimeout: () => throw TimeoutException('Request timed out'),
    );
  }

  // ── Health ──
  Future<Map<String, dynamic>> healthCheck() async {
    final res = await _safeGet(Uri.parse('$_rootUrl/health'));
    return jsonDecode(res.body);
  }

  // ── Categories ──
  Future<List<String>> getUserCategories() async {
    try {
      final res = await _safeGet(Uri.parse('$baseUrl/transactions/categories'));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        return (data['categories'] as List).map((e) => e.toString()).toList();
      }
    } catch (_) {}
    return [];
  }

  // ── Transactions ──
  Future<Map<String, dynamic>> getTransactions({
    int page = 1, int pageSize = 20,
    String? category, String? direction, String? search,
  }) async {
    final params = <String, String>{
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };
    if (category != null) params['category'] = category;
    if (direction != null) params['direction'] = direction;
    if (search != null) params['search'] = search;

    final uri = Uri.parse('$baseUrl/transactions').replace(queryParameters: params);
    final res = await _safeGet(uri);
    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    }
    return {'transactions': [], 'total': 0, 'page': page, 'page_size': pageSize, 'has_more': false};
  }

  Future<void> correctCategory(String txnId, String oldCat, String newCat) async {
    await _safePost(
      Uri.parse('$baseUrl/transactions/correct-category'),
      body: jsonEncode({
        'transaction_id': txnId,
        'old_category': oldCat,
        'new_category': newCat,
      }),
    );
  }

  Future<Map<String, dynamic>> addTransaction({
    required double amount,
    required String direction,
    required String merchant,
    required String category,
    String? paymentMethod,
    String? bank,
    String? transactionDate,
    String? notes,
  }) async {
    final res = await _safePost(
      Uri.parse('$baseUrl/transactions/create'),
      body: jsonEncode({
        'amount': amount,
        'direction': direction,
        'merchant': merchant,
        'category': category,
        'payment_method': paymentMethod,
        'bank': bank,
        'transaction_date': transactionDate,
        'notes': notes,
      }),
    );
    return jsonDecode(res.body);
  }

  // ── Analytics ──
  Future<Map<String, dynamic>> getAnalytics({String period = '30d'}) async {
    final uri = Uri.parse('$baseUrl/analytics?period=$period');
    final res = await _safeGet(uri);
    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    }
    return {
      'net_flow': 0, 'total_income': 0, 'total_expense': 0,
      'category_breakdown': {}, 'payment_method_distribution': {},
      'top_merchants': [], 'daily_trend': [], 'period': period,
    };
  }

  /// Invalidate analytics cache after new transactions are synced
  Future<void> invalidateAnalyticsCache() async {
    try {
      await http.delete(
        Uri.parse('$baseUrl/analytics/cache'),
        headers: _headers,
      ).timeout(const Duration(seconds: 5));
    } catch (_) {}
  }

  // ── Subscriptions ──
  Future<Map<String, dynamic>> getSubscriptions() async {
    final res = await _safeGet(Uri.parse('$baseUrl/subscriptions'));
    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    }
    return {
      'subscriptions': [], 'total_monthly_cost': 0,
      'total_annual_cost': 0, 'active_count': 0,
    };
  }

  Future<void> subscriptionAction(String subId, String action) async {
    await _safePost(
      Uri.parse('$baseUrl/subscriptions/action'),
      body: jsonEncode({'subscription_id': subId, 'action': action}),
    );
  }

  Future<Map<String, dynamic>> detectSubscriptions() async {
    final res = await _safePost(
      Uri.parse('$baseUrl/subscriptions/detect'),
    );
    return jsonDecode(res.body);
  }

  // ── Dataset Ingestion ──
  Future<Map<String, dynamic>> ingestDataset(List<Map<String, dynamic>> transactions) async {
    final res = await _safePost(
      Uri.parse('$baseUrl/dataset/ingest'),
      body: jsonEncode({'transactions': transactions}),
    );
    return jsonDecode(res.body);
  }

  // ── SMS Ingestion ──
  Future<Map<String, dynamic>> ingestSms(List<Map<String, dynamic>> messages) async {
    final res = await http.post(
      Uri.parse('$baseUrl/sms/ingest'),
      headers: _headers,
      body: jsonEncode({'messages': messages}),
    ).timeout(const Duration(seconds: 30)); // Longer timeout for batch processing
    return jsonDecode(res.body);
  }

  // ── AI Chat ──
  Future<http.StreamedResponse> chatStream(String message, List<Map<String, String>> history) async {
    final request = http.Request('POST', Uri.parse('$baseUrl/ai/chat'));
    request.headers.addAll(_headers);
    request.body = jsonEncode({
      'message': message,
      'history': history,
      'include_web': false,
    });
    return await http.Client().send(request);
  }

  Future<Map<String, dynamic>> getChatHistory() async {
    final res = await _safeGet(Uri.parse('$baseUrl/ai/history'));
    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    }
    return {'history': []};
  }

  // ── Model Update ──
  Future<Map<String, dynamic>> checkModelUpdate(String deviceVersion) async {
    final uri = Uri.parse('$baseUrl/model/update?device_version=$deviceVersion');
    final res = await _safeGet(uri);
    return jsonDecode(res.body);
  }
}
