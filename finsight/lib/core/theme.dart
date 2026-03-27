import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // ── Premium Light Palette ──
  static const Color primary = Color(0xFF6C5CE7);      // Rich violet
  static const Color primaryLight = Color(0xFF8B7FF0);  // Light violet
  static const Color primaryDark = Color(0xFF5A4BD1);   // Deep violet
  static const Color secondary = Color(0xFF00B894);     // Emerald green
  static const Color accent = Color(0xFFE17055);        // Warm coral

  // ── Light backgrounds ──
  static const Color background = Color(0xFFF0F2F8);   // Soft cool grey
  static const Color surface = Color(0xFFFFFFFF);       // Pure white cards
  static const Color surfaceRaised = Color(0xFFF7F8FC); // Slightly elevated
  static const Color surfaceDimmed = Color(0xFFE8EAF0); // Inset/pressed

  // ── Text ──
  static const Color textPrimary = Color(0xFF1A1D2E);   // Near-black
  static const Color textSecondary = Color(0xFF5A5F7A);  // Muted grey-blue
  static const Color textMuted = Color(0xFF9BA0B5);      // Subtle hint

  // ── Semantic ──
  static const Color success = Color(0xFF00B894);
  static const Color warning = Color(0xFFFDAA33);
  static const Color error = Color(0xFFE74C3C);
  static const Color income = Color(0xFF00B894);
  static const Color expense = Color(0xFFE74C3C);

  // ── Category Colors ──
  static const Map<String, Color> categoryColors = {
    'food_dining': Color(0xFFE17055),
    'shopping': Color(0xFF6C5CE7),
    'transport': Color(0xFF00B894),
    'entertainment': Color(0xFFFDAA33),
    'utilities': Color(0xFF00CEC9),
    'health': Color(0xFFE74C3C),
    'education': Color(0xFF0984E3),
    'travel': Color(0xFF9B59B6),
    'groceries': Color(0xFF27AE60),
    'rent_emi': Color(0xFFD35400),
    'investment': Color(0xFF0984E3),
    'insurance': Color(0xFF7F8C8D),
    'salary': Color(0xFF00B894),
    'income': Color(0xFF00B894),
    'subscriptions': Color(0xFFE84393),
    'finance': Color(0xFF5B6ABF),
    'telecom': Color(0xFF1ABC9C),
    'uncategorized': Color(0xFF95A5A6),
  };

  static Color getCategoryColor(String category) {
    return categoryColors[category.toLowerCase()] ?? textMuted;
  }

  // ── Neomorphic Decorations ──
  /// Raised neomorphic card — appears "popped out" with highlight & shadow
  static BoxDecoration neoCard({
    double radius = 20,
    Color? color,
  }) {
    final base = color ?? surface;
    return BoxDecoration(
      color: base,
      borderRadius: BorderRadius.circular(radius),
      boxShadow: [
        BoxShadow(
          color: const Color(0xFFD1D9E6).withValues(alpha: 0.7),
          offset: const Offset(6, 6),
          blurRadius: 15,
        ),
        const BoxShadow(
          color: Colors.white,
          offset: Offset(-6, -6),
          blurRadius: 15,
        ),
      ],
    );
  }

  /// Pressed/inset neomorphic — appears "pushed in"
  static BoxDecoration neoInset({
    double radius = 16,
    Color? color,
  }) {
    final base = color ?? surfaceDimmed;
    return BoxDecoration(
      color: base,
      borderRadius: BorderRadius.circular(radius),
      boxShadow: [
        BoxShadow(
          color: const Color(0xFFD1D9E6).withValues(alpha: 0.5),
          offset: const Offset(3, 3),
          blurRadius: 6,
          spreadRadius: -2,
        ),
        const BoxShadow(
          color: Colors.white,
          offset: Offset(-3, -3),
          blurRadius: 6,
          spreadRadius: -2,
        ),
      ],
    );
  }

  /// Subtle flat card — no heavy shadows, just border
  static BoxDecoration flatCard({
    double radius = 16,
    Color? borderColor,
  }) {
    return BoxDecoration(
      color: surface,
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(
        color: borderColor ?? const Color(0xFFE8EAF0),
        width: 1,
      ),
    );
  }

  /// Accent card with color tint
  static BoxDecoration accentCard({
    required Color color,
    double radius = 16,
  }) {
    return BoxDecoration(
      color: color.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(
        color: color.withValues(alpha: 0.15),
        width: 1,
      ),
    );
  }

  // ── Theme Data ──
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: background,
      colorScheme: const ColorScheme.light(
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
        scrolledUnderElevation: 0,
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
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
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
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceRaised,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: surfaceDimmed),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: surfaceDimmed),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: primary, width: 1.5),
        ),
        hintStyle: const TextStyle(color: textMuted),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: surfaceRaised,
        selectedColor: primary.withValues(alpha: 0.12),
        labelStyle: const TextStyle(color: textSecondary, fontSize: 13),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        side: BorderSide(color: surfaceDimmed),
      ),
    );
  }
}
