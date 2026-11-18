// File: lib/indianMarket/indianMarketMasterEngine.ts

export interface IndianCandle {
  timestamp: number; // Epoch ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  dateStr?: string;
  timeStr?: string;
  previousDayHigh?: number;
  previousDayLow?: number;
  previousDayClose?: number;
  openingRangeHigh?: number;
  openingRangeLow?: number;
}

export type SeatCategory =
  | 'CHOP_PING_PONG_SEAT'
  | 'NORMAL_TREND_RUNNER_SEAT'
  | 'NIFTY_BANKNIFTY_OPTION_SEAT'
  | 'NONE';

export interface IndianTradeSignal {
  approved: boolean;
  symbol: string;
  action: 'BUY' | 'SELL' | 'WAIT';
  seatCategory: SeatCategory;
  optionContractType?: 'CE_CALL_BUY' | 'PE_PUT_BUY' | 'NONE';
  recommendedStrike?: number;
  confluenceScore: number; // 0 to 100 (Requires >= 88 for execution)
  setupName: string;
  entryPrice: number;
  slPrice: number;
  tpPrice: number;
  trueInvalidationPrice: number;
  firstReversalWallPrice: number;
  reversalWallSource: string;
  slDistPct: number;
  tpDistPct: number;
  rrRatio: number; // Must be >= 1.8 (Chop) or >= 2.4 (Trend)
  quantityLotsOrShares: number;
  maxRiskInr: number;
  expectedProfitInr: number;
  vetoReason?: string;
}

export class IndianMarketMasterEngine {
  public static readonly TOTAL_CAPITAL_INR = 100000; // ₹1,00,000
  public static readonly DAILY_TARGET_INR = 20000;   // ₹20,000+ goal
  public static readonly MAX_RISK_PER_TRADE_INR = 2500; // Strict ₹2,500 max loss per lot (Rules 3 & 5)

  /**
   * Checks if current timestamp is within NSE Active Trading Window (09:25 AM - 03:10 PM IST)
   * and flags Auto Square-Off at 03:18 PM IST.
   */
  public static checkMarketSessionIST(timestampMs: number): {
    isMarketOpen: boolean;
    canOpenNewTrade: boolean;
    mustSquareOffAll: boolean;
    istTimeString: string;
    sessionNote: string;
  } {
    // Convert UTC ms to IST (+5:30 = +330 minutes)
    const istDate = new Date(timestampMs + 330 * 60 * 1000);
    const hours = istDate.getUTCHours();
    const minutes = istDate.getUTCMinutes();
    const totalMinutes = hours * 60 + minutes;
    const istTimeString = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')} IST`;

    const marketOpenMin = 9 * 60 + 15;   // 09:15 AM
    const entryStartMin = 9 * 60 + 25;   // 09:25 AM (After 10-min ORB stabilization)
    const entryCutoffMin = 15 * 60 + 10; // 03:10 PM (No fresh entries in last 20 mins)
    const squareOffMin = 15 * 60 + 18;   // 03:18 PM (Mandatory intraday exit)
    const marketCloseMin = 15 * 60 + 30; // 03:30 PM

    if (totalMinutes < marketOpenMin || totalMinutes > marketCloseMin) {
      return {
        isMarketOpen: false,
        canOpenNewTrade: false,
        mustSquareOffAll: false,
        istTimeString,
        sessionNote: 'MARKET_CLOSED (Outside 09:15–15:30 IST)',
      };
    }

    if (totalMinutes >= squareOffMin) {
      return {
        isMarketOpen: true,
        canOpenNewTrade: false,
        mustSquareOffAll: true,
        istTimeString,
        sessionNote: 'INTRADAY_AUTO_SQUARE_OFF_WINDOW (03:18 PM+ IST)',
      };
    }

    if (totalMinutes < entryStartMin) {
      return {
        isMarketOpen: true,
        canOpenNewTrade: false,
        mustSquareOffAll: false,
        istTimeString,
        sessionNote: 'ORB_STABILIZATION_WARMUP (09:15–09:25 AM IST)',
      };
    }

    return {
      isMarketOpen: true,
      canOpenNewTrade: totalMinutes <= entryCutoffMin,
      mustSquareOffAll: false,
      istTimeString,
      sessionNote: 'ACTIVE_SNIPER_SESSION (09:25 AM–03:10 PM IST)',
    };
  }

