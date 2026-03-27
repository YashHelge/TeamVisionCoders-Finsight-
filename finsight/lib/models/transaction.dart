class TransactionModel {
  final String? id;
  final String? userId;
  final String? fingerprint;
  final double amount;
  final String direction;
  final String merchant;
  final String? merchantRaw;
  final String? bank;
  final String? paymentMethod;
  final String? upiRef;
  final String? accountLast4;
  final String transactionDate;
  final double? balanceAfter;
  final String source;
  final String category;
  final double? categoryConfidence;
  final bool rlAdjusted;
  final double fraudScore;
  final double anomalyScore;
  final bool isSubscription;
  final String? syncMode;
  final String? createdAt;

  TransactionModel({
    this.id,
    this.userId,
    this.fingerprint,
    required this.amount,
    required this.direction,
    required this.merchant,
    this.merchantRaw,
    this.bank,
    this.paymentMethod,
    this.upiRef,
    this.accountLast4,
    required this.transactionDate,
    this.balanceAfter,
    this.source = 'sms',
    this.category = 'uncategorized',
    this.categoryConfidence,
    this.rlAdjusted = false,
    this.fraudScore = 0.0,
    this.anomalyScore = 0.0,
    this.isSubscription = false,
    this.syncMode,
    this.createdAt,
  });

  factory TransactionModel.fromJson(Map<String, dynamic> json) {
    return TransactionModel(
      id: json['id']?.toString(),
      userId: json['user_id']?.toString(),
      fingerprint: json['fingerprint']?.toString(),
      amount: (json['amount'] ?? 0).toDouble(),
      direction: json['direction'] ?? 'debit',
      merchant: json['merchant'] ?? 'Unknown',
      merchantRaw: json['merchant_raw']?.toString(),
      bank: json['bank']?.toString(),
      paymentMethod: json['payment_method']?.toString(),
      upiRef: json['upi_ref']?.toString(),
      accountLast4: json['account_last4']?.toString(),
      transactionDate: json['transaction_date'] ?? '',
      balanceAfter: json['balance_after'] != null ? (json['balance_after']).toDouble() : null,
      source: json['source'] ?? 'sms',
      category: json['category'] ?? 'uncategorized',
      categoryConfidence: json['category_confidence'] != null ? (json['category_confidence']).toDouble() : null,
      rlAdjusted: json['rl_adjusted'] ?? false,
      fraudScore: (json['fraud_score'] ?? 0).toDouble(),
      anomalyScore: (json['anomaly_score'] ?? 0).toDouble(),
      isSubscription: json['is_subscription'] ?? false,
      syncMode: json['sync_mode']?.toString(),
      createdAt: json['created_at']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id, 'user_id': userId, 'fingerprint': fingerprint,
    'amount': amount, 'direction': direction, 'merchant': merchant,
    'merchant_raw': merchantRaw, 'bank': bank, 'payment_method': paymentMethod,
    'upi_ref': upiRef, 'account_last4': accountLast4,
    'transaction_date': transactionDate, 'balance_after': balanceAfter,
    'source': source, 'category': category,
    'category_confidence': categoryConfidence, 'rl_adjusted': rlAdjusted,
    'fraud_score': fraudScore, 'anomaly_score': anomalyScore,
    'is_subscription': isSubscription, 'sync_mode': syncMode,
    'created_at': createdAt,
  };

  bool get isCredit => direction == 'credit';
  bool get isDebit => direction == 'debit';
  String get formattedAmount => isCredit ? '+₹${amount.toStringAsFixed(2)}' : '-₹${amount.toStringAsFixed(2)}';
}
