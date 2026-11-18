/**
 * FILE: lib/bharat/foOptionSniperEngine.ts
 * ============================================================================
 * NEXUS BHARAT TOP 50 F&O ATM OPTION SNIPER & TRAILING LADDER ENGINE
 * Rules:
 *   - Stock Signal BUY  --> Buy ATM Call Option (CE)
 *   - Stock Signal SELL --> Buy ATM Put Option (PE)
 *   - Max Risk per lot  --> Strictly capped at -₹2,500
 *   - Profit Ladder     --> TP1 (+₹500), TP2 (+₹1,000), +₹2,000, +₹4,000, +₹8,000+ Runner
 *   - Session Square-Off--> Mandatory market close at 03:18 PM IST
 * ============================================================================
 */

import {
  UniversalIndianMarketConnector,
  type ExchangeContractMaster
} from './universalIndianMarketConnector.ts';
import { DiamondHandsHoldManager } from './diamondHandsHoldManager.ts';

export interface StockOptionConfig {
  symbol: string;
  lotSize: number;
  strikeStep: number;
}

export interface ActiveFoOptionPosition {
  id: string;
  stockSymbol: string;
  optionSymbol: string; // e.g. RELIANCE26NOV2500CE
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
  openedEpochMs?: number;
  entrySpot?: number;
}

export interface ClosedFoTrade {
  id: string;
  stockSymbol: string;
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
    | 'HARD_SL_HIT'
    | 'STRUCTURAL_15M_INVALIDATION_CLOSED'
    | 'STAGE_1_LOCK_850_HIT'
    | 'STAGE_2_LOCK_1650_HIT'
    | 'STAGE_3_LOCK_2800_HIT'
    | 'STAGE_4_RUNNER_TRAIL_HIT'
    | 'MANDATORY_318PM_SQUARE_OFF'
    | 'AUTO_SQUARE_OFF_318PM';
  closedAtIst: string;
}

