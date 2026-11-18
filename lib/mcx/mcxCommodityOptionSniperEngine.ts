/**
 * FILE: lib/mcx/mcxCommodityOptionSniperEngine.ts
 * ============================================================================
 * MCX COMMODITY 15M S&R + 5M SNIPER ENGINE (CRUDEOIL, NATURALGAS, GOLD, SILVER, COPPER)
 * Core Architecture:
 *   1. 15-Min Macro S&R: Maps Major Demand & Supply Pivots across Session
 *   2. 5-Min Micro Trigger: Session VWAP + EMA 9/21/50 + Price Action Rejection
 *   3. S&R Confluence:
 *      - Bouncing off 15m Support -> Buy ATM Call Option (CE)
 *      - Rejecting off 15m Resistance -> Buy ATM Put Option (PE)
 *   4. Risk & Trailing Ladder:
 *      - Hard Stop Loss: Strictly capped at -₹2,500 per lot
 *      - TP1 (+₹500): Move SL to Cost + Buffer (100% Risk-Free)
 *      - TP2 (+₹1,000): Lock +₹600
 *      - +₹2,000 (Lock +₹1,400) | +₹4,000 (Lock +₹3,000)
 *      - +₹8,000+ Runner: Lock +₹6,500, then trail tightly ₹1,000 behind peak
 *      - Mandatory Auto Square-Off: 11:20 PM IST
 * ============================================================================
 */

import { UniversalIndianMarketConnector } from '../bharat/universalIndianMarketConnector.ts';

export interface McxCandle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface McxCommodityConfig {
  symbol: string;
  lotSize: number;
  strikeStep: number;
  tickSize: number;
  activeFromHour: number; // 9 = 09:00 AM
  activeToHour: number;   // 23 = 11:00 PM
}

export interface McxSupportResistance {
  majorResistance: number;
  majorSupport: number;
  swingHighs: number[];
  swingLows: number[];
  rangePosPct: number;
}

export interface McxSignalResult {
  approved: boolean;
  commoditySymbol: string;
  underlyingLtp: number;
  action: 'BUY_ATM_CE' | 'BUY_ATM_PE' | 'WAIT';
  atmStrike: number;
  strikeStep: number;
  lotSize: number;
  patternTag: string;
  reason: string;
  sr15m: McxSupportResistance;
  targetResistanceWall: number;
  invalidationSupportWall: number;
  runwayPoints: number;
  riskRewardRatio: number;
  maxRiskInr: number;
}

export interface ActiveMcxOptionPosition {
  id: string;
  commoditySymbol: string;
  optionSymbol: string;
  optionType: 'CE' | 'PE';
  strike: number;
  lotSize: number;
  qty: number;
  entryPremium: number;
  currentPremium: number;
  initialSlPremium: number;
  currentSlPremium: number;
  unrealizedPnlInr: number;
  lockedProfitInr: number;
  peakProfitInr: number;
  ladderStage: number;
  openedAtIst: string;
}

export interface ClosedMcxTrade {
  id: string;
  commoditySymbol: string;
  optionSymbol: string;
  optionType: 'CE' | 'PE';
  lotSize: number;
  qty: number;
  entryPremium: number;
  exitPremium: number;
  netPnlInr: number;
  ladderStageReached: number;
  exitReason:
    | 'TP1_TRAIL_HIT'
    | 'TP2_TRAIL_HIT'
    | 'LADDER_TRAIL_HIT'
    | 'RUNNER_TRAIL_HIT'
    | 'HARD_SL_2500_HIT'
    | 'MCX_AUTO_SQUARE_OFF_1120PM';
  closedAtIst: string;
}

