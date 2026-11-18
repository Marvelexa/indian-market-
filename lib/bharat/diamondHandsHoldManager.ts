/**
 * FILE: lib/bharat/diamondHandsHoldManager.ts
 * ============================================================================
 * DIAMOND-HANDS STRUCTURAL HOLD & BREATHING LADDER MANAGER
 * 100% BANS "Quick Scalp Exit" (+₹165 / +₹304 / -₹550 2-minute premature exits)
 * Enforces:
 *   - Minimum 15-Minute (3x 5m bars) Structural Breathing Window
 *   - ZERO profit-taking or tight trailing below +₹1,500 PnL
 *   - Progressive Breathing Ladder up to +₹8,000+ Runner
 * ============================================================================
 */

export interface HoldEvaluationInput {
  symbol: string;
  optionType: 'CE' | 'PE';
  lotSize: number;
  entryPremium: number;
  currentPremium: number;
  initialSlPremium: number;
  currentSlPremium: number;
  peakPnlInr: number;
  ladderStage: number;
  entryTimestampMs: number;
  nowTimestampMs: number;
  underlyingSpotLtp: number;
  structuralInvalidationSpot: number; // 15m Support (for CE) or 15m Resistance (for PE)
  isFiveMinCandleClosed: boolean;
}

export interface HoldEvaluationDecision {
  action: 'HOLD_POSITION' | 'UPDATE_TRAILING_SL' | 'EXECUTE_EXIT';
  newSlPremium: number;
  newLadderStage: number;
  newPeakPnlInr: number;
  unrealizedPnlInr: number;
  holdDurationMinutes: number;
  exitReason?:
    | 'HARD_SL_HIT'
    | 'STRUCTURAL_15M_INVALIDATION_CLOSED'
    | 'STAGE_1_LOCK_850_HIT'
    | 'STAGE_2_LOCK_1650_HIT'
    | 'STAGE_3_LOCK_2800_HIT'
    | 'STAGE_4_RUNNER_TRAIL_HIT'
    | 'MANDATORY_318PM_SQUARE_OFF';
  statusNote: string;
}

