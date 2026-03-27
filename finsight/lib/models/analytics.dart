class AnalyticsModel {
  final double netFlow;
  final double totalIncome;
  final double totalExpense;
  final Map<String, double> categoryBreakdown;
  final Map<String, dynamic> paymentMethodDistribution;
  final List<Map<String, dynamic>> topMerchants;
  final List<Map<String, dynamic>> dailyTrend;
  final double? forecast7d;
  final double? forecast30d;
  final String period;
  final bool cached;

  AnalyticsModel({
    required this.netFlow,
    required this.totalIncome,
    required this.totalExpense,
    required this.categoryBreakdown,
    required this.paymentMethodDistribution,
    required this.topMerchants,
    required this.dailyTrend,
    this.forecast7d,
    this.forecast30d,
    this.period = '30d',
    this.cached = false,
  });

  factory AnalyticsModel.fromJson(Map<String, dynamic> json) {
    return AnalyticsModel(
      netFlow: (json['net_flow'] ?? 0).toDouble(),
      totalIncome: (json['total_income'] ?? 0).toDouble(),
      totalExpense: (json['total_expense'] ?? 0).toDouble(),
      categoryBreakdown: Map<String, double>.from(
        (json['category_breakdown'] ?? {}).map((k, v) => MapEntry(k, (v ?? 0).toDouble())),
      ),
      paymentMethodDistribution: Map<String, dynamic>.from(json['payment_method_distribution'] ?? {}),
      topMerchants: List<Map<String, dynamic>>.from(json['top_merchants'] ?? []),
      dailyTrend: List<Map<String, dynamic>>.from(json['daily_trend'] ?? []),
      forecast7d: json['forecast_7d'] != null ? (json['forecast_7d']).toDouble() : null,
      forecast30d: json['forecast_30d'] != null ? (json['forecast_30d']).toDouble() : null,
      period: json['period'] ?? '30d',
      cached: json['cached'] ?? false,
    );
  }

  double get savingsRate => totalIncome > 0 ? ((totalIncome - totalExpense) / totalIncome * 100) : 0;
}
