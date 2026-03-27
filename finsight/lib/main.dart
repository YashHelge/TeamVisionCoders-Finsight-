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
      theme: AppTheme.lightTheme,
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
    setState(() {});
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
          return Scaffold(
            backgroundColor: AppTheme.background,
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 72, height: 72,
                    decoration: AppTheme.neoCard(radius: 20),
                    child: const Icon(Icons.account_balance_wallet_rounded, color: AppTheme.primary, size: 36),
                  ),
                  const SizedBox(height: 20),
                  const Text('FinSight', style: TextStyle(color: AppTheme.textPrimary, fontSize: 26, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: 28, height: 28,
                    child: CircularProgressIndicator(color: AppTheme.primary, strokeWidth: 2.5),
                  ),
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
    final auth = context.read<AuthService>();
    setState(() {
      _syncing = true;
      _syncStatus = 'Scanning SMS inbox...';
    });

    final result = await _smsService.syncSmsToBackend(
      months: 6,
      userId: auth.userId,
    );

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
      backgroundColor: AppTheme.background,
      body: Column(
        children: [
          // Sync status bar
          if (_syncStatus != null || _syncing)
            Container(
              width: double.infinity,
              padding: EdgeInsets.fromLTRB(20, MediaQuery.of(context).padding.top + 6, 20, 10),
              decoration: BoxDecoration(
                color: _syncing ? AppTheme.primary.withValues(alpha: 0.06) : AppTheme.surface,
                border: Border(bottom: BorderSide(color: AppTheme.surfaceDimmed, width: 1)),
              ),
              child: Row(
                children: [
                  if (_syncing)
                    const SizedBox(
                      width: 14, height: 14,
                      child: CircularProgressIndicator(color: AppTheme.primary, strokeWidth: 2),
                    ),
                  if (_syncing) const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _syncStatus ?? 'Syncing...',
                      style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13, fontWeight: FontWeight.w500),
                    ),
                  ),
                  if (!_syncing)
                    GestureDetector(
                      onTap: _autoSync,
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.refresh_rounded, color: AppTheme.primary, size: 18),
                      ),
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
          boxShadow: [
            BoxShadow(
              color: const Color(0xFFD1D9E6).withValues(alpha: 0.4),
              offset: const Offset(0, -4),
              blurRadius: 16,
            ),
          ],
        ),
        child: SafeArea(
          child: Container(
            height: 64,
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _navItem(Icons.home_rounded, 'Home', 0),
                _navItem(Icons.receipt_long_rounded, 'Txns', 1),
                _navItem(Icons.analytics_rounded, 'Analytics', 2),
                _navItem(Icons.subscriptions_rounded, 'Subs', 3),
                _navItem(Icons.smart_toy_rounded, 'AI', 4),
                _navItem(Icons.person_rounded, 'Profile', 5),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _navItem(IconData icon, String label, int index) {
    final selected = _currentIndex == index;
    return GestureDetector(
      onTap: () => setState(() => _currentIndex = index),
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: selected
            ? BoxDecoration(
                color: AppTheme.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(14),
              )
            : null,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: selected ? AppTheme.primary : AppTheme.textMuted, size: 22),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                color: selected ? AppTheme.primary : AppTheme.textMuted,
                fontSize: 10,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
