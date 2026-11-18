/**
 * FILE: lib/bharat/institutionalStrikeSelector2026.ts
 * ============================================================================
 * INSTITUTIONAL STRIKE SELECTION & LIQUIDITY ENGINE (2026 SEBI FRAMEWORK)
 * Implements all 5 Core Pillars:
 *   1. Synthetic Future Reference Price: `Synthetic_Fut = ATM_CE - ATM_PE + Strike`
 *   2. 2026 SEBI Index Config (NIFTY=65, BANKNIFTY=30, SENSEX=20, FINNIFTY=60)
 *      + Daily ScripMaster Override
 *   3. 4 Strike Selection Modes: OFFSET (ATM/ITM1/OTM), PREMIUM, DELTA, STRADDLE_RANGE
 *   4. 3-Layer Liquidity Filter: Bid-Ask Spread (<= ₹0.50 or 0.5%), Min OI/Volume,
 *      and Round-Number Magnet Bias (100 for Nifty, 500 for BankNifty/Sensex)
 *   5. 2026 Guardrails: 0-DTE Gamma Shift (Auto ITM1), Freeze Limit Order Slicing,
 *      and Mandatory SEBI Algo Compliance Tagging
 * ============================================================================
 */

export type StrikeSelectionMode = 'OFFSET' | 'PREMIUM' | 'DELTA' | 'STRADDLE_RANGE';

export interface Sebi2026IndexSpec {
  symbol: string;
  exchange: 'NFO' | 'BFO';
  expiryType: 'WEEKLY_AND_MONTHLY' | 'MONTHLY_ONLY';
  expiryDayOfWeek: 'TUESDAY' | 'THURSDAY';
  lotSize: number;
  strikeStep: number;
  roundNumberMagnetStep: number; // 100 for Nifty, 500 for BankNifty/Sensex
  freezeQtyLimit: number;
  maxBidAskSpreadInr: number;
  maxBidAskSpreadPct: number;
  minOpenInterest: number;
}

export interface OptionChainStrikeRow {
  strike: number;
  expiryDate: string; // e.g., "24-Nov-2026"
  dte: number; // Days to expiry (0 = Expiry Day)
  type: 'CE' | 'PE';
  tradingSymbol: string;
  ltp: number;
  bid: number;
  ask: number;
  oi: number;
  volume: number;
  iv?: number;
  delta?: number; // Positive for CE (0..1), Positive magnitude or signed for PE
}

export interface StrikeSelectionRequest {
  indexOrStockSymbol: string;
  spotPrice: number;
  futuresPrice?: number; // Optional direct current-month futures price
  optionType: 'CE' | 'PE';
  selectionMode?: StrikeSelectionMode;
  offset?: number; // For OFFSET mode: -1 = ITM1, 0 = ATM, +1 = OTM1
  targetPremium?: number; // For PREMIUM mode (e.g., ₹100)
  targetDelta?: number; // For DELTA mode (e.g., 0.55 for Buying, 0.25 for Selling)
  requestedLots?: number;
  optionChain: OptionChainStrikeRow[];
  sebiAlgoId?: string;
  overrideSpec?: Partial<Sebi2026IndexSpec>;
}

export interface SelectedStrikeDecision {
  approved: boolean;
  symbol: string;
  tradingSymbol: string;
  optionType: 'CE' | 'PE';
  expiryDate: string;
  dte: number;
  referencePriceUsed: number;
  referencePriceSource: 'CURRENT_MONTH_FUTURES' | 'SYNTHETIC_FUTURE' | 'SPOT_FALLBACK';
  baseAtmStrike: number;
  selectedStrike: number;
  shiftedForLiquidityOrRoundNumber: boolean;
  shiftedForZeroDteGamma: boolean;
  selectionModeUsed: StrikeSelectionMode;
  ltp: number;
  bid: number;
  ask: number;
  bidAskSpreadInr: number;
  bidAskSpreadPct: number;
  openInterest: number;
  volume: number;
  estimatedDelta: number;
  impliedStraddleRangePts: number;
  lotSize: number;
  totalQty: number;
  orderSlices: number[]; // Slicing array respecting exchange Freeze Quantity Limit
  sebiAlgoTag: string;
  vetoReason?: string;
}

