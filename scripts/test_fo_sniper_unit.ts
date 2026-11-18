import { FoOptionSniperEngine } from '../lib/bharat/foOptionSniperEngine.ts';

console.log('='.repeat(80));
console.log('  TESTING NEXUS BHARAT TOP 50 F&O OPTION SNIPER & LADDER ENGINE');
console.log('='.repeat(80));

// 1. Verify 50 Whitelist Stocks
const whitelistKeys = Object.keys(FoOptionSniperEngine.FO_WHITELIST_50);
console.log(`\n[Test 1] 50 Whitelist Stocks count: ${whitelistKeys.length}`);
if (whitelistKeys.length !== 50) {
  throw new Error(`Expected 50 stocks in whitelist, got ${whitelistKeys.length}`);
}

// 2. Test ATM Strike Calculation
console.log('\n[Test 2] Testing Dynamic ATM Strike Resolver:');
const strikeTests = [
  { sym: 'RELIANCE', spot: 1336.50, step: 20, expected: 1340 },
  { sym: 'HDFCBANK', spot: 816.15, step: 10, expected: 820 },
  { sym: 'ICICIBANK', spot: 1592.30, step: 10, expected: 1590 },
  { sym: 'SBIN', spot: 812.40, step: 5, expected: 810 },
  { sym: 'TATASTEEL', spot: 145.40, step: 1, expected: 145 },
  { sym: 'ONGC', spot: 247.60, step: 2.5, expected: 247.5 },
  { sym: 'TCS', spot: 2396.00, step: 50, expected: 2400 },
  { sym: 'LT', spot: 4147.30, step: 50, expected: 4150 },
];

for (const t of strikeTests) {
  const calc = FoOptionSniperEngine.calculateAtmStrike(t.spot, t.step);
  console.log(`  ${t.sym.padEnd(10)} Spot: ${t.spot.toFixed(2).padStart(8)} | Step: ${t.step.toString().padStart(4)} | ATM Strike: ${calc} (Expected: ${t.expected})`);
  if (calc !== t.expected) {
    throw new Error(`Strike mismatch for ${t.sym}: expected ${t.expected}, got ${calc}`);
  }
}