export class McxCommodityOptionSniperEngine {
  // MCX Liquid F&O Commodities Whitelist
  public static readonly MCX_WHITELIST: Record<string, McxCommodityConfig> = {
    CRUDEOIL: {
      symbol: 'CRUDEOIL',
      lotSize: 100, // 1 point = ₹100
      strikeStep: 50,
      tickSize: 1,
      activeFromHour: 9,
      activeToHour: 23,
    },
    NATURALGAS: {
      symbol: 'NATURALGAS',
      lotSize: 1250, // 1 point = ₹1,250
      strikeStep: 2.5,
      tickSize: 0.1,
      activeFromHour: 9,
      activeToHour: 23,
    },
    GOLD: {
      symbol: 'GOLD',
      lotSize: 1, // 100 grams
      strikeStep: 100,
      tickSize: 1,
      activeFromHour: 9,
      activeToHour: 23,
    },
    SILVER: {
      symbol: 'SILVER',
      lotSize: 1, // 30 kg lot
      strikeStep: 500,
      tickSize: 1,
      activeFromHour: 9,
      activeToHour: 23,
    },
    COPPER: {
      symbol: 'COPPER',
      lotSize: 2500, // 1 point = ₹2,500
      strikeStep: 5,
      tickSize: 0.05,
      activeFromHour: 9,
      activeToHour: 23,
    },
  };

  private activePositions: Map<string, ActiveMcxOptionPosition> = new Map();
  private closedTrades: ClosedMcxTrade[] = [];

  public getActivePositions(): ActiveMcxOptionPosition[] {
    return Array.from(this.activePositions.values());
  }

  public getClosedTrades(): ClosedMcxTrade[] {
    return [...this.closedTrades];
  }

  /**
   * 1. 15-Minute Macro Support & Resistance Calculator for MCX
   */
  public static calculate15mSupportResistance(candles15m: McxCandle[]): McxSupportResistance {
    const clean = candles15m.filter((c) => c && c.close > 0);
    if (clean.length < 20) {
      return {
        majorResistance: 0,
        majorSupport: 0,
        swingHighs: [],
        swingLows: [],
        rangePosPct: 0.5,
      };
    }

    const currentPrice = clean[clean.length - 1].close;
    const lookback = clean.slice(-48); // Last 12 hours of trading
    const swingHighs: number[] = [];
    const swingLows: number[] = [];

    for (let i = 2; i < lookback.length - 2; i++) {
      const b = lookback[i];
      if (
        b.high >= lookback[i - 1].high &&
        b.high >= lookback[i - 2].high &&
        b.high >= lookback[i + 1].high &&
        b.high >= lookback[i + 2].high
      ) {
        swingHighs.push(b.high);
      }
      if (
        b.low <= lookback[i - 1].low &&
        b.low <= lookback[i - 2].low &&
        b.low <= lookback[i + 1].low &&
        b.low <= lookback[i + 2].low
      ) {
        swingLows.push(b.low);
      }
    }

    const windowHigh = Math.max(...lookback.map((c) => c.high));
    const windowLow = Math.min(...lookback.map((c) => c.low));
    if (!swingHighs.includes(windowHigh)) swingHighs.push(windowHigh);
    if (!swingLows.includes(windowLow)) swingLows.push(windowLow);

    const rangePosPct = (currentPrice - windowLow) / Math.max(windowHigh - windowLow, 1e-8);

    return {
      majorResistance: windowHigh,
      majorSupport: windowLow,
      swingHighs: swingHighs.sort((a, b) => a - b),
      swingLows: swingLows.sort((a, b) => a - b),
      rangePosPct,
    };
  }

