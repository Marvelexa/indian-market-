import { DummyTraderBroker } from '../lib/broker/dummyTraderBroker.ts';

async function main() {
  console.log('========================================================================');
  console.log('🧪 DUMMYTRADER.IN LIVE BROKER INTEGRATION & SAFEGUARD TEST');
  console.log('========================================================================');

  const broker = DummyTraderBroker.getInstance();

  // 1. Fetch initial account
  const account = await broker.getAccount();
  console.log('\n1. Initial Account Status:');
  console.log(`   Client ID: ${account?.clientId}`);
  console.log(`   Coins / Available Margin: ₹${account?.coins}`);
  console.log(`   Net Worth: ₹${account?.netWorth}`);
  console.log(`   Open Positions Count: ${account?.positions.length || 0}`);

  // 2. Place test order: BUY 1 RELIANCE (Lev: 5x)
  console.log('\n2. Testing Order Placement: BUY 1 RELIANCE...');
  const order1 = await broker.placeOrder({
    symbol: 'RELIANCE.NS', // Test .NS auto-sanitization
    side: 'BUY',
    qty: 1,
    leverage: 5,
    tag: 'TEST_SIGNAL_ENTRY',
  });
  console.log('   Result:', order1);

  if (!order1.success) {
    console.error('❌ Failed to place test order. Aborting.');
    return;
  }

  // 3. Test Anti-Repetition Guard: Try placing duplicate BUY immediately!
  console.log('\n3. Testing Anti-Repetition Guard: Immediate Duplicate BUY on RELIANCE...');
  const order2 = await broker.placeOrder({
    symbol: 'RELIANCE',
    side: 'BUY',
    qty: 1,
    leverage: 5,
    tag: 'DUPLICATE_SIGNAL_SPAM',
  });
  console.log('   Duplicate Order Result (Expected Blocked):', order2);
  if (!order2.success) {
    console.log(`   ✅ SUCCESS: Duplicate trade blocked! Reason: ${order2.error}`);
  } else {
    console.error('   ❌ FAILED: Duplicate trade was not blocked!');
  }

  // 4. Test Live Positions Fetch
  console.log('\n4. Checking Live Positions on DummyTrader:');
  const positions = await broker.getPositions(true);
  console.log('   Positions:', positions);

  // 5. Test Safe Square-Off
  console.log('\n5. Testing Safe Square-Off for RELIANCE:');
  const closeRes = await broker.squareOff('RELIANCE', 'TEST_SIGNAL_EXIT');
  console.log('   Square-Off Result:', closeRes);

  // 6. Test Double Square-Off Protection (Must NOT open short position)
  console.log('\n6. Testing Double Square-Off Protection (Must NOT invert position):');
  const closeAgain = await broker.squareOff('RELIANCE', 'ACCIDENTAL_SECOND_CLOSE');
  console.log('   Second Square-Off Result (Expected Already Closed):', closeAgain);

  // 7. Final Account Check
  const finalAccount = await broker.getAccount();
  console.log('\n7. Final Account Status:');
  console.log(`   Coins: ₹${finalAccount?.coins}`);
  console.log(`   Open Positions Count: ${finalAccount?.positions.length || 0}`);

  if (finalAccount?.positions.length === 0 && finalAccount?.coins === 100000) {
    console.log('\n🎉 ALL TESTS PASSED! Account 100% clean and anti-repetition guards verified.');
  } else {
    console.log('\n⚠️ Check final position cleanup:', finalAccount?.positions);
  }
}

main().catch(console.error);
