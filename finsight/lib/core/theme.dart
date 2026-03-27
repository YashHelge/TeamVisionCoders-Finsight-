import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // ── Brand Colors ──
  static const Color primary = Color(0xFF6C63FF);
  static const Color primaryDark = Color(0xFF5A52D5);
  static const Color secondary = Color(0xFF00D9A6);
  static const Color accent = Color(0xFFFF6B6B);
  static const Color background = Color(0xFF0A0E21);
  static const Color surface = Color(0xFF1D1F33);
  static const Color surfaceLight = Color(0xFF252840);
  static const Color textPrimary = Color(0xFFFFFFFF);
  static const Color textSecondary = Color(0xFFB0B3C5);
  static const Color textMuted = Color(0xFF6C7293);
  static const Color success = Color(0xFF00E676);
  static const Color warning = Color(0xFFFFAB40);
  static const Color error = Color(0xFFFF5252);
  static const Color income = Color(0xFF00E676);
  static const Color expense = Color(0xFFFF5252);

  // ── Category Colors ──
  static const Map<String, Color> categoryColors = {
    'food_dining': Color(0xFFFF6B6B),
    'shopping': Color(0xFF6C63FF),
    'transport': Color(0xFF00D9A6),
    'entertainment': Color(0xFFFFAB40),
    'utilities': Color(0xFF26C6DA),
    'health': Color(0xFFEF5350),
    'education': Color(0xFF42A5F5),
    'travel': Color(0xFFAB47BC),
    'groceries': Color(0xFF66BB6A),
    'rent_emi': Color(0xFFFF7043),
    'investment': Color(0xFF29B6F6),
    'insurance': Color(0xFF78909C),
    'salary': Color(0xFF00E676),
    'income': Color(0xFF00E676),
    'subscriptions': Color(0xFFEC407A),
    'finance': Color(0xFF5C6BC0),
    'telecom': Color(0xFF26A69A),
    'uncategorized': Color(0xFF78909C),
  };

  static Color getCategoryColor(String category) {
    return categoryColors[category.toLowerCase()] ?? textMuted;
  }

  // ── Gradients ──
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF6C63FF), Color(0xFF00D9A6)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient incomeGradient = LinearGradient(
    colors: [Color(0xFF00E676), Color(0xFF00BFA5)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient expenseGradient = LinearGradient(
    colors: [Color(0xFFFF5252), Color(0xFFFF6B6B)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  // ── Theme Data ──
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: background,
      colorScheme: const ColorScheme.dark(
        primary: primary,
        secondary: secondary,
        surface: surface,
        error: error,
      ),
      textTheme: GoogleFonts.interTextTheme(
        const TextTheme(
          displayLarge: TextStyle(color: textPrimary, fontSize: 32, fontWeight: FontWeight.bold),
          displayMedium: TextStyle(color: textPrimary, fontSize: 28, fontWeight: FontWeight.bold),
          headlineMedium: TextStyle(color: textPrimary, fontSize: 22, fontWeight: FontWeight.w600),
          titleLarge: TextStyle(color: textPrimary, fontSize: 18, fontWeight: FontWeight.w600),
          titleMedium: TextStyle(color: textSecondary, fontSize: 16),
          bodyLarge: TextStyle(color: textPrimary, fontSize: 16),
          bodyMedium: TextStyle(color: textSecondary, fontSize: 14),
          bodySmall: TextStyle(color: textMuted, fontSize: 12),
        ),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: background,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: GoogleFonts.inter(
          color: textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w600,
        ),
        iconTheme: const IconThemeData(color: textPrimary),
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: surface,
        selectedItemColor: primary,
        unselectedItemColor: textMuted,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: textPrimary,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceLight,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        hintStyle: const TextStyle(color: textMuted),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
    );
  }
}
