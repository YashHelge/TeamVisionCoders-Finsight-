import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../services/api_service.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<_ChatMessage> _messages = [];
  bool _isTyping = false;

  final _suggestions = [
    'How much did I spend on food this month?',
    'What subscriptions should I cancel?',
    'Show my savings rate trend',
    'How can I reduce my expenses?',
  ];

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _sendMessage(String text) async {
    if (text.trim().isEmpty) return;
    _controller.clear();

    setState(() {
      _messages.add(_ChatMessage(role: 'user', content: text));
      _isTyping = true;
    });
    _scrollToBottom();

    try {
      final api = context.read<ApiService>();
      final history = _messages
          .where((m) => m.role != 'system')
          .map((m) => {'role': m.role, 'content': m.content})
          .toList();

      final response = await api.chatStream(text, history);
      final assistantMsg = _ChatMessage(role: 'assistant', content: '');
      setState(() => _messages.add(assistantMsg));

      // Read the streaming response
      final stream = response.stream.transform(utf8.decoder);
      await for (final chunk in stream) {
        final lines = chunk.split('\n');
        for (final line in lines) {
          if (line.startsWith('data: ')) {
            try {
              final data = jsonDecode(line.substring(6));
              if (data['content'] != null) {
                setState(() => assistantMsg.content += data['content']);
                _scrollToBottom();
              }
              if (data['done'] == true) {
                setState(() => _isTyping = false);
              }
            } catch (e) {
              // Skip malformed JSON
            }
          }
        }
      }
      setState(() => _isTyping = false);
    } catch (e) {
      setState(() {
        _messages.add(_ChatMessage(
          role: 'assistant',
          content: 'Unable to connect to AI service. Make sure the backend is running and GROQ_API_KEY is configured.',
        ));
        _isTyping = false;
      });
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        children: [
          _buildHeader(),
          Expanded(
            child: _messages.isEmpty ? _buildWelcome() : _buildMessageList(),
          ),
          if (_isTyping) _buildTypingIndicator(),
          _buildInputBar(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
      child: Row(
        children: [
          Container(
            width: 38, height: 38,
            decoration: BoxDecoration(gradient: AppTheme.primaryGradient, borderRadius: BorderRadius.circular(10)),
            child: const Icon(Icons.smart_toy_rounded, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('FinSight AI', style: Theme.of(context).textTheme.titleLarge),
              const Text('Powered by Llama 3.3 70B', style: TextStyle(color: AppTheme.textMuted, fontSize: 11)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildWelcome() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          const SizedBox(height: 40),
          Container(
            width: 80, height: 80,
            decoration: BoxDecoration(gradient: AppTheme.primaryGradient, borderRadius: BorderRadius.circular(24)),
            child: const Icon(Icons.smart_toy_rounded, color: Colors.white, size: 40),
          ).animate().scale(duration: 600.ms, curve: Curves.elasticOut),
          const SizedBox(height: 20),
          const Text(
            'Ask me anything about\nyour finances',
            style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          const Text(
            'I have access to your complete financial profile\nand can provide personalized insights.',
            style: TextStyle(color: AppTheme.textMuted, fontSize: 14),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 32),
          ...List.generate(_suggestions.length, (i) => _buildSuggestionChip(_suggestions[i], i)),
        ],
      ),
    );
  }

  Widget _buildSuggestionChip(String text, int index) {
    return GestureDetector(
      onTap: () => _sendMessage(text),
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.surfaceLight),
        ),
        child: Row(
          children: [
            const Icon(Icons.auto_awesome_rounded, color: AppTheme.primary, size: 18),
            const SizedBox(width: 12),
            Expanded(child: Text(text, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 14))),
            const Icon(Icons.arrow_forward_ios_rounded, color: AppTheme.textMuted, size: 14),
          ],
        ),
      ),
    ).animate().fadeIn(duration: 300.ms, delay: (100 * index).ms).slideY(begin: 0.1);
  }

  Widget _buildMessageList() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: _messages.length,
      itemBuilder: (ctx, i) => _buildMessageBubble(_messages[i]),
    );
  }

  Widget _buildMessageBubble(_ChatMessage msg) {
    final isUser = msg.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isUser ? AppTheme.primary : AppTheme.surface,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(isUser ? 16 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 16),
          ),
          border: isUser ? null : Border.all(color: AppTheme.surfaceLight),
        ),
        child: Text(
          msg.content,
          style: TextStyle(color: isUser ? Colors.white : AppTheme.textSecondary, fontSize: 14.5, height: 1.4),
        ),
      ),
    ).animate().fadeIn(duration: 200.ms).slideY(begin: 0.1);
  }

  Widget _buildTypingIndicator() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 4),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(14)),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                ...List.generate(3, (i) => Container(
                  width: 8, height: 8,
                  margin: const EdgeInsets.symmetric(horizontal: 2),
                  decoration: BoxDecoration(color: AppTheme.primary.withValues(alpha: 0.6), shape: BoxShape.circle),
                ).animate(onPlay: (c) => c.repeat(reverse: true))
                    .fadeIn(delay: (200 * i).ms)
                    .scaleXY(begin: 0.5, end: 1.0, duration: 600.ms)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 8, 8, 16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        border: Border(top: BorderSide(color: AppTheme.surfaceLight, width: 0.5)),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              style: const TextStyle(color: Colors.white),
              onSubmitted: _sendMessage,
              decoration: const InputDecoration(
                hintText: 'Ask about your finances...',
                filled: true,
                fillColor: AppTheme.surfaceLight,
                border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(24)), borderSide: BorderSide.none),
                contentPadding: EdgeInsets.symmetric(horizontal: 18, vertical: 12),
              ),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: () => _sendMessage(_controller.text),
            child: Container(
              width: 46, height: 46,
              decoration: BoxDecoration(gradient: AppTheme.primaryGradient, borderRadius: BorderRadius.circular(23)),
              child: const Icon(Icons.send_rounded, color: Colors.white, size: 20),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatMessage {
  final String role;
  String content;

  _ChatMessage({required this.role, required this.content});
}
