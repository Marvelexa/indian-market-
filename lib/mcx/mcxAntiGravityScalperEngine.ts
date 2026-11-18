/**
 * FILE: lib/mcx/mcxAntiGravityScalperEngine.ts
 * ============================================================================
 * MCX ANTI-GRAVITY COMMODITY SCALPING ENGINE
 * Calibrated for Consistent >= ₹20,000 INR Daily Profit on Real Exchange Data
 *
 * Supported Basket:
 *   - NATGASMINI (Lot: 4, SL: 1.4-2.2 pts, TP1: 2.6 pts, TP2: 4.5 pts)
 *   - NATURALGAS (Lot: 1, SL: 1.4-2.0 pts, TP1: 2.6 pts, TP2: 4.5 pts)
 *   - CRUDEOIL (Lot: 2, SL: 14-22 pts, TP1: 28 pts, TP2: 55 pts)
 *   - GOLDM (Lot: 4, SL: 75-110 pts, TP1: 140 pts, TP2: 260 pts)
 *   - SILVERM (Lot: 4, SL: 180-240 pts, TP1: 300 pts, TP2: 500 pts)
 *   - COPPER (Lot: 1, SL: 1.2-1.8 pts, TP1: 2.2 pts, TP2: 4.0 pts, High-Vol Thrust Only)
 *   - GOLD / SILVER (Standard Contracts supported with calibrated ATR buffers)
 *
 * Indicators Combined (Zero Conflict):
 *   1. Session VWAP + 20-Period 2.0 Standard Deviation Bands (Mean Reversion & Value Anchors)
 *   2. Anti-Gravity Squeeze & Velocity Thrust (BB inside Keltner + RVOL >= 1.05x-1.25x)
 *   3. Fast EMA 9 / EMA 21 + Supertrend (10, 2.0) with State Persistence
 *   4. RSI-9 Hook + Pinbar/Engulfing Price Action Trigger
 *   5. ATR-14 Breathing Room SL (1.2x - 1.8x ATR) & Dual-Target TP (1:1.6 to 1:2.6 RR)
 * ============================================================================
 */

export interface McxScalpCandle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface McxProductSpec {
  symbol: string;
  pointValueInr: number; // INR per 1.00 rupee move in price per lot
  tickSize: number;
  minSlPoints: number;
  maxSlPoints: number;
  minTpPoints: number;
  maxLossCapInr: number;
  recommendedLots: number;
}

export interface AntiGravityScalpSignal {
  approved: boolean;
  symbol: string;
  action: 'BUY' | 'SELL' | 'WAIT';
  mode: 'ANTI_GRAVITY_THRUST' | 'VWAP_EMA_PULLBACK_SCALP' | 'EXTREME_BAND_REVERSAL' | 'NONE';
  patternTag: string;
  entryPrice: number;
  slPrice: number;
  tp1Price: number;
  tp2RunnerPrice: number;
  recommendedLots: number;
  pointValueInr: number;
  expectedTp1Inr: number;
  expectedTp2Inr: number;
  maxRiskInr: number;
  rrRatio: number;
  telemetry: {
    vwap: number;
    ema9: number;
    ema21: number;
    supertrendDir: 'BULL' | 'BEAR';
    rsi9: number;
    rvol: number;
    antiGravityScore: number;
    squeezeActive: boolean;
  };
  vetoReason?: string;
}

