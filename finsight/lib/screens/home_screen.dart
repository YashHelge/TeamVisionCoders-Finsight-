import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/theme.dart';
import '../core/constants.dart';
import '../services/api_service.dart';
import '../models/transaction.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Map<String, dynamic>? _analytics;
  List<TransactionModel> _recentTxns = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final api = context.read<ApiService>();
    final prefs = await SharedPreferences.getInstance();
    if (_analytics == null && _recentTxns.isEmpty) {
      final cachedAnalytics = prefs.getString('cached_analytics');
      final cachedTxn = prefs.getString('cached_txns');
      if (cachedAnalytics != null && cachedTxn != null) {
        try {
          final analyticsRes = jsonDecode(cachedAnalytics);
          final txnRes = jsonDecode(cachedTxn);
          final txns = txnRes['transactions'] as List? ?? [];
          setState(() {
            _analytics = analyticsRes;
            _recentTxns = txns.map((t) => TransactionModel.fromJson(t)).toList();
            _loading = false;
          });
        } catch (_) {}
      }
    }

    if (_analytics == null) {
      setState(() { _loading = true; _error = null; });
    }

    try {
      final analyticsRes = await api.getAnalytics(period: '30d');
      final txnRes = await api.getTransactions(pageSize: 5);

      await prefs.setString('cached_analytics', jsonEncode(analyticsRes));
      await prefs.setString('cached_txns', jsonEncode(txnRes));

      if (mounted) {
        setState(() {
          _analytics = analyticsRes;
          final txns = txnRes['transactions'] as List? ?? [];
          _recentTxns = txns.map((t) => TransactionModel.fromJson(t)).toList();
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted && _analytics == null) {
        setState(() { _error = 'Connect your backend to see live data'; _loading = false; });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: _loading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.primary))
          : RefreshIndicator(
        onRefresh: _loadData,
        color: AppTheme.primary,
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(child: _buildHeader()),
            SliverToBoxAdapter(child: _buildNetFlowCard()),
            SliverToBoxAdapter(child: _buildQuickStats()),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                child: Text('Recent Transactions', style: Theme.of(context).textTheme.titleLarge),
              ),
            ),
            _recentTxns.isEmpty
                ? SliverToBoxAdapter(child: _buildEmptyState())
                : SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (ctx, i) => _buildTxnTile(_recentTxns[i], i),
                      childCount: _recentTxns.length,
                    ),
                  ),
            const SliverToBoxAdapter(child: SizedBox(height: 100)),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          Container(
            width: 44, height: 44,
            decoration: BoxDecoration(
              gradient: AppTheme.primaryGradient,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.account_balance_wallet_rounded, color: Colors.white, size: 22),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('FinSight', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
              Text('AI Finance Intelligence', style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.notifications_none_rounded, color: AppTheme.textSecondary),
            onPressed: () {},
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideX(begin: -0.1);
  }

  Widget _buildNetFlowCard() {
    final income = _analytics?['total_income']?.toDouble() ?? 0.0;
    final expense = _analytics?['total_expense']?.toDouble() ?? 0.0;
    final net = income - expense;
    final fmt = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

    return Container(
      margin: const EdgeInsets.fromLTRB(20, 20, 20, 0),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: AppTheme.primaryGradient,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(color: AppTheme.primary.withValues(alpha: 0.3), blurRadius: 20, offset: const Offset(0, 8)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Net Flow (30 days)', style: TextStyle(color: Colors.white70, fontSize: 14)),
          const SizedBox(height: 8),
          Text(
            fmt.format(net), 
            style: const TextStyle(color: Colors.white, fontSize: 36, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              _flowChip('Income', fmt.format(income), AppTheme.income),
              const SizedBox(width: 16),
              _flowChip('Expense', fmt.format(expense), AppTheme.expense),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms).slideY(begin: 0.2);
  }

  Widget _flowChip(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 12),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(label == 'Income' ? Icons.arrow_downward_rounded : Icons.arrow_upward_rounded, color: color, size: 16),
                const SizedBox(width: 4),
                Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
              ],
            ),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickStats() {
    final savingsRate = _analytics != null && (_analytics!['total_income'] ?? 0) > 0
        ? ((_analytics!['total_income'] - _analytics!['total_expense']) / _analytics!['total_income'] * 100)
        : 0.0;
    final forecast = _analytics?['forecast_7d']?.toDouble();

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          _statCard('Savings Rate', '${savingsRate.toStringAsFixed(1)}%', Icons.savings_rounded, AppTheme.success),
          const SizedBox(width: 12),
          _statCard(
            '7d Forecast',
            forecast != null ? '₹${NumberFormat('#,##0').format(forecast)}' : '--',
            Icons.trending_up_rounded, AppTheme.warning,
          ),
        ],
      ),
    ).animate().fadeIn(duration: 600.ms, delay: 200.ms);
  }

  Widget _statCard(String label, String value, IconData icon, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.surfaceLight),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 8),
            Text(value, style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Widget _buildTxnTile(TransactionModel txn, int index) {
    final catIcon = AppConstants.categoryIcons[txn.category] ?? '❓';
    final catColor = AppTheme.getCategoryColor(txn.category);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.surfaceLight),
      ),
      child: Row(
        children: [
          Container(
            width: 42, height: 42,
            decoration: BoxDecoration(
              color: catColor.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(child: Text(catIcon, style: const TextStyle(fontSize: 20))),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(txn.merchant, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 15)),
                const SizedBox(height: 2),
                Text(
                  AppConstants.categoryLabels[txn.category] ?? txn.category,
                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 12),
                ),
              ],
            ),
          ),
          Text(
            txn.formattedAmount,
            style: TextStyle(
              color: txn.isCredit ? AppTheme.income : AppTheme.expense,
              fontWeight: FontWeight.bold, fontSize: 16,
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 300.ms, delay: (100 * index).ms).slideX(begin: 0.1);
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          children: [
            Icon(Icons.receipt_long_rounded, size: 64, color: AppTheme.textMuted.withValues(alpha: 0.5)),
            const SizedBox(height: 16),
            Text(
              _error ?? 'No transactions yet',
              style: const TextStyle(color: AppTheme.textMuted, fontSize: 16),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            const Text(
              'Start the backend and ingest demo data\nto see your financial dashboard',
              style: TextStyle(color: AppTheme.textMuted, fontSize: 13),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
