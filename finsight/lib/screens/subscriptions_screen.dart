import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';

import '../core/theme.dart';
import '../services/api_service.dart';
import '../models/subscription.dart';

class SubscriptionsScreen extends StatefulWidget {
  const SubscriptionsScreen({super.key});

  @override
  State<SubscriptionsScreen> createState() => _SubscriptionsScreenState();
}

class _SubscriptionsScreenState extends State<SubscriptionsScreen> {
  List<SubscriptionModel> _subs = [];
  double _totalMonthly = 0;
  double _totalAnnual = 0;
  int _activeCount = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadSubscriptions();
  }

  Future<void> _loadSubscriptions() async {
    setState(() => _loading = true);
    try {
      final api = context.read<ApiService>();
      final res = await api.getSubscriptions();
      final subList = (res['subscriptions'] as List? ?? []).map((s) => SubscriptionModel.fromJson(s)).toList();
      setState(() {
        _subs = subList;
        _totalMonthly = (res['total_monthly_cost'] ?? 0).toDouble();
        _totalAnnual = (res['total_annual_cost'] ?? 0).toDouble();
        _activeCount = res['active_count'] ?? 0;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

    return SafeArea(
      child: _loading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.primary))
          : CustomScrollView(
              slivers: [
                SliverToBoxAdapter(child: _buildHeader()),
                SliverToBoxAdapter(child: _buildSummaryCard(fmt)),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
                    child: Row(
                      children: [
                        const Text('Active Subscriptions', style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
                        const Spacer(),
                        TextButton.icon(
                          onPressed: _detectSubscriptions,
                          icon: const Icon(Icons.refresh_rounded, size: 16, color: AppTheme.primary),
                          label: const Text('Detect', style: TextStyle(color: AppTheme.primary, fontSize: 13)),
                        ),
                      ],
                    ),
                  ),
                ),
                _subs.isEmpty
                    ? SliverToBoxAdapter(child: _buildEmpty())
                    : SliverList(
                        delegate: SliverChildBuilderDelegate(
                          (ctx, i) => _buildSubCard(_subs[i], i, fmt),
                          childCount: _subs.length,
                        ),
                      ),
                const SliverToBoxAdapter(child: SizedBox(height: 100)),
              ],
            ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Text('Subscriptions', style: Theme.of(context).textTheme.displayMedium),
    );
  }

  Widget _buildSummaryCard(NumberFormat fmt) {
    return Container(
      margin: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFEC407A), Color(0xFFFF6B6B)],
          begin: Alignment.topLeft, end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [BoxShadow(color: const Color(0xFFEC407A).withValues(alpha: 0.3), blurRadius: 20, offset: const Offset(0, 8))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Monthly Subscription Cost', style: TextStyle(color: Colors.white70, fontSize: 14)),
          const SizedBox(height: 8),
          Text(fmt.format(_totalMonthly), style: const TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          Row(
            children: [
              _summaryChip('Annual', fmt.format(_totalAnnual)),
              const SizedBox(width: 16),
              _summaryChip('Active', '$_activeCount subs'),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms).slideY(begin: 0.2);
  }

  Widget _summaryChip(String label, String value) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(12)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
            const SizedBox(height: 2),
            Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 15)),
          ],
        ),
      ),
    );
  }

  Widget _buildSubCard(SubscriptionModel sub, int index, NumberFormat fmt) {
    final wasteColor = sub.wasteScore != null && sub.wasteScore! > 500
        ? AppTheme.error
        : sub.wasteScore != null && sub.wasteScore! > 200
            ? AppTheme.warning
            : AppTheme.success;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 5),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.surfaceLight),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 44, height: 44,
                decoration: BoxDecoration(
                  color: AppTheme.getCategoryColor(sub.category).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Center(child: Text('📱', style: TextStyle(fontSize: 20))),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(sub.merchant, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 15)),
                    Row(children: [
                      Text('${sub.category} • ${sub.periodLabel}', style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                    ]),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(fmt.format(sub.avgMonthlyCost), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                  Text('/month', style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                ],
              ),
            ],
          ),
          if (sub.wasteScore != null && sub.wasteScore! > 0) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(Icons.warning_amber_rounded, size: 14, color: wasteColor),
                const SizedBox(width: 6),
                Text(
                  'Waste score: ${fmt.format(sub.wasteScore!)}/yr',
                  style: TextStyle(color: wasteColor, fontSize: 12, fontWeight: FontWeight.w500),
                ),
                const Spacer(),
                _actionButton('Cancel', AppTheme.error, () => _takeAction(sub, 'cancel')),
                const SizedBox(width: 8),
                _actionButton('Keep', AppTheme.success, () => _takeAction(sub, 'keep')),
              ],
            ),
          ],
        ],
      ),
    ).animate().fadeIn(duration: 300.ms, delay: (80 * index).ms).slideX(begin: 0.05);
  }

  Widget _actionButton(String label, Color color, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
      ),
    );
  }

  Future<void> _takeAction(SubscriptionModel sub, String action) async {
    if (sub.id == null) return;
    try {
      final api = context.read<ApiService>();
      await api.subscriptionAction(sub.id!, action);
      if (action == 'cancel') {
        setState(() => _subs.remove(sub));
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${sub.merchant}: $action'), backgroundColor: AppTheme.surface),
        );
      }
    } catch (e) {
      // Ignore
    }
  }

  Future<void> _detectSubscriptions() async {
    try {
      final api = context.read<ApiService>();
      await api.detectSubscriptions();
      await _loadSubscriptions();
    } catch (e) {
      // Ignore
    }
  }

  Widget _buildEmpty() {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(40),
        child: Column(
          children: [
            Icon(Icons.subscriptions_rounded, size: 64, color: AppTheme.textMuted),
            SizedBox(height: 16),
            Text('No subscriptions detected', style: TextStyle(color: AppTheme.textMuted, fontSize: 16)),
            SizedBox(height: 8),
            Text('Tap "Detect" to scan your transactions', style: TextStyle(color: AppTheme.textMuted, fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
