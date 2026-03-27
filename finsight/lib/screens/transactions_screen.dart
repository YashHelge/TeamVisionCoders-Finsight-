import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';

import '../core/theme.dart';
import '../core/constants.dart';
import '../services/api_service.dart';
import '../models/transaction.dart';

class TransactionsScreen extends StatefulWidget {
  const TransactionsScreen({super.key});

  @override
  State<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen> {
  List<TransactionModel> _transactions = [];
  bool _loading = true;
  int _page = 1;
  bool _hasMore = true;
  String? _selectedCategory;
  String? _selectedDirection;
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _loadTransactions();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200 && _hasMore && !_loading) {
      _loadMore();
    }
  }

  Future<void> _loadTransactions({bool reset = true}) async {
    if (reset) {
      setState(() { _page = 1; _loading = true; });
    }
    final api = context.read<ApiService>();
    try {
      final res = await api.getTransactions(
        page: _page, pageSize: 20,
        category: _selectedCategory, direction: _selectedDirection,
        search: _searchController.text.isEmpty ? null : _searchController.text,
      );
      final txns = (res['transactions'] as List? ?? []).map((t) => TransactionModel.fromJson(t)).toList();
      setState(() {
        if (reset) {
          _transactions = txns;
        } else {
          _transactions.addAll(txns);
        }
        _hasMore = res['has_more'] ?? false;
        _loading = false;
      });
    } catch (e) {
      setState(() { _loading = false; });
    }
  }

  Future<void> _loadMore() async {
    _page++;
    await _loadTransactions(reset: false);
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        children: [
          _buildHeader(),
          _buildSearchBar(),
          _buildFilters(),
          Expanded(
            child: _loading && _transactions.isEmpty
                ? const Center(child: CircularProgressIndicator(color: AppTheme.primary))
                : _transactions.isEmpty
                    ? _buildEmpty()
                    : RefreshIndicator(
                        onRefresh: _loadTransactions,
                        color: AppTheme.primary,
                        child: ListView.builder(
                          controller: _scrollController,
                          padding: const EdgeInsets.only(bottom: 100),
                          itemCount: _transactions.length + (_hasMore ? 1 : 0),
                          itemBuilder: (ctx, i) {
                            if (i >= _transactions.length) {
                              return const Center(child: Padding(
                                padding: EdgeInsets.all(16),
                                child: CircularProgressIndicator(color: AppTheme.primary, strokeWidth: 2),
                              ));
                            }
                            return _buildTxnCard(_transactions[i], i);
                          },
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          Text('Transactions', style: Theme.of(context).textTheme.displayMedium),
          const Spacer(),
          Text('${_transactions.length} items', style: const TextStyle(color: AppTheme.textMuted)),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: TextField(
        controller: _searchController,
        onSubmitted: (_) => _loadTransactions(),
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          hintText: 'Search merchants...',
          prefixIcon: const Icon(Icons.search_rounded, color: AppTheme.textMuted),
          suffixIcon: _searchController.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear, color: AppTheme.textMuted, size: 18),
                  onPressed: () { _searchController.clear(); _loadTransactions(); },
                )
              : null,
        ),
      ),
    );
  }

  Widget _buildFilters() {
    return SizedBox(
      height: 42,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          _filterChip('All', null, _selectedCategory == null && _selectedDirection == null),
          _filterChip('💰 Income', 'credit', _selectedDirection == 'credit'),
          _filterChip('💸 Expense', 'debit', _selectedDirection == 'debit'),
          ...['food_dining', 'shopping', 'transport', 'entertainment', 'utilities', 'subscriptions']
              .map((c) => _filterChip(
                    '${AppConstants.categoryIcons[c] ?? "❓"} ${AppConstants.categoryLabels[c] ?? c}',
                    c, _selectedCategory == c,
                  )),
        ],
      ),
    );
  }

  Widget _filterChip(String label, String? value, bool selected) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: FilterChip(
        label: Text(label, style: TextStyle(fontSize: 12, color: selected ? Colors.white : AppTheme.textSecondary)),
        selected: selected,
        selectedColor: AppTheme.primary.withValues(alpha: 0.3),
        backgroundColor: AppTheme.surfaceLight,
        side: BorderSide(color: selected ? AppTheme.primary : Colors.transparent),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        onSelected: (_) {
          setState(() {
            if (value == 'credit' || value == 'debit') {
              _selectedDirection = selected ? null : value;
              _selectedCategory = null;
            } else if (value == null) {
              _selectedCategory = null;
              _selectedDirection = null;
            } else {
              _selectedCategory = selected ? null : value;
              _selectedDirection = null;
            }
          });
          _loadTransactions();
        },
      ),
    );
  }

  Widget _buildTxnCard(TransactionModel txn, int index) {
    final catIcon = AppConstants.categoryIcons[txn.category] ?? '❓';
    final catColor = AppTheme.getCategoryColor(txn.category);
    final fmt = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: txn.anomalyScore > 0.7 ? AppTheme.warning.withValues(alpha: 0.5) : AppTheme.surfaceLight),
      ),
      child: Row(
        children: [
          Container(
            width: 44, height: 44,
            decoration: BoxDecoration(color: catColor.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(12)),
            child: Center(child: Text(catIcon, style: const TextStyle(fontSize: 20))),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(txn.merchant, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Text(AppConstants.categoryLabels[txn.category] ?? txn.category, style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                    if (txn.paymentMethod != null) ...[
                      const Text(' • ', style: TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                      Text(txn.paymentMethod!.toUpperCase(), style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                    ],
                  ],
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                txn.isCredit ? '+${fmt.format(txn.amount)}' : '-${fmt.format(txn.amount)}',
                style: TextStyle(color: txn.isCredit ? AppTheme.income : AppTheme.expense, fontWeight: FontWeight.bold, fontSize: 15),
              ),
              if (txn.anomalyScore > 0.7)
                const Text('⚠️ Anomaly', style: TextStyle(color: AppTheme.warning, fontSize: 10)),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 200.ms, delay: (50 * (index % 10)).ms);
  }

  Widget _buildEmpty() {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.receipt_long_rounded, size: 64, color: AppTheme.textMuted),
          SizedBox(height: 16),
          Text('No transactions found', style: TextStyle(color: AppTheme.textMuted, fontSize: 16)),
        ],
      ),
    );
  }
}