export class FoOptionSniperEngine {
  // Top 50 NSE F&O Whitelist with exact lot size & strike step
  public static readonly FO_WHITELIST_50: Record<string, StockOptionConfig> = {
    RELIANCE: { symbol: 'RELIANCE', lotSize: 250, strikeStep: 20 },
    HDFCBANK: { symbol: 'HDFCBANK', lotSize: 550, strikeStep: 10 },
    ICICIBANK: { symbol: 'ICICIBANK', lotSize: 700, strikeStep: 10 },
    SBIN: { symbol: 'SBIN', lotSize: 750, strikeStep: 5 },
    INFY: { symbol: 'INFY', lotSize: 400, strikeStep: 20 },
    TCS: { symbol: 'TCS', lotSize: 175, strikeStep: 50 },
    AXISBANK: { symbol: 'AXISBANK', lotSize: 625, strikeStep: 10 },
    TATAMOTORS: { symbol: 'TATAMOTORS', lotSize: 550, strikeStep: 10 },
    M_M: { symbol: 'M&M', lotSize: 350, strikeStep: 20 },
    LT: { symbol: 'LT', lotSize: 150, strikeStep: 50 },
    BAJFINANCE: { symbol: 'BAJFINANCE', lotSize: 125, strikeStep: 50 },
    KOTAKBANK: { symbol: 'KOTAKBANK', lotSize: 400, strikeStep: 20 },
    BHARTIARTL: { symbol: 'BHARTIARTL', lotSize: 475, strikeStep: 10 },
    TATASTEEL: { symbol: 'TATASTEEL', lotSize: 5500, strikeStep: 1 },
    MARUTI: { symbol: 'MARUTI', lotSize: 50, strikeStep: 100 },
    SUNPHARMA: { symbol: 'SUNPHARMA', lotSize: 350, strikeStep: 20 },
    HINDUNILVR: { symbol: 'HINDUNILVR', lotSize: 300, strikeStep: 20 },
    ITC: { symbol: 'ITC', lotSize: 1600, strikeStep: 5 },
    NTPC: { symbol: 'NTPC', lotSize: 1500, strikeStep: 5 },
    POWERGRID: { symbol: 'POWERGRID', lotSize: 1800, strikeStep: 5 },
    COALINDIA: { symbol: 'COALINDIA', lotSize: 2100, strikeStep: 5 },
    ONGC: { symbol: 'ONGC', lotSize: 3850, strikeStep: 2.5 },
    BPCL: { symbol: 'BPCL', lotSize: 1800, strikeStep: 5 },
    IOC: { symbol: 'IOC', lotSize: 4875, strikeStep: 2.5 },
    HCLTECH: { symbol: 'HCLTECH', lotSize: 350, strikeStep: 20 },
    WIPRO: { symbol: 'WIPRO', lotSize: 1500, strikeStep: 5 },
    TECHM: { symbol: 'TECHM', lotSize: 600, strikeStep: 20 },
    COFORGE: { symbol: 'COFORGE', lotSize: 150, strikeStep: 50 },
    PERSISTENT: { symbol: 'PERSISTENT', lotSize: 100, strikeStep: 50 },
    JINDALSTEL: { symbol: 'JINDALSTEL', lotSize: 625, strikeStep: 10 },
    JSWSTEEL: { symbol: 'JSWSTEEL', lotSize: 675, strikeStep: 10 },
    HINDALCO: { symbol: 'HINDALCO', lotSize: 1400, strikeStep: 5 },
    VEDL: { symbol: 'VEDL', lotSize: 1150, strikeStep: 5 },
    NMDC: { symbol: 'NMDC', lotSize: 4500, strikeStep: 2.5 },
    BAJAJFINSV: { symbol: 'BAJAJFINSV', lotSize: 500, strikeStep: 20 },
    CHOLAFIN: { symbol: 'CHOLAFIN', lotSize: 500, strikeStep: 20 },
    SHRIRAMFIN: { symbol: 'SHRIRAMFIN', lotSize: 300, strikeStep: 20 },
    PFC: { symbol: 'PFC', lotSize: 1300, strikeStep: 5 },
    RECLTD: { symbol: 'RECLTD', lotSize: 1400, strikeStep: 5 },
    MUTHOOTFIN: { symbol: 'MUTHOOTFIN', lotSize: 300, strikeStep: 20 },
    PNB: { symbol: 'PNB', lotSize: 8000, strikeStep: 1 },
    BANKBARODA: { symbol: 'BANKBARODA', lotSize: 2925, strikeStep: 2.5 },
    FEDERALBNK: { symbol: 'FEDERALBNK', lotSize: 5000, strikeStep: 1 },
    INDUSINDBK: { symbol: 'INDUSINDBK', lotSize: 500, strikeStep: 20 },
    CIPLA: { symbol: 'CIPLA', lotSize: 650, strikeStep: 20 },
    DRREDDY: { symbol: 'DRREDDY', lotSize: 125, strikeStep: 50 },
    DIVISLAB: { symbol: 'DIVISLAB', lotSize: 100, strikeStep: 50 },
    APOLLOHOSP: { symbol: 'APOLLOHOSP', lotSize: 125, strikeStep: 50 },
    ADANIENT: { symbol: 'ADANIENT', lotSize: 300, strikeStep: 20 },
    ADANIPORTS: { symbol: 'ADANIPORTS', lotSize: 400, strikeStep: 20 },
  };

  private activePositions: Map<string, ActiveFoOptionPosition> = new Map();
  private closedTrades: ClosedFoTrade[] = [];
  public static readonly stockCooldownUntilMs: Map<string, number> = new Map();

  /**
   * 1. Calculate Exact ATM Strike Price
   */
  public static calculateAtmStrike(spotPrice: number, strikeStep: number): number {
    return Math.round(spotPrice / strikeStep) * strikeStep;
  }

  /**
   * Helper to format current standard NSE monthly expiry (e.g. "26NOV")
   */
  public static getCurrentExpiryCode(): string {
    const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    const now = new Date(Date.now() + 5.5 * 60 * 60 * 1000);
    const yr = String(now.getUTCFullYear()).slice(-2);
    const mon = months[now.getUTCMonth()];
    return `${yr}${mon}`;
  }