export class InstitutionalStrikeSelector2026 {
  /**
   * PILLAR 2: 2026 SEBI OFFICIAL INDEX SPECIFICATIONS
   * (Can be dynamically overridden at runtime by UniversalIndianMarketConnector ScripMaster)
   */
  public static readonly SEBI_2026_INDEX_CONFIG: Record<string, Sebi2026IndexSpec> = {
    NIFTY: {
      symbol: 'NIFTY',
      exchange: 'NFO',
      expiryType: 'WEEKLY_AND_MONTHLY',
      expiryDayOfWeek: 'TUESDAY',
      lotSize: 65,
      strikeStep: 50,
      roundNumberMagnetStep: 100, // 25200, 25300 have higher OI/liquidity than 25250
      freezeQtyLimit: 1800,
      maxBidAskSpreadInr: 0.50,
      maxBidAskSpreadPct: 0.005, // 0.5%
      minOpenInterest: 50000,
    },
    BANKNIFTY: {
      symbol: 'BANKNIFTY',
      exchange: 'NFO',
      expiryType: 'MONTHLY_ONLY',
      expiryDayOfWeek: 'TUESDAY', // Last Tuesday of the month
      lotSize: 30,
      strikeStep: 100,
      roundNumberMagnetStep: 500, // 61500, 62000 carry peak liquidity
      freezeQtyLimit: 900,
      maxBidAskSpreadInr: 1.25,
      maxBidAskSpreadPct: 0.005,
      minOpenInterest: 25000,
    },
    SENSEX: {
      symbol: 'SENSEX',
      exchange: 'BFO',
      expiryType: 'WEEKLY_AND_MONTHLY',
      expiryDayOfWeek: 'THURSDAY',
      lotSize: 20,
      strikeStep: 100,
      roundNumberMagnetStep: 500,
      freezeQtyLimit: 1000,
      maxBidAskSpreadInr: 1.50,
      maxBidAskSpreadPct: 0.006,
      minOpenInterest: 15000,
    },
    FINNIFTY: {
      symbol: 'FINNIFTY',
      exchange: 'NFO',
      expiryType: 'MONTHLY_ONLY',
      expiryDayOfWeek: 'TUESDAY', // Last Tuesday of the month
      lotSize: 60,
      strikeStep: 50,
      roundNumberMagnetStep: 100,
      freezeQtyLimit: 1800,
      maxBidAskSpreadInr: 0.80,
      maxBidAskSpreadPct: 0.005,
      minOpenInterest: 20000,
    },
  };

  /**
   * PILLAR 1: CALCULATE SYNTHETIC FUTURE PRICE & STRADDLE RANGE
   * Formula: `Synthetic_Future = ATM_Call_LTP - ATM_Put_LTP + Provisional_ATM_Strike`
   */
  public static computeReferenceAndStraddle(params: {
    spotPrice: number;
    futuresPrice?: number;
    strikeStep: number;
    optionChain: OptionChainStrikeRow[];
  }): {
    referencePrice: number;
    source: 'CURRENT_MONTH_FUTURES' | 'SYNTHETIC_FUTURE' | 'SPOT_FALLBACK';
    impliedStraddleRangePts: number;
  } {
    const { spotPrice, futuresPrice, strikeStep, optionChain } = params;
    const provisionalAtm = Math.round(spotPrice / strikeStep) * strikeStep;

    const atmCe = optionChain.find(
      (r) => r.type === 'CE' && Math.abs(r.strike - provisionalAtm) < 0.01 && r.ltp > 0
    );
    const atmPe = optionChain.find(
      (r) => r.type === 'PE' && Math.abs(r.strike - provisionalAtm) < 0.01 && r.ltp > 0
    );

    const impliedStraddleRangePts =
      atmCe && atmPe ? Number((atmCe.ltp + atmPe.ltp).toFixed(2)) : 0;

    if (futuresPrice && futuresPrice > 0) {
      return {
        referencePrice: futuresPrice,
        source: 'CURRENT_MONTH_FUTURES',
        impliedStraddleRangePts,
      };
    }

    if (atmCe && atmPe) {
      const syntheticFuture = Number(
        (atmCe.ltp - atmPe.ltp + provisionalAtm).toFixed(2)
      );
      return {
        referencePrice: syntheticFuture,
        source: 'SYNTHETIC_FUTURE',
        impliedStraddleRangePts,
      };
    }

    return {
      referencePrice: spotPrice,
      source: 'SPOT_FALLBACK',
      impliedStraddleRangePts,
    };
  }

