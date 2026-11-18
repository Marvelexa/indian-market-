/**
 * FILE: lib/bharat/unlimitedBreathingTrailEngine.ts
 * ============================================================================
 * DUAL-SHIELD BREATHING TRAIL ENGINE (TP1 +₹500 -> TP2 +₹1,000 -> UNLIMITED)
 *
 * Solves the Ultimate Option Trailing Dilemma:
 *   1. Gives 100% Breathing Room against fake 1m/5m wicks via `softCloseLockInr`
 *      (checked ONLY when a 5-minute candle finishes closing!).
 *   2. Protects profits from sudden intra-candle V-shape crashes via
 *      `hardTickAirbagInr` (checked on EVERY live tick!).
 *   3. Scales infinitely in ₹500 steps (`TP1 500`, `TP2 1000`, `1500`, `2000` ... ∞)
 * ============================================================================
 */

export interface DualShieldTrailState {
  stage: number; // 0 = Base, 1 = TP1(500), 2 = TP2(1000), 3 = 1500 ... N = Unlimited
  peakPnlInr: number;
  softCloseLockInr: number; // Checked ONLY on 5-minute candle close (Wick-Immune!)
  hardTickAirbagInr: number; // Checked on EVERY live tick (Flash-Crash Shield!)
  softSlPremium: number;
  hardSlPremium: number;
}

export interface DualShieldEvaluationInput {
  entryPremium: number;
  currentPremium: number; // Live tick LTP or candle close premium
  candleLowPremium?: number; // For backtest/replay: intra-bar worst wick low
  lotSize: number;
  prevState: DualShieldTrailState;
  isFiveMinuteCandleClose: boolean;
  isEma9BrokenAgainstTrend?: boolean; // Optional extra confirmation on 5m close
  maxInitialLossInr?: number; // Default -₹2,200
}

export interface DualShieldEvaluationResult {
  shouldExit: boolean;
  exitPremium: number;
  realizedPnlInr: number;
  exitReason: string;
  updatedState: DualShieldTrailState;
}

export class UnlimitedBreathingTrailEngine {
  /**
   * Initializes Dual-Shield state when a new option trade is opened
   */
  public static createInitialState(
    entryPremium: number,
    lotSize: number,
    maxInitialLossInr = 2500
  ): DualShieldTrailState {
    const hardFloorInr = -Math.abs(maxInitialLossInr);
    const hardSlPremium = Number(
      Math.max(0.05, entryPremium + hardFloorInr / lotSize).toFixed(2)
    );

    return {
      stage: 0,
      peakPnlInr: 0,
      softCloseLockInr: hardFloorInr,
      hardTickAirbagInr: hardFloorInr,
      softSlPremium: hardSlPremium,
      hardSlPremium,
    };
  }