  /**
   * 2. Receive Signal from Underlying Stock and Open ATM Option Trade
   */
  public async handleStockSignal(params: {
    stockSymbol: string;
    signalAction: 'BUY' | 'SELL';
    spotPrice: number;
    currentExpiryCode?: string; // e.g. "26NOV"
    getOptionLtp: (optionSymbol: string) => Promise<number>;
    executeBrokerOrder: (order: {
      optionSymbol: string;
      side: 'BUY';
      qty: number;
      price: number;
      tag: string;
      sebiAlgoTag?: string;
      orderSlices?: number[];
    }) => Promise<void>;
  }): Promise<{ status: string; position?: ActiveFoOptionPosition }> {
    const cleanSym = params.stockSymbol.replace('.NS', '').replace('^', '');
    const config =
      FoOptionSniperEngine.FO_WHITELIST_50[cleanSym] ||
      FoOptionSniperEngine.FO_WHITELIST_50[cleanSym.replace('&', '_')] ||
      Object.values(FoOptionSniperEngine.FO_WHITELIST_50).find(c => c.symbol === cleanSym);

    if (!config) {
      return { status: `VETO: ${params.stockSymbol} not in Top 50 F&O Whitelist` };
    }

    // STRICT 03:15 PM ENTRY CUTOFF: Zero new positions can be initiated after 03:15 PM IST
    const istMins = this.getIstMinutes();
    if (istMins >= 15 * 60 + 15) {
      return { status: `VETO: Past 03:15 PM IST Entry Cutoff (No new entries allowed)` };
    }

    if (this.activePositions.has(config.symbol)) {
      return { status: `VETO: Position already open for ${config.symbol}` };
    }

    // ANTI-SPAM & OVER-TRADING SHIELD: 20-minute mandatory cooldown on exited symbol
    const cooldownUntil = FoOptionSniperEngine.stockCooldownUntilMs.get(config.symbol) || 0;
    if (Date.now() < cooldownUntil) {
      const remMin = Math.ceil((cooldownUntil - Date.now()) / 60000);
      return { status: `VETO: ${config.symbol} in post-exit cooldown (${remMin}m remaining to prevent repetitive trading)` };
    }

    // STRICT SEAT ALLOCATION: Max 4 concurrent Stock Option seats (Seats 3-6) to prevent over-trading
    if (this.activePositions.size >= 4) {
      return { status: `VETO: Max 4 Stock Option seats already active (${this.activePositions.size}/4 filled)` };
    }

    // Determine Option Type
    // Underlying BUY  -> ATM CE
    // Underlying SELL -> ATM PE
    const optionType: 'CE' | 'PE' = params.signalAction === 'BUY' ? 'CE' : 'PE';

    // 1. Resolve Exact Real Exchange-Listed Contract via 5-Guardrail Stock Option Engine
    const decision = await UniversalIndianMarketConnector.resolveStockOptionWithGuardrails({
      symbol: config.symbol,
      spotPrice: params.spotPrice,
      optionType,
      offset: 0,
      requestedLots: 1,
      autoRollToNextMonthOnPhysicalWindow: true,
    });

    if (!decision.approved || !decision.tradingSymbol) {
      return {
        status: `STRICT_VETO: ${decision.vetoReason || 'Stock Option 5-Guardrail Selector rejected ' + config.symbol}`,
      };
    }

    const optionSymbol = decision.tradingSymbol;
    const atmStrike = decision.selectedStrike;
    const lotQty = decision.lotSize;
    // Mandatory Protected Limit Order Price (@ Ask + 0.2%)
    const optionPremium = decision.protectedLimitBuyPrice;

    console.log(
      `🏛️ [5-Guardrail Stock Option Selected] ${config.symbol} | Spot: ₹${params.spotPrice} | ` +
      `Strike: ${atmStrike} ${optionType} (${optionSymbol}) | Protected Limit Buy: ₹${optionPremium} (Ask: ₹${decision.ask}) | ` +
      `Spread: ₹${decision.spreadInr} (${decision.spreadPct}%) | OI: ${decision.openInterest.toLocaleString('en-IN')} | ` +
      `DTE: ${decision.daysToExpiry} (Rolled Next Month: ${decision.rolledToNextMonthForPhysicalGuard ? 'YES' : 'NO'}) | ` +
      `Order: ${decision.orderType} | Slices: [${decision.orderSlices.join(', ')}] | SEBI Tag: ${decision.sebiAlgoTag}`
    );

    // MAX RISK RULE: Strictly Capped at -₹2,500 hard Stop Loss per lot for Stocks
    // Points drop needed to lose ₹2500 = 2500 / lotSize
    const maxPointsDrop = 2500 / lotQty;
    const initialSlPremium = Number(Math.max(0.05, optionPremium - maxPointsDrop).toFixed(2));

    const istNow = this.getIstTimeStr();
    const nowMs = Date.now();
    const position: ActiveFoOptionPosition = {
      id: `${optionSymbol}-${nowMs}`,
      stockSymbol: config.symbol,
      optionSymbol,
      optionType,
      strike: atmStrike,
      lotSize: lotQty,
      qty: lotQty,
      entryPremium: optionPremium,
      currentPremium: optionPremium,
      initialSlPremium,
      currentSlPremium: initialSlPremium,
      unrealizedPnlInr: 0,
      lockedProfitInr: 0,
      peakProfitInr: 0,
      ladderStage: 0,
      openedAtIst: istNow,
      openedEpochMs: nowMs,
      entrySpot: params.spotPrice,
    };

    this.activePositions.set(config.symbol, position);

    // Fire Broker Order with SEBI Algo Compliance Tag and Slices
    await params.executeBrokerOrder({
      optionSymbol,
      side: 'BUY',
      qty: lotQty,
      price: optionPremium,
      tag: `ATM_${optionType}_${decision.sebiAlgoTag}`,
      sebiAlgoTag: decision.sebiAlgoTag,
      orderSlices: decision.orderSlices,
    });

    return { status: 'ORDER_FIRED', position };
  }

