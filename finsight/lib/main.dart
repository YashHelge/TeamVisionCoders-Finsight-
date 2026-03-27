import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/theme.dart';
import 'services/api_service.dart';
import 'services/auth_service.dart';
import 'services/sms_service.dart';
import 'screens/auth_screen.dart';
import 'screens/permission_setup_screen.dart';
import 'screens/home_screen.dart';
import 'screens/transactions_screen.dart';
import 'screens/analytics_screen.dart';
import 'screens/subscriptions_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/profile_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthService()..init()),
        ProxyProvider<AuthService, ApiService>(
          create: (_) => ApiService(),
          update: (_, auth, api) {
            final apiService = api ?? ApiService();
            if (auth.accessToken != null) {
              apiService.setToken(auth.accessToken!);
            } else {
              apiService.setToken('');
            }
            return apiService;
          },
        ),
      ],
      child: const FinSightApp(),
    ),
  );
}

class FinSightApp extends StatelessWidget {
  const FinSightApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FinSight',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const AppEntry(),
    );
  }
}

/// App entry — shows loading → auth → permissions → main nav.
class AppEntry extends StatefulWidget {
  const AppEntry({super.key});

  @override
  State<AppEntry> createState() => _AppEntryState();
}

class _AppEntryState extends State<AppEntry> {
  bool _permissionsDone = false;

  @override
  void initState() {
    super.initState();
    _checkPermissionsDone();
  }

  Future<void> _checkPermissionsDone() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() => _permissionsDone = prefs.getBool('permissions_done') ?? false);
  }

  void _onAuthSuccess() {
    setState(() {}); // Rebuild to show permissions or main nav
  }

  Future<void> _onPermissionsComplete() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('permissions_done', true);
    setState(() => _permissionsDone = true);
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthService>(
      builder: (context, auth, _) {
        // 1. Loading
        if (auth.loading) {
          return const Scaffold(
            backgroundColor: AppTheme.background,
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(color: AppTheme.primary),
                  SizedBox(height: 16),
                  Text('FinSight', style: TextStyle(color: AppTheme.textPrimary, fontSize: 24, fontWeight: FontWeight.w800)),
                ],
              ),
            ),
          );
        }

        // 2. Not logged in → Auth screen
        if (!auth.isLoggedIn) {
          return AuthScreen(onAuthSuccess: _onAuthSuccess);
        }

        // 3. Permissions not done → Permission setup
        if (!_permissionsDone) {
          return PermissionSetupScreen(onComplete: _onPermissionsComplete);
        }

        // 4. Main navigation
        return const MainNavigationScreen();
      },
    );
  }
}

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _currentIndex = 0;
  bool _syncing = false;
  String? _syncStatus;

  late final SmsService _smsService;

  final _screens = const [
    HomeScreen(),
    TransactionsScreen(),
    AnalyticsScreen(),
    SubscriptionsScreen(),
    ChatScreen(),
    ProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _smsService = SmsService(context.read<ApiService>());
      _autoSync();
    });
  }

  Future<void> _autoSync() async {
    setState(() {
      _syncing = true;
      _syncStatus = 'Scanning SMS inbox...';
    });

    final result = await _smsService.syncSmsToBackend(months: 6);

    setState(() {
      _syncing = false;
      if (result.hasNewData) {
        _syncStatus = '✅ Synced ${result.synced} transactions';
      } else if (result.error != null) {
        _syncStatus = '⚠️ ${result.error}';
      } else {
        _syncStatus = 'Up to date';
      }
    });

    await Future.delayed(const Duration(seconds: 3));
    if (mounted) {
      setState(() => _syncStatus = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Listen to auth changes for logout
    final auth = context.watch<AuthService>();
    if (!auth.isLoggedIn && !auth.loading) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => const AppEntry()),
          (_) => false,
        );
      });
    }

    return Scaffold(
      body: Column(
        children: [
          // Sync status bar
          if (_syncStatus != null || _syncing)
            Container(
              width: double.infinity,
              padding: EdgeInsets.fromLTRB(16, MediaQuery.of(context).padding.top + 4, 16, 8),
              decoration: BoxDecoration(
                color: _syncing ? AppTheme.primary.withValues(alpha: 0.15) : AppTheme.surface,
              ),
              child: Row(
                children: [
                  if (_syncing)
                    const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(color: AppTheme.primary, strokeWidth: 2),
                    ),
                  if (_syncing) const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _syncStatus ?? 'Syncing...',
                      style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                    ),
                  ),
                  if (!_syncing)
                    GestureDetector(
                      onTap: _autoSync,
                      child: const Icon(Icons.refresh_rounded, color: AppTheme.primary, size: 18),
                    ),
                ],
              ),
            ),
          // Main content
          Expanded(
            child: IndexedStack(
              index: _currentIndex,
              children: _screens,
            ),
          ),
        ],
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: AppTheme.surface,
          border: Border(
            top: BorderSide(color: AppTheme.surfaceLight, width: 0.5),
          ),
        ),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: (i) => setState(() => _currentIndex = i),
          type: BottomNavigationBarType.fixed,
          items: const [
            BottomNavigationBarItem(icon: Icon(Icons.home_rounded), label: 'Home'),
            BottomNavigationBarItem(icon: Icon(Icons.receipt_long_rounded), label: 'Transactions'),
            BottomNavigationBarItem(icon: Icon(Icons.analytics_rounded), label: 'Analytics'),
            BottomNavigationBarItem(icon: Icon(Icons.subscriptions_rounded), label: 'Subscriptions'),
            BottomNavigationBarItem(icon: Icon(Icons.smart_toy_rounded), label: 'AI Chat'),
            BottomNavigationBarItem(icon: Icon(Icons.person_rounded), label: 'Profile'),
          ],
        ),
      ),
    );
  }
}
