import 'package:flutter/material.dart';
import 'package:provider/provider.dart';


import 'core/theme.dart';
import 'services/api_service.dart';
import 'screens/home_screen.dart';
import 'screens/transactions_screen.dart';
import 'screens/analytics_screen.dart';
import 'screens/subscriptions_screen.dart';
import 'screens/chat_screen.dart';

void main() {
  runApp(
    Provider<ApiService>(
      create: (_) => ApiService(),
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
      home: const MainNavigationScreen(),
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

  final _screens = const [
    HomeScreen(),
    TransactionsScreen(),
    AnalyticsScreen(),
    SubscriptionsScreen(),
    ChatScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
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
          items: const [
            BottomNavigationBarItem(icon: Icon(Icons.home_rounded), label: 'Home'),
            BottomNavigationBarItem(icon: Icon(Icons.receipt_long_rounded), label: 'Transactions'),
            BottomNavigationBarItem(icon: Icon(Icons.analytics_rounded), label: 'Analytics'),
            BottomNavigationBarItem(icon: Icon(Icons.subscriptions_rounded), label: 'Subscriptions'),
            BottomNavigationBarItem(icon: Icon(Icons.smart_toy_rounded), label: 'AI Chat'),
          ],
        ),
      ),
    );
  }
}
