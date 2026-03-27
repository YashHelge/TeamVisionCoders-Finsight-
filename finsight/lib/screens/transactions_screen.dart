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
  List<String> _customCategories = [];
  bool _loading = true;
  int _page = 1;
  bool _hasMore = true;
  String? _selectedCategory;
  String? _selectedDirection;
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();

  List<String> get _allCategories => {...AppConstants.categories, ..._customCategories}.toList();

  @override
  void initState() {
    super.initState();
    _loadCategories();
    _loadTransactions();
    _scrollController.addListener(_onScroll);
  }

  Future<void> _loadCategories() async {
    final api = context.read<ApiService>();
    try {
      final cats = await api.getUserCategories();
      if (mounted) {
        setState(() {
          _customCategories = cats.where((c) => !AppConstants.categories.contains(c)).toList();
        });
      }
    } catch (_) {}
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
      child: Scaffold(
        backgroundColor: AppTheme.background,
        body: Column(
          children: [
            _buildHeader(),
            _buildSearchBar(),
            _buildFilters(),
            Expanded(
              child: _loading && _transactions.isEmpty
                  ? _buildLoadingShimmer()
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
        floatingActionButton: Container(
          decoration: AppTheme.neoCard(radius: 16),
          child: FloatingActionButton(
            backgroundColor: AppTheme.primary,
            elevation: 0,
            onPressed: _showAddTransactionDialog,
            child: const Icon(Icons.add_rounded, color: Colors.white),
          ),
        ),
      ),
    );
  }

  Widget _buildLoadingShimmer() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: List.generate(6, (i) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Container(height: 74, decoration: AppTheme.neoCard(radius: 14)),
        )),
      ).animate(onPlay: (c) => c.repeat()).shimmer(duration: 1200.ms, color: AppTheme.surfaceDimmed.withValues(alpha: 0.5)),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          Text('Transactions', style: Theme.of(context).textTheme.displayMedium),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: AppTheme.accentCard(color: AppTheme.primary, radius: 10),
            child: Text('${_transactions.length}', style: const TextStyle(color: AppTheme.primary, fontWeight: FontWeight.w700, fontSize: 14)),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Container(
        decoration: AppTheme.neoInset(radius: 14),
        child: TextField(
          controller: _searchController,
          onSubmitted: (_) => _loadTransactions(),
          style: const TextStyle(color: AppTheme.textPrimary),
          decoration: InputDecoration(
            hintText: 'Search merchants...',
            hintStyle: const TextStyle(color: AppTheme.textMuted),
            prefixIcon: const Icon(Icons.search_rounded, color: AppTheme.textMuted),
            suffixIcon: _searchController.text.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.clear, color: AppTheme.textMuted, size: 18),
                    onPressed: () { _searchController.clear(); _loadTransactions(); },
                  )
                : null,
            filled: true,
            fillColor: Colors.transparent,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
          ),
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
        label: Text(label, style: TextStyle(
          fontSize: 12,
          color: selected ? AppTheme.primary : AppTheme.textSecondary,
          fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
        )),
        selected: selected,
        selectedColor: AppTheme.primary.withValues(alpha: 0.12),
        backgroundColor: AppTheme.surface,
        side: BorderSide(color: selected ? AppTheme.primary.withValues(alpha: 0.3) : AppTheme.surfaceDimmed),
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
    final catLabel = AppConstants.categoryLabels[txn.category] ?? txn.category;
    final catColor = AppTheme.getCategoryColor(txn.category);
    final fmt = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

    return GestureDetector(
      onLongPress: () => _showEditCategoryDialog(txn),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: txn.anomalyScore > 0.7 ? AppTheme.warning.withValues(alpha: 0.4) : AppTheme.surfaceDimmed,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 44, height: 44,
              decoration: AppTheme.accentCard(color: catColor, radius: 12),
              child: Center(child: Text(catIcon, style: const TextStyle(fontSize: 20))),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(txn.merchant, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 3),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: catColor.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(catLabel, style: TextStyle(color: catColor, fontSize: 10, fontWeight: FontWeight.w500)),
                      ),
                      if (txn.paymentMethod != null) ...[
                        const SizedBox(width: 6),
                        Text(txn.paymentMethod!.toUpperCase(), style: const TextStyle(color: AppTheme.textMuted, fontSize: 10)),
                      ],
                    ],
                  ),
                  if (txn.transactionDate.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(_formatDate(txn.transactionDate), style: const TextStyle(color: AppTheme.textMuted, fontSize: 10)),
                  ],
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
                if (txn.rlAdjusted)
                  const Text('✏️ Edited', style: TextStyle(color: AppTheme.primary, fontSize: 10)),
              ],
            ),
          ],
        ),
      ),
    ).animate().fadeIn(duration: 200.ms, delay: (40 * (index % 10)).ms);
  }

  String _formatDate(String dateStr) {
    try {
      final dt = DateTime.parse(dateStr);
      return DateFormat('dd MMM yyyy, hh:mm a').format(dt);
    } catch (_) {
      return dateStr;
    }
  }

  void _showEditCategoryDialog(TransactionModel txn) {
    String selectedCategory = txn.category;

    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setSheetState) {
          return Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.edit_rounded, color: AppTheme.primary, size: 20),
                    const SizedBox(width: 8),
                    const Text('Edit Category', style: TextStyle(color: AppTheme.textPrimary, fontSize: 18, fontWeight: FontWeight.w700)),
                    const Spacer(),
                    GestureDetector(
                      onTap: () => Navigator.pop(ctx),
                      child: Container(
                        padding: const EdgeInsets.all(6),
                        decoration: AppTheme.neoCard(radius: 10),
                        child: const Icon(Icons.close, color: AppTheme.textMuted, size: 18),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(txn.merchant, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 14)),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8, runSpacing: 8,
                  children: [
                    ..._allCategories.map((cat) {
                      final icon = AppConstants.categoryIcons[cat] ?? '❓';
                      final label = AppConstants.categoryLabels[cat] ?? cat;
                      final isSelected = selectedCategory == cat;
                      return GestureDetector(
                        onTap: () => setSheetState(() => selectedCategory = cat),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: isSelected ? AppTheme.primary.withValues(alpha: 0.1) : AppTheme.surfaceRaised,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: isSelected ? AppTheme.primary : AppTheme.surfaceDimmed),
                          ),
                          child: Text('$icon $label', style: TextStyle(
                            color: isSelected ? AppTheme.primary : AppTheme.textSecondary, fontSize: 13,
                            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                          )),
                        ),
                      );
                    }),
                    GestureDetector(
                      onTap: () async {
                        final newCategory = await _showAddCustomCategoryDialog();
                        if (newCategory != null && newCategory.isNotEmpty) {
                          setSheetState(() {
                            if (!_customCategories.contains(newCategory) && !AppConstants.categories.contains(newCategory)) {
                              _customCategories.add(newCategory);
                            }
                            selectedCategory = newCategory;
                          });
                        }
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceRaised,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AppTheme.surfaceDimmed),
                        ),
                        child: const Text('➕ Add Custom', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity, height: 48,
                  child: ElevatedButton(
                    onPressed: selectedCategory == txn.category ? null : () async {
                      Navigator.pop(ctx);
                      final api = context.read<ApiService>();
                      try {
                        await api.correctCategory(txn.id ?? '', txn.category, selectedCategory);
                        setState(() {
                          final idx = _transactions.indexOf(txn);
                          if (idx != -1) {
                            _transactions[idx] = TransactionModel(
                              id: txn.id, userId: txn.userId, fingerprint: txn.fingerprint,
                              amount: txn.amount, direction: txn.direction, merchant: txn.merchant,
                              merchantRaw: txn.merchantRaw, bank: txn.bank, paymentMethod: txn.paymentMethod,
                              upiRef: txn.upiRef, accountLast4: txn.accountLast4,
                              transactionDate: txn.transactionDate, balanceAfter: txn.balanceAfter,
                              source: txn.source, category: selectedCategory,
                              categoryConfidence: 1.0, rlAdjusted: true,
                              fraudScore: txn.fraudScore, anomalyScore: txn.anomalyScore,
                              isSubscription: txn.isSubscription, syncMode: txn.syncMode, createdAt: txn.createdAt,
                            );
                          }
                        });
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                            content: Text('Category updated to ${AppConstants.categoryLabels[selectedCategory] ?? selectedCategory}'),
                            backgroundColor: AppTheme.success,
                          ));
                        }
                      } catch (e) {
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Failed to update category'), backgroundColor: Colors.redAccent));
                        }
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primary, foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      elevation: 0,
                    ),
                    child: const Text('Save & Train Model', style: TextStyle(fontWeight: FontWeight.w600)),
                  ),
                ),
              ],
            ),
          );
        });
      },
    );
  }

  void _showAddTransactionDialog() {
    final amountCtrl = TextEditingController();
    final merchantCtrl = TextEditingController();
    final notesCtrl = TextEditingController();
    String direction = 'debit';
    String category = 'uncategorized';

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setSheetState) {
          return Padding(
            padding: EdgeInsets.fromLTRB(24, 24, 24, MediaQuery.of(ctx).viewInsets.bottom + 24),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.add_circle_rounded, color: AppTheme.primary, size: 22),
                      const SizedBox(width: 8),
                      const Text('Add Transaction', style: TextStyle(color: AppTheme.textPrimary, fontSize: 18, fontWeight: FontWeight.w700)),
                      const Spacer(),
                      GestureDetector(
                        onTap: () => Navigator.pop(ctx),
                        child: Container(
                          padding: const EdgeInsets.all(6),
                          decoration: AppTheme.neoCard(radius: 10),
                          child: const Icon(Icons.close, color: AppTheme.textMuted, size: 18),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),

                  // Direction toggle
                  Row(
                    children: [
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setSheetState(() => direction = 'debit'),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            decoration: BoxDecoration(
                              color: direction == 'debit' ? AppTheme.expense.withValues(alpha: 0.08) : AppTheme.surfaceRaised,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: direction == 'debit' ? AppTheme.expense.withValues(alpha: 0.3) : AppTheme.surfaceDimmed),
                            ),
                            child: Center(child: Text('💸 Expense', style: TextStyle(
                              color: direction == 'debit' ? AppTheme.expense : AppTheme.textMuted, fontWeight: FontWeight.w600,
                            ))),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setSheetState(() => direction = 'credit'),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            decoration: BoxDecoration(
                              color: direction == 'credit' ? AppTheme.income.withValues(alpha: 0.08) : AppTheme.surfaceRaised,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: direction == 'credit' ? AppTheme.income.withValues(alpha: 0.3) : AppTheme.surfaceDimmed),
                            ),
                            child: Center(child: Text('💰 Income', style: TextStyle(
                              color: direction == 'credit' ? AppTheme.income : AppTheme.textMuted, fontWeight: FontWeight.w600,
                            ))),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  TextField(
                    controller: amountCtrl,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    style: const TextStyle(color: AppTheme.textPrimary, fontSize: 24, fontWeight: FontWeight.bold),
                    decoration: InputDecoration(
                      labelText: 'Amount',
                      prefixText: '₹ ',
                      prefixStyle: const TextStyle(color: AppTheme.primary, fontSize: 24, fontWeight: FontWeight.bold),
                      labelStyle: const TextStyle(color: AppTheme.textMuted),
                      filled: true, fillColor: AppTheme.surfaceRaised,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: merchantCtrl,
                    style: const TextStyle(color: AppTheme.textPrimary),
                    decoration: InputDecoration(
                      labelText: 'Merchant / Description',
                      labelStyle: const TextStyle(color: AppTheme.textMuted),
                      filled: true, fillColor: AppTheme.surfaceRaised,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: notesCtrl,
                    style: const TextStyle(color: AppTheme.textPrimary),
                    decoration: InputDecoration(
                      labelText: 'Notes (optional)',
                      labelStyle: const TextStyle(color: AppTheme.textMuted),
                      filled: true, fillColor: AppTheme.surfaceRaised,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 16),

                  const Text('Category', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6, runSpacing: 6,
                    children: [
                      ..._allCategories.map((cat) {
                        final icon = AppConstants.categoryIcons[cat] ?? '❓';
                        final label = AppConstants.categoryLabels[cat] ?? cat;
                        final isSelected = category == cat;
                        return GestureDetector(
                          onTap: () => setSheetState(() => category = cat),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            decoration: BoxDecoration(
                              color: isSelected ? AppTheme.primary.withValues(alpha: 0.1) : AppTheme.surfaceRaised,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: isSelected ? AppTheme.primary : AppTheme.surfaceDimmed),
                            ),
                            child: Text('$icon $label', style: TextStyle(
                              color: isSelected ? AppTheme.primary : AppTheme.textMuted, fontSize: 12,
                              fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                            )),
                          ),
                        );
                      }),
                      GestureDetector(
                        onTap: () async {
                          final newCategory = await _showAddCustomCategoryDialog();
                          if (newCategory != null && newCategory.isNotEmpty) {
                            setSheetState(() {
                              if (!_customCategories.contains(newCategory) && !AppConstants.categories.contains(newCategory)) {
                                _customCategories.add(newCategory);
                              }
                              category = newCategory;
                            });
                          }
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: AppTheme.surfaceRaised,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppTheme.surfaceDimmed),
                          ),
                          child: const Text('➕ Custom', style: TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),

                  SizedBox(
                    width: double.infinity, height: 50,
                    child: ElevatedButton.icon(
                      onPressed: () async {
                        final amount = double.tryParse(amountCtrl.text);
                        if (amount == null || amount <= 0 || merchantCtrl.text.trim().isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Enter valid amount and merchant'), backgroundColor: Colors.redAccent),
                          );
                          return;
                        }
                        Navigator.pop(ctx);
                        final api = context.read<ApiService>();
                        try {
                          await api.addTransaction(
                            amount: amount, direction: direction,
                            merchant: merchantCtrl.text.trim(), category: category,
                            notes: notesCtrl.text.trim().isEmpty ? null : notesCtrl.text.trim(),
                            transactionDate: DateTime.now().toIso8601String(),
                          );
                          await _loadTransactions();
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                              content: Text('Transaction added!'),
                              backgroundColor: AppTheme.success,
                            ));
                          }
                        } catch (e) {
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Failed to add'), backgroundColor: Colors.redAccent));
                          }
                        }
                      },
                      icon: const Icon(Icons.check_rounded, size: 20),
                      label: const Text('Add Transaction', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primary, foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                        elevation: 0,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        });
      },
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
            child: const Icon(Icons.receipt_long_rounded, size: 32, color: AppTheme.textMuted),
          ),
          const SizedBox(height: 20),
          const Text('No transactions found', style: TextStyle(color: AppTheme.textSecondary, fontSize: 16, fontWeight: FontWeight.w500)),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: _showAddTransactionDialog,
            icon: const Icon(Icons.add_rounded, size: 18),
            label: const Text('Add Manually'),
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

  Future<String?> _showAddCustomCategoryDialog() async {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('Add Custom Category', style: TextStyle(color: AppTheme.textPrimary, fontSize: 18, fontWeight: FontWeight.bold)),
        content: TextField(
          controller: ctrl,
          style: const TextStyle(color: AppTheme.textPrimary),
          textCapitalization: TextCapitalization.words,
          decoration: InputDecoration(
            hintText: 'e.g. Pet Care, Gaming, Freelance',
            hintStyle: const TextStyle(color: AppTheme.textMuted),
            filled: true,
            fillColor: AppTheme.surfaceRaised,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
          ),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel', style: TextStyle(color: AppTheme.textSecondary)),
          ),
          ElevatedButton(
            onPressed: () {
              final raw = ctrl.text.trim();
              if (raw.isNotEmpty) {
                final capitalized = raw.split(' ').map((word) {
                  if (word.isEmpty) return '';
                  return word[0].toUpperCase() + word.substring(1).toLowerCase();
                }).join(' ');
                Navigator.pop(ctx, capitalized);
              } else {
                Navigator.pop(ctx);
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primary, foregroundColor: Colors.white, elevation: 0),
            child: const Text('Add'),
          ),
        ],
      ),
    );
  }
}
