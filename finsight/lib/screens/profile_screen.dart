import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _backendOnline = false;
  bool _checkingHealth = true;

  @override
  void initState() {
    super.initState();
    _checkBackendHealth();
  }

  Future<void> _checkBackendHealth() async {
    setState(() => _checkingHealth = true);
    try {
      final api = context.read<ApiService>();
      await api.healthCheck();
      if (mounted) setState(() { _backendOnline = true; _checkingHealth = false; });
    } catch (e) {
      if (mounted) setState(() { _backendOnline = false; _checkingHealth = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthService>(
      builder: (context, auth, _) {
        return SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Profile', style: Theme.of(context).textTheme.displayMedium).animate().fadeIn(),
                const SizedBox(height: 24),

                // User card
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: AppTheme.neoCard(radius: 20),
                  child: Row(
                    children: [
                      Container(
                        width: 56, height: 56,
                        decoration: AppTheme.accentCard(color: AppTheme.primary, radius: 16),
                        child: const Icon(Icons.person_rounded, color: AppTheme.primary, size: 28),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              auth.email ?? 'Guest User',
                              style: const TextStyle(color: AppTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 4),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: auth.isLoggedIn ? AppTheme.secondary.withValues(alpha: 0.1) : AppTheme.error.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                auth.isLoggedIn ? '● Authenticated' : '○ Not Authenticated',
                                style: TextStyle(
                                  color: auth.isLoggedIn ? AppTheme.secondary : AppTheme.error,
                                  fontSize: 12, fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ).animate().fadeIn().slideY(begin: 0.1),
                const SizedBox(height: 24),

                // System Status
                const Text('System Status', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                const SizedBox(height: 12),

                _StatusTile(
                  icon: Icons.cloud_done_rounded,
                  title: 'Backend API',
                  value: _checkingHealth ? 'Checking...' : (_backendOnline ? 'Connected' : 'Offline'),
                  color: _checkingHealth ? AppTheme.warning : (_backendOnline ? AppTheme.secondary : AppTheme.error),
                ).animate().fadeIn(delay: 100.ms),
                _StatusTile(
                  icon: Icons.memory_rounded,
                  title: 'ML Model Version',
                  value: '2026.03.15',
                  color: AppTheme.primary,
                ).animate().fadeIn(delay: 150.ms),
                _StatusTile(
                  icon: Icons.sync_rounded,
                  title: 'Sync Mode',
                  value: 'Realtime',
                  color: AppTheme.secondary,
                ).animate().fadeIn(delay: 200.ms),
                _StatusTile(
                  icon: Icons.sms_rounded,
                  title: 'SMS Capture',
                  value: 'Active',
                  color: AppTheme.secondary,
                ).animate().fadeIn(delay: 250.ms),
                _StatusTile(
                  icon: Icons.notifications_active_rounded,
                  title: 'UPI Notification Capture',
                  value: 'Active',
                  color: AppTheme.secondary,
                ).animate().fadeIn(delay: 300.ms),

                const SizedBox(height: 24),

                // App Info
                const Text('About', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                const SizedBox(height: 12),
                _InfoTile(title: 'App Version', value: '1.0.0'),
                _InfoTile(title: 'AI Engine', value: 'Groq Llama 3.3 70B'),
                _InfoTile(title: 'ML Pipeline', value: 'XGBoost + RF Ensemble'),
                _InfoTile(title: 'Subscription Detection', value: 'ACF + FFT + HDBSCAN'),

                const SizedBox(height: 32),

                // Logout
                SizedBox(
                  width: double.infinity,
                  height: 50,
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      await auth.logout();
                    },
                    icon: const Icon(Icons.logout_rounded, size: 18),
                    label: const Text('Sign Out', style: TextStyle(fontWeight: FontWeight.w600)),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.error,
                      side: BorderSide(color: AppTheme.error.withValues(alpha: 0.3)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    ),
                  ),
                ).animate().fadeIn(delay: 400.ms),
                const SizedBox(height: 20),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _StatusTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String value;
  final Color color;

  const _StatusTile({required this.icon, required this.title, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.flatCard(radius: 14),
      child: Row(
        children: [
          Container(
            width: 36, height: 36,
            decoration: AppTheme.accentCard(color: color, radius: 10),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(title, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 14))),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(value, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  final String title;
  final String value;

  const _InfoTile({required this.title, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.flatCard(radius: 14),
      child: Row(
        children: [
          Expanded(child: Text(title, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 14))),
          Text(value, style: const TextStyle(color: AppTheme.textPrimary, fontSize: 13, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}
