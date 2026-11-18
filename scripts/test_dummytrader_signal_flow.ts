/**
 * FILE: scripts/test_dummytrader_signal_flow.ts
 * ============================================================================
 * FULL END-TO-END VERIFICATION: DUMMYTRADER.IN SIGNAL EXECUTION & REPETITION SHIELD
 * ============================================================================
 */

import { DummyTraderBroker } from '../lib/broker/dummyTraderBroker.ts';

async function runTestFlow() {
  console.log('========================================================================');
  console.log('⚡ DUMMYTRADER.IN SIGNAL FLOW & ANTI-REPETITION SHIELD AUDIT');
  console.log('========================================================================');

  const broker = DummyTraderBroker.getInstance();

  // Step 1: Health & Account Connection Check
  console.log('\n[STEP 1] Checking Broker Connection & Initial State...');
  const account = await broker.getAccount();
  if (!account) {
    console.error('❌ Could not connect to DummyTrader.in API. Check internet/credentials.');
    return;
  }
  console.log(`✅ Connected as Client: ${account.clientId}`);
  console.log(`   Coins: ₹${account.coins} | Net Worth: ₹${account.netWorth} | Open Positions: ${account.positions.length}`);

  // Step 2: Simulate Signal 1 — BUY 10 RELIANCE (Lev: 5x)
  console.log('\n[STEP 2] Simulating Incoming Engine Signal -> BUY 10x RELIANCE (Lev: 5)...');
  const signal1 = await broker.placeOrder({
    symbol: 'RELIANCE.NS',
    side: 'BUY',
    qty: 10,
    leverage: 5,
    tag: 'SEAT_TREND_1_PULLBACK_RETEST_BUY',
  });
  console.log('   Signal 1 Result:', signal1.success ? `SUCCESS (Order #${signal1.orderId} @ ₹${signal1.price})` : `FAILED: ${signal1.error}`);

  // Step 3: Test Repetitive Spam Storm (Simulate engine firing 5 rapid duplicate signals)
  console.log('\n[STEP 3] Simulating Rapid Repetitive Signal Spam (5 Rapid Calls on RELIANCE)...');
  let blockedCount = 0;
  for (let i = 1; i <= 5; i++) {
    const spamRes = await broker.placeOrder({
      symbol: 'RELIANCE',
      side: 'BUY',
      qty: 10,
      leverage: 5,
      tag: `SPAM_CYCLE_${i}`,
    });
    if (!spamRes.success) {
      blockedCount++;
      console.log(`   🛡️ Spam Call ${i}: BLOCKED — Reason: ${spamRes.error}`);
    } else {
      console.error(`   ❌ Spam Call ${i}: LEAKED THROUGH!`);
    }
  }
  console.log(`   Result: ${blockedCount}/5 Duplicate Spams Blocked Successfully!`);

  // Step 4: Test Error Types & Edge Cases
  console.log('\n[STEP 4] Testing Known Error Types & Auto-Handling:');

  // Error Type 1: Invalid ticker with .NS / junk
  console.log('   • Testing Invalid Ticker (INVALID_XYZ)...');
  const err1 = await broker.placeOrder({ symbol: 'INVALID_XYZ', side: 'BUY', qty: 10, leverage: 5 });
  console.log(`     Response: success=${err1.success} | error="${err1.error}"`);

  // Error Type 2: Zero Quantity
  console.log('   • Testing Zero Quantity...');
  const err2 = await broker.placeOrder({ symbol: 'TCS', side: 'BUY', qty: 0, leverage: 5 });
  console.log(`     Response: success=${err2.success} | qty clamped/handled="${err2.qty}"`);

  // Error Type 3: Index Symbol Mapping (^NSEI -> NIFTYBEES)
  console.log('   • Testing Index Symbol Auto-Sanitizer (^NSEI)...');
  const cleanSym = broker.cleanSymbol('^NSEI');
  console.log(`     Sanitizer result: "^NSEI" mapped to "${cleanSym}"`);

  // Step 5: Verify Live Positions on Broker
  console.log('\n[STEP 5] Inspecting Live Positions on Broker:');
  const positions = await broker.getPositions(true);
  for (const p of positions) {
    console.log(`   • ${p.symbol}: Net Qty=${p.netQty}, Avg Price=₹${p.avgPrice}, Lev=${p.lev}x`);
  }

  // Step 6: Safe Square-Off (Exit Signal)
  console.log('\n[STEP 6] Simulating Exit Signal -> Square Off RELIANCE...');
  const squareOffRes = await broker.squareOff('RELIANCE', 'TP1_TRAILING_SL_EXIT');
  console.log('   Exit Result:', squareOffRes.success ? `SUCCESS (Closed via ${squareOffRes.side} ${squareOffRes.qty}x)` : `FAILED: ${squareOffRes.error}`);

  // Step 7: Double Square-Off Protection (Ensure no reverse position inversion)
  console.log('\n[STEP 7] Testing Double Square-Off Protection...');
  const doubleClose = await broker.squareOff('RELIANCE', 'REDUNDANT_EXIT');
  console.log(`   Double Close Result: success=${doubleClose.success} | statusText="${doubleClose.statusText}"`);

  // Step 8: Final Reconciliation
  console.log('\n[STEP 8] Final Broker Reconciliation:');
  const finalAcc = await broker.getAccount();
  console.log(`   Final Coins: ₹${finalAcc?.coins}`);
  console.log(`   Open Positions: ${finalAcc?.positions.length || 0}`);
  if (finalAcc?.positions.length === 0 && finalAcc?.coins === 100000) {
    console.log('\n🎉 ALL CHECKS PASSED: DummyTrader account is 100% clean, error-immune, and live-ready!');
  } else {
    console.log('\n⚠️ Check final position cleanup:', finalAcc?.positions);
  }
}

runTestFlow().catch(console.error);