  /**
   * 2. Evaluates 15m S&R + 5m Indicators + Price Action for MCX
   */
  public static evaluateSetup(params: {
    commoditySymbol: string;
    candles15m: McxCandle[];
    candles5m: McxCandle[];
  }): McxSignalResult {
    const config = this.MCX_WHITELIST[params.commoditySymbol];
    if (!config) {
      return this.reject(params.commoditySymbol, 'COMMODITY_NOT_IN_WHITELIST');
    }

    const { candles15m, candles5m } = params;
    if (candles15m.length < 24 || candles5m.length < 40) {
      return this.reject(config.symbol, 'INSUFFICIENT_CANDLES');
    }

    const c0 = candles5m[candles5m.length - 1];
    const c1 = candles5m[candles5m.length - 2];
    const spotPrice = c0.close;

    // STEP 1: Compute 15-Minute S&R
    const sr15m = this.calculate15mSupportResistance(candles15m);
    if (sr15m.majorResistance === 0 || sr15m.majorSupport === 0) {
      return this.reject(config.symbol, 'INVALID_15M_SR');
    }

    // STEP 2: Compute 5-Minute Indicators
    const closes5m = candles5m.map((c) => c.close);
    const vwap5m = this.computeSessionVwap(candles5m.slice(-90));
    const ema9 = this.computeEma(closes5m, 9);
    const ema21 = this.computeEma(closes5m, 21);
    const rsi14 = this.computeRsi(closes5m, 14);

    const prior20 = candles5m.slice(-21, -1);
    const avgVol =
      prior20.reduce((sum, b) => sum + (b.volume || 1), 0) / Math.max(1, prior20.length);
    const rvol = avgVol > 0 ? (c0.volume || avgVol) / avgVol : 1.0;

    // STEP 3: 5-Minute Price Action Patterns
    const range0 = Math.max(c0.high - c0.low, 1e-8);
    const body0 = Math.abs(c0.close - c0.open);
    const lowerWick0 = (Math.min(c0.open, c0.close) - c0.low) / range0;
    const upperWick0 = (c0.high - Math.max(c0.open, c0.close)) / range0;

    const isBullishPinbar =
      c0.close > c0.open && lowerWick0 >= 0.35 && upperWick0 <= 0.25;
    const isBullishEngulfing =
      c0.close > c0.open &&
      c1.close < c1.open &&
      c0.close > (c1.open + c1.close) / 2 &&
      body0 / range0 >= 0.42;
    const isBullishReclaim =
      c0.close > c0.open && c0.close > c1.high && body0 / range0 >= 0.45;

    const isBearishPinbar =
      c0.close < c0.open && upperWick0 >= 0.35 && lowerWick0 <= 0.25;
    const isBearishEngulfing =
      c0.close < c0.open &&
      c1.close > c1.open &&
      c0.close < (c1.open + c1.close) / 2 &&
      body0 / range0 >= 0.42;
    const isBearishBreakdown =
      c0.close < c0.open && c0.close < c1.low && body0 / range0 >= 0.45;

    // STEP 4: 15-Minute S&R Proximity & Runway Calculations
    const validSupports = sr15m.swingLows.filter((l) => l <= spotPrice);
    const nearestSupport =
      validSupports.length > 0 ? validSupports[validSupports.length - 1] : sr15m.majorSupport;

    const validResistances = sr15m.swingHighs.filter((h) => h >= spotPrice);
    const nearestResistance =
      validResistances.length > 0 ? validResistances[0] : sr15m.majorResistance;

    const targetResistanceWall = Math.max(nearestResistance, sr15m.majorResistance);
    const targetSupportWall = Math.min(nearestSupport, sr15m.majorSupport);

    const runwayToResistance = targetResistanceWall - spotPrice;
    const runwayToSupport = spotPrice - targetSupportWall;

    const distToResistancePct = runwayToResistance / spotPrice;
    const distToSupportPct = runwayToSupport / spotPrice;

    const rsiPrev = this.computeRsi(closes5m.slice(0, -1), 14);
    const hasBullishPa = isBullishPinbar || isBullishEngulfing || isBullishReclaim;
    const hasBearishPa = isBearishPinbar || isBearishEngulfing || isBearishBreakdown;

    const recent3Low = Math.min(
      c0.low,
      c1.low,
      candles5m[candles5m.length - 3]?.low ?? c0.low
    );
    const recent3High = Math.max(
      c0.high,
      c1.high,
      candles5m[candles5m.length - 3]?.high ?? c0.high
    );

    // =========================================================================
    // BUY ATM CE: EITHER (MODE 1: ZERO-LAG 15M SUPPORT REVERSAL)
    //             OR     (MODE 2: TREND VWAP/EMA PULLBACK CONTINUATION)
    // =========================================================================
    const isAt15mSupport =
      distToSupportPct <= 0.0045 ||
      sr15m.rangePosPct <= 0.35 ||
      recent3Low <= nearestSupport * 1.0020;

    // Mode 1 (Support Reversal): No lagging VWAP/EMA cross required at the bottom!
    const mode1SupportReversalBuy =
      isAt15mSupport &&
      hasBullishPa &&
      rsi14 >= 25 &&
      rsi14 <= 62 &&
      rsi14 >= rsiPrev - 1.0 &&
      rvol >= 0.65;

    // Mode 2 (Trend Pullback Buy): Price in uptrend above VWAP/EMA21 pulling back to EMA9/21/VWAP
    const mode2TrendPullbackBuy =
      spotPrice >= vwap5m * 0.998 &&
      ema9 >= ema21 * 0.9985 &&
      recent3Low <= Math.max(ema9, ema21, vwap5m) * 1.0030 &&
      hasBullishPa &&
      rsi14 >= 45 &&
      rsi14 <= 72 &&
      sr15m.rangePosPct <= 0.72 &&
      rvol >= 0.65;

    const approvedBuyCe =
      (mode1SupportReversalBuy || mode2TrendPullbackBuy) &&
      distToResistancePct >= 0.0055;

    if (approvedBuyCe) {
      const atmStrike = Math.round(spotPrice / config.strikeStep) * config.strikeStep;
      const invalidationPrice = Number((nearestSupport * (1 - 0.0015)).toFixed(2));
      const targetWall = Number((nearestResistance * (1 - 0.0008)).toFixed(2));
      const riskPoints = Math.max(1, spotPrice - invalidationPrice);
      const rr = Number((runwayToResistance / riskPoints).toFixed(2));

      return {
        approved: true,
        commoditySymbol: config.symbol,
        underlyingLtp: spotPrice,
        action: 'BUY_ATM_CE',
        atmStrike,
        strikeStep: config.strikeStep,
        lotSize: config.lotSize,
        patternTag: mode1SupportReversalBuy
          ? (isBullishPinbar
              ? 'MCX_15M_SUPPORT_HAMMER_BOUNCE'
              : isBullishEngulfing
              ? 'MCX_15M_SUPPORT_ENGULFING_RECLAIM'
              : 'MCX_15M_SUPPORT_STRUCTURE_BREAKOUT')
          : 'MCX_15M_TREND_PULLBACK_BUY',
        reason: mode1SupportReversalBuy
          ? `MCX_15M_SUPPORT_REVERSAL (Supp=${nearestSupport.toFixed(1)}, ResTarget=${targetWall.toFixed(1)}, RR=${rr})`
          : `MCX_15M_TREND_PULLBACK (Supp=${nearestSupport.toFixed(1)}, ResTarget=${targetWall.toFixed(1)}, RR=${rr})`,
        sr15m,
        targetResistanceWall: targetWall,
        invalidationSupportWall: invalidationPrice,
        runwayPoints: runwayToResistance,
        riskRewardRatio: rr,
        maxRiskInr: 2500,
      };
    }

    // =========================================================================
    // BUY ATM PE: EITHER (MODE 1: ZERO-LAG 15M RESISTANCE REVERSAL)
    //             OR     (MODE 2: TREND VWAP/EMA PULLBACK CONTINUATION)
    // =========================================================================
    const isAt15mResistance =
      distToResistancePct <= 0.0045 ||
      sr15m.rangePosPct >= 0.65 ||
      recent3High >= nearestResistance * 0.9980;

    // Mode 1 (Resistance Reversal - Catches the exact 02:00 PM Crude & 10:55 AM Silver Tops!):
    // No lagging EMA9 < EMA21 or Price < VWAP required at the top!
    const mode1ResistanceReversalSell =
      isAt15mResistance &&
      hasBearishPa &&
      rsi14 >= 38 &&
      rsi14 <= 75 &&
      rsi14 <= rsiPrev + 1.0 &&
      rvol >= 0.65;

    // Mode 2 (Trend Pullback Sell): Price in downtrend below VWAP/EMA21 bouncing into EMA9/21/VWAP
    const mode2TrendPullbackSell =
      spotPrice <= vwap5m * 1.002 &&
      ema9 <= ema21 * 1.0015 &&
      recent3High >= Math.min(ema9, ema21, vwap5m) * 0.9970 &&
      hasBearishPa &&
      rsi14 >= 28 &&
      rsi14 <= 56 &&
      sr15m.rangePosPct >= 0.28 &&
      rvol >= 0.65;

    const approvedBuyPe =
      (mode1ResistanceReversalSell || mode2TrendPullbackSell) &&
      distToSupportPct >= 0.0055;

    if (approvedBuyPe) {
      const atmStrike = Math.round(spotPrice / config.strikeStep) * config.strikeStep;
      const invalidationPrice = Number((nearestResistance * (1 + 0.0015)).toFixed(2));
      const targetWall = Number((nearestSupport * (1 + 0.0008)).toFixed(2));
      const riskPoints = Math.max(1, invalidationPrice - spotPrice);
      const rr = Number((runwayToSupport / riskPoints).toFixed(2));

      return {
        approved: true,
        commoditySymbol: config.symbol,
        underlyingLtp: spotPrice,
        action: 'BUY_ATM_PE',
        atmStrike,
        strikeStep: config.strikeStep,
        lotSize: config.lotSize,
        patternTag: mode1ResistanceReversalSell
          ? (isBearishPinbar
              ? 'MCX_15M_RESISTANCE_SHOOTING_STAR'
              : isBearishEngulfing
              ? 'MCX_15M_RESISTANCE_ENGULFING_REJECT'
              : 'MCX_15M_RESISTANCE_STRUCTURE_BREAKDOWN')
          : 'MCX_15M_TREND_PULLBACK_SELL',
        reason: mode1ResistanceReversalSell
          ? `MCX_15M_RESISTANCE_REVERSAL (Res=${nearestResistance.toFixed(1)}, SuppTarget=${targetWall.toFixed(1)}, RR=${rr})`
          : `MCX_15M_TREND_PULLBACK (Res=${nearestResistance.toFixed(1)}, SuppTarget=${targetWall.toFixed(1)}, RR=${rr})`,
        sr15m,
        targetResistanceWall: targetWall,
        invalidationSupportWall: invalidationPrice,
        runwayPoints: runwayToSupport,
        riskRewardRatio: rr,
        maxRiskInr: 2500,
      };
    }

    return this.reject(config.symbol, 'NO_MCX_15M_SR_SETUP', sr15m, spotPrice);
  }

