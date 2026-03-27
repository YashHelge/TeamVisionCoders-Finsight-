import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:permission_handler/permission_handler.dart';

import '../core/theme.dart';

/// Three-step permission setup: SMS, Notifications, Battery Optimization.
class PermissionSetupScreen extends StatefulWidget {
  final VoidCallback onComplete;

  const PermissionSetupScreen({super.key, required this.onComplete});

  @override
  State<PermissionSetupScreen> createState() => _PermissionSetupScreenState();
}

class _PermissionSetupScreenState extends State<PermissionSetupScreen> with WidgetsBindingObserver {
  int _currentStep = 0;
  bool _smsGranted = false;
  bool _notificationGranted = false;
  bool _batteryGranted = false;

  final _steps = const [
    _PermissionStep(
      icon: Icons.sms_rounded,
      title: 'SMS Access',
      subtitle: 'Read your bank SMS to track transactions automatically',
      description: 'FinSight reads only bank and financial SMS. Personal messages are never accessed.',
      color: AppTheme.primary,
    ),
    _PermissionStep(
      icon: Icons.notifications_active_rounded,
      title: 'Notification Access',
      subtitle: 'Capture UPI payments that don\'t send an SMS',
      description: 'Monitors only payment app notifications (PhonePe, GPay, Paytm, etc). Other app notifications are ignored.',
      color: AppTheme.secondary,
    ),
    _PermissionStep(
      icon: Icons.battery_saver_rounded,
      title: 'Battery Optimization',
      subtitle: 'Keep FinSight running when the app is closed',
      description: 'Exempts FinSight from battery restrictions so it can capture transactions in the background.',
      color: AppTheme.accent,
    ),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _checkPermissions();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _checkPermissions();
      if (_isCurrentStepGranted()) {
        _nextStep();
      }
    }
  }

  Future<void> _checkPermissions() async {
    final sms = await Permission.sms.isGranted;
    final notification = await Permission.notification.isGranted;
    final battery = await Permission.ignoreBatteryOptimizations.isGranted;
    setState(() {
      _smsGranted = sms;
      _notificationGranted = notification;
      _batteryGranted = battery;
    });
  }

  Future<void> _requestPermission() async {
    switch (_currentStep) {
      case 0:
        final status = await Permission.sms.request();
        setState(() => _smsGranted = status.isGranted);
        if (status.isGranted) _nextStep();
        break;
      case 1:
        final status = await Permission.notification.request();
        setState(() => _notificationGranted = status.isGranted);
        if (status.isGranted) _nextStep();
        break;
      case 2:
        await Permission.ignoreBatteryOptimizations.request();
        final isGranted = await Permission.ignoreBatteryOptimizations.isGranted;
        setState(() => _batteryGranted = isGranted);
        if (isGranted) _nextStep();
        break;
    }
  }

  void _nextStep() {
    if (_currentStep < 2) {
      setState(() => _currentStep++);
    } else {
      widget.onComplete();
    }
  }

  bool _isCurrentStepGranted() {
    switch (_currentStep) {
      case 0: return _smsGranted;
      case 1: return _notificationGranted;
      case 2: return _batteryGranted;
      default: return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final step = _steps[_currentStep];

    return Scaffold(
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            children: [
              // Progress dots
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(3, (i) {
                  final isActive = i <= _currentStep;
                  return AnimatedContainer(
                    duration: const Duration(milliseconds: 300),
                    width: i == _currentStep ? 32 : 10,
                    height: 10,
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    decoration: BoxDecoration(
                      color: isActive ? AppTheme.primary : AppTheme.surfaceDimmed,
                      borderRadius: BorderRadius.circular(5),
                    ),
                  );
                }),
              ),
              const SizedBox(height: 16),
              Text(
                'Step ${_currentStep + 1} of 3',
                style: const TextStyle(color: AppTheme.textMuted, fontSize: 13),
              ),

              const Spacer(),

              // Icon
              Container(
                width: 100,
                height: 100,
                decoration: AppTheme.neoCard(radius: 28),
                child: Icon(step.icon, color: step.color, size: 48),
              ).animate().fadeIn(duration: 300.ms).scale(begin: const Offset(0.8, 0.8)),
              const SizedBox(height: 32),

              // Title & subtitle
              Text(
                step.title,
                style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: AppTheme.textPrimary),
              ).animate().fadeIn(delay: 100.ms),
              const SizedBox(height: 12),
              Text(
                step.subtitle,
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 16, color: step.color, fontWeight: FontWeight.w500),
              ).animate().fadeIn(delay: 200.ms),
              const SizedBox(height: 20),

              // Description in a card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: AppTheme.accentCard(color: step.color, radius: 14),
                child: Row(
                  children: [
                    Icon(Icons.info_outline_rounded, color: step.color, size: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        step.description,
                        style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4),
                      ),
                    ),
                  ],
                ),
              ).animate().fadeIn(delay: 300.ms),

              const Spacer(),

              // Grant button
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton.icon(
                  onPressed: _isCurrentStepGranted() ? _nextStep : _requestPermission,
                  icon: Icon(
                    _isCurrentStepGranted() ? Icons.check_circle_rounded : Icons.security_rounded,
                    size: 20,
                  ),
                  label: Text(
                    _isCurrentStepGranted() ? 'Continue' : 'Grant Permission',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isCurrentStepGranted() ? AppTheme.secondary : AppTheme.primary,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    elevation: 0,
                  ),
                ),
              ).animate().fadeIn(delay: 400.ms),
              const SizedBox(height: 12),

              // Skip
              TextButton(
                onPressed: _nextStep,
                child: const Text('Skip for now', style: TextStyle(color: AppTheme.textMuted, fontSize: 13)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PermissionStep {
  final IconData icon;
  final String title;
  final String subtitle;
  final String description;
  final Color color;

  const _PermissionStep({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.description,
    required this.color,
  });
}