  /**
   * MASTER STRIKE SELECTOR: Combines Pillars 1, 2, 3, 4 & 5
   */
  public static selectOptimalStrike(
    req: StrikeSelectionRequest
  ): SelectedStrikeDecision {
    const sym = req.indexOrStockSymbol.toUpperCase();
    const baseSpec: Sebi2026IndexSpec = {
      ...(this.SEBI_2026_INDEX_CONFIG[sym] || {
        symbol: sym,
        exchange: 'NFO',
        expiryType: 'MONTHLY_ONLY',
        expiryDayOfWeek: 'TUESDAY',
        lotSize: 250,
        strikeStep: 10,
        roundNumberMagnetStep: 20,
        freezeQtyLimit: 5000,
        maxBidAskSpreadInr: 0.50,
        maxBidAskSpreadPct: 0.006,
        minOpenInterest: 5000,
      }),
      ...(req.overrideSpec || {}),
    };

    const chainSide = (req.optionChain || []).filter(
      (r) => r.type === req.optionType && r.ltp > 0
    );
    if (chainSide.length === 0) {
      return this.reject(sym, req.optionType, 'EMPTY_OPTION_CHAIN_FOR_SIDE');
    }

    // 1. PILLAR 1: Compute Synthetic Future Reference Price & Base ATM Strike
    const refData = this.computeReferenceAndStraddle({
      spotPrice: req.spotPrice,
      futuresPrice: req.futuresPrice,
      strikeStep: baseSpec.strikeStep,
      optionChain: req.optionChain,
    });

    const baseAtmStrike =
      Math.round(refData.referencePrice / baseSpec.strikeStep) * baseSpec.strikeStep;

    // Determine Days-to-Expiry (DTE) from nearest contract
    const dte = chainSide[0].dte ?? 1;
    const mode: StrikeSelectionMode = req.selectionMode || 'OFFSET';

    // 2. PILLAR 5 (0-DTE GAMMA GUARDRAIL):
    // On Expiry Day (0-DTE), if Option Buying with offset=0 (ATM), auto-shift to ITM1 (offset = -1)
    // so high Gamma/Theta decay on ATM doesn't crush the premium!
    let effectiveOffset = req.offset ?? 0;
    let shiftedForZeroDteGamma = false;
    if (mode === 'OFFSET' && dte === 0 && effectiveOffset === 0) {
      effectiveOffset = -1; // Shift to ITM1 (~0.60 Delta) on Expiry Day!
      shiftedForZeroDteGamma = true;
    }

    // 3. PILLAR 3: SELECT TARGET STRIKE USING ONE OF THE 4 MODES
    let targetStrike = baseAtmStrike;

    if (mode === 'OFFSET') {
      // CE: +offset = OTM, -offset = ITM | PE: -offset = ITM (higher strike), +offset = OTM (lower strike)
      targetStrike =
        req.optionType === 'CE'
          ? baseAtmStrike + effectiveOffset * baseSpec.strikeStep
          : baseAtmStrike - effectiveOffset * baseSpec.strikeStep;
    } else if (mode === 'PREMIUM' && req.targetPremium && req.targetPremium > 0) {
      const liquidCandidates = chainSide.filter((r) =>
        this.passesLiquidityCheck(r, baseSpec)
      );
      const pool = liquidCandidates.length > 0 ? liquidCandidates : chainSide;
      pool.sort(
        (a, b) =>
          Math.abs(a.ltp - req.targetPremium!) - Math.abs(b.ltp - req.targetPremium!)
      );
      targetStrike = pool[0].strike;
    } else if (mode === 'DELTA') {
      const desiredDelta = req.targetDelta ?? 0.55; // Default 0.55 Delta (ATM/ITM1 for Option Buying)
      const liquidCandidates = chainSide.filter((r) =>
        this.passesLiquidityCheck(r, baseSpec)
      );
      const pool = liquidCandidates.length > 0 ? liquidCandidates : chainSide;
      pool.sort((a, b) => {
        const dA = Math.abs(
          a.delta ?? this.estimateOptionDelta(a.strike, refData.referencePrice, baseSpec.strikeStep, req.optionType)
        );
        const dB = Math.abs(
          b.delta ?? this.estimateOptionDelta(b.strike, refData.referencePrice, baseSpec.strikeStep, req.optionType)
        );
        return Math.abs(dA - desiredDelta) - Math.abs(dB - desiredDelta);
      });
      targetStrike = pool[0].strike;
    } else if (mode === 'STRADDLE_RANGE') {
      const straddleOffset = Math.max(
        baseSpec.strikeStep,
        Math.round(refData.impliedStraddleRangePts / baseSpec.strikeStep) *
          baseSpec.strikeStep
      );
      targetStrike =
        req.optionType === 'CE'
          ? baseAtmStrike + straddleOffset
          : baseAtmStrike - straddleOffset;
    }

    // 4. PILLAR 4: LIQUIDITY, BID-ASK SPREAD & ROUND-NUMBER BIAS (100/500 MAGNET)
    let chosenRow = chainSide.find((r) => Math.abs(r.strike - targetStrike) < 0.01);
    let shiftedForLiquidityOrRoundNumber = false;

    // Check if an adjacent Round-Number Strike (e.g., 25300 vs 25250 on Nifty, or 61500 vs 61600 on BankNifty)
    // has significantly tighter Bid-Ask spread and higher OI, OR if initial strike fails liquidity check
    const initialLiquid = chosenRow ? this.passesLiquidityCheck(chosenRow, baseSpec) : false;

    if (!chosenRow || !initialLiquid || targetStrike % baseSpec.roundNumberMagnetStep !== 0) {
      // Find nearby strikes within +/- 1 strikeStep
      const nearby = chainSide.filter(
        (r) =>
          Math.abs(r.strike - targetStrike) <= baseSpec.strikeStep &&
          this.passesLiquidityCheck(r, baseSpec)
      );

      if (nearby.length > 0) {
        // Prefer Round-Number strikes (multiples of 100 on Nifty / 500 on BankNifty) with highest OI & tightest spread
        nearby.sort((a, b) => {
          const aIsRound = a.strike % baseSpec.roundNumberMagnetStep === 0 ? 1 : 0;
          const bIsRound = b.strike % baseSpec.roundNumberMagnetStep === 0 ? 1 : 0;
          if (aIsRound !== bIsRound && !initialLiquid) return bIsRound - aIsRound;
          const spreadA = Math.max(0, a.ask - a.bid);
          const spreadB = Math.max(0, b.ask - b.bid);
          return spreadA - spreadB || b.oi - a.oi;
        });

        if (!chosenRow || !initialLiquid || nearby[0].strike !== chosenRow.strike) {
          chosenRow = nearby[0];
          shiftedForLiquidityOrRoundNumber = chosenRow.strike !== targetStrike;
        }
      }
    }

    if (!chosenRow || !this.passesLiquidityCheck(chosenRow, baseSpec)) {
      return this.reject(
        sym,
        req.optionType,
        `LIQUIDITY_OR_SPREAD_VETO: Strike ${targetStrike} ${req.optionType} failed Bid-Ask Spread / OI check`
      );
    }

    // 5. PILLAR 5: ORDER SLICING FOR EXCHANGE FREEZE QUANTITY LIMIT & SEBI ALGO TAG
    const lots = Math.max(1, req.requestedLots ?? 1);
    const totalQty = lots * baseSpec.lotSize;
    const orderSlices = this.sliceOrderByFreezeLimit(
      totalQty,
      baseSpec.lotSize,
      baseSpec.freezeQtyLimit
    );

    const spreadInr = Number(Math.max(0, chosenRow.ask - chosenRow.bid).toFixed(2));
    const spreadPct = Number((spreadInr / Math.max(1, chosenRow.ltp)).toFixed(4));
    const estimatedDelta = Number(
      (
        chosenRow.delta ??
        this.estimateOptionDelta(
          chosenRow.strike,
          refData.referencePrice,
          baseSpec.strikeStep,
          req.optionType
        )
      ).toFixed(2)
    );

    return {
      approved: true,
      symbol: sym,
      tradingSymbol: chosenRow.tradingSymbol,
      optionType: req.optionType,
      expiryDate: chosenRow.expiryDate,
      dte,
      referencePriceUsed: refData.referencePrice,
      referencePriceSource: refData.source,
      baseAtmStrike,
      selectedStrike: chosenRow.strike,
      shiftedForLiquidityOrRoundNumber,
      shiftedForZeroDteGamma,
      selectionModeUsed: mode,
      ltp: chosenRow.ltp,
      bid: chosenRow.bid,
      ask: chosenRow.ask,
      bidAskSpreadInr: spreadInr,
      bidAskSpreadPct: spreadPct,
      openInterest: chosenRow.oi,
      volume: chosenRow.volume,
      estimatedDelta,
      impliedStraddleRangePts: refData.impliedStraddleRangePts,
      lotSize: baseSpec.lotSize,
      totalQty,
      orderSlices,
      sebiAlgoTag: req.sebiAlgoId || 'SEBI_ALGO_NEXUS_BHARAT_2026',
    };
  }

