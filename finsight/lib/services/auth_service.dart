import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/constants.dart';

/// AuthService — Handles Supabase Auth (signup, login, logout, session).
class AuthService extends ChangeNotifier {
  final _storage = const FlutterSecureStorage();
  final String _supabaseUrl;
  final String _anonKey;

  String? _accessToken;
  String? _refreshToken;
  String? _userId;
  String? _email;
  bool _isLoggedIn = false;
  bool _loading = true;

  AuthService({String? supabaseUrl, String? anonKey})
      : _supabaseUrl = supabaseUrl ?? AppConstants.supabaseUrl,
        _anonKey = anonKey ?? AppConstants.supabaseAnonKey;

  bool get isLoggedIn => _isLoggedIn;
  bool get loading => _loading;
  String? get accessToken => _accessToken;
  String? get userId => _userId;
  String? get email => _email;

  Map<String, String> get _authHeaders => {
        'Content-Type': 'application/json',
        'apikey': _anonKey,
        'Authorization': 'Bearer ${_accessToken ?? _anonKey}',
      };

  /// Initialize — check for existing session.
  Future<void> init() async {
    _loading = true;
    notifyListeners();

    _accessToken = await _storage.read(key: AppConstants.tokenKey);
    _refreshToken = await _storage.read(key: 'refresh_token');
    _userId = await _storage.read(key: AppConstants.userIdKey);
    _email = await _storage.read(key: 'user_email');

    if (_accessToken != null && _accessToken!.isNotEmpty) {
      // Verify token is still valid
      final valid = await _verifyToken();
      _isLoggedIn = valid;
      if (!valid) {
        // Try refresh
        final refreshed = await _refreshSession();
        _isLoggedIn = refreshed;
      }
    }

    _loading = false;
    notifyListeners();
  }

  /// Sign up with email & password.
  Future<AuthResult> signUp(String email, String password) async {
    try {
      final res = await http.post(
        Uri.parse('$_supabaseUrl/auth/v1/signup'),
        headers: {'Content-Type': 'application/json', 'apikey': _anonKey},
        body: jsonEncode({'email': email, 'password': password}),
      );

      if (res.statusCode == 200 || res.statusCode == 201) {
        final data = jsonDecode(res.body);
        // Supabase may return user immediately or require email confirmation
        if (data['access_token'] != null) {
          await _saveSession(data);
          return AuthResult.success('Account created successfully!');
        } else {
          return AuthResult.success('Check your email to confirm your account.');
        }
      } else {
        final err = jsonDecode(res.body);
        return AuthResult.failure(err['msg'] ?? err['error_description'] ?? 'Sign up failed');
      }
    } catch (e) {
      return AuthResult.failure('Network error: $e');
    }
  }

  /// Log in with email & password.
  Future<AuthResult> login(String email, String password) async {
    try {
      final res = await http.post(
        Uri.parse('$_supabaseUrl/auth/v1/token?grant_type=password'),
        headers: {'Content-Type': 'application/json', 'apikey': _anonKey},
        body: jsonEncode({'email': email, 'password': password}),
      );

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        await _saveSession(data);
        return AuthResult.success('Logged in successfully!');
      } else {
        final err = jsonDecode(res.body);
        return AuthResult.failure(err['error_description'] ?? err['msg'] ?? 'Login failed');
      }
    } catch (e) {
      return AuthResult.failure('Network error: $e');
    }
  }

  /// Log out — clear stored session.
  Future<void> logout() async {
    // Call Supabase logout
    try {
      await http.post(
        Uri.parse('$_supabaseUrl/auth/v1/logout'),
        headers: _authHeaders,
      );
    } catch (_) {}

    await _storage.deleteAll();
    
    // Clear last sync timestamps and any other local prefs
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();

    _accessToken = null;
    _refreshToken = null;
    _userId = null;
    _email = null;
    _isLoggedIn = false;
    notifyListeners();
  }

  /// Save session tokens to secure storage.
  Future<void> _saveSession(Map<String, dynamic> data) async {
    _accessToken = data['access_token'];
    _refreshToken = data['refresh_token'];
    _userId = data['user']?['id'] ?? '';
    _email = data['user']?['email'] ?? '';
    _isLoggedIn = true;

    await _storage.write(key: AppConstants.tokenKey, value: _accessToken);
    await _storage.write(key: 'refresh_token', value: _refreshToken);
    await _storage.write(key: AppConstants.userIdKey, value: _userId);
    await _storage.write(key: 'user_email', value: _email);

    notifyListeners();
  }

  /// Verify current token is still valid.
  Future<bool> _verifyToken() async {
    try {
      final res = await http.get(
        Uri.parse('$_supabaseUrl/auth/v1/user'),
        headers: _authHeaders,
      );
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Refresh the session using the refresh token.
  Future<bool> _refreshSession() async {
    if (_refreshToken == null) return false;
    try {
      final res = await http.post(
        Uri.parse('$_supabaseUrl/auth/v1/token?grant_type=refresh_token'),
        headers: {'Content-Type': 'application/json', 'apikey': _anonKey},
        body: jsonEncode({'refresh_token': _refreshToken}),
      );

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        await _saveSession(data);
        return true;
      }
    } catch (_) {}
    return false;
  }
}

class AuthResult {
  final bool isSuccess;
  final String message;

  AuthResult._(this.isSuccess, this.message);

  factory AuthResult.success(String message) => AuthResult._(true, message);
  factory AuthResult.failure(String message) => AuthResult._(false, message);
}