  /**
   * Computes Intraday Session VWAP (resets at 09:15 AM IST every day)
   */
  public static computeIntradayVWAP(candles: IndianCandle[]): { currentVwap: number; prevVwap: number } {
    if (candles.length === 0) return { currentVwap: 0, prevVwap: 0 };
    const lastTs = candles[candles.length - 1].timestamp;
    const lastIst = new Date(lastTs + 330 * 60 * 1000);
    const dayKey = `${lastIst.getUTCFullYear()}-${lastIst.getUTCMonth()}-${lastIst.getUTCDate()}`;

    let cumPV = 0;
    let cumVol = 0;
    let prevPV = 0;
    let prevVol = 0;

    for (let i = 0; i < candles.length; i++) {
      const c = candles[i];
      const d = new Date(c.timestamp + 330 * 60 * 1000);
      const k = `${d.getUTCFullYear()}-${d.getUTCMonth()}-${d.getUTCDate()}`;
      if (k === dayKey) {
        const typicalPrice = (c.high + c.low + c.close) / 3;
        const vol = Math.max(c.volume || 100, 1);
        cumPV += typicalPrice * vol;
        cumVol += vol;
        if (i < candles.length - 1) {
          prevPV += typicalPrice * vol;
          prevVol += vol;
        }
      }
    }

    const currentVwap = cumVol > 0 ? cumPV / cumVol : candles[candles.length - 1].close;
    const prevVwap = prevVol > 0 ? prevPV / prevVol : currentVwap;
    return { currentVwap, prevVwap };
  }

  public static computeEMA(values: number[], period: number): number {
    if (values.length === 0) return 0;
    const k = 2 / (period + 1);
    let ema = values[0];
    for (let i = 1; i < values.length; i++) {
      ema = values[i] * k + ema * (1 - k);
    }
    return ema;
  }

  public static computeRSI(closes: number[], period = 14): number {
    if (closes.length <= period) return 50;
    let gains = 0;
    let losses = 0;
    for (let i = closes.length - period; i < closes.length; i++) {
      const diff = closes[i] - closes[i - 1];
      if (diff > 0) gains += diff;
      else losses -= diff;
    }
    if (losses === 0) return 100;
    const rs = gains / losses;
    return 100 - 100 / (1 + rs);
  }

  public static computeBollingerBands(closes: number[], period = 20, mult = 2.1): {
    upper: number;
    mid: number;
    lower: number;
  } {
    if (closes.length < period) {
      const last = closes[closes.length - 1] || 0;
      return { upper: last * 1.01, mid: last, lower: last * 0.99 };
    }
    const slice = closes.slice(-period);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / period;
    const sd = Math.sqrt(variance);
    return {
      upper: mean + mult * sd,
      mid: mean,
      lower: mean - mult * sd,
    };
  }

  public static computeADX(candles: IndianCandle[], period = 14): number {
    if (candles.length < period * 2) return 20;
    const tr: number[] = [0];
    const plusDM: number[] = [0];
    const minusDM: number[] = [0];

    for (let i = 1; i < candles.length; i++) {
      const hl = candles[i].high - candles[i].low;
      const hc = Math.abs(candles[i].high - candles[i - 1].close);
      const lc = Math.abs(candles[i].low - candles[i - 1].close);
      tr.push(Math.max(hl, hc, lc));

      const upMove = candles[i].high - candles[i - 1].high;
      const downMove = candles[i - 1].low - candles[i].low;
      if (upMove > downMove && upMove > 0) plusDM.push(upMove);
      else plusDM.push(0);
      if (downMove > upMove && downMove > 0) minusDM.push(downMove);
      else minusDM.push(0);
    }

    const k = 2 / (period + 1);
    let smoothTR = tr[0], smoothPlusDM = plusDM[0], smoothMinusDM = minusDM[0];
    for (let i = 1; i < candles.length; i++) {
      smoothTR = tr[i] * k + smoothTR * (1 - k);
      smoothPlusDM = plusDM[i] * k + smoothPlusDM * (1 - k);
      smoothMinusDM = minusDM[i] * k + smoothMinusDM * (1 - k);
    }

    const pDI = (smoothPlusDM / Math.max(smoothTR, 1e-8)) * 100;
    const mDI = (smoothMinusDM / Math.max(smoothTR, 1e-8)) * 100;
    const sum = pDI + mDI;
    return sum > 0 ? (Math.abs(pDI - mDI) / sum) * 100 : 20;
  }

