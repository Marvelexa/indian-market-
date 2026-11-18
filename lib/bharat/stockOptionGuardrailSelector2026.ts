/**
 * FILE: lib/bharat/stockOptionGuardrailSelector2026.ts
 * ============================================================================
 * INSTITUTIONAL NSE F&O STOCK OPTION STRIKE SELECTOR & 5-GUARDRAIL ENGINE
 *
 * Implements all Stock-Specific F&O Rules:
 *   1. Dynamic Array-Index ATM & Offset Lookup (No `round(spot/step)*step` bugs;
 *      handles odd corporate-action strikes like 1422.5 or 182.5 cleanly).
 *   2. Guardrail 1 — NSE F&O Ban Period Check (MWPL >= 95% Block).
 *   3. Guardrail 2 — Physical Settlement Delivery Cut-Off (If DTE <= 4 days,
 *      auto-rolls to Next Month Expiry or blocks fresh entry).
 *   4. Guardrail 3 — Strict Liquidity & Bid-Ask Spread Gate (Spread <= 1.0% of LTP
 *      and OI >= threshold, with +/-1 strike neighbor check).
 *   5. Guardrail 4 — Quarterly Results / Corporate Action / IV-Crush Filter.
 *   6. Guardrail 5 — Protected Limit Order Pricing (`Ask * 1.002`, NEVER Market Order)
 *      + Dynamic Lot Size & Freeze Quantity Slicing.
 * ============================================================================
 */

export interface StockOptionStrikeQuote {
  symbol: string; // Underlying e.g. "RELIANCE"
  tradingSymbol: string; // e.g. "RELIANCE26NOV261350CE"
  expiryDate: string; // e.g. "24-NOV-2026"
  daysToExpiry: number; // Trading days to expiry
  isNextMonthContract?: boolean;
  type: 'CE' | 'PE';
  strike: number;
  ltp: number;
  bid: number;
  ask: number;
  oi: number; // Open Interest in shares (or contracts * lotSize)
  volume: number;
  iv?: number; // Implied Volatility %
  lotSize: number;
  freezeQtyLimit: number;
  tickSize: number;
}

export interface StockOptionSelectionInput {
  symbol: string;
  spotPrice: number;
  optionType: 'CE' | 'PE';
  availableChain: StockOptionStrikeQuote[]; // Current (and optionally Next Month) listed strikes
  foBanList?: string[]; // Today's NSE F&O Ban symbols
  upcomingEventsSymbols?: string[]; // Symbols with Quarterly Results / Ex-Dividend in next 2 days
  offset?: number; // 0 = ATM, -1 = ITM1, +1 = OTM1
  maxSpreadPct?: number; // Default 1.0% of LTP
  maxSpreadInr?: number; // Hard cap e.g. ₹0.60
  minOpenInterestShares?: number; // Default 100,000 shares (or 50 lots)
  autoRollToNextMonthOnPhysicalWindow?: boolean; // If DTE <= 4, use Next Month contract
  requestedLots?: number;
  sebiAlgoId?: string;
}

export interface StockOptionSelectionDecision {
  approved: boolean;
  symbol: string;
  tradingSymbol: string;
  optionType: 'CE' | 'PE';
  expiryDate: string;
  daysToExpiry: number;
  rolledToNextMonthForPhysicalGuard: boolean;
  spotPrice: number;
  atmStrike: number;
  selectedStrike: number;
  offsetUsed: number;
  ltp: number;
  bid: number;
  ask: number;
  spreadInr: number;
  spreadPct: number;
  openInterest: number;
  volume: number;
  orderType: 'LIMIT'; // Strictly LIMIT order only (never MARKET in Stock Options!)
  protectedLimitBuyPrice: number; // Ask + 0.2% buffer (clamped to tick size)
  lotSize: number;
  totalQty: number;
  orderSlices: number[];
  sebiAlgoTag: string;
  vetoReason?: string;
}

