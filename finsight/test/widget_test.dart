import 'package:flutter_test/flutter_test.dart';

import 'package:finsight/main.dart';

void main() {
  testWidgets('FinSight app renders', (WidgetTester tester) async {
    await tester.pumpWidget(const FinSightApp());
    expect(find.text('FinSight'), findsOneWidget);
  });
}
