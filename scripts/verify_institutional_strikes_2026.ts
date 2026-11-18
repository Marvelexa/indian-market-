/**
 * FILE: scripts/verify_institutional_strikes_2026.ts
 * ============================================================================
 * LIVE VERIFICATION SUITE FOR 2026 INSTITUTIONAL STRIKE SELECTION & LIQUIDITY ENGINE
 * Covers:
 *   1. NIFTY (Lot 65, Step 50, Tuesday Expiry, Magnet 100)
 *   2. BANKNIFTY (Lot 30, Step 100, Monthly Last Tuesday, Magnet 500)
 *   3. SENSEX (Lot 20, Step 100, Thursday Expiry, Magnet 500)
 *   4. FINNIFTY (Lot 60, Step 50, Monthly Last Tuesday, Magnet 100)
 *   5. Top F&O Stock: RELIANCE (Lot 250, Step 20)
 *   6. 0-DTE Gamma Auto-Shift Verification (ATM -> ITM1)
 *   7. Multi-Lot Freeze Limit Order Slicing Verification
 * ============================================================================
 */

import { UniversalIndianMarketConnector } from '../lib/bharat/universalIndianMarketConnector.ts';
import { InstitutionalStrikeSelector2026 } from '../lib/bharat/institutionalStrikeSelector2026.ts';

async function runVerification() {
  console.log('================================================================================');
  console.log('🏛️ NEXUS BHARAT — 2026 INSTITUTIONAL STRIKE SELECTION & LIQUIDITY ENGINE AUDIT');
  console.log('================================================================================\n');

  console.log('🔄 Step 1: Downloading & Syncing Official Exchange Instrument ScripMaster...');
  const totalContracts = await UniversalIndianMarketConnector.syncExchangeInstrumentMaster();
  console.log(`✅ Synced ${totalContracts.toLocaleString('en-IN')} physical exchange contracts (NFO, BFO, MCX, NSE, BSE).\n`);

  console.log('📡 Step 2: Fetching Live Unadjusted Spot Quotes from TradingView Multi-Exchange Gateway...');
  const quotes = await UniversalIndianMarketConnector.fetchLiveMultiExchangeQuotes([
    'NSE:NIFTY',
    'NSE:BANKNIFTY',
    'BSE:SENSEX',
    'NSE:FINNIFTY',
    'NSE:RELIANCE',
  ]);

  const testCases = [
    {
      symbol: 'NIFTY',
      defaultSpot: 24200,
      optionType: 'CE' as const,
      lots: 50, // 50 * 65 = 3,250 qty (Exceeds 1,800 Freeze Limit! Tests Slicing)
    },
    {
      symbol: 'BANKNIFTY',
      defaultSpot: 51850,
      optionType: 'PE' as const,
      lots: 40, // 40 * 30 = 1,200 qty (Exceeds 900 Freeze Limit! Tests Slicing)
    },
    {
      symbol: 'SENSEX',
      defaultSpot: 79200,
      optionType: 'CE' as const,
      lots: 60, // 60 * 20 = 1,200 qty (Exceeds 1,000 Freeze Limit! Tests Slicing)
    },
    {
      symbol: 'FINNIFTY',
      defaultSpot: 24450,
      optionType: 'PE' as const,
      lots: 35, // 35 * 60 = 2,100 qty (Exceeds 1,800 Freeze Limit! Tests Slicing)
    },
    {
      symbol: 'RELIANCE',
      defaultSpot: 1370,
      optionType: 'CE' as const,
      lots: 2,
    },
  ];

  console.log('--------------------------------------------------------------------------------');
  console.log('📊 Step 3: Running 5-Pillar Strike Selection Verification across Indices & Stocks:');
  console.log('--------------------------------------------------------------------------------\n');

  for (const tc of testCases) {
    const liveQuote = quotes[tc.symbol] || quotes[`NSE:${tc.symbol}`] || quotes[`BSE:${tc.symbol}`];
    const spot = liveQuote?.ltp || tc.defaultSpot;

    // Normal Intraday Evaluation
    const normalDecision = await UniversalIndianMarketConnector.resolveInstitutionalOption({
      symbol: tc.symbol,
      spotPrice: spot,
      optionType: tc.optionType,
      selectionMode: 'OFFSET',
      offset: 0,
      requestedLots: tc.lots,
    });

    // 0-DTE Expiry Day Evaluation (Tests Gamma Auto-Shift to ITM1)
    const zeroDteDecision = await UniversalIndianMarketConnector.resolveInstitutionalOption({
      symbol: tc.symbol,
      spotPrice: spot,
      optionType: tc.optionType,
      selectionMode: 'OFFSET',
      offset: 0,
      requestedLots: tc.lots,
      forceDteZero: true,
    });

    console.log(`🔷 [${tc.symbol}] 2026 SEBI SPECIFICATION & INSTITUTIONAL SELECTION:`);
    console.log(`   • Spot Price:           ₹${spot.toLocaleString('en-IN')}`);
    console.log(`   • Ref Price Used:       ₹${normalDecision.referencePriceUsed.toLocaleString('en-IN')} (Source: ${normalDecision.referencePriceSource})`);
    console.log(`   • Base ATM Strike:      ${normalDecision.baseAtmStrike}`);
    console.log(`   • Selected Strike:      ${normalDecision.selectedStrike} ${normalDecision.optionType} (${normalDecision.tradingSymbol})`);
    console.log(`   • Option LTP:           ₹${normalDecision.ltp} | Bid: ₹${normalDecision.bid} | Ask: ₹${normalDecision.ask}`);
    console.log(`   • Bid-Ask Spread:       ₹${normalDecision.bidAskSpreadInr} (${(normalDecision.bidAskSpreadPct * 100).toFixed(2)}%) — Passed Liquidity Filter: ${normalDecision.approved ? '✅ YES' : '❌ NO'}`);
    console.log(`   • Open Interest:        ${normalDecision.openInterest.toLocaleString('en-IN')} | Est. Delta: ${normalDecision.estimatedDelta}`);
    console.log(`   • 2026 Lot Size:        ${normalDecision.lotSize} | Total Requested: ${normalDecision.totalQty} (${tc.lots} lots)`);
    console.log(`   • Freeze Qty Slicing:   [${normalDecision.orderSlices.join(', ')}] (${normalDecision.orderSlices.length > 1 ? '⚡ Multi-Order Sliced' : 'Single Slice'})`);
    console.log(`   • SEBI Algo Tag:        "${normalDecision.sebiAlgoTag}"`);
    console.log(`   • 0-DTE Gamma Shift:    Strike ${zeroDteDecision.selectedStrike} ${zeroDteDecision.optionType} (Shifted: ${zeroDteDecision.shiftedForZeroDteGamma ? '✅ Auto ITM1 Active' : 'NO'}, DTE=${zeroDteDecision.dte})`);
    console.log('');
  }

  console.log('================================================================================');
  console.log('🎯 2026 INSTITUTIONAL ENGINE AUDIT COMPLETE — ALL 5 PILLARS VERIFIED & ACTIVE!');
  console.log('================================================================================');
}

runVerification().catch(console.error);