  /**
   * 3. Tick Manager: Manages +₹3,000 Profit Hurdle, +₹2,200 Lock,
   *    +₹8,000 Max Target, and -₹1,500 Hard Stop Loss with 5-Minute Hard Lock.
   */
  public async evaluateOpenPositionsTick(params: {
    nowEpochMs?: number;
    liveOptionLtpMap: Record<string, number>;
    executeBrokerExit: (order: {
      optionSymbol: string;
      side: 'SELL';
      qty: number;
      price: number;
      tag: string;
    }) => Promise<void>;
  }): Promise<void> {
    const ist = this.getIstMinutes(params.nowEpochMs);
    const isSquareOffTime = ist >= 15 * 60 + 18 && ist <= 15 * 60 + 35; // 03:18 PM IST auto close window
    const nowMs = params.nowEpochMs ?? Date.now();

    for (const [stockSym, pos] of Array.from(this.activePositions.entries())) {
      const livePremium = params.liveOptionLtpMap[pos.optionSymbol] ?? pos.currentPremium;
      pos.currentPremium = livePremium;

      // PnL in INR = (Current Premium - Entry Premium) * Lot Size
      const pnlPoints = livePremium - pos.entryPremium;
      pos.unrealizedPnlInr = Number((pnlPoints * pos.qty).toFixed(2));
      pos.peakProfitInr = Math.max(pos.peakProfitInr, pos.unrealizedPnlInr);

      // --- ROUTE THROUGH DIAMOND-HANDS STRUCTURAL HOLD & BREATHING LADDER MANAGER ---
      const decision = DiamondHandsHoldManager.evaluatePositionHold({
        symbol: pos.stockSymbol,
        optionType: pos.optionType,
        lotSize: pos.qty,
        entryPremium: pos.entryPremium,
        currentPremium: livePremium,
        initialSlPremium: pos.initialSlPremium,
        currentSlPremium: pos.currentSlPremium,
        peakPnlInr: pos.peakProfitInr,
        ladderStage: pos.ladderStage,
        entryTimestampMs: pos.openedEpochMs || nowMs,
        nowTimestampMs: nowMs,
        underlyingSpotLtp: pos.entrySpot || 0,
        structuralInvalidationSpot: 0,
        isFiveMinCandleClosed: false,
      });

      pos.peakProfitInr = decision.newPeakPnlInr;
      pos.ladderStage = decision.newLadderStage;
      pos.currentSlPremium = decision.newSlPremium;

      if (decision.action === 'EXECUTE_EXIT') {
        const exitReason = (decision.exitReason || 'HARD_SL_HIT') as ClosedFoTrade['exitReason'];
        await this.closePosition(
          stockSym,
          pos,
          livePremium,
          exitReason,
          params.executeBrokerExit
        );
        continue;
      }
    }
  }