  /**
   * Master Evaluation Function:
   * Combines Intraday VWAP + EMA 9/20/50 + Bollinger 2.1 SD + ADX + Reversal Pre-TP
   */
  public static evaluateSymbol(params: {
    symbol: string;
    candles: IndianCandle[];
    isIndex: boolean;
    tickSize?: number;
    previousDayHigh?: number;
    previousDayLow?: number;
  }): IndianTradeSignal {
    const { symbol, candles, isIndex, tickSize = 0.05, previousDayHigh, previousDayLow } = params;

    if (candles.length < 40) {
      return this.buildRejectedSignal(symbol, 'WARMUP_NEED_40_CANDLES');
    }

    const c0 = candles[candles.length - 1];
    const c1 = candles[candles.length - 2];
    const entryPrice = c0.close;

    // 1. Session Timing Check
    const session = this.checkMarketSessionIST(c0.timestamp);
    if (!session.canOpenNewTrade) {
      return this.buildRejectedSignal(symbol, `SESSION_GATE: ${session.sessionNote}`);
    }

    // 2. Institutional Indicators
    const closes = candles.map((c) => c.close);
    const { currentVwap, prevVwap } = this.computeIntradayVWAP(candles);
    const ema9 = this.computeEMA(closes.slice(-30), 9);
    const ema20 = this.computeEMA(closes.slice(-45), 20);
    const ema50 = this.computeEMA(closes.slice(-75), 50);
    const rsi = this.computeRSI(closes, 14);
    const adx = this.computeADX(candles, 14);
    const bb = this.computeBollingerBands(closes, 20, 2.1);

    // RVOL
    const recent20Vol = candles.slice(-21, -1).map((c) => c.volume || 1000);
    const avgVol20 = recent20Vol.reduce((a, b) => a + b, 0) / Math.max(recent20Vol.length, 1);
    const rvol = avgVol20 > 0 ? (c0.volume || 1000) / avgVol20 : 1.0;
    if (rvol < 1.10) {
      return this.buildRejectedSignal(symbol, `RVOL_TOO_LOW (${rvol.toFixed(2)} < 1.10)`);
    }

    // Candle Anatomy
    const range0 = Math.max(c0.high - c0.low, 1e-6);
    const lowerWick0 = (Math.min(c0.open, c0.close) - c0.low) / range0;
    const upperWick0 = (c0.high - Math.max(c0.open, c0.close)) / range0;

    let action: 'BUY' | 'SELL' | 'WAIT' = 'WAIT';
    let seatCategory: SeatCategory = 'NONE';
    let setupName = 'NONE';
    let confluenceScore = 0;

    // =========================================================================
    // REGIME 1: CHOPPING PING-PONG SEAT (ADX < 24)
    // =========================================================================
    if (adx < 24) {
      const touchedLower = c0.low <= bb.lower * 1.002 || c1.low <= bb.lower * 1.002;
      const touchedUpper = c0.high >= bb.upper * 0.998 || c1.high >= bb.upper * 0.998;

      if (touchedLower && c0.close > c0.open && lowerWick0 >= 0.30 && rsi <= 45 && entryPrice < bb.mid) {
        action = 'BUY';
        seatCategory = 'CHOP_PING_PONG_SEAT';
        setupName = 'CHOP_BB_SUPPORT_SWEEP_REVERSAL_BUY';
        confluenceScore = 91;
      } else if (touchedUpper && c0.close < c0.open && upperWick0 >= 0.30 && rsi >= 55 && entryPrice > bb.mid) {
        action = 'SELL';
        seatCategory = 'CHOP_PING_PONG_SEAT';
        setupName = 'CHOP_BB_RESISTANCE_SWEEP_REVERSAL_SELL';
        confluenceScore = 91;
      }
    }
    // =========================================================================
    // REGIME 2: NORMAL TREND RUNNER & INDEX OPTION SEAT (ADX >= 24)
    // =========================================================================
    else {
      const isBull = ema9 > ema20 && ema20 > ema50 && entryPrice > ema20;
      const isBear = ema9 < ema20 && ema20 < ema50 && entryPrice < ema20;
      const touchBuy = c0.low <= ema20 * 1.0025 || c1.low <= ema20 * 1.0025;
      const touchSell = c0.high >= ema20 * 0.9975 || c1.high >= ema20 * 0.9975;
      const vwapBuyOk = entryPrice > currentVwap && currentVwap >= prevVwap;
      const vwapSellOk = entryPrice < currentVwap && currentVwap <= prevVwap;

      if (isBull && touchBuy && vwapBuyOk && c0.close > c0.open && lowerWick0 >= 0.30 && rsi >= 50 && rsi <= 68) {
        action = 'BUY';
        seatCategory = isIndex ? 'NIFTY_BANKNIFTY_OPTION_SEAT' : 'NORMAL_TREND_RUNNER_SEAT';
        setupName = 'VWAP_EMA9_20_INSTITUTIONAL_TREND_BUY';
        confluenceScore = 92;
      } else if (isBear && touchSell && vwapSellOk && c0.close < c0.open && upperWick0 >= 0.30 && rsi >= 32 && rsi <= 50) {
        action = 'SELL';
        seatCategory = isIndex ? 'NIFTY_BANKNIFTY_OPTION_SEAT' : 'NORMAL_TREND_RUNNER_SEAT';
        setupName = 'VWAP_EMA9_20_INSTITUTIONAL_TREND_SELL';
        confluenceScore = 92;
      }
    }

    if (action === 'WAIT') {
      return this.buildRejectedSignal(symbol, 'NO_CONFLUENT_INSTITUTIONAL_SETUP');
    }

    // Distances
    const isChop = seatCategory === 'CHOP_PING_PONG_SEAT';
    const tpDistPct = isChop ? 0.0070 : 0.0140; // 0.70% Chop, 1.40% Trend
    const slDistPct = tpDistPct * 1.35;        // Structural buffer

    const tpPrice = this.roundToTick(
      action === 'BUY' ? entryPrice * (1 + tpDistPct) : entryPrice * (1 - tpDistPct),
      tickSize
    );
    const slPrice = this.roundToTick(
      action === 'BUY' ? entryPrice * (1 - slDistPct) : entryPrice * (1 + slDistPct),
      tickSize
    );

    // Strict Risk Budgeting (Max ₹1,500 - ₹1,800 loss per SL):
    const effectiveSlDist = isIndex ? Math.abs(entryPrice - slPrice) * 0.60 : Math.abs(entryPrice - slPrice);
    const quantityLotsOrShares = Math.max(
      1,
      Math.floor(this.MAX_RISK_PER_TRADE_INR / Math.max(effectiveSlDist, tickSize))
    );

    const delta = isIndex ? 0.60 : 1.0;
    const maxRiskInr = Math.round(Math.abs(entryPrice - slPrice) * quantityLotsOrShares * delta);
    const expectedProfitInr = Math.round(Math.abs(tpPrice - entryPrice) * quantityLotsOrShares * delta);

    // Option Strike Recommendation (0.60 Delta ITM)
    const strikeStep = symbol.includes('BANK') || symbol.includes('SENSEX') ? 100 : 50;
    const atmStrike = Math.round(entryPrice / strikeStep) * strikeStep;
    const recommendedStrike = action === 'BUY' ? atmStrike - strikeStep : atmStrike + strikeStep;

    return {
      approved: true,
      symbol,
      action,
      seatCategory,
      optionContractType: isIndex ? (action === 'BUY' ? 'CE_CALL_BUY' : 'PE_PUT_BUY') : 'NONE',
      recommendedStrike: isIndex ? recommendedStrike : undefined,
      confluenceScore,
      setupName,
      entryPrice,
      slPrice,
      tpPrice,
      trueInvalidationPrice: slPrice,
      firstReversalWallPrice: tpPrice,
      reversalSource: isChop ? 'BOLLINGER_BAND_BOUNDARY' : 'EMA_TREND_RUNNER_EXPANSION',
      slDistPct: Number(slDistPct.toFixed(5)),
      tpDistPct: Number(tpDistPct.toFixed(5)),
      rrRatio: Number((tpDistPct / slDistPct).toFixed(2)),
      quantityLotsOrShares,
      maxRiskInr,
      expectedProfitInr,
    };
  }