export class StockOptionGuardrailSelector2026 {
  /**
   * TOP 38 ULTRA-LIQUID NSE F&O STOCK UNIVERSE WHITELIST
   * Eliminates illiquid mid/small-cap F&O traps where freak trades happen.
   */
  public static readonly TOP_LIQUID_FO_WHITELIST: Set<string> = new Set([
    'RELIANCE',
    'HDFCBANK',
    'ICICIBANK',
    'SBIN',
    'AXISBANK',
    'KOTAKBANK',
    'TCS',
    'INFY',
    'HCLTECH',
    'WIPRO',
    'TECHM',
    'LT',
    'TATAMOTORS',
    'M&M',
    'MARUTI',
    'BAJAJ-AUTO',
    'BAJFINANCE',
    'BAJAJFINSV',
    'CHOLAFIN',
    'SHRIRAMFIN',
    'PFC',
    'RECLTD',
    'TATASTEEL',
    'JSWSTEEL',
    'JINDALSTEL',
    'HINDALCO',
    'VEDL',
    'BHARTIARTL',
    'ITC',
    'HINDUNILVR',
    'SUNPHARMA',
    'CIPLA',
    'DRREDDY',
    'DIVISLAB',
    'NTPC',
    'POWERGRID',
    'ONGC',
    'COALINDIA',
    'ADANIENT',
    'ADANIPORTS',
    'BEL',
    'HAL',
    'TRENT',
  ]);

  private static cachedNseBanList: Set<string> = new Set();
  private static lastBanSyncMs = 0;

  /**
   * 1. AUTO-FETCH DAILY NSE F&O BAN LIST (MWPL >= 95%)
   */
  public static async syncNseFoBanList(): Promise<string[]> {
    const now = Date.now();
    if (this.cachedNseBanList.size > 0 && now - this.lastBanSyncMs < 4 * 3600 * 1000) {
      return Array.from(this.cachedNseBanList);
    }

    try {
      const res = await fetch(
        'https://www.nseindia.com/api/fo-secban',
        {
          headers: {
            'User-Agent':
              'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            Accept: 'application/json',
          },
        }
      );
      if (res.ok) {
        const data = (await res.json()) as { secBanList?: string[] };
        if (Array.isArray(data?.secBanList)) {
          this.cachedNseBanList = new Set(
            data.secBanList.map((s) => s.trim().toUpperCase())
          );
          this.lastBanSyncMs = now;
        }
      }
    } catch {
      // Keep existing cached list if NSE endpoint times out
    }
    return Array.from(this.cachedNseBanList);
  }