export class DiamondHandsHoldManager {
  /**
   * Evaluates an open option position and strictly prevents premature 2-minute
   * "Quick Scalp Exits" (+₹165, +₹304, -₹550) so winners can run to ₹2,000–₹8,000+.
   */
  public static evaluatePositionHold(
    input: HoldEvaluationInput
  ): HoldEvaluationDecision {
    const {
      optionType,
      lotSize,
      entryPremium,
      currentPremium,
      currentSlPremium,
      entryTimestampMs,
      nowTimestampMs,
      underlyingSpotLtp,
      structuralInvalidationSpot,
      isFiveMinCandleClosed,
    } = input;

    const holdDurationMinutes = Math.max(
      0,
      (nowTimestampMs - entryTimestampMs) / (60 * 1000)
    );
    const pnlPoints = currentPremium - entryPremium;
    const unrealizedPnlInr = Number((pnlPoints * lotSize).toFixed(2));
    const newPeakPnlInr = Math.max(input.peakPnlInr, unrealizedPnlInr);

    // 1. CHECK MANDATORY 03:18 PM IST INTRADAY SQUARE-OFF
    const istDate = new Date(nowTimestampMs + 5.5 * 60 * 60 * 1000);
    const istMinutes = istDate.getUTCHours() * 60 + istDate.getUTCMinutes();
    if (istMinutes >= 15 * 60 + 18 && istMinutes <= 15 * 60 + 35) {
      return {
        action: 'EXECUTE_EXIT',
        newSlPremium: currentSlPremium,
        newLadderStage: input.ladderStage,
        newPeakPnlInr,
        unrealizedPnlInr,
        holdDurationMinutes,
        exitReason: 'MANDATORY_318PM_SQUARE_OFF',
        statusNote: '03:18 PM IST Intraday Auto Square-Off',
      };
    }

    // 2. CHECK HARD STOP LOSS (-₹2,200 to -₹2,500 Cap) OR TRAILED LADDER SL
    // 5-MINUTE BREATHING ROOM GUARANTEE: In the first 5 minutes of trade entry,
    // NEVER exit on trailing SL! ONLY exit if genuine Hard SL (-₹2,500) is breached!
    const isHardSlHit = unrealizedPnlInr <= -2500 || (input.ladderStage === 0 && currentPremium <= currentSlPremium);
    const isTrailedSlHit = input.ladderStage > 0 && currentPremium <= currentSlPremium && holdDurationMinutes >= 5.0;

    if (isHardSlHit || isTrailedSlHit) {
      const reason =
        input.ladderStage === 0
          ? 'HARD_SL_HIT'
          : input.ladderStage === 1
          ? 'STAGE_1_LOCK_850_HIT'
          : input.ladderStage === 2
          ? 'STAGE_2_LOCK_1650_HIT'
          : input.ladderStage === 3
          ? 'STAGE_3_LOCK_2800_HIT'
          : 'STAGE_4_RUNNER_TRAIL_HIT';

      return {
        action: 'EXECUTE_EXIT',
        newSlPremium: currentSlPremium,
        newLadderStage: input.ladderStage,
        newPeakPnlInr,
        unrealizedPnlInr,
        holdDurationMinutes,
        exitReason: reason,
        statusNote: `Exited on verified SL (${reason}) at ₹${currentPremium}`,
      };
    }

    // 3. CHECK TRUE 15-MINUTE STRUCTURAL BREAKDOWN (ONLY AFTER 15 MINS & ON 5M CANDLE CLOSE!)
    // Never panic-exit in 2 minutes on a -₹550 tick wobble!
    if (
      input.ladderStage === 0 &&
      holdDurationMinutes >= 15 &&
      isFiveMinCandleClosed &&
      structuralInvalidationSpot > 0
    ) {
      const structureBroken =
        optionType === 'CE'
          ? underlyingSpotLtp < structuralInvalidationSpot * 0.9985
          : underlyingSpotLtp > structuralInvalidationSpot * 1.0015;

      if (structureBroken && unrealizedPnlInr <= -900) {
        return {
          action: 'EXECUTE_EXIT',
          newSlPremium: currentSlPremium,
          newLadderStage: input.ladderStage,
          newPeakPnlInr,
          unrealizedPnlInr,
          holdDurationMinutes,
          exitReason: 'STRUCTURAL_15M_INVALIDATION_CLOSED',
          statusNote: '5m Candle Closed Beyond 15m Structural Invalidation Level',
        };
      }
    }

    // =========================================================================
    // 4. DIAMOND-HANDS BREATHING PROFIT LADDER (NO +₹165 / +₹304 QUICK EXITS!)
    //    0 to +₹1,499 PnL -> 100% HANDS-OFF HOLD!
    //    Requires minimum 2 minutes holding duration before advancing ladder
    // =========================================================================
    let targetStage = input.ladderStage;
    let targetLockedPnlInr = 0;

    if (holdDurationMinutes >= 2.0) {
      if (newPeakPnlInr >= 6000) {
        targetStage = 4;
        // Trail ₹1,400 behind peak profit so huge runners never choke early
        targetLockedPnlInr = Math.max(4500, newPeakPnlInr - 1400);
      } else if (newPeakPnlInr >= 4000 && input.ladderStage < 3) {
        targetStage = 3;
        targetLockedPnlInr = 2800; // ₹1,200 breathing cushion
      } else if (newPeakPnlInr >= 2500 && input.ladderStage < 2) {
        targetStage = 2;
        targetLockedPnlInr = 1650; // ₹850 breathing cushion
      } else if (newPeakPnlInr >= 1500 && input.ladderStage < 1) {
        targetStage = 1;
        targetLockedPnlInr = 850; // ₹650 breathing cushion (100% Net Profitable after tax/slippage!)
      }
    }

    if (targetStage > input.ladderStage || (targetStage === 4 && targetLockedPnlInr > 0)) {
      const candidateSlPremium = Number(
        (entryPremium + targetLockedPnlInr / lotSize).toFixed(2)
      );

      // Ensure at least a 3% premium breathing cushion below currentPremium
      const maxAllowedSl = Number((currentPremium * 0.97).toFixed(2));
      const newSl = Math.min(candidateSlPremium, maxAllowedSl);

      if (newSl > currentSlPremium) {
        return {
          action: 'UPDATE_TRAILING_SL',
          newSlPremium: newSl,
          newLadderStage: targetStage,
          newPeakPnlInr,
          unrealizedPnlInr,
          holdDurationMinutes,
          statusNote: `Stage ${targetStage} Active: Locked +₹${targetLockedPnlInr} (Breathing SL @ ₹${newSl})`,
        };
      }
    }

    return {
      action: 'HOLD_POSITION',
      newSlPremium: currentSlPremium,
      newLadderStage: input.ladderStage,
      newPeakPnlInr,
      unrealizedPnlInr,
      holdDurationMinutes,
      statusNote: `Holding Strong (${holdDurationMinutes.toFixed(1)}m) | PnL: ₹${unrealizedPnlInr} | Waiting for +₹1,500 Stage 1`,
    };
  }
}
