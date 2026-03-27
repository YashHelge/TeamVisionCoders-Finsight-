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
          ? _buildLoadingShimmer()
          : _analytics == null || (_analytics!.totalIncome == 0 && _analytics!.totalExpense == 0)
              ? _buildEmpty()
              : RefreshIndicator(
                  onRefresh: _loadAnalytics,
                  color: AppTheme.primary,
                  child: CustomScrollView(
                    slivers: [
                      SliverToBoxAdapter(child: _buildHeader()),
                      SliverToBoxAdapter(child: _buildPeriodSelector()),
                      SliverToBoxAdapter(child: _buildSummaryCards()),
                      SliverToBoxAdapter(child: _buildCategoryChart()),
                      SliverToBoxAdapter(child: _buildTopMerchants()),
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
          Container(width: 120, height: 28, decoration: AppTheme.neoInset(radius: 8)),
          const SizedBox(height: 16),
          Row(children: List.generate(4, (i) => Expanded(
            child: Container(margin: const EdgeInsets.symmetric(horizontal: 4), height: 40, decoration: AppTheme.neoCard(radius: 10)),
          ))),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(child: Container(height: 80, decoration: AppTheme.neoCard(radius: 14))),
            const SizedBox(width: 12),
            Expanded(child: Container(height: 80, decoration: AppTheme.neoCard(radius: 14))),
          ]),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: Container(height: 80, decoration: AppTheme.neoCard(radius: 14))),
            const SizedBox(width: 12),
            Expanded(child: Container(height: 80, decoration: AppTheme.neoCard(radius: 14))),
          ]),
          const SizedBox(height: 16),
          Container(height: 260, decoration: AppTheme.neoCard(radius: 16)),
        ],
      ).animate(onPlay: (c) => c.repeat()).shimmer(duration: 1200.ms, color: AppTheme.surfaceDimmed.withValues(alpha: 0.5)),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 72, height: 72,
            decoration: AppTheme.neoCard(radius: 20),
            child: const Icon(Icons.analytics_rounded, size: 32, color: AppTheme.textMuted),
          ),
          const SizedBox(height: 20),
          const Text('No analytics yet', style: TextStyle(color: AppTheme.textSecondary, fontSize: 16, fontWeight: FontWeight.w500)),
          const SizedBox(height: 8),
          const Text('Sync your transactions to see\nspending insights here.',
            style: TextStyle(color: AppTheme.textMuted, fontSize: 13), textAlign: TextAlign.center),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: _loadAnalytics,
            icon: const Icon(Icons.refresh_rounded, size: 18),
            label: const Text('Refresh'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primary, foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              elevation: 0,
            ),
          ),
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
      child: Container(
        padding: const EdgeInsets.all(4),
        decoration: AppTheme.neoInset(radius: 14),
        child: Row(
          children: ['7d', '30d', '90d', '1y'].map((p) {
            final selected = p == _period;
            return Expanded(
              child: GestureDetector(
                onTap: () { setState(() => _period = p); _loadAnalytics(); },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  margin: const EdgeInsets.all(2),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: selected
                      ? AppTheme.neoCard(radius: 10, color: AppTheme.surface)
                      : null,
                  child: Center(
                    child: Text(p.toUpperCase(), style: TextStyle(
                      color: selected ? AppTheme.primary : AppTheme.textMuted,
                      fontWeight: FontWeight.w600, fontSize: 13,
                    )),
                  ),
                ),
              ),
            );
          }).toList(),
        ),
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
              _summaryCard('Savings', '${_analytics!.savingsRate.toStringAsFixed(1)}%', AppTheme.secondary, Icons.savings_rounded),
              const SizedBox(width: 12),
              _summaryCard(
                '7d Forecast',
                _analytics!.forecast7d != null ? fmt.format(_analytics!.forecast7d!) : 'N/A',
                AppTheme.accent, Icons.trending_up_rounded,
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
        decoration: AppTheme.neoCard(radius: 16),
        child: Row(
          children: [
            Container(
              width: 36, height: 36,
              decoration: AppTheme.accentCard(color: color, radius: 10),
              child: Icon(icon, color: color, size: 18),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                  const SizedBox(height: 2),
                  Text(value, style: TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.bold, fontSize: 15)),
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
      decoration: AppTheme.neoCard(radius: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Spending by Category', style: TextStyle(color: AppTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.w600)),
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
              padding: const EdgeInsets.symmetric(vertical: 5),
              child: Row(
                children: [
                  Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                  const SizedBox(width: 8),
                  Text('$icon $label', style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                  const Spacer(),
                  Text('₹${NumberFormat('#,##0').format(e.value)}', style: const TextStyle(color: AppTheme.textPrimary, fontSize: 13, fontWeight: FontWeight.w500)),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(6)),
                    child: Text('${pct.toStringAsFixed(1)}%', style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w500)),
                  ),
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
      decoration: AppTheme.neoCard(radius: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Top Merchants', style: TextStyle(color: AppTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.w600)),
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
                      Container(
                        width: 28, height: 28,
                        decoration: AppTheme.accentCard(color: AppTheme.primary, radius: 8),
                        child: Center(child: Text('${i + 1}', style: const TextStyle(color: AppTheme.primary, fontSize: 12, fontWeight: FontWeight.bold))),
                      ),
                      const SizedBox(width: 12),
                      Expanded(child: Text(m['merchant'] ?? '', style: const TextStyle(color: AppTheme.textPrimary, fontSize: 14))),
                      Text('₹${NumberFormat('#,##0').format(amt)}', style: const TextStyle(color: AppTheme.textSecondary, fontWeight: FontWeight.w600)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: maxAmt > 0 ? amt / maxAmt : 0,
                      backgroundColor: AppTheme.surfaceDimmed,
                      valueColor: AlwaysStoppedAnimation(AppTheme.primary.withValues(alpha: 0.5)),
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