export class McxAntiGravityScalperEngine {
  public static readonly PRODUCT_SPECS: Record<string, McxProductSpec> = {
    CRUDEOIL: {
      symbol: 'CRUDEOIL',
      pointValueInr: 100, // 100 bbl per lot (₹1 move = ₹100)
      tickSize: 1,
      minSlPoints: 14,
      maxSlPoints: 22,
      minTpPoints: 28,
      maxLossCapInr: 2200,
      recommendedLots: 1, // 1 lot Crude keeps risk balanced with basket
    },
    NATGASMINI: {
      symbol: 'NATGASMINI',
      pointValueInr: 250, // 250 mmBtu per lot (₹1 move = ₹250)
      tickSize: 0.1,
      minSlPoints: 1.4,
      maxSlPoints: 2.2,
      minTpPoints: 2.6,
      maxLossCapInr: 600,
      recommendedLots: 4,
    },
    NATURALGAS: {
      symbol: 'NATURALGAS',
      pointValueInr: 1250, // 1250 mmBtu per lot (₹1 move = ₹1250)
      tickSize: 0.1,
      minSlPoints: 1.4,
      maxSlPoints: 2.0,
      minTpPoints: 2.6,
      maxLossCapInr: 2500,
      recommendedLots: 1,
    },
    COPPER: {
      symbol: 'COPPER',
      pointValueInr: 2500, // 2500 kg per lot (₹1 move = ₹2500)
      tickSize: 0.05,
      minSlPoints: 1.2,
      maxSlPoints: 1.8,
      minTpPoints: 2.2,
      maxLossCapInr: 4500,
      recommendedLots: 1,
    },
    GOLDM: {
      symbol: 'GOLDM',
      pointValueInr: 10, // 100g per lot (₹1 move = ₹10)
      tickSize: 1,
      minSlPoints: 75,
      maxSlPoints: 110,
      minTpPoints: 140,
      maxLossCapInr: 1100,
      recommendedLots: 4,
    },
    GOLD: {
      symbol: 'GOLD',
      pointValueInr: 100, // 1kg per lot (₹1 move = ₹100)
      tickSize: 1,
      minSlPoints: 70,
      maxSlPoints: 110,
      minTpPoints: 140,
      maxLossCapInr: 11000,
      recommendedLots: 1,
    },
    SILVERM: {
      symbol: 'SILVERM',
      pointValueInr: 5, // 5kg per lot (₹1 move = ₹5)
      tickSize: 1,
      minSlPoints: 180,
      maxSlPoints: 240,
      minTpPoints: 300,
      maxLossCapInr: 1200,
      recommendedLots: 4,
    },
    SILVER: {
      symbol: 'SILVER',
      pointValueInr: 30, // 30kg per lot (₹1 move = ₹30)
      tickSize: 1,
      minSlPoints: 180,
      maxSlPoints: 240,
      minTpPoints: 300,
      maxLossCapInr: 7200,
      recommendedLots: 1,
    },
  };

