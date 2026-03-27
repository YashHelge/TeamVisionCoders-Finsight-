import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/theme.dart';
import '../core/constants.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
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
    final auth = context.read<AuthService>();
    final prefs = await SharedPreferences.getInstance();
    final userId = auth.userId ?? 'default';

    // Load from user-scoped cache first
    if (_analytics == null && _recentTxns.isEmpty) {
      final cachedAnalytics = prefs.getString('cached_analytics_$userId');
      final cachedTxn = prefs.getString('cached_txns_$userId');
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

      // Cache with user-scoped keys
      await prefs.setString('cached_analytics_$userId', jsonEncode(analyticsRes));
      await prefs.setString('cached_txns_$userId', jsonEncode(txnRes));

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
        setState(() { _error = 'Unable to connect to backend'; _loading = false; });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: _loading
          ? _buildLoadingShimmer()
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
                      padding: const EdgeInsets.fromLTRB(20, 28, 20, 12),
                      child: Row(
                        children: [
                          Text('Recent Transactions', style: Theme.of(context).textTheme.titleLarge),
                          const Spacer(),
                          if (_recentTxns.isNotEmpty)
                            Text('${_recentTxns.length} items', style: const TextStyle(color: AppTheme.textMuted, fontSize: 13)),
                        ],
                      ),
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

  Widget _buildLoadingShimmer() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          const SizedBox(height: 20),
          // Shimmer header
          Row(children: [
            Container(width: 44, height: 44, decoration: AppTheme.neoCard(radius: 12)),
            const SizedBox(width: 12),
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(width: 100, height: 16, decoration: AppTheme.neoInset(radius: 6)),
              const SizedBox(height: 6),
              Container(width: 140, height: 12, decoration: AppTheme.neoInset(radius: 6)),
            ]),
          ]),
          const SizedBox(height: 24),
          // Shimmer card
          Container(height: 180, decoration: AppTheme.neoCard(radius: 20)),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(child: Container(height: 90, decoration: AppTheme.neoCard(radius: 16))),
            const SizedBox(width: 12),
            Expanded(child: Container(height: 90, decoration: AppTheme.neoCard(radius: 16))),
          ]),
          const SizedBox(height: 24),
          ...List.generate(3, (i) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Container(height: 70, decoration: AppTheme.neoCard(radius: 14)),
          )),
        ],
      ).animate(onPlay: (c) => c.repeat()).shimmer(duration: 1200.ms, color: AppTheme.surfaceDimmed.withValues(alpha: 0.5)),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          Container(
            width: 44, height: 44,
            decoration: AppTheme.neoCard(radius: 14),
            child: const Icon(Icons.account_balance_wallet_rounded, color: AppTheme.primary, size: 22),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('FinSight', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
              const Text('AI Finance Intelligence', style: TextStyle(color: AppTheme.textMuted, fontSize: 12)),
            ],
          ),
          const Spacer(),
          Container(
            width: 40, height: 40,
            decoration: AppTheme.neoCard(radius: 12),
            child: const Icon(Icons.notifications_none_rounded, color: AppTheme.textSecondary, size: 20),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms);
  }

  Widget _buildNetFlowCard() {
    final income = _analytics?['total_income']?.toDouble() ?? 0.0;
    final expense = _analytics?['total_expense']?.toDouble() ?? 0.0;
    final net = income - expense;
    final fmt = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

    return Container(
      margin: const EdgeInsets.fromLTRB(20, 20, 20, 0),
      padding: const EdgeInsets.all(24),
      decoration: AppTheme.neoCard(radius: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: AppTheme.accentCard(color: AppTheme.primary, radius: 8),
                child: const Text('30 Days', style: TextStyle(color: AppTheme.primary, fontSize: 11, fontWeight: FontWeight.w600)),
              ),
              const Spacer(),
              Icon(
                net >= 0 ? Icons.trending_up_rounded : Icons.trending_down_rounded,
                color: net >= 0 ? AppTheme.income : AppTheme.expense,
                size: 20,
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Text('Net Flow', style: TextStyle(color: AppTheme.textMuted, fontSize: 14)),
          const SizedBox(height: 4),
          Text(
            fmt.format(net),
            style: TextStyle(
              color: net >= 0 ? AppTheme.income : AppTheme.expense,
              fontSize: 34, fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              _flowChip('Income', fmt.format(income), AppTheme.income, Icons.arrow_downward_rounded),
              const SizedBox(width: 12),
              _flowChip('Expense', fmt.format(expense), AppTheme.expense, Icons.arrow_upward_rounded),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms).slideY(begin: 0.1);
  }

  Widget _flowChip(String label, String value, Color color, IconData icon) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: AppTheme.accentCard(color: color, radius: 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 22, height: 22,
                  decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6)),
                  child: Icon(icon, color: color, size: 14),
                ),
                const SizedBox(width: 6),
                Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w500)),
              ],
            ),
            const SizedBox(height: 8),
            Text(value, style: TextStyle(color: AppTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.w700)),
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
          _statCard('Savings Rate', '${savingsRate.toStringAsFixed(1)}%', Icons.savings_rounded, AppTheme.secondary),
          const SizedBox(width: 12),
          _statCard(
            '7d Forecast',
            forecast != null ? '₹${NumberFormat('#,##0').format(forecast)}' : '--',
            Icons.trending_up_rounded, AppTheme.accent,
          ),
        ],
      ),
    ).animate().fadeIn(duration: 600.ms, delay: 200.ms);
  }

  Widget _statCard(String label, String value, IconData icon, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: AppTheme.neoCard(radius: 18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 36, height: 36,
              decoration: AppTheme.accentCard(color: color, radius: 10),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(height: 10),
            Text(value, style: const TextStyle(color: AppTheme.textPrimary, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 2),
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
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.flatCard(radius: 16),
      child: Row(
        children: [
          Container(
            width: 42, height: 42,
            decoration: AppTheme.accentCard(color: catColor, radius: 12),
            child: Center(child: Text(catIcon, style: const TextStyle(fontSize: 20))),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(txn.merchant, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 15)),
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
    ).animate().fadeIn(duration: 250.ms, delay: (80 * index).ms).slideX(begin: 0.05);
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          children: [
            Container(
              width: 72, height: 72,
              decoration: AppTheme.neoCard(radius: 20),
              child: Icon(Icons.receipt_long_rounded, size: 32, color: AppTheme.textMuted.withValues(alpha: 0.5)),
            ),
            const SizedBox(height: 20),
            Text(
              _error ?? 'No transactions yet',
              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 16, fontWeight: FontWeight.w500),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            const Text(
              'Your financial data will appear here\nonce SMS are synced with the backend.',
              style: TextStyle(color: AppTheme.textMuted, fontSize: 13),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