  /**
   * 3. Handle Signal & Fire ATM Option Broker Order
   */
  public async executeOptionEntry(params: {
    decision: McxSignalResult;
    currentExpiryCode?: string; // e.g. "26NOV"
    getOptionPremium: (optSymbol: string) => Promise<number>;
    sendBrokerOrder: (order: {
      optionSymbol: string;
      side: 'BUY';
      qty: number;
      price: number;
      tag: string;
    }) => Promise<void>;
  }): Promise<{ status: string; position?: ActiveMcxOptionPosition }> {
    const { decision } = params;
    if (!decision.approved || decision.action === 'WAIT') {
      return { status: 'NO_ENTRY' };
    }

    if (this.activePositions.has(decision.commoditySymbol)) {
      return { status: `VETO: Position already active for ${decision.commoditySymbol}` };
    }

    const optionType = decision.action === 'BUY_ATM_CE' ? 'CE' : 'PE';

    // 1. Resolve Exact Real Exchange-Listed Contract from Official ScripMaster (Zero fake strikes!)
    const realContract = await UniversalIndianMarketConnector.resolveRealListedAtmOption({
      exchange: 'MCX',
      underlyingName: decision.commoditySymbol,
      realSpotLtp: decision.underlyingLtp,
      optionType,
    });

    if (!realContract) {
      return {
        status: `STRICT_VETO: No real exchange-listed ${optionType} contract found in ScripMaster for MCX ${decision.commoditySymbol} @ spot ₹${decision.underlyingLtp}`,
      };
    }

    const optionSymbol = realContract.symbol;
    const atmStrike = realContract.strike;
    const lotSize = realContract.lotSize;

    const premium = await params.getOptionPremium(optionSymbol);
    if (!premium || premium <= 0) {
      return { status: `STRICT_VETO: Unable to fetch live option premium for listed MCX contract ${optionSymbol}` };
    }

    // STRICT RISK CAP: Maximum -₹2,500 Loss per Lot
    // Max drop in points = 2500 / lotSize
    const maxDropPoints = 2500 / lotSize;
    const initialSlPremium = Number(Math.max(0.5, premium - maxDropPoints).toFixed(2));

    const position: ActiveMcxOptionPosition = {
      id: `${optionSymbol}-${Date.now()}`,
      commoditySymbol: decision.commoditySymbol,
      optionSymbol,
      optionType,
      strike: atmStrike,
      lotSize,
      qty: lotSize,
      entryPremium: premium,
      currentPremium: premium,
      initialSlPremium,
      currentSlPremium: initialSlPremium,
      unrealizedPnlInr: 0,
      lockedProfitInr: 0,
      peakProfitInr: 0,
      ladderStage: 0,
      openedAtIst: this.getIstTimeStr(),
    };

    this.activePositions.set(decision.commoditySymbol, position);

    await params.sendBrokerOrder({
      optionSymbol,
      side: 'BUY',
      qty: decision.lotSize,
      price: premium,
      tag: decision.patternTag,
    });

    return { status: 'ORDER_FIRED', position };
  }