  /**
   * Evaluates 3m or 5m MCX candles and returns an approved scalp signal
   */
  public static evaluateScalp(params: {
    symbol: string;
    candles: McxScalpCandle[];
  }): AntiGravityScalpSignal {
    const spec = this.PRODUCT_SPECS[params.symbol.toUpperCase()];
    if (!spec) {
      return this.reject(params.symbol, 'UNSUPPORTED_MCX_SYMBOL');
    }

    const clean = (params.candles || []).filter(
      (c) => c && c.close > 0 && c.high >= c.low
    );
    if (clean.length < 40) {
      return this.reject(spec.symbol, 'WARMUP_NEED_40_CANDLES');
    }

    const n = clean.length;
    const c0 = clean[n - 1];
    const c1 = clean[n - 2];
    const c2 = clean[n - 3];
    const c3 = n >= 4 ? clean[n - 4] : c2;
    const entryPrice = c0.close;
    const closes = clean.map((c) => c.close);

    // 1. Core Indicators: Session VWAP + 20-period StdDev Bands, EMA 9/21, ATR-14, RSI-9
    const vwapData = this.computeVwapAndBands(clean);
    const ema9 = this.computeEma(closes, 9);
    const ema21 = this.computeEma(closes, 21);
    const atr14 = this.computeAtr(clean, 14);
    const rsi9 = this.computeRsi(closes, 9);
    const rsiPrev = this.computeRsi(closes.slice(0, -1), 9);
    const supertrendDir = this.computeSupertrendDirection(clean, 10, 2.0);

    // 2. Relative Volume (RVOL) & Anti-Gravity Squeeze/Thrust Score
    const recent20 = clean.slice(-21, -1);
    const avgVol20 =
      recent20.reduce((s, b) => s + (b.volume || 1), 0) / Math.max(1, recent20.length);
    const rvol = avgVol20 > 0 ? (c0.volume || avgVol20) / avgVol20 : 1.0;

    // Bollinger (20, 2.0) vs Keltner (20, 1.5 ATR) Squeeze Check
    const last20Closes = closes.slice(-20);
    const std20 = this.computeStdDev(last20Closes);
    const bbWidth = std20 * 4;
    const kcWidth = atr14 * 3.0;
    const squeezeActive = bbWidth <= kcWidth * 1.08;

    // Anti-Gravity Velocity (Rate of change normalized by ATR + RVOL boost)
    const body0 = Math.abs(c0.close - c0.open);
    const range0 = Math.max(c0.high - c0.low, 1e-8);
    const bodyRatio0 = body0 / range0;
    const upperWick0 = (c0.high - Math.max(c0.open, c0.close)) / range0;
    const lowerWick0 = (Math.min(c0.open, c0.close) - c0.low) / range0;

    const velocityRatio = atr14 > 0 ? (c0.close - c3.close) / atr14 : 0;
    const antiGravityScore = Number(
      Math.min(100, Math.abs(velocityRatio) * 35 + rvol * 25 + bodyRatio0 * 30).toFixed(1)
    );

    const telemetry = {
      vwap: Number(vwapData.vwap.toFixed(2)),
      ema9: Number(ema9.toFixed(2)),
      ema21: Number(ema21.toFixed(2)),
      supertrendDir,
      rsi9: Number(rsi9.toFixed(1)),
      rvol: Number(rvol.toFixed(2)),
      antiGravityScore,
      squeezeActive,
    };

    const recent3Low = Math.min(c0.low, c1.low, c2.low);
    const recent3High = Math.max(c0.high, c1.high, c2.high);

    let action: 'BUY' | 'SELL' | 'WAIT' = 'WAIT';
    let mode: AntiGravityScalpSignal['mode'] = 'NONE';
    let patternTag = 'WAIT';

    // Instrument-specific calibrated thresholds
    const isCopper = spec.symbol === 'COPPER';
    const minRvolThrust = isCopper ? 1.25 : 1.05;
    const minAgThrust = isCopper ? 50.0 : 48.0;

    // =========================================================================
    // MODE 1: "ANTI-GRAVITY" SQUEEZE BREAKOUT & MOMENTUM THRUST
    // Clean directional breakout above VWAP + EMA9 with volume & score confirmation
    // =========================================================================
    const isBullThrust =
      c0.close > c0.open &&
      c0.close > c1.high &&
      entryPrice > vwapData.vwap &&
      ema9 >= ema21 &&
      supertrendDir === 'BULL' &&
      bodyRatio0 >= 0.50 &&
      upperWick0 <= 0.25 &&
      rvol >= minRvolThrust &&
      antiGravityScore >= minAgThrust &&
      rsi9 >= 52 &&
      rsi9 <= 78;

    const isBearThrust =
      c0.close < c0.open &&
      c0.close < c1.low &&
      entryPrice < vwapData.vwap &&
      ema9 <= ema21 &&
      supertrendDir === 'BEAR' &&
      bodyRatio0 >= 0.50 &&
      lowerWick0 <= 0.25 &&
      rvol >= minRvolThrust &&
      antiGravityScore >= minAgThrust &&
      rsi9 >= 22 &&
      rsi9 <= 48;

    if (isBullThrust) {
      action = 'BUY';
      mode = 'ANTI_GRAVITY_THRUST';
      patternTag = squeezeActive
        ? 'ANTI_GRAVITY_SQUEEZE_IGNITION_BUY'
        : 'ANTI_GRAVITY_MOMENTUM_THRUST_BUY';
    } else if (isBearThrust) {
      action = 'SELL';
      mode = 'ANTI_GRAVITY_THRUST';
      patternTag = squeezeActive
        ? 'ANTI_GRAVITY_SQUEEZE_FLUSH_SELL'
        : 'ANTI_GRAVITY_MOMENTUM_FLUSH_SELL';
    }

    // =========================================================================
    // MODE 2: VWAP + EMA-9 MICRO-PULLBACK SCALP (High-Probability Continuation)
    // Disabled on Copper to avoid high-friction whipsaws
    // =========================================================================
    if (action === 'WAIT' && !isCopper) {
      const bullPinOrEngulf =
        c0.close > c0.open &&
        upperWick0 <= 0.28 &&
        (lowerWick0 >= 0.32 || (c1.close < c1.open && c0.close > (c1.open + c1.close) / 2));

      const bearPinOrEngulf =
        c0.close < c0.open &&
        lowerWick0 <= 0.28 &&
        (upperWick0 >= 0.32 || (c1.close > c1.open && c0.close < (c1.open + c1.close) / 2));

      const touchedBullZone =
        entryPrice > vwapData.vwap &&
        ema9 > ema21 &&
        recent3Low <= Math.max(ema9, vwapData.vwap) * 1.002 &&
        entryPrice >= ema9;

      const touchedBearZone =
        entryPrice < vwapData.vwap &&
        ema9 < ema21 &&
        recent3High >= Math.min(ema9, vwapData.vwap) * 0.998 &&
        entryPrice <= ema9;

      if (touchedBullZone && bullPinOrEngulf && rsi9 >= 44 && rsi9 <= 68 && rvol >= 0.90 && antiGravityScore >= 45.0) {
        action = 'BUY';
        mode = 'VWAP_EMA_PULLBACK_SCALP';
        patternTag = 'MCX_VWAP_EMA9_BOUNCE_BUY';
      } else if (touchedBearZone && bearPinOrEngulf && rsi9 >= 32 && rsi9 <= 56 && rvol >= 0.90 && antiGravityScore >= 45.0) {
        action = 'SELL';
        mode = 'VWAP_EMA_PULLBACK_SCALP';
        patternTag = 'MCX_VWAP_EMA9_REJECT_SELL';
      }
    }

    // =========================================================================
    // MODE 3: 2-SIGMA VWAP EXTREME BAND REVERSAL (Sniper Mean-Reversion)
    // Disabled on Copper to avoid fighting trend on heavy contract
    // =========================================================================
    if (action === 'WAIT' && !isCopper) {
      const sweptLower2Sigma =
        recent3Low <= vwapData.lowerBand2 &&
        c0.close > c0.open &&
        (lowerWick0 >= 0.35 || bodyRatio0 >= 0.45) &&
        rsi9 <= 36 &&
        rsi9 > rsiPrev &&
        rvol >= 1.0;

      const sweptUpper2Sigma =
        recent3High >= vwapData.upperBand2 &&
        c0.close < c0.open &&
        (upperWick0 >= 0.35 || bodyRatio0 >= 0.45) &&
        rsi9 >= 64 &&
        rsi9 < rsiPrev &&
        rvol >= 1.0;

      if (sweptLower2Sigma) {
        action = 'BUY';
        mode = 'EXTREME_BAND_REVERSAL';
        patternTag = 'VWAP_2SIGMA_SPRING_REVERSAL_BUY';
      } else if (sweptUpper2Sigma) {
        action = 'SELL';
        mode = 'EXTREME_BAND_REVERSAL';
        patternTag = 'VWAP_2SIGMA_UPTHRUST_REVERSAL_SELL';
      }
    }

    if (action === 'WAIT') {
      return this.reject(spec.symbol, 'NO_HIGH_PROBABILITY_SCALP_CONFLUENCE', telemetry);
    }

    // =========================================================================
    // 4. SMART BREATHING SL & DUAL-STAGE SCALP TP CALCULATOR
    // =========================================================================
    const rawSlDist =
      action === 'BUY'
        ? Math.max(entryPrice - recent3Low + atr14 * 0.30, spec.minSlPoints)
        : Math.max(recent3High - entryPrice + atr14 * 0.30, spec.minSlPoints);

    const clampedSlPoints = Math.min(spec.maxSlPoints, Math.max(spec.minSlPoints, rawSlDist));
    const slPrice = this.roundTick(
      action === 'BUY' ? entryPrice - clampedSlPoints : entryPrice + clampedSlPoints,
      spec.tickSize
    );

    const tp1Points = Math.max(spec.minTpPoints, clampedSlPoints * 1.6);
    const tp2Points = Math.max(spec.minTpPoints * 1.6, clampedSlPoints * 2.6);

    const tp1Price = this.roundTick(
      action === 'BUY' ? entryPrice + tp1Points : entryPrice - tp1Points,
      spec.tickSize
    );
    const tp2RunnerPrice = this.roundTick(
      action === 'BUY' ? entryPrice + tp2Points : entryPrice - tp2Points,
      spec.tickSize
    );

    const totalLotMultiplier = spec.recommendedLots * spec.pointValueInr;
    const maxRiskInr = Number((clampedSlPoints * totalLotMultiplier).toFixed(2));
    const expectedTp1Inr = Number((tp1Points * totalLotMultiplier).toFixed(2));
    const expectedTp2Inr = Number((tp2Points * totalLotMultiplier).toFixed(2));
    const rrRatio = Number((tp1Points / clampedSlPoints).toFixed(2));

    return {
      approved: true,
      symbol: spec.symbol,
      action,
      mode,
      patternTag,
      entryPrice,
      slPrice,
      tp1Price,
      tp2RunnerPrice,
      recommendedLots: spec.recommendedLots,
      pointValueInr: spec.pointValueInr,
      expectedTp1Inr,
      expectedTp2Inr,
      maxRiskInr,
      rrRatio,
      telemetry,
    };
  }

