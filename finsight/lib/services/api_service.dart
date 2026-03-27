import 'dart:convert';
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

  // ── Health ──
  Future<Map<String, dynamic>> healthCheck() async {
    final res = await http.get(Uri.parse('$baseUrl/../health'), headers: _headers);
    return jsonDecode(res.body);
  }

  // ── Categories ──
  Future<List<String>> getUserCategories() async {
    final res = await http.get(Uri.parse('$baseUrl/transactions/categories'), headers: _headers);
    if (res.statusCode == 200) {
      final data = jsonDecode(res.body);
      return (data['categories'] as List).map((e) => e.toString()).toList();
    }
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
    final res = await http.get(uri, headers: _headers);
    return jsonDecode(res.body);
  }

  Future<void> correctCategory(String txnId, String oldCat, String newCat) async {
    await http.post(
      Uri.parse('$baseUrl/transactions/correct-category'),
      headers: _headers,
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
    final res = await http.post(
      Uri.parse('$baseUrl/transactions/create'),
      headers: _headers,
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
    final res = await http.get(uri, headers: _headers);
    return jsonDecode(res.body);
  }

  // ── Subscriptions ──
  Future<Map<String, dynamic>> getSubscriptions() async {
    final res = await http.get(Uri.parse('$baseUrl/subscriptions'), headers: _headers);
    return jsonDecode(res.body);
  }

  Future<void> subscriptionAction(String subId, String action) async {
    await http.post(
      Uri.parse('$baseUrl/subscriptions/action'),
      headers: _headers,
      body: jsonEncode({'subscription_id': subId, 'action': action}),
    );
  }

  Future<Map<String, dynamic>> detectSubscriptions() async {
    final res = await http.post(
      Uri.parse('$baseUrl/subscriptions/detect'),
      headers: _headers,
    );
    return jsonDecode(res.body);
  }

  // ── Dataset Ingestion ──
  Future<Map<String, dynamic>> ingestDataset(List<Map<String, dynamic>> transactions) async {
    final res = await http.post(
      Uri.parse('$baseUrl/dataset/ingest'),
      headers: _headers,
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
    );
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
    final res = await http.get(Uri.parse('$baseUrl/ai/history'), headers: _headers);
    return jsonDecode(res.body);
  }

  // ── Model Update ──
  Future<Map<String, dynamic>> checkModelUpdate(String deviceVersion) async {
    final uri = Uri.parse('$baseUrl/model/update?device_version=$deviceVersion');
    final res = await http.get(uri, headers: _headers);
    return jsonDecode(res.body);
  }
}
