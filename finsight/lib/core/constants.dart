class AppConstants {
  // API
  static const String baseUrl = 'http://10.0.2.2:8080/api/v1'; // Android emulator localhost
  static const String demoToken = 'demo-token';
  
  // Storage Keys
  static const String tokenKey = 'auth_token';
  static const String userIdKey = 'user_id';
  static const String syncModeKey = 'sync_mode';
  static const String lastSyncKey = 'last_sync_timestamp';
  
  // Budget
  static const double defaultMonthlyBudget = 50000;
  
  // Categories
  static const List<String> categories = [
    'food_dining', 'shopping', 'transport', 'entertainment',
    'utilities', 'health', 'education', 'travel',
    'groceries', 'rent_emi', 'investment', 'insurance',
    'salary', 'income', 'subscriptions', 'finance',
    'telecom', 'uncategorized',
  ];
  
  static const Map<String, String> categoryLabels = {
    'food_dining': 'Food & Dining',
    'shopping': 'Shopping',
    'transport': 'Transport',
    'entertainment': 'Entertainment',
    'utilities': 'Utilities',
    'health': 'Health',
    'education': 'Education',
    'travel': 'Travel',
    'groceries': 'Groceries',
    'rent_emi': 'Rent & EMI',
    'investment': 'Investment',
    'insurance': 'Insurance',
    'salary': 'Salary',
    'income': 'Income',
    'subscriptions': 'Subscriptions',
    'finance': 'Finance',
    'telecom': 'Telecom',
    'uncategorized': 'Uncategorized',
  };

  static const Map<String, String> categoryIcons = {
    'food_dining': '🍔',
    'shopping': '🛍️',
    'transport': '🚗',
    'entertainment': '🎬',
    'utilities': '💡',
    'health': '🏥',
    'education': '📚',
    'travel': '✈️',
    'groceries': '🛒',
    'rent_emi': '🏠',
    'investment': '📈',
    'insurance': '🛡️',
    'salary': '💰',
    'income': '💵',
    'subscriptions': '📱',
    'finance': '🏦',
    'telecom': '📶',
    'uncategorized': '❓',
  };
}