  private static passesLiquidityCheck(
    row: OptionChainStrikeRow,
    spec: Sebi2026IndexSpec
  ): boolean {
    if (!row || row.ltp <= 0) return false;
    const spreadInr = Math.max(0, row.ask - row.bid);
    const spreadPct = spreadInr / row.ltp;

    // Spread passes if it is within EITHER the ₹ cap OR the % of LTP cap
    const spreadOk =
      spreadInr <= spec.maxBidAskSpreadInr || spreadPct <= spec.maxBidAskSpreadPct;
    const oiOk = row.oi >= spec.minOpenInterest;
    return spreadOk && oiOk;
  }

  private static estimateOptionDelta(
    strike: number,
    refPrice: number,
    step: number,
    optionType: 'CE' | 'PE'
  ): number {
    const stepsAway = (strike - refPrice) / Math.max(1, step);
    const rawCallDelta = 1 / (1 + Math.exp(0.35 * stepsAway));
    return optionType === 'CE' ? rawCallDelta : 1 - rawCallDelta;
  }

  private static sliceOrderByFreezeLimit(
    totalQty: number,
    lotSize: number,
    freezeLimit: number
  ): number[] {
    if (totalQty <= freezeLimit) return [totalQty];
    const maxLotsPerSlice = Math.max(1, Math.floor(freezeLimit / lotSize));
    const maxSliceQty = maxLotsPerSlice * lotSize;
    const slices: number[] = [];
    let remaining = totalQty;
    while (remaining > 0) {
      const slice = Math.min(remaining, maxSliceQty);
      slices.push(slice);
      remaining -= slice;
    }
    return slices;
  }

  private static reject(
    symbol: string,
    optionType: 'CE' | 'PE',
    reason: string
  ): SelectedStrikeDecision {
    return {
      approved: false,
      symbol,
      tradingSymbol: '',
      optionType,
      expiryDate: '',
      dte: 0,
      referencePriceUsed: 0,
      referencePriceSource: 'SPOT_FALLBACK',
      baseAtmStrike: 0,
      selectedStrike: 0,
      shiftedForLiquidityOrRoundNumber: false,
      shiftedForZeroDteGamma: false,
      selectionModeUsed: 'OFFSET',
      ltp: 0,
      bid: 0,
      ask: 0,
      bidAskSpreadInr: 0,
      bidAskSpreadPct: 0,
      openInterest: 0,
      volume: 0,
      estimatedDelta: 0,
      impliedStraddleRangePts: 0,
      lotSize: 0,
      totalQty: 0,
      orderSlices: [],
      sebiAlgoTag: 'SEBI_ALGO_NEXUS_BHARAT_2026',
      vetoReason: reason,
    };
  }
}
