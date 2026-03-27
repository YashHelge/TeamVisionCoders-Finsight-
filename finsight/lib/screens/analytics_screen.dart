import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';

import '../core/theme.dart';
import '../core/constants.dart';
import '../services/api_service.dart';
import '../models/analytics.dart';

class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  AnalyticsModel? _analytics;
  bool _loading = true;
  String _period = '30d';

  @override
  void initState() {
    super.initState();
    _loadAnalytics();
  }

  Future<void> _loadAnalytics() async {
    setState(() => _loading = true);
    try {
      final api = context.read<ApiService>();
      final res = await api.getAnalytics(period: _period);
      setState(() { _analytics = AnalyticsModel.fromJson(res); _loading = false; });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: _loading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.primary))
          : CustomScrollView(
              slivers: [
                SliverToBoxAdapter(child: _buildHeader()),
                SliverToBoxAdapter(child: _buildPeriodSelector()),
                SliverToBoxAdapter(child: _buildSummaryCards()),
                SliverToBoxAdapter(child: _buildCategoryChart()),
                SliverToBoxAdapter(child: _buildTopMerchants()),
                const SliverToBoxAdapter(child: SizedBox(height: 100)),
              ],
            ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Text('Analytics', style: Theme.of(context).textTheme.displayMedium),
    );
  }

  Widget _buildPeriodSelector() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: ['7d', '30d', '90d', '1y'].map((p) {
          final selected = p == _period;
          return Expanded(
            child: GestureDetector(
              onTap: () { setState(() => _period = p); _loadAnalytics(); },
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 4),
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: selected ? AppTheme.primary : AppTheme.surfaceLight,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Center(
                  child: Text(p.toUpperCase(), style: TextStyle(
                    color: selected ? Colors.white : AppTheme.textMuted,
                    fontWeight: FontWeight.w600, fontSize: 13,
                  )),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildSummaryCards() {
    if (_analytics == null) return const SizedBox.shrink();
    final fmt = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Column(
        children: [
          Row(
            children: [
              _summaryCard('Income', fmt.format(_analytics!.totalIncome), AppTheme.income, Icons.arrow_downward_rounded),
              const SizedBox(width: 12),
              _summaryCard('Expense', fmt.format(_analytics!.totalExpense), AppTheme.expense, Icons.arrow_upward_rounded),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _summaryCard('Savings', '${_analytics!.savingsRate.toStringAsFixed(1)}%', AppTheme.success, Icons.savings_rounded),
              const SizedBox(width: 12),
              _summaryCard(
                '7d Forecast',
                _analytics!.forecast7d != null ? fmt.format(_analytics!.forecast7d!) : 'N/A',
                AppTheme.warning, Icons.trending_up_rounded,
              ),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms);
  }

  Widget _summaryCard(String label, String value, Color color, IconData icon) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Row(
          children: [
            Container(
              width: 36, height: 36,
              decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, color: color, size: 18),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                  const SizedBox(height: 2),
                  Text(value, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 16)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCategoryChart() {
    if (_analytics == null || _analytics!.categoryBreakdown.isEmpty) return const SizedBox.shrink();
    final entries = _analytics!.categoryBreakdown.entries.toList()..sort((a, b) => b.value.compareTo(a.value));
    final total = entries.fold<double>(0, (sum, e) => sum + e.value);

    return Container(
      margin: const EdgeInsets.fromLTRB(20, 20, 20, 0),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.surfaceLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Spending by Category', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 20),
          SizedBox(
            height: 200,
            child: PieChart(
              PieChartData(
                sectionsSpace: 3,
                centerSpaceRadius: 40,
                sections: entries.take(8).map((e) {
                  final pct = total > 0 ? (e.value / total * 100) : 0.0;
                  final color = AppTheme.getCategoryColor(e.key);
                  return PieChartSectionData(
                    value: e.value,
                    color: color,
                    radius: 50,
                    title: pct > 5 ? '${pct.toStringAsFixed(0)}%' : '',
                    titleStyle: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold),
                  );
                }).toList(),
              ),
            ),
          ),
          const SizedBox(height: 16),
          ...entries.take(6).map((e) {
            final icon = AppConstants.categoryIcons[e.key] ?? '❓';
            final label = AppConstants.categoryLabels[e.key] ?? e.key;
            final color = AppTheme.getCategoryColor(e.key);
            final pct = total > 0 ? (e.value / total * 100) : 0.0;
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                  const SizedBox(width: 8),
                  Text('$icon $label', style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                  const Spacer(),
                  Text('₹${NumberFormat('#,##0').format(e.value)}', style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
                  const SizedBox(width: 8),
                  Text('${pct.toStringAsFixed(1)}%', style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                ],
              ),
            );
          }),
        ],
      ),
    ).animate().fadeIn(duration: 600.ms, delay: 200.ms);
  }

  Widget _buildTopMerchants() {
    if (_analytics == null || _analytics!.topMerchants.isEmpty) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.surfaceLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Top Merchants', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 14),
          ..._analytics!.topMerchants.take(5).toList().asMap().entries.map((entry) {
            final i = entry.key;
            final m = entry.value;
            final maxAmt = _analytics!.topMerchants.first['total_amount']?.toDouble() ?? 1;
            final amt = m['total_amount']?.toDouble() ?? 0;

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Column(
                children: [
                  Row(
                    children: [
                      CircleAvatar(
                        radius: 16, backgroundColor: AppTheme.primary.withValues(alpha: 0.15),
                        child: Text('${i + 1}', style: const TextStyle(color: AppTheme.primary, fontSize: 12, fontWeight: FontWeight.bold)),
                      ),
                      const SizedBox(width: 12),
                      Expanded(child: Text(m['merchant'] ?? '', style: const TextStyle(color: Colors.white, fontSize: 14))),
                      Text('₹${NumberFormat('#,##0').format(amt)}', style: const TextStyle(color: AppTheme.textSecondary, fontWeight: FontWeight.w600)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: maxAmt > 0 ? amt / maxAmt : 0,
                      backgroundColor: AppTheme.surfaceLight,
                      valueColor: AlwaysStoppedAnimation(AppTheme.primary.withValues(alpha: 0.6)),
                      minHeight: 4,
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    ).animate().fadeIn(duration: 600.ms, delay: 400.ms);
  }
}