  /**
   * 4. Live Tick Manager: TP1 (+500), TP2 (+1000), Ladder (+8000),
   *    and 11:20 PM IST Mandatory Square-Off
   */
  public async evaluateOpenPositionsTick(params: {
    livePremiumMap: Record<string, number>;
    sendBrokerExit: (order: {
      optionSymbol: string;
      side: 'SELL';
      qty: number;
      price: number;
      tag: string;
    }) => Promise<void>;
    nowEpochMs?: number;
  }): Promise<void> {
    const istMinutes = this.getIstMinutes(params.nowEpochMs);
    // Mandatory MCX Auto Square-Off at 11:20 PM IST (11:20 PM = 23 * 60 + 20 = 1400)
    // Only fire during the market close window (23:20 to 23:45 IST)
    const isAutoSquareOff = istMinutes >= 23 * 60 + 20 && istMinutes <= 23 * 60 + 45;

    for (const [sym, pos] of Array.from(this.activePositions.entries())) {
      const livePremium = params.livePremiumMap[pos.optionSymbol] ?? pos.currentPremium;
      pos.currentPremium = livePremium;

      const pnlPoints = livePremium - pos.entryPremium;
      pos.unrealizedPnlInr = Number((pnlPoints * pos.qty).toFixed(2));
      pos.peakProfitInr = Math.max(pos.peakProfitInr, pos.unrealizedPnlInr);

      // --- RULE 1: MANDATORY 11:20 PM IST SQUARE-OFF ---
      if (isAutoSquareOff) {
        await this.closePosition(
          sym,
          pos,
          livePremium,
          'MCX_AUTO_SQUARE_OFF_1120PM',
          params.sendBrokerExit,
          params.nowEpochMs
        );
        continue;
      }

      // --- RULE 2: HARD SL (-₹2,500 PER LOT) OR TRAILING PROFIT SL HIT ---
      if (
        livePremium <= pos.currentSlPremium ||
        pos.unrealizedPnlInr <= -2500 ||
        (pos.lockedProfitInr > 0 && pos.unrealizedPnlInr <= pos.lockedProfitInr)
      ) {
        const exitReason =
          pos.ladderStage === 0
            ? 'HARD_SL_2500_HIT'
            : pos.ladderStage === 1
            ? 'TP1_TRAIL_HIT'
            : pos.ladderStage === 2
            ? 'TP2_TRAIL_HIT'
            : pos.ladderStage >= 8
            ? 'RUNNER_TRAIL_HIT'
            : 'LADDER_TRAIL_HIT';

        await this.closePosition(sym, pos, livePremium, exitReason, params.sendBrokerExit, params.nowEpochMs);
        continue;
      }

      // --- RULE 3: INFINITE PROGRESSIVE PROFIT LADDER (TP1: +₹500, TP2: +₹1,000, TP3: +₹1,500 ... INFINITE) ---
      if (pos.unrealizedPnlInr >= 500) {
        const step = Math.floor(pos.unrealizedPnlInr / 500);
        // Step 1 (+500): Lock +150 (brokerage shielded, risk free)
        // Step 2 (+1000): Lock +600
        // Step 3 (+1500): Lock +1050
        // Step n: Lock 150 + (n - 1) * 450
        const stepLocked = step === 1 ? 150 : 150 + (step - 1) * 450;
        // For runners (peak >= 4000), trail at least peak - 1000 dynamically with zero upper limit
        const dynamicTrail =
          pos.peakProfitInr >= 4000
            ? Math.max(stepLocked, pos.peakProfitInr - 1000)
            : stepLocked;
        const newLock = Math.max(pos.lockedProfitInr, dynamicTrail);

        if (newLock > pos.lockedProfitInr) {
          pos.lockedProfitInr = newLock;
          pos.ladderStage = Math.max(pos.ladderStage, step);
          pos.currentSlPremium = this.calculateTargetSl(pos, newLock);
        }
      }
    }
  }

