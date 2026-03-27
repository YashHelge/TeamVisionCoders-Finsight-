class SubscriptionModel {
  final String? id;
  final String merchant;
  final String category;
  final double avgMonthlyCost;
  final int periodicityDays;
  final double periodicityScore;
  final String? firstSeen;
  final String? lastSeen;
  final int occurrenceCount;
  final double? wasteScore;
  final String? recommendation;
  final bool isActive;
  final String? userAction;

  SubscriptionModel({
    this.id,
    required this.merchant,
    this.category = 'Other',
    required this.avgMonthlyCost,
    this.periodicityDays = 30,
    this.periodicityScore = 0.0,
    this.firstSeen,
    this.lastSeen,
    this.occurrenceCount = 0,
    this.wasteScore,
    this.recommendation,
    this.isActive = true,
    this.userAction,
  });

  factory SubscriptionModel.fromJson(Map<String, dynamic> json) {
    return SubscriptionModel(
      id: json['id']?.toString(),
      merchant: json['merchant'] ?? 'Unknown',
      category: json['category'] ?? 'Other',
      avgMonthlyCost: (json['avg_monthly_cost'] ?? 0).toDouble(),
      periodicityDays: json['periodicity_days'] ?? 30,
      periodicityScore: (json['periodicity_score'] ?? 0).toDouble(),
      firstSeen: json['first_seen']?.toString(),
      lastSeen: json['last_seen']?.toString(),
      occurrenceCount: json['occurrence_count'] ?? 0,
      wasteScore: json['waste_score'] != null ? (json['waste_score']).toDouble() : null,
      recommendation: json['recommendation']?.toString(),
      isActive: json['is_active'] ?? true,
      userAction: json['user_action']?.toString(),
    );
  }

  double get annualCost => avgMonthlyCost * 12;
  String get periodLabel {
    if (periodicityDays <= 7) return 'Weekly';
    if (periodicityDays <= 14) return 'Bi-weekly';
    if (periodicityDays <= 31) return 'Monthly';
    if (periodicityDays <= 90) return 'Quarterly';
    if (periodicityDays <= 180) return 'Semi-annual';
    return 'Annual';
  }
}
