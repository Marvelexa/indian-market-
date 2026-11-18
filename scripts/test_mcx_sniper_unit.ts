/**
 * scripts/test_mcx_sniper_unit.ts
 * Unit and integration tests for McxCommodityOptionSniperEngine
 */

import {
  McxCommodityOptionSniperEngine,
  type McxCandle
} from '../lib/mcx/mcxCommodityOptionSniperEngine.ts';
import { aggregateMcx5mTo15m } from '../mcxServer.ts';

function createSyntheticCandles(basePrice: number, count: number): McxCandle[] {
  const candles: McxCandle[] = [];
  const startTs = Date.now() - count * 5 * 60 * 1000;
  let price = basePrice;
  for (let i = 0; i < count; i++) {
    const ts = startTs + i * 5 * 60 * 1000;
    const delta = (Math.random() - 0.5) * (basePrice * 0.002);
    const open = price;
    price += delta;
    const high = Math.max(open, price) + Math.random() * (basePrice * 0.001);
    const low = Math.min(open, price) - Math.random() * (basePrice * 0.001);
    const close = price;
    candles.push({ timestamp: ts, open, high, low, close, volume: 500 });
  }
  return candles;
}

async function runTests() {
  console.log('='.repeat(75));
  console.log('🧪 TESTING MCX COMMODITY OPTION SNIPER ENGINE');
  console.log('='.repeat(75));

  // TEST 1: Whitelist & Lot Sizes
  console.log('\n--- TEST 1: MCX Whitelist & Lot Sizes ---');
  const whitelist = McxCommodityOptionSniperEngine.MCX_WHITELIST;
  console.log(`Tracked commodities: ${Object.keys(whitelist).join(', ')}`);
  if (
    whitelist.CRUDEOIL.lotSize === 100 &&
    whitelist.NATURALGAS.lotSize === 1250 &&
    whitelist.GOLD.lotSize === 1 &&
    whitelist.SILVER.lotSize === 1 &&
    whitelist.COPPER.lotSize === 2500
  ) {
    console.log('✅ TEST 1 PASSED: All 5 MCX commodities configured with exact lot sizes.');
  } else {
    throw new Error('TEST 1 FAILED: Lot size mismatch.');
  }

  // TEST 2: Strike Step Resolution
  console.log('\n--- TEST 2: Strike Step Resolution ---');
  const crudePrice = 7572.4;
  const crudeStrike = Math.round(crudePrice / whitelist.CRUDEOIL.strikeStep) * whitelist.CRUDEOIL.strikeStep;
  console.log(`Crude Spot: ₹${crudePrice} -> ATM Strike: ₹${crudeStrike} (Step: ${whitelist.CRUDEOIL.strikeStep})`);

  const ngPrice = 276.1;
  const ngStrike = Math.round(ngPrice / whitelist.NATURALGAS.strikeStep) * whitelist.NATURALGAS.strikeStep;
  console.log(`Natural Gas Spot: ₹${ngPrice} -> ATM Strike: ₹${ngStrike} (Step: ${whitelist.NATURALGAS.strikeStep})`);

  if (crudeStrike === 7550 && ngStrike === 275) {
    console.log('✅ TEST 2 PASSED: ATM strikes resolved accurately.');
  } else {
    throw new Error(`TEST 2 FAILED: Got Crude ${crudeStrike}, NG ${ngStrike}`);
  }

  // TEST 3: 5m to 15m Aggregation
  console.log('\n--- TEST 3: 5m to 15m Aggregation ---');
  const c5m = createSyntheticCandles(7500, 75);
  const c15m = aggregateMcx5mTo15m(c5m);
  console.log(`5m bars: ${c5m.length} -> 15m bars: ${c15m.length}`);
  if (c15m.length >= 24 && c15m.length <= 26) {
    console.log('✅ TEST 3 PASSED: 15m aggregation accurate.');
  } else {
    throw new Error(`TEST 3 FAILED: Unexpected 15m count ${c15m.length}`);
  }

  // TEST 4: Entry & Hard SL Capping (-₹2,500 Risk)
  console.log('\n--- TEST 4: Entry & Risk Shield (-₹2,500 Hard SL) ---');
  const sniper = new McxCommodityOptionSniperEngine();
  const fakeDecision = {
    approved: true,
    commoditySymbol: 'CRUDEOIL',
    underlyingLtp: 7550,
    action: 'BUY_ATM_CE' as const,
    atmStrike: 7550,
    strikeStep: 50,
    lotSize: 100,
    patternTag: 'MCX_15M_SUPPORT_HAMMER_BOUNCE',
    reason: 'TEST_BOUNCE',
    sr15m: {
      majorResistance: 7650,
      majorSupport: 7500,
      swingHighs: [7650],
      swingLows: [7500],
      rangePosPct: 0.25
    },
    targetResistanceWall: 7640,
    invalidationSupportWall: 7490,
    runwayPoints: 90,
    riskRewardRatio: 1.5,
    maxRiskInr: 2500
  };

  let brokerOrderFired: any = null;
  const entryRes = await sniper.executeOptionEntry({
    decision: fakeDecision,
    currentExpiryCode: '26NOV',
    getOptionPremium: async () => 150.0,
    sendBrokerOrder: async (order) => {
      brokerOrderFired = order;
    }
  });

  console.log(`Order status: ${entryRes.status}`);
  console.log(`Option Symbol: ${entryRes.position?.optionSymbol}`);
  console.log(`Entry Premium: ₹${entryRes.position?.entryPremium}`);
  console.log(`Current SL Premium: ₹${entryRes.position?.currentSlPremium}`);
  const maxLoss = (entryRes.position!.entryPremium - entryRes.position!.currentSlPremium) * entryRes.position!.qty;
  console.log(`Max Loss per lot: -₹${maxLoss.toFixed(2)}`);

  if (entryRes.position?.optionSymbol === 'CRUDEOIL26NOV7550CE' && Math.abs(maxLoss - 2500) < 1) {
    console.log('✅ TEST 4 PASSED: Hard SL strictly capped at -₹2,500.');
  } else {
    throw new Error(`TEST 4 FAILED: Max loss was ${maxLoss}`);
  }

  // TEST 5: Trailing Ladder Stages (+₹500 -> Lock +₹150, +₹1,000 -> Lock +₹600)
  console.log('\n--- TEST 5: Trailing Profit Ladder ---');
  const ltpMap: Record<string, number> = {};
  // Simulate +15 points gain in Crude option (15 * 100 = +₹1,500 profit)
  ltpMap[entryRes.position!.optionSymbol] = 165.0;

  // Use fixed test epoch time (14:00 IST) to avoid 11:20 PM auto square-off during test
  const testEpoch = new Date('2026-11-16T14:00:00+05:30').getTime();
  await sniper.evaluateOpenPositionsTick({
    livePremiumMap: ltpMap,
    sendBrokerExit: async () => {},
    nowEpochMs: testEpoch
  });

  const posAfterPump = sniper.getActivePositions()[0];
  console.log(`Stage reached: Stage ${posAfterPump.ladderStage}`);
  console.log(`Locked Profit: +₹${posAfterPump.lockedProfitInr}`);
  console.log(`Updated SL Premium: ₹${posAfterPump.currentSlPremium}`);

  if (posAfterPump.ladderStage === 3 && posAfterPump.lockedProfitInr === 1050) {
    console.log('✅ TEST 5 PASSED: Infinite Trailing Ladder successfully locked +₹1,050 profit for Stage 3 (+₹1,500 gain).');
  } else {
    throw new Error(`TEST 5 FAILED: Expected Stage 3 and +₹1,050 lock, got Stage ${posAfterPump.ladderStage} and +₹${posAfterPump.lockedProfitInr}`);
  }

  // TEST 6: 11:20 PM IST Mandatory Auto Square-Off
  console.log('\n--- TEST 6: 11:20 PM IST Auto Square-Off ---');
  let exitFired: any = null;
  const squareOffEpoch = new Date('2026-11-16T23:21:00+05:30').getTime(); // 11:21 PM IST
  await sniper.evaluateOpenPositionsTick({
    livePremiumMap: ltpMap,
    sendBrokerExit: async (order) => {
      exitFired = order;
    },
    nowEpochMs: squareOffEpoch
  });

  console.log(`Active positions count: ${sniper.getActivePositions().length}`);
  console.log(`Closed trade reason: ${sniper.getClosedTrades()[0]?.exitReason}`);
  if (sniper.getActivePositions().length === 0 && exitFired?.tag === 'MCX_AUTO_SQUARE_OFF_1120PM') {
    console.log('✅ TEST 6 PASSED: Auto Square-Off triggered at 11:20 PM IST.');
  } else {
    throw new Error('TEST 6 FAILED: Position not squared off at 11:20 PM.');
  }

  console.log('\n' + '='.repeat(75));
  console.log('🎉 ALL MCX UNIT & INTEGRATION TESTS PASSED 100%');
  console.log('='.repeat(75));
}

runTests().catch(err => {
  console.error('Test error:', err);
  process.exit(1);
});