  private calculateTargetSl(pos: ActiveMcxOptionPosition, targetPnlInr: number): number {
    const requiredPoints = targetPnlInr / pos.qty;
    return Number((pos.entryPremium + requiredPoints).toFixed(2));
  }

  private async closePosition(
    sym: string,
    pos: ActiveMcxOptionPosition,
    exitPremium: number,
    exitReason: ClosedMcxTrade['exitReason'],
    sendBrokerExit: (order: {
      optionSymbol: string;
      side: 'SELL';
      qty: number;
      price: number;
      tag: string;
    }) => Promise<void>,
    nowEpochMs?: number
  ): Promise<void> {
    const netPnlInr = Number(((exitPremium - pos.entryPremium) * pos.qty).toFixed(2));

    this.activePositions.delete(sym);
    this.closedTrades.unshift({
      id: pos.id,
      commoditySymbol: pos.commoditySymbol,
      optionSymbol: pos.optionSymbol,
      optionType: pos.optionType,
      lotSize: pos.lotSize,
      qty: pos.qty,
      entryPremium: pos.entryPremium,
      exitPremium,
      netPnlInr,
      ladderStageReached: pos.ladderStage,
      exitReason,
      closedAtIst: this.getIstTimeStr(nowEpochMs),
    });

    await sendBrokerExit({
      optionSymbol: pos.optionSymbol,
      side: 'SELL',
      qty: pos.qty,
      price: exitPremium,
      tag: exitReason,
    });
  }