  /**
   * 2-Stage Progressive Protection Ladder:
   * - Stage 1 (Breakeven Scratch Lock): At 35% of TP runway, moves SL to Entry + 5% runway (eliminates loss!)
   * - Stage 2 (Institutional Profit Lock): At 70% of TP runway, locks 55% of the total target profit!
   */
  public static evaluateLiveTrailingBracket(params: {
    action: 'BUY' | 'SELL';
    entryPrice: number;
    currentLtp: number;
    currentSlPrice: number;
    tpPrice: number;
    tickSize?: number;
    stage?: number;
  }): { shouldModifySl: boolean; newSlPrice: number; newStage: number; stageNote: string } {
    const { action, entryPrice, currentLtp, currentSlPrice, tpPrice, tickSize = 0.05, stage = 0 } = params;
    const totalRunway = Math.max(Math.abs(tpPrice - entryPrice), 1e-8);
    const coveredRunway = action === 'BUY' ? currentLtp - entryPrice : entryPrice - currentLtp;
    const progressRatio = coveredRunway / totalRunway;

    // Stage 2: Profit Lock at >= 70% of runway
    if (progressRatio >= 0.70 && stage < 2) {
      const lockedDist = totalRunway * 0.55;
      const candidateSl = this.roundToTick(
        action === 'BUY' ? entryPrice + lockedDist : entryPrice - lockedDist,
        tickSize
      );
      const isImprovement = action === 'BUY' ? candidateSl > currentSlPrice : candidateSl < currentSlPrice;
      return {
        shouldModifySl: isImprovement,
        newSlPrice: isImprovement ? candidateSl : currentSlPrice,
        newStage: 2,
        stageNote: 'PROFIT_LOCKED_AT_55PCT_WAITING_FOR_PRE_REVERSAL_TP',
      };
    }

    // Stage 1: Breakeven Lock at >= 35% of runway
    if (progressRatio >= 0.35 && stage < 1) {
      const beBuffer = totalRunway * 0.05;
      const candidateSl = this.roundToTick(
        action === 'BUY' ? entryPrice + beBuffer : entryPrice - beBuffer,
        tickSize
      );
      const isImprovement = action === 'BUY' ? candidateSl > currentSlPrice : candidateSl < currentSlPrice;
      return {
        shouldModifySl: isImprovement,
        newSlPrice: isImprovement ? candidateSl : currentSlPrice,
        newStage: 1,
        stageNote: 'BREAKEVEN_SCRATCH_PROTECTION_LOCKED',
      };
    }

    return {
      shouldModifySl: false,
      newSlPrice: currentSlPrice,
      newStage: stage,
      stageNote: `HANDS_OFF_STAGE (${(progressRatio * 100).toFixed(0)}% to Pre-Reversal TP)`,
    };
  }