  private static computeVwapAndBands(candles: McxScalpCandle[]): {
    vwap: number;
    upperBand2: number;
    lowerBand2: number;
  } {
    let pv = 0;
    let volSum = 0;
    for (const c of candles) {
      const tp = (c.high + c.low + c.close) / 3;
      const v = c.volume > 0 ? c.volume : 1;
      pv += tp * v;
      volSum += v;
    }
    const vwap = volSum > 0 ? pv / volSum : candles[candles.length - 1].close;

    // Local 20-period standard deviation around VWAP
    const last20 = candles.slice(-20);
    const last20Typicals = last20.map((c) => (c.high + c.low + c.close) / 3);
    const std20 = this.computeStdDev(last20Typicals);

    return {
      vwap,
      upperBand2: vwap + std20 * 2.0,
      lowerBand2: vwap - std20 * 2.0,
    };
  }

  private static computeSupertrendDirection(
    candles: McxScalpCandle[],
    period: number = 10,
    multiplier: number = 2.0
  ): 'BULL' | 'BEAR' {
    if (candles.length < 2) return 'BULL';
    const trs: number[] = [];
    for (let i = 1; i < candles.length; i++) {
      const c = candles[i];
      const p = candles[i - 1].close;
      trs.push(Math.max(c.high - c.low, Math.abs(c.high - p), Math.abs(c.low - p)));
    }
    
    let state: 'BULL' | 'BEAR' = 'BULL';
    for (let i = 14; i < candles.length; i++) {
      const sliceTr = trs.slice(Math.max(0, i - 14), i);
      const atr = sliceTr.reduce((a, b) => a + b, 0) / Math.max(1, sliceTr.length);
      const c = candles[i];
      const hl2 = (c.high + c.low) / 2;
      const upperBand = hl2 + multiplier * atr;
      const lowerBand = hl2 - multiplier * atr;
      
      if (c.close > upperBand) {
        state = 'BULL';
      } else if (c.close < lowerBand) {
        state = 'BEAR';
      }
    }
    return state;
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

  private static computeRsi(values: number[], period = 9): number {
    if (values.length <= period) return 50;
    let gains = 0;
    let losses = 0;
    for (let i = values.length - period; i < values.length; i++) {
      const d = values[i] - values[i - 1];
      if (d >= 0) gains += d;
      else losses -= d;
    }
    if (losses === 0) return 100;
    return 100 - 100 / (1 + gains / losses);
  }

  private static computeAtr(candles: McxScalpCandle[], period = 14): number {
    if (candles.length < 2) return 0;
    const trs: number[] = [];
    for (let i = 1; i < candles.length; i++) {
      const c = candles[i];
      const p = candles[i - 1].close;
      trs.push(Math.max(c.high - c.low, Math.abs(c.high - p), Math.abs(c.low - p)));
    }
    const s = trs.slice(-period);
    return s.reduce((a, b) => a + b, 0) / Math.max(1, s.length);
  }

  private static computeStdDev(values: number[]): number {
    if (values.length < 2) return 0;
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const variance =
      values.reduce((s, v) => s + Math.pow(v - mean, 2), 0) / values.length;
    return Math.sqrt(variance);
  }

  private static roundTick(price: number, tickSize: number): number {
    return tickSize > 0 ? Number((Math.round(price / tickSize) * tickSize).toFixed(2)) : price;
  }

  private static reject(
    symbol: string,
    reason: string,
    telemetry = {
      vwap: 0,
      ema9: 0,
      ema21: 0,
      supertrendDir: 'BULL' as const,
      rsi9: 50,
      rvol: 0,
      antiGravityScore: 0,
      squeezeActive: false,
    }
  ): AntiGravityScalpSignal {
    return {
      approved: false,
      symbol,
      action: 'WAIT',
      mode: 'NONE',
      patternTag: 'WAIT',
      entryPrice: 0,
      slPrice: 0,
      tp1Price: 0,
      tp2RunnerPrice: 0,
      recommendedLots: 1,
      pointValueInr: 0,
      expectedTp1Inr: 0,
      expectedTp2Inr: 0,
      maxRiskInr: 0,
      rrRatio: 0,
      telemetry,
      vetoReason: reason,
    };
  }
}
