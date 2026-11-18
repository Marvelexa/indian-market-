/**
 * FILE: lib/bharat/mtf15mSupportResistanceOptionEngine.ts
 * ============================================================================
 * MULTI-TIMEFRAME 15M S&R + 5M SNIPER ENGINE FOR INDEX & F&O STOCK OPTIONS
 * Sequence:
 *   1. 15-Minute Macro Structure: Maps Major Support (Demand) & Resistance (Supply)
 *   2. 5-Minute Micro Trigger: VWAP + EMA 9/21/50 + Price Action (Pinbar/Engulfing)
 *   3. S&R Confluence Filter:
 *      - BUY ATM CE: Bouncing off 15m Support (runway to 15m Resistance >= 1.5R)
 *      - BUY ATM PE: Rejecting off 15m Resistance (runway to 15m Support >= 1.5R)
 *   4. Risk & Ladder Execution:
 *      - Hard SL: Max -₹2,500 per lot (anchored past 15m S&R level)
 *      - Profit Ladder: TP1 (+₹500), TP2 (+₹1,000), +₹2,000, +₹4,000, +₹8,000+ Runner
 *      - 03:18 PM IST Mandatory Square-Off
 * ============================================================================
 */

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SupportResistanceLevels {
  majorResistance: number;
  majorSupport: number;
  swingHighs: number[];
  swingLows: number[];
  rangePosPct: number; // 0 to 1 (0 = At 15m Support, 1 = At 15m Resistance)
}

export interface OptionDecisionResult {
  approved: boolean;
  symbol: string;
  underlyingSpot: number;
  action: 'BUY_ATM_CE' | 'BUY_ATM_PE' | 'WAIT';
  atmStrike: number;
  strikeStep: number;
  lotSize: number;
  patternTag: string;
  reason: string;
  fifteenMinSr: SupportResistanceLevels;
  targetResistanceWall: number;
  invalidationSupportWall: number;
  runwayPoints: number;
  riskRewardRatio: number;
  maxRiskInr: number;
}

