import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/theme.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
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
  bool _detecting = false;

  @override
  void initState() {
    super.initState();
    _loadSubscriptions();
  }

  Future<void> _loadSubscriptions() async {
    final api = context.read<ApiService>();
    final auth = context.read<AuthService>();
    final prefs = await SharedPreferences.getInstance();
    final userId = auth.userId ?? 'default';

    // Load from user-scoped cache first
    if (_subs.isEmpty) {
      final cached = prefs.getString('cached_subs_$userId');
      if (cached != null) {
        try {
          final res = jsonDecode(cached);
          final subList = (res['subscriptions'] as List? ?? []).map((s) => SubscriptionModel.fromJson(s)).toList();
          setState(() {
            _subs = subList;
            _totalMonthly = (res['total_monthly_cost'] ?? 0).toDouble();
            _totalAnnual = (res['total_annual_cost'] ?? 0).toDouble();
            _activeCount = res['active_count'] ?? 0;
            _loading = false;
          });
        } catch (_) {}
      }
    }

    if (_subs.isEmpty) {
      setState(() => _loading = true);
    }

    try {
      final res = await api.getSubscriptions();
      await prefs.setString('cached_subs_$userId', jsonEncode(res));

      final subList = (res['subscriptions'] as List? ?? []).map((s) => SubscriptionModel.fromJson(s)).toList();
      if (mounted) {
        setState(() {
          _subs = subList;
          _totalMonthly = (res['total_monthly_cost'] ?? 0).toDouble();
          _totalAnnual = (res['total_annual_cost'] ?? 0).toDouble();
          _activeCount = res['active_count'] ?? 0;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted && _subs.isEmpty) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

    return SafeArea(
      child: _loading
          ? _buildLoadingShimmer()
          : RefreshIndicator(
              onRefresh: _loadSubscriptions,
              color: AppTheme.primary,
              child: CustomScrollView(
                slivers: [
                  SliverToBoxAdapter(child: _buildHeader()),
                  SliverToBoxAdapter(child: _buildSummaryCard(fmt)),
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                      child: Row(
                        children: [
                          const Text('Active Subscriptions', style: TextStyle(color: AppTheme.textPrimary, fontSize: 17, fontWeight: FontWeight.w600)),
                          const Spacer(),
                          GestureDetector(
                            onTap: _detecting ? null : _detectSubscriptions,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                              decoration: AppTheme.accentCard(color: AppTheme.primary, radius: 10),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  if (_detecting)
                                    const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(color: AppTheme.primary, strokeWidth: 2))
                                  else
                                    const Icon(Icons.radar_rounded, size: 16, color: AppTheme.primary),
                                  const SizedBox(width: 6),
                                  Text(_detecting ? 'Scanning...' : 'Detect', style: const TextStyle(color: AppTheme.primary, fontSize: 13, fontWeight: FontWeight.w600)),
                                ],
                              ),
                            ),
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
            ),
    );
  }

  Widget _buildLoadingShimmer() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 16),
          Container(width: 140, height: 28, decoration: AppTheme.neoInset(radius: 8)),
          const SizedBox(height: 16),
          Container(height: 160, decoration: AppTheme.neoCard(radius: 20)),
          const SizedBox(height: 20),
          ...List.generate(4, (i) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Container(height: 80, decoration: AppTheme.neoCard(radius: 14)),
          )),
        ],
      ).animate(onPlay: (c) => c.repeat()).shimmer(duration: 1200.ms, color: AppTheme.surfaceDimmed.withValues(alpha: 0.5)),
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
      decoration: AppTheme.neoCard(radius: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40, height: 40,
                decoration: AppTheme.accentCard(color: AppTheme.accent, radius: 12),
                child: const Icon(Icons.subscriptions_rounded, color: AppTheme.accent, size: 20),
              ),
              const SizedBox(width: 12),
              const Text('Monthly Cost', style: TextStyle(color: AppTheme.textMuted, fontSize: 14)),
            ],
          ),
          const SizedBox(height: 12),
          Text(fmt.format(_totalMonthly), style: const TextStyle(color: AppTheme.textPrimary, fontSize: 34, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          Row(
            children: [
              _summaryChip('Annual', fmt.format(_totalAnnual), AppTheme.secondary),
              const SizedBox(width: 12),
              _summaryChip('Active', '$_activeCount subs', AppTheme.primary),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms).slideY(begin: 0.1);
  }

  Widget _summaryChip(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: AppTheme.accentCard(color: color, radius: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(color: color.withValues(alpha: 0.7), fontSize: 12)),
            const SizedBox(height: 2),
            Text(value, style: TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 15)),
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
            : AppTheme.secondary;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.flatCard(radius: 16),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 44, height: 44,
                decoration: AppTheme.accentCard(color: AppTheme.getCategoryColor(sub.category), radius: 12),
                child: const Center(child: Text('📱', style: TextStyle(fontSize: 20))),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(sub.merchant, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 15)),
                    Row(children: [
                      Text('${sub.category} • ${sub.periodLabel}', style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                    ]),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(fmt.format(sub.avgMonthlyCost), style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.bold, fontSize: 16)),
                  const Text('/month', style: TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                ],
              ),
            ],
          ),
          if (sub.wasteScore != null && sub.wasteScore! > 0) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: AppTheme.accentCard(color: wasteColor, radius: 10),
              child: Row(
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
                  _actionButton('Keep', AppTheme.secondary, () => _takeAction(sub, 'keep')),
                ],
              ),
            ),
          ],
        ],
      ),
    ).animate().fadeIn(duration: 300.ms, delay: (80 * index).ms);
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
          SnackBar(content: Text('${sub.merchant}: $action'), backgroundColor: AppTheme.secondary),
        );
      }
    } catch (e) {}
  }

  Future<void> _detectSubscriptions() async {
    setState(() => _detecting = true);
    try {
      final api = context.read<ApiService>();
      await api.detectSubscriptions();
      await _loadSubscriptions();
    } catch (e) {}
    if (mounted) setState(() => _detecting = false);
  }

  Widget _buildEmpty() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          children: [
            Container(
              width: 72, height: 72,
              decoration: AppTheme.neoCard(radius: 20),
              child: const Icon(Icons.subscriptions_rounded, size: 32, color: AppTheme.textMuted),
            ),
            const SizedBox(height: 20),
            const Text('No subscriptions detected', style: TextStyle(color: AppTheme.textSecondary, fontSize: 16, fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            const Text('Tap "Detect" to scan your transactions', style: TextStyle(color: AppTheme.textMuted, fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