  private calculatePremiumForTargetPnl(pos: ActiveFoOptionPosition, targetPnlInr: number): number {
    const requiredPoints = targetPnlInr / pos.qty;
    return Number((pos.entryPremium + requiredPoints).toFixed(2));
  }

  private async closePosition(
    stockSymbol: string,
    pos: ActiveFoOptionPosition,
    exitPremium: number,
    exitReason: ClosedFoTrade['exitReason'],
    executeBrokerExit: (order: {
      optionSymbol: string;
      side: 'SELL';
      qty: number;
      price: number;
      tag: string;
    }) => Promise<void>
  ): Promise<void> {
    const netPnlInr = Number(((exitPremium - pos.entryPremium) * pos.qty).toFixed(2));

    this.activePositions.delete(stockSymbol);
    // Anti-Spam: 20-minute mandatory cooldown on any exited stock
    FoOptionSniperEngine.stockCooldownUntilMs.set(stockSymbol, Date.now() + 20 * 60 * 1000);
    FoOptionSniperEngine.stockCooldownUntilMs.set(pos.stockSymbol, Date.now() + 20 * 60 * 1000);

    this.closedTrades.unshift({
      id: pos.id,
      stockSymbol: pos.stockSymbol,
      optionSymbol: pos.optionSymbol,
      optionType: pos.optionType,
      lotSize: pos.lotSize,
      qty: pos.qty,
      entryPremium: pos.entryPremium,
      exitPremium,
      netPnlInr,
      ladderStageReached: pos.ladderStage,
      exitReason,
      closedAtIst: this.getIstTimeStr(),
    });

    await executeBrokerExit({
      optionSymbol: pos.optionSymbol,
      side: 'SELL',
      qty: pos.qty,
      price: exitPremium,
      tag: exitReason,
    });
  }

  public getActivePositions(): ActiveFoOptionPosition[] {
    return Array.from(this.activePositions.values());
  }

  public hasOpenPosition(stockSymbol: string): boolean {
    const clean = stockSymbol.replace('.NS', '').replace('^', '').trim().toUpperCase();
    if (this.activePositions.has(clean) || this.activePositions.has(stockSymbol)) return true;
    for (const [key, pos] of this.activePositions.entries()) {
      if (key.toUpperCase() === clean) return true;
      if (pos.optionSymbol.toUpperCase() === clean) return true;
      if (pos.optionSymbol.toUpperCase().startsWith(clean)) return true;
      const m = pos.optionSymbol.match(/^([A-Z&_-]+?)(?:\d{2}[A-Z]{3}|\d{2}[A-Z]|\d{4}|_\d)/);
      if (m && m[1].toUpperCase() === clean) return true;
    }
    return false;
  }

  public getClosedTrades(): ClosedFoTrade[] {
    return this.closedTrades;
  }

  public clearAllTrades(): void {
    this.activePositions.clear();
    this.closedTrades = [];
  }

  public getIstMinutes(nowEpochMs?: number): number {
    const ist = nowEpochMs ? new Date(nowEpochMs + 5.5 * 60 * 60 * 1000) : new Date(Date.now() + 5.5 * 60 * 60 * 1000);
    return ist.getUTCHours() * 60 + ist.getUTCMinutes();
  }

  public getIstTimeStr(nowEpochMs?: number): string {
    const ist = nowEpochMs ? new Date(nowEpochMs + 5.5 * 60 * 60 * 1000) : new Date(Date.now() + 5.5 * 60 * 60 * 1000);
    return `${String(ist.getUTCHours()).padStart(2, '0')}:${String(ist.getUTCMinutes()).padStart(
      2,
      '0'
    )}:${String(ist.getUTCSeconds()).padStart(2, '0')} IST`;
  }
}