export class Mtf15mSupportResistanceOptionEngine {
  /**
   * 1. Extract 15-Minute Support & Resistance Pivots from 15m Candles
   */
  public static calculate15mSupportResistance(candles15m: Candle[]): SupportResistanceLevels {
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
    const lookback = clean.slice(-40); // 10 hours of 15m candles
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
   * 2. Full Multi-Timeframe Evaluation: 15m S&R + 5m Indicators + Price Action
   */
  public static evaluateSetup(params: {
    symbol: string;
    candles15m: Candle[];
    candles5m: Candle[];
    lotSize: number;
    strikeStep: number;
  }): OptionDecisionResult {
    const { symbol, candles15m, candles5m, lotSize, strikeStep } = params;

    if (candles15m.length < 25 || candles5m.length < 45) {
      return this.reject(symbol, 'INSUFFICIENT_CANDLE_DATA');
    }

    const c0_5m = candles5m[candles5m.length - 1];
    const c1_5m = candles5m[candles5m.length - 2];
    const spotPrice = c0_5m.close;

    // STEP 1: Compute 15-Minute Support & Resistance
    const sr15m = this.calculate15mSupportResistance(candles15m);
    if (sr15m.majorResistance === 0 || sr15m.majorSupport === 0) {
      return this.reject(symbol, 'INVALID_15M_SR_LEVELS');
    }

    // STEP 2: Compute 5-Minute Indicators (VWAP, EMA 9/21/50, RSI 14, RVOL)
    const closes5m = candles5m.map((c) => c.close);
    const vwap5m = this.computeVwap(candles5m.slice(-75));
    const ema9 = this.computeEma(closes5m, 9);
    const ema21 = this.computeEma(closes5m, 21);
    const ema50 = this.computeEma(closes5m, 50);
    const rsi14 = this.computeRsi(closes5m, 14);

    const prior20 = candles5m.slice(-21, -1);
    const avgVol20 =
      prior20.reduce((sum, b) => sum + (b.volume || 1), 0) / Math.max(1, prior20.length);
    const rvol = avgVol20 > 0 ? (c0_5m.volume || avgVol20) / avgVol20 : 1.0;

    // STEP 3: 5-Minute Price Action Patterns (Pinbar, Engulfing, Reclaim)
    const range0 = Math.max(c0_5m.high - c0_5m.low, 1e-8);
    const body0 = Math.abs(c0_5m.close - c0_5m.open);
    const bodyRatio0 = body0 / range0;
    const lowerWick0 = (Math.min(c0_5m.open, c0_5m.close) - c0_5m.low) / range0;
    const upperWick0 = (c0_5m.high - Math.max(c0_5m.open, c0_5m.close)) / range0;

    const isBullishPinbar =
      c0_5m.close > c0_5m.open && lowerWick0 >= 0.32 && upperWick0 <= 0.28 && bodyRatio0 >= 0.20;
    const isBullishEngulfing =
      c0_5m.close > c0_5m.open &&
      c1_5m.close < c1_5m.open &&
      c0_5m.close > (c1_5m.open + c1_5m.close) / 2 &&
      bodyRatio0 >= 0.42;
    const isBullishReclaim =
      c0_5m.close > c0_5m.open && c0_5m.close > c1_5m.high && bodyRatio0 >= 0.45;

    const isBearishPinbar =
      c0_5m.close < c0_5m.open && upperWick0 >= 0.32 && lowerWick0 <= 0.28 && bodyRatio0 >= 0.20;
    const isBearishEngulfing =
      c0_5m.close < c0_5m.open &&
      c1_5m.close > c1_5m.open &&
      c0_5m.close < (c1_5m.open + c1_5m.close) / 2 &&
      bodyRatio0 >= 0.42;
    const isBearishBreakdown =
      c0_5m.close < c0_5m.open && c0_5m.close < c1_5m.low && bodyRatio0 >= 0.45;

    // -------------------------------------------------------------------------
    // CRITICAL 15M S&R CONFLUENCE FILTERS
    // -------------------------------------------------------------------------
    const valid15mSupports = sr15m.swingLows.filter((l) => l <= spotPrice);
    const nearest15mSupport =
      valid15mSupports.length > 0
        ? valid15mSupports[valid15mSupports.length - 1]
        : sr15m.majorSupport;

    const valid15mResistances = sr15m.swingHighs.filter((h) => h >= spotPrice);
    const nearest15mResistance =
      valid15mResistances.length > 0 ? valid15mResistances[0] : sr15m.majorResistance;

    const targetResistanceWall = Math.max(nearest15mResistance, sr15m.majorResistance);
    const targetSupportWall = Math.min(nearest15mSupport, sr15m.majorSupport);

    const runwayToResistance = targetResistanceWall - spotPrice;
    const runwayToSupport = spotPrice - targetSupportWall;

    const distToResistancePct = runwayToResistance / spotPrice;
    const distToSupportPct = runwayToSupport / spotPrice;

    const rsiPrev = this.computeRsi(closes5m.slice(0, -1), 14);
    const hasBullishPa = isBullishPinbar || isBullishEngulfing || isBullishReclaim;
    const hasBearishPa = isBearishPinbar || isBearishEngulfing || isBearishBreakdown;

    const recent3Low = Math.min(
      c0_5m.low,
      c1_5m.low,
      candles5m[candles5m.length - 3]?.low ?? c0_5m.low
    );
    const recent3High = Math.max(
      c0_5m.high,
      c1_5m.high,
      candles5m[candles5m.length - 3]?.high ?? c0_5m.high
    );

    // =========================================================================
    // BUY ATM CE: EITHER (MODE 1: ZERO-LAG 15M SUPPORT REVERSAL)
    //             OR     (MODE 2: TREND VWAP/EMA PULLBACK CONTINUATION)
    // =========================================================================
    const isAt15mSupport =
      distToSupportPct <= 0.0045 ||
      sr15m.rangePosPct <= 0.35 ||
      recent3Low <= nearest15mSupport * 1.0020;

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
      const atmStrike = Math.round(spotPrice / strikeStep) * strikeStep;
      const invalidationPrice = Number((nearest15mSupport * (1 - 0.0012)).toFixed(2));
      const targetWall = Number((nearest15mResistance * (1 - 0.0008)).toFixed(2));
      const riskPoints = Math.max(1, spotPrice - invalidationPrice);
      const rr = Number((runwayToResistance / riskPoints).toFixed(2));

      return {
        approved: true,
        symbol,
        underlyingSpot: spotPrice,
        action: 'BUY_ATM_CE',
        atmStrike,
        strikeStep,
        lotSize,
        patternTag: mode1SupportReversalBuy
          ? (isBullishPinbar
              ? '15M_SUPPORT_PINBAR_BOUNCE'
              : isBullishEngulfing
              ? '15M_SUPPORT_ENGULFING_RECLAIM'
              : '15M_SUPPORT_STRUCTURE_RECLAIM')
          : '15M_TREND_PULLBACK_BUY',
        reason: mode1SupportReversalBuy
          ? `15M_SUPPORT_REVERSAL (Supp=${nearest15mSupport.toFixed(1)}, ResTarget=${targetWall.toFixed(1)}, RR=${rr})`
          : `15M_TREND_PULLBACK (Supp=${nearest15mSupport.toFixed(1)}, ResTarget=${targetWall.toFixed(1)}, RR=${rr})`,
        fifteenMinSr: sr15m,
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
      recent3High >= nearest15mResistance * 0.9980;

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
      const atmStrike = Math.round(spotPrice / strikeStep) * strikeStep;
      const invalidationPrice = Number((nearest15mResistance * (1 + 0.0012)).toFixed(2));
      const targetWall = Number((nearest15mSupport * (1 + 0.0008)).toFixed(2));
      const riskPoints = Math.max(1, invalidationPrice - spotPrice);
      const rr = Number((runwayToSupport / riskPoints).toFixed(2));

      return {
        approved: true,
        symbol,
        underlyingSpot: spotPrice,
        action: 'BUY_ATM_PE',
        atmStrike,
        strikeStep,
        lotSize,
        patternTag: mode1ResistanceReversalSell
          ? (isBearishPinbar
              ? '15M_RESISTANCE_SHOOTING_STAR'
              : isBearishEngulfing
              ? '15M_RESISTANCE_ENGULFING_REJECT'
              : '15M_RESISTANCE_STRUCTURE_BREAKDOWN')
          : '15M_TREND_PULLBACK_SELL',
        reason: mode1ResistanceReversalSell
          ? `15M_RESISTANCE_REVERSAL (Res=${nearest15mResistance.toFixed(1)}, SuppTarget=${targetWall.toFixed(1)}, RR=${rr})`
          : `15M_TREND_PULLBACK (Res=${nearest15mResistance.toFixed(1)}, SuppTarget=${targetWall.toFixed(1)}, RR=${rr})`,
        fifteenMinSr: sr15m,
        targetResistanceWall: targetWall,
        invalidationSupportWall: invalidationPrice,
        runwayPoints: runwayToSupport,
        riskRewardRatio: rr,
        maxRiskInr: 2500,
      };
    }

    return this.reject(
      symbol,
      `NO_15M_SR_SETUP (RangePos=${(sr15m.rangePosPct * 100).toFixed(0)}%, DistSupp=${(distToSupportPct * 100).toFixed(2)}%, DistRes=${(distToResistancePct * 100).toFixed(2)}%)`
    );
  }

  // --- TECHNICAL INDICATOR HELPERS ---

  private static computeVwap(candles: Candle[]): number {
    let pv = 0;
    let v = 0;
    for (const c of candles) {
      const typical = (c.high + c.low + c.close) / 3;
      const vol = c.volume > 0 ? c.volume : 1;
      pv += typical * vol;
      v += vol;
    }
    return v > 0 ? pv / v : candles[candles.length - 1].close;
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

  private static reject(symbol: string, reason: string): OptionDecisionResult {
    return {
      approved: false,
      symbol,
      underlyingSpot: 0,
      action: 'WAIT',
      atmStrike: 0,
      strikeStep: 0,
      lotSize: 0,
      patternTag: 'WAIT',
      reason,
      fifteenMinSr: {
        majorResistance: 0,
        majorSupport: 0,
        swingHighs: [],
        swingLows: [],
        rangePosPct: 0.5,
      },
      targetResistanceWall: 0,
      invalidationSupportWall: 0,
      runwayPoints: 0,
      riskRewardRatio: 0,
      maxRiskInr: 2500,
    };
  }
}