  /**
   * Evaluates live tick or 5-minute candle close:
   * - Updates TP1 (500), TP2 (1000), and Unlimited +500 step shields
   * - Checks Hard Tick Airbag on every tick / intra-bar wick
   * - Checks Soft Lock ONLY on 5-minute candle close
   */
  public static evaluateTickOrCandle(
    input: DualShieldEvaluationInput
  ): DualShieldEvaluationResult {
    const {
      entryPremium,
      currentPremium,
      lotSize,
      prevState,
      isFiveMinuteCandleClose,
    } = input;

    const worstTickPremium =
      input.candleLowPremium !== undefined
        ? Math.min(currentPremium, input.candleLowPremium)
        : currentPremium;

    const currentPnlInr = Number(
      ((currentPremium - entryPremium) * lotSize).toFixed(2)
    );
    const worstWickPnlInr = Number(
      ((worstTickPremium - entryPremium) * lotSize).toFixed(2)
    );

    // -------------------------------------------------------------------------
    // 1. CHECK HARD TICK AIRBAG FIRST (Protects against sudden mid-bar crash)
    // -------------------------------------------------------------------------
    if (
      worstTickPremium <= prevState.hardSlPremium ||
      worstWickPnlInr <= prevState.hardTickAirbagInr
    ) {
      const exitPrem = Math.max(0.05, prevState.hardSlPremium);
      const realizedPnlInr = Number(((exitPrem - entryPremium) * lotSize).toFixed(2));
      const label =
        prevState.stage === 0
          ? `Hard Shield SL (${realizedPnlInr >= 0 ? '+' : ''}₹${realizedPnlInr.toFixed(0)})`
          : `TP${prevState.stage} Hard Airbag Shield (+₹${realizedPnlInr.toFixed(0)})`;

      return {
        shouldExit: true,
        exitPremium: exitPrem,
        realizedPnlInr,
        exitReason: label,
        updatedState: prevState,
      };
    }

    // -------------------------------------------------------------------------
    // 2. CHECK SOFT LOCK ONLY ON 5-MINUTE CANDLE CLOSE (100% Wick-Immune!)
    //    If an intra-bar wick dipped below Soft Lock but recovered before the
    //    5m candle closed, the trade STAYS ALIVE!
    // -------------------------------------------------------------------------
    if (
      isFiveMinuteCandleClose &&
      prevState.stage >= 1 &&
      (currentPremium <= prevState.softSlPremium ||
        currentPnlInr <= prevState.softCloseLockInr) &&
      (input.isEma9BrokenAgainstTrend === undefined || input.isEma9BrokenAgainstTrend)
    ) {
      const exitPrem = currentPremium;
      const realizedPnlInr = Number(((exitPrem - entryPremium) * lotSize).toFixed(2));
      return {
        shouldExit: true,
        exitPremium: exitPrem,
        realizedPnlInr,
        exitReason: `TP${prevState.stage} 5m-Close Trail Lock (+₹${realizedPnlInr.toFixed(0)})`,
        updatedState: prevState,
      };
    }

    // -------------------------------------------------------------------------
    // 3. ADVANCE THE DUAL-SHIELD LADDER (TP1 500 -> TP2 1000 -> UNLIMITED ∞)
    // -------------------------------------------------------------------------
    const newPeakPnlInr = Math.max(prevState.peakPnlInr, currentPnlInr);
    // Calculate current ₹500 step stage (500 = Stage 1, 1000 = Stage 2, 1500 = Stage 3 ... ∞)
    const computedStage = Math.max(
      prevState.stage,
      Math.floor(newPeakPnlInr / 500)
    );

    let targetSoftLockInr = prevState.softCloseLockInr;
    let targetHardAirbagInr = prevState.hardTickAirbagInr;

    if (computedStage === 1) {
      // TP1 (+₹500 reached):
      // Soft 5m-Close Lock = +₹250 | Hard Tick Airbag = -₹350 (₹850 wick breathing room!)
      targetSoftLockInr = 250;
      targetHardAirbagInr = -350;
    } else if (computedStage === 2) {
      // TP2 (+₹1,000 reached):
      // Soft 5m-Close Lock = +₹650 | Hard Tick Airbag = +₹300 (100% Risk-Free + ₹700 wick room!)
      targetSoftLockInr = 650;
      targetHardAirbagInr = 300;
    } else if (computedStage === 3) {
      // TP3 (+₹1,500 reached):
      targetSoftLockInr = 1100;
      targetHardAirbagInr = 750;
    } else if (computedStage === 4) {
      // TP4 (+₹2,000 reached):
      targetSoftLockInr = 1550;
      targetHardAirbagInr = 1200;
    } else if (computedStage === 5) {
      // TP5 (+₹2,500 reached):
      targetSoftLockInr = 2000;
      targetHardAirbagInr = 1600;
    } else if (computedStage >= 6) {
      // UNLIMITED RUNNER (+₹3,000 to +₹1,00,000+ in ₹500 steps forever):
      // Soft 5m-Close Lock = 82% of Peak Profit
      // Hard Tick Airbag = 70% of Peak Profit (leaves 30% breathing room for big trend swings!)
      targetSoftLockInr = Math.round(newPeakPnlInr * 0.82);
      targetHardAirbagInr = Math.round(newPeakPnlInr * 0.70);
    }

    // Never allow locks to move backward (Ratchet only upward!)
    const finalSoftLockInr = Math.max(prevState.softCloseLockInr, targetSoftLockInr);
    const finalHardAirbagInr = Math.max(
      prevState.hardTickAirbagInr,
      targetHardAirbagInr
    );

    const updatedState: DualShieldTrailState = {
      stage: computedStage,
      peakPnlInr: newPeakPnlInr,
      softCloseLockInr: finalSoftLockInr,
      hardTickAirbagInr: finalHardAirbagInr,
      softSlPremium: Number(
        Math.max(0.05, entryPremium + finalSoftLockInr / lotSize).toFixed(2)
      ),
      hardSlPremium: Number(
        Math.max(0.05, entryPremium + finalHardAirbagInr / lotSize).toFixed(2)
      ),
    };

    return {
      shouldExit: false,
      exitPremium: currentPremium,
      realizedPnlInr: currentPnlInr,
      exitReason: 'HOLDING_WITH_DUAL_SHIELD',
      updatedState,
    };
  }
}