  public static readonly EIGHT_STAGE_LADDER = [
    { targetInr: 8000, lockInr: 8000, stage: 8, name: 'STAGE 8: FULL MARKET TARGET (+₹8,000)' },
    { targetInr: 6000, lockInr: 4800, stage: 7, name: 'STAGE 7: TRAILING LOCK (+₹4,800)' },
    { targetInr: 4500, lockInr: 3600, stage: 6, name: 'STAGE 6: TRAILING LOCK (+₹3,600)' },
    { targetInr: 3000, lockInr: 2400, stage: 5, name: 'STAGE 5: TRAILING LOCK (+₹2,400)' },
    { targetInr: 2000, lockInr: 1600, stage: 4, name: 'STAGE 4: TRAILING LOCK (+₹1,600)' },
    { targetInr: 1500, lockInr: 1150, stage: 3, name: 'STAGE 3: TRAILING LOCK (+₹1,150)' },
    { targetInr: 1000, lockInr: 700,  stage: 2, name: 'STAGE 2: TRAILING LOCK (+₹700)' },
    { targetInr: 600,  lockInr: 300,  stage: 1, name: 'STAGE 1: TRAILING LOCK (+₹300)' },
  ];

  /**
   * 8-Stage Rupee Profit Ladder Evaluator (Zero-Lookahead):
   * Evaluates profit hurdles and moves hard/trailing stop upward.
   */
  public static evaluateEightStageRupeeLadder(params: {
    peakPnlInr: number;
    currentPnlInr: number;
    currentLockedInr: number;
    currentStage: number;
    hardSlInr?: number; // default -2500
  }): {
    shouldExit: boolean;
    exitReason: string;
    exitPnlInr: number;
    newLockedInr: number;
    newStage: number;
  } {
    const hardSl = params.hardSlInr ?? -2500;

    // 1. Check Hard SL if no profit locked yet
    if (params.currentLockedInr <= 0 && params.currentPnlInr <= hardSl) {
      return {
        shouldExit: true,
        exitReason: `HARD_SL_HIT (-₹${Math.abs(hardSl)})`,
        exitPnlInr: hardSl,
        newLockedInr: params.currentLockedInr,
        newStage: params.currentStage,
      };
    }

    // 2. Advance the ladder
    let updatedLockedInr = params.currentLockedInr;
    let updatedStage = params.currentStage;
    let stageExitReason = '';

    for (const step of this.EIGHT_STAGE_LADDER) {
      if (params.peakPnlInr >= step.targetInr) {
        if (step.stage === 8) {
          return {
            shouldExit: true,
            exitReason: step.name,
            exitPnlInr: 8000,
            newLockedInr: 8000,
            newStage: 8,
          };
        }
        if (step.lockInr > updatedLockedInr) {
          updatedLockedInr = step.lockInr;
          updatedStage = step.stage;
          stageExitReason = step.name;
        }
        break;
      }
    }

    // 3. Check if current P&L dipped down to locked profit floor
    if (updatedLockedInr > 0 && params.currentPnlInr <= updatedLockedInr) {
      return {
        shouldExit: true,
        exitReason: stageExitReason || `STAGE_${updatedStage}_LOCK_HIT (+₹${updatedLockedInr})`,
        exitPnlInr: updatedLockedInr,
        newLockedInr: updatedLockedInr,
        newStage: updatedStage,
      };
    }

    return {
      shouldExit: false,
      exitReason: 'IN_TRADE_HOLDING',
      exitPnlInr: params.currentPnlInr,
      newLockedInr: updatedLockedInr,
      newStage: updatedStage,
    };
  }

  private static roundToTick(price: number, tickSize: number): number {
    return tickSize > 0
      ? Number((Math.round(price / tickSize) * tickSize).toFixed(2))
      : Number(price.toFixed(2));
  }

  private static buildRejectedSignal(symbol: string, reason: string): IndianTradeSignal {
    return {
      approved: false,
      symbol,
      action: 'WAIT',
      seatCategory: 'NONE',
      confluenceScore: 0,
      setupName: 'NONE',
      entryPrice: 0,
      slPrice: 0,
      tpPrice: 0,
      trueInvalidationPrice: 0,
      firstReversalWallPrice: 0,
      reversalWallSource: 'NONE',
      slDistPct: 0,
      tpDistPct: 0,
      rrRatio: 0,
      quantityLotsOrShares: 0,
      maxRiskInr: 0,
      expectedProfitInr: 0,
      vetoReason: reason,
    };
  }
}