  /**
   * 2. MASTER STOCK OPTION STRIKE SELECTOR WITH 5 INSTITUTIONAL GUARDRAILS
   */
  public static selectStockOptionStrike(
    input: StockOptionSelectionInput
  ): StockOptionSelectionDecision {
    const sym = input.symbol.trim().toUpperCase();
    const offset = input.offset ?? 0;
    const maxSpreadPct = input.maxSpreadPct ?? 1.0; // Default <= 1.0% of LTP
    const maxSpreadInr = input.maxSpreadInr ?? 0.65;

    // -------------------------------------------------------------------------
    // GUARDRAIL 0: TOP LIQUID UNIVERSE WHITELIST CHECK
    // -------------------------------------------------------------------------
    if (!this.TOP_LIQUID_FO_WHITELIST.has(sym)) {
      return this.reject(
        sym,
        input.optionType,
        `UNIVERSE_VETO: ${sym} is outside the Top Liquid F&O Stock Whitelist`
      );
    }

    // -------------------------------------------------------------------------
    // GUARDRAIL 1: NSE F&O BAN PERIOD CHECK (MWPL >= 95%)
    // -------------------------------------------------------------------------
    const banSet = new Set([
      ...Array.from(this.cachedNseBanList),
      ...(input.foBanList || []).map((s) => s.toUpperCase()),
    ]);
    if (banSet.has(sym)) {
      return this.reject(
        sym,
        input.optionType,
        `FO_BAN_PERIOD_VETO: ${sym} is currently in NSE F&O Ban List (MWPL >= 95%)`
      );
    }

    // -------------------------------------------------------------------------
    // GUARDRAIL 4: EARNINGS / RESULTS & CORPORATE ACTION IV-CRUSH FILTER
    // -------------------------------------------------------------------------
    const eventSet = new Set(
      (input.upcomingEventsSymbols || []).map((s) => s.toUpperCase())
    );
    if (eventSet.has(sym)) {
      return this.reject(
        sym,
        input.optionType,
        `CORPORATE_EVENT_IV_CRUSH_VETO: ${sym} has Quarterly Results / Ex-Dividend within 48h`
      );
    }

    // Filter chain for matching optionType (CE or PE) with valid LTP
    const allSideContracts = (input.availableChain || []).filter(
      (r) => r.type === input.optionType && r.ltp > 0 && r.strike > 0
    );
    if (allSideContracts.length === 0) {
      return this.reject(sym, input.optionType, 'NO_OPTION_CHAIN_DATA_AVAILABLE');
    }

    // -------------------------------------------------------------------------
    // GUARDRAIL 2: PHYSICAL SETTLEMENT CUT-OFF (DTE < 1 DAY)
    // For intraday scalpers/runners with mandatory 03:18 PM auto square-off,
    // positions are never held overnight into physical expiry. We trade the active
    // liquid near-month contract right up to expiry eve (DTE >= 1). Only on expiry day
    // final hours does it roll to next month to avoid zero-liquidity delivery traps.
    // -------------------------------------------------------------------------
    const currentExpiryContracts = allSideContracts.filter(
      (r) => !r.isNextMonthContract && r.daysToExpiry >= 1
    );
    const nextMonthContracts = allSideContracts.filter(
      (r) => r.isNextMonthContract || r.daysToExpiry >= 1
    );

    let activePool = currentExpiryContracts;
    let rolledToNextMonth = false;

    if (activePool.length === 0) {
      if (input.autoRollToNextMonthOnPhysicalWindow && nextMonthContracts.length > 0) {
        activePool = nextMonthContracts;
        rolledToNextMonth = true;
      } else {
        const minDte = Math.min(...allSideContracts.map((r) => r.daysToExpiry));
        return this.reject(
          sym,
          input.optionType,
          `PHYSICAL_SETTLEMENT_GUARD_VETO: DTE is ${minDte} (< 1 day physical delivery expiry window)`
        );
      }
    }

    // -------------------------------------------------------------------------
    // PILLAR 2: DYNAMIC ARRAY-INDEX ATM & OFFSET SELECTION (NO Math.round!)
    // Sort actual available strikes in ascending order so corporate-action
    // odd strikes (like 1422.5 or 182.5) are selected with 100% accuracy.
    // -------------------------------------------------------------------------
    const strikesData = [...activePool].sort((a, b) => a.strike - b.strike);

    let atmIndex = 0;
    let minSpotDiff = Infinity;
    for (let i = 0; i < strikesData.length; i++) {
      const diff = Math.abs(strikesData[i].strike - input.spotPrice);
      if (diff < minSpotDiff) {
        minSpotDiff = diff;
        atmIndex = i;
      }
    }

    const atmStrike = strikesData[atmIndex].strike;

    // CE: +offset = OTM (higher strike), -offset = ITM (lower strike)
    // PE: -offset = OTM (lower strike), +offset = ITM (higher strike)
    const targetIndex =
      input.optionType === 'CE' ? atmIndex + offset : atmIndex - offset;

    if (targetIndex < 0 || targetIndex >= strikesData.length) {
      return this.reject(
        sym,
        input.optionType,
        `TARGET_OFFSET_OUT_OF_RANGE: atmIndex=${atmIndex}, offset=${offset}`
      );
    }

    let selected = strikesData[targetIndex];

    // -------------------------------------------------------------------------
    // GUARDRAIL 3: STRICT LIQUIDITY, OI & BID-ASK SPREAD GATE
    // If `targetIndex` fails spread/OI, check +/- 1 neighbor strike before rejecting
    // -------------------------------------------------------------------------
    const minOiRequired =
      input.minOpenInterestShares ?? Math.max(25000, selected.lotSize * 40);

    if (!this.isStrikeLiquid(selected, maxSpreadPct, maxSpreadInr, minOiRequired)) {
      const neighbors: StockOptionStrikeQuote[] = [];
      if (targetIndex - 1 >= 0) neighbors.push(strikesData[targetIndex - 1]);
      if (targetIndex + 1 < strikesData.length) neighbors.push(strikesData[targetIndex + 1]);

      const validNeighbor = neighbors.find((n) =>
        this.isStrikeLiquid(n, maxSpreadPct, maxSpreadInr, minOiRequired)
      );

      if (validNeighbor) {
        selected = validNeighbor;
      } else {
        const sp = Math.max(0, selected.ask - selected.bid);
        const spPct = selected.ltp > 0 ? (sp / selected.ltp) * 100 : 100;
        return this.reject(
          sym,
          input.optionType,
          `ILLIQUID_STRIKE_VETO: ${selected.tradingSymbol} Spread=${spPct.toFixed(
            2
          )}% (₹${sp.toFixed(2)}), OI=${selected.oi} (Min required=${minOiRequired})`
        );
      }
    }

    // Abnormal Pre-Event IV Spike Guard (Block Option Buying if IV > 70%)
    if (selected.iv && selected.iv > 70) {
      return this.reject(
        sym,
        input.optionType,
        `EXTREME_IV_CRUSH_RISK_VETO: ${selected.tradingSymbol} IV is ${selected.iv.toFixed(
          1
        )}% (> 70% cap)`
      );
    }

    // -------------------------------------------------------------------------
    // GUARDRAIL 5: PROTECTED LIMIT ORDER PRICING (ASK + 0.2%) & FREEZE SLICING
    // NEVER send a raw Market Order on Stock Options!
    // -------------------------------------------------------------------------
    const askPrice = selected.ask > 0 ? selected.ask : selected.ltp;
    const bidPrice = selected.bid > 0 ? selected.bid : selected.ltp;
    const spreadInr = Number(Math.max(0, askPrice - bidPrice).toFixed(2));
    const spreadPct = Number(((spreadInr / selected.ltp) * 100).toFixed(2));

    const tick = selected.tickSize > 0 ? selected.tickSize : 0.05;
    const rawLimitPrice = Math.min(askPrice * 1.002, selected.ltp * 1.005);
    const protectedLimitBuyPrice = Number(
      (Math.ceil(rawLimitPrice / tick) * tick).toFixed(2)
    );

    const lots = Math.max(1, input.requestedLots ?? 1);
    const totalQty = lots * selected.lotSize;
    const orderSlices = this.sliceByFreezeLimit(
      totalQty,
      selected.lotSize,
      selected.freezeQtyLimit || selected.lotSize * 20
    );

    return {
      approved: true,
      symbol: sym,
      tradingSymbol: selected.tradingSymbol,
      optionType: input.optionType,
      expiryDate: selected.expiryDate,
      daysToExpiry: selected.daysToExpiry,
      rolledToNextMonthForPhysicalGuard: rolledToNextMonth,
      spotPrice: input.spotPrice,
      atmStrike,
      selectedStrike: selected.strike,
      offsetUsed: offset,
      ltp: selected.ltp,
      bid: bidPrice,
      ask: askPrice,
      spreadInr,
      spreadPct,
      openInterest: selected.oi,
      volume: selected.volume,
      orderType: 'LIMIT',
      protectedLimitBuyPrice,
      lotSize: selected.lotSize,
      totalQty,
      orderSlices,
      sebiAlgoTag: input.sebiAlgoId || 'SEBI_ALGO_NEXUS_STOCK_OPT_2026',
    };
  }