  // --- TECHNICAL INDICATOR HELPERS ---

  private static computeSessionVwap(candles: McxCandle[]): number {
    let pv = 0;
    let vol = 0;
    for (const c of candles) {
      const typical = (c.high + c.low + c.close) / 3;
      const v = c.volume > 0 ? c.volume : 1;
      pv += typical * v;
      vol += v;
    }
    return vol > 0 ? pv / vol : candles[candles.length - 1].close;
  }

  private static computeEma(values: number[], period: number): number {
    if (values.length === 0) return 0;
    const k = 2 / (period + 1);
    let ema = values[0];
    for (let i = 1; i < values.length; i++) {
      ema = values[i] * k + ema * (1 - k);
    }
    return ema;
  }

  private static computeRsi(values: number[], period = 14): number {
    if (values.length <= period) return 50;
    let gains = 0;
    let losses = 0;
    for (let i = values.length - period; i < values.length; i++) {
      const diff = values[i] - values[i - 1];
      if (diff >= 0) gains += diff;
      else losses -= diff;
    }
    if (losses === 0) return 100;
    return 100 - 100 / (1 + gains / losses);
  }

  private static reject(
    commoditySymbol: string,
    reason: string,
    sr15m?: McxSupportResistance,
    underlyingLtp?: number
  ): McxSignalResult {
    return {
      approved: false,
      commoditySymbol,
      underlyingLtp: underlyingLtp || 0,
      action: 'WAIT',
      atmStrike: 0,
      strikeStep: 0,
      lotSize: 0,
      patternTag: 'WAIT',
      reason,
      sr15m: sr15m || {
        majorResistance: 0,
        majorSupport: 0,
        swingHighs: [],
        swingLows: [],
        rangePosPct: 0.5,
      },
      targetResistanceWall: sr15m ? sr15m.majorResistance : 0,
      invalidationSupportWall: sr15m ? sr15m.majorSupport : 0,
      runwayPoints: 0,
      riskRewardRatio: 0,
      maxRiskInr: 2500,
    };
  }

  private getIstMinutes(nowEpochMs?: number): number {
    const base = nowEpochMs ? new Date(nowEpochMs) : new Date();
    const ist = new Date(base.getTime() + 5.5 * 60 * 60 * 1000);
    return ist.getUTCHours() * 60 + ist.getUTCMinutes();
  }

  private getIstTimeStr(nowEpochMs?: number): string {
    const base = nowEpochMs ? new Date(nowEpochMs) : new Date();
    const ist = new Date(base.getTime() + 5.5 * 60 * 60 * 1000);
    return `${String(ist.getUTCHours()).padStart(2, '0')}:${String(ist.getUTCMinutes()).padStart(
      2,
      '0'
    )}:${String(ist.getUTCSeconds()).padStart(2, '0')} IST`;
  }
}