// 3. Test Signal Routing & Hard SL (-₹2,500)
async function testSignalRoutingAndLadder() {
  console.log('\n[Test 3] Testing Signal Routing (BUY -> CE, SELL -> PE) & Hard SL (-₹2,500):');
  const engine = new FoOptionSniperEngine();

  // Test Stock BUY Signal -> ATM CE
  const buyRes = await engine.handleStockSignal({
    stockSymbol: 'RELIANCE',
    signalAction: 'BUY',
    spotPrice: 1336.50,
    currentExpiryCode: '26NOV',
    getOptionLtp: async (optSym) => 30.0, // Initial premium ₹30
    executeBrokerOrder: async (order) => {
      console.log(`    [Broker Buy Callback]: ${order.side} ${order.qty}x ${order.optionSymbol} @ ₹${order.price}`);
    }
  });

  const pos1 = buyRes.position!;
  console.log(`  RELIANCE BUY Signal -> Created Option Symbol: ${pos1.optionSymbol}`);
  console.log(`  Option Type: ${pos1.optionType} | Strike: ${pos1.strike} | Lot Qty: ${pos1.qty}`);
  console.log(`  Entry Premium: ₹${pos1.entryPremium} | Initial SL: ₹${pos1.initialSlPremium}`);

  // Max Points Drop for Reliance (Lot 250): 2500 / 250 = 10 pts.
  // Initial SL = 30 - 10 = ₹20.00
  if (pos1.optionType !== 'CE' || pos1.strike !== 1340) {
    throw new Error(`Expected RELIANCE ATM 1340 CE, got ${pos1.optionSymbol}`);
  }
  if (Math.abs(pos1.initialSlPremium - 20.0) > 0.01) {
    throw new Error(`Expected Initial SL ₹20.00 (-₹2,500 max loss), got ${pos1.initialSlPremium}`);
  }

  // Test Stock SELL Signal -> ATM PE
  const sellRes = await engine.handleStockSignal({
    stockSymbol: 'HDFCBANK',
    signalAction: 'SELL',
    spotPrice: 816.15,
    currentExpiryCode: '26NOV',
    getOptionLtp: async (optSym) => 18.0, // Initial premium ₹18
    executeBrokerOrder: async (order) => {
      console.log(`    [Broker Buy Callback]: ${order.side} ${order.qty}x ${order.optionSymbol} @ ₹${order.price}`);
    }
  });

  const pos2 = sellRes.position!;
  console.log(`\n  HDFCBANK SELL Signal -> Created Option Symbol: ${pos2.optionSymbol}`);
  console.log(`  Option Type: ${pos2.optionType} | Strike: ${pos2.strike} | Lot Qty: ${pos2.qty}`);
  console.log(`  Entry Premium: ₹${pos2.entryPremium} | Initial SL: ₹${pos2.currentSlPremium}`);

  // Max Points Drop for HDFCBANK (Lot 550): 2500 / 550 = 4.55 pts.
  // Initial SL = 18 - 4.55 = ₹13.45
  if (pos2.optionType !== 'PE' || pos2.strike !== 820) {
    throw new Error(`Expected HDFCBANK ATM 820 PE, got ${pos2.optionSymbol}`);
  }

  // 4. Test Progressive Profit Ladder (+₹500, +₹1,000, +₹2,000, +₹4,000, +₹8,000 Runner)
  console.log('\n[Test 4] Testing Progressive Profit Ladder on RELIANCE26NOV1340CE:');

  // Step 4.1: Live tick moves premium from ₹30 to ₹32.00 (+2 pts * 250 = +₹500 -> TP1)
  await engine.evaluateOpenPositionsTick({
    liveOptionLtpMap: { 'RELIANCE26NOV1340CE': 32.0 },
    executeBrokerExit: async () => {}
  });
  console.log(`  At Premium ₹32.00 (+₹500 PnL):`);
  console.log(`    Ladder Stage: ${pos1.ladderStage} (Expected: 1)`);
  console.log(`    Locked Profit: ₹${pos1.lockedProfitInr} (Expected: ₹150)`);
  console.log(`    Current SL: ₹${pos1.currentSlPremium} (Expected: ₹30.60, Cost + ₹150)`);
  if (pos1.ladderStage !== 1 || pos1.lockedProfitInr !== 150) {
    throw new Error('TP1 Ladder Stage 1 failed');
  }

  // Step 4.2: Live tick moves premium to ₹34.00 (+4 pts * 250 = +₹1,000 -> TP2)
  await engine.evaluateOpenPositionsTick({
    liveOptionLtpMap: { 'RELIANCE26NOV1340CE': 34.0 },
    executeBrokerExit: async () => {}
  });
  console.log(`  At Premium ₹34.00 (+₹1,000 PnL):`);
  console.log(`    Ladder Stage: ${pos1.ladderStage} (Expected: 2)`);
  console.log(`    Locked Profit: ₹${pos1.lockedProfitInr} (Expected: ₹600)`);
  console.log(`    Current SL: ₹${pos1.currentSlPremium} (Expected: ₹32.40)`);
  if (pos1.ladderStage !== 2 || pos1.lockedProfitInr !== 600) {
    throw new Error('TP2 Ladder Stage 2 failed');
  }

  // Step 4.3: Live tick moves premium to ₹38.00 (+8 pts * 250 = +₹2,000)
  await engine.evaluateOpenPositionsTick({
    liveOptionLtpMap: { 'RELIANCE26NOV1340CE': 38.0 },
    executeBrokerExit: async () => {}
  });
  console.log(`  At Premium ₹38.00 (+₹2,000 PnL):`);
  console.log(`    Ladder Stage: ${pos1.ladderStage} (Expected: 3)`);
  console.log(`    Locked Profit: ₹${pos1.lockedProfitInr} (Expected: ₹1,400)`);
  if (pos1.ladderStage !== 3 || pos1.lockedProfitInr !== 1400) {
    throw new Error('Stage 3 failed');
  }

  // Step 4.4: Live tick moves premium to ₹46.00 (+16 pts * 250 = +₹4,000)
  await engine.evaluateOpenPositionsTick({
    liveOptionLtpMap: { 'RELIANCE26NOV1340CE': 46.0 },
    executeBrokerExit: async () => {}
  });
  console.log(`  At Premium ₹46.00 (+₹4,000 PnL):`);
  console.log(`    Ladder Stage: ${pos1.ladderStage} (Expected: 4)`);
  console.log(`    Locked Profit: ₹${pos1.lockedProfitInr} (Expected: ₹3,000)`);
  if (pos1.ladderStage !== 4 || pos1.lockedProfitInr !== 3000) {
    throw new Error('Stage 4 failed');
  }

  // Step 4.5: Live tick moves premium to ₹65.00 (+35 pts * 250 = +₹8,750 Runner!)
  await engine.evaluateOpenPositionsTick({
    liveOptionLtpMap: { 'RELIANCE26NOV1340CE': 65.0 },
    executeBrokerExit: async () => {}
  });
  console.log(`  At Premium ₹65.00 (+₹8,750 PnL Runner):`);
  console.log(`    Ladder Stage: ${pos1.ladderStage} (Expected: 5)`);
  console.log(`    Peak Profit: ₹${pos1.peakProfitInr}`);
  console.log(`    Dynamic Locked Profit (Peak - ₹1,000): ₹${pos1.lockedProfitInr} (Expected: ₹7,750)`);
  if (pos1.ladderStage !== 5 || pos1.lockedProfitInr !== 7750) {
    throw new Error('Stage 5 Parabolic Runner failed');
  }

  // Step 4.6: Reversal tick hits trailing stop
  let exitedOrder: any = null;
  await engine.evaluateOpenPositionsTick({
    liveOptionLtpMap: { 'RELIANCE26NOV1340CE': 60.5 }, // Dropped below ₹61.0 (7750/250 + 30 = 61.0)
    executeBrokerExit: async (order) => {
      exitedOrder = order;
      console.log(`\n  [Broker Exit Callback Triggered!]: ${order.side} ${order.qty}x ${order.optionSymbol} @ ₹${order.price} | Tag: ${order.tag}`);
    }
  });

  if (!exitedOrder || exitedOrder.tag !== 'LADDER_TRAIL_HIT') {
    throw new Error('Expected trailing exit execution');
  }

  console.log(`\n✅ ALL TESTS PASSED SUCCESSFULLY! 100% SPEC COMPLIANT.`);
}

testSignalRoutingAndLadder().catch(err => {
  console.error('❌ Test failed:', err);
  process.exit(1);
});