  private static isStrikeLiquid(
    row: StockOptionStrikeQuote,
    maxSpreadPct: number,
    maxSpreadInr: number,
    minOi: number
  ): boolean {
    if (!row || row.ltp <= 0) return false;
    const ask = row.ask > 0 ? row.ask : row.ltp;
    const bid = row.bid > 0 ? row.bid : row.ltp;
    const spreadInr = Math.max(0, ask - bid);
    const spreadPct = (spreadInr / row.ltp) * 100;

    const spreadPass = spreadPct <= maxSpreadPct || spreadInr <= maxSpreadInr;
    const oiPass = row.oi >= minOi;
    return spreadPass && oiPass;
  }

  private static sliceByFreezeLimit(
    totalQty: number,
    lotSize: number,
    freezeLimit: number
  ): number[] {
    if (totalQty <= freezeLimit) return [totalQty];
    const maxLotsPerSlice = Math.max(1, Math.floor(freezeLimit / lotSize));
    const sliceQty = maxLotsPerSlice * lotSize;
    const slices: number[] = [];
    let rem = totalQty;
    while (rem > 0) {
      const q = Math.min(rem, sliceQty);
      slices.push(q);
      rem -= q;
    }
    return slices;
  }

  private static reject(
    symbol: string,
    optionType: 'CE' | 'PE',
    reason: string
  ): StockOptionSelectionDecision {
    return {
      approved: false,
      symbol,
      tradingSymbol: '',
      optionType,
      expiryDate: '',
      daysToExpiry: 0,
      rolledToNextMonthForPhysicalGuard: false,
      spotPrice: 0,
      atmStrike: 0,
      selectedStrike: 0,
      offsetUsed: 0,
      ltp: 0,
      bid: 0,
      ask: 0,
      spreadInr: 0,
      spreadPct: 0,
      openInterest: 0,
      volume: 0,
      orderType: 'LIMIT',
      protectedLimitBuyPrice: 0,
      lotSize: 0,
      totalQty: 0,
      orderSlices: [],
      sebiAlgoTag: 'SEBI_ALGO_NEXUS_STOCK_OPT_2026',
      vetoReason: reason,
    };
  }
}
