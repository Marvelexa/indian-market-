/**
 * NEXUS BHARAT — Day-Type Classifier & Adaptive Strategy Engine
 *
 * Classification happens at 10:20 AM based on first 65 minutes of market data.
 * Strategy parameters change PER day type to protect capital on bad days.
 *
 * Day Types:
 *  TRENDING_UP   → NIFTY > +0.4% by 10:15 AND breadth >= 60%
 *  TRENDING_DOWN → NIFTY < -0.4% by 10:15 AND breadth <= 40%
 *  CHOPPY        → NIFTY move < ±0.25% AND breadth 42–58% (like 18-Nov-2026!)
 *  VOLATILE      → NIFTY gap > ±0.8% at open OR VIX-equivalent spike (ATR high)
 *  UNKNOWN       → Before 10:20 AM classification — use conservative defaults
 */

import { getMarketBreadth, recordOpeningPrices, BreadthSnapshot } from './marketBreadthEngine.js';

export type DayType = 'TRENDING_UP' | 'TRENDING_DOWN' | 'CHOPPY' | 'VOLATILE' | 'UNKNOWN';

export interface DayProfile {
  dayType: DayType;
  classifiedAt: Date;
  breadthPct: number;
  niftyMovePct: number;
  strategy: DayStrategy;
  reason: string;
}

export interface DayStrategy {
  // Trade Filters
  allowStockOptions: boolean;       // On CHOPPY/VOLATILE only trade NIFTY/BANKNIFTY
  allowedSeats: number;             // Max concurrent positions (reduce on bad days)
  lotSizeMultiplier: number;        // 1.0 = normal, 0.5 = half size on choppy
  skipFirstMinutes: number;         // Skip initial minutes (30 on VOLATILE)

  // Entry Rules
  minRR: number;                    // Min Risk:Reward before entry
  requireOptionMomentumUp: boolean; // Must option LTP be rising before buy?
  requireBreadthAlignment: boolean; // Breadth must align with trade direction?

  // Exit Rules
  exitAtTP1: boolean;               // On CHOPPY → take TP1 and exit, no runners
  exitAtTP2: boolean;               // On VOLATILE → exit at TP2 max
  runUnlimitedLadder: boolean;      // On TRENDING → ride the full 8-stage ladder

  // Soft Lock Overrides (₹)
  tp1LockInr: number;               // Lock-in at TP1 (default +₹250)
  tp2LockInr: number;               // Lock-in at TP2 (default +₹650)

  // Descriptions
  label: string;
  emoji: string;
}

// ─── STRATEGY TEMPLATES PER DAY TYPE ───────────────────────────────────────

const STRATEGIES: Record<DayType, DayStrategy> = {
  TRENDING_UP: {
    allowStockOptions: true,
    allowedSeats: 6,
    lotSizeMultiplier: 1.0,
    skipFirstMinutes: 0,
    minRR: 2.0,
    requireOptionMomentumUp: true,
    requireBreadthAlignment: true,
    exitAtTP1: false,
    exitAtTP2: false,
    runUnlimitedLadder: true,
    tp1LockInr: 300,          // Slightly tighter lock on trend day (ride more)
    tp2LockInr: 700,
    label: 'TRENDING UP — Full Aggressive Mode',
    emoji: '🚀',
  },
  TRENDING_DOWN: {
    allowStockOptions: true,
    allowedSeats: 6,
    lotSizeMultiplier: 1.0,
    skipFirstMinutes: 0,
    minRR: 2.0,
    requireOptionMomentumUp: true,
    requireBreadthAlignment: true,
    exitAtTP1: false,
    exitAtTP2: false,
    runUnlimitedLadder: true,
    tp1LockInr: 300,
    tp2LockInr: 700,
    label: 'TRENDING DOWN — Full Bear Mode',
    emoji: '📉',
  },
  CHOPPY: {
    allowStockOptions: false,     // ⚠️ ONLY NIFTY & BANKNIFTY index options
    allowedSeats: 3,              // ⚠️ Max 3 seats (half capacity)
    lotSizeMultiplier: 0.5,       // ⚠️ Half lot size to protect capital
    skipFirstMinutes: 15,         // Skip first 15 min extra caution
    minRR: 3.0,                   // ⚠️ Stricter RR required (3:1 min)
    requireOptionMomentumUp: true,
    requireBreadthAlignment: true,
    exitAtTP1: true,              // ⚠️ EXIT at TP1, NO runners on choppy day!
    exitAtTP2: false,
    runUnlimitedLadder: false,
    tp1LockInr: 200,              // Even tighter — take profit fast
    tp2LockInr: 600,
    label: 'CHOPPY — Capital Protection Mode (Index Only, TP1 Exit)',
    emoji: '⚠️',
  },
  VOLATILE: {
    allowStockOptions: false,     // ⚠️ Index only on volatile days
    allowedSeats: 2,              // ⚠️ Only 2 seats max
    lotSizeMultiplier: 0.5,
    skipFirstMinutes: 30,         // ⚠️ Skip first 30 minutes entirely
    minRR: 3.5,
    requireOptionMomentumUp: true,
    requireBreadthAlignment: false, // Direction unclear on volatile
    exitAtTP1: false,
    exitAtTP2: true,              // Max TP2, don't overstay volatile moves
    runUnlimitedLadder: false,
    tp1LockInr: 200,
    tp2LockInr: 600,
    label: 'VOLATILE — Risk-Off Mode (Index Only, Max TP2, Skip 30min)',
    emoji: '🌪️',
  },
  UNKNOWN: {
    allowStockOptions: false,
    allowedSeats: 2,
    lotSizeMultiplier: 0.5,
    skipFirstMinutes: 20,
    minRR: 3.0,
    requireOptionMomentumUp: true,
    requireBreadthAlignment: true,
    exitAtTP1: true,
    exitAtTP2: false,
    runUnlimitedLadder: false,
    tp1LockInr: 200,
    tp2LockInr: 600,
    label: 'UNKNOWN — Conservative Until Classified at 10:20 AM',
    emoji: '❓',
  },
};

// ─── SINGLETON STATE ─────────────────────────────────────────────────────────

let currentDayProfile: DayProfile | null = null;
let openingNiftyPrice: number | null = null;
let classificationScheduled = false;

/**
 * Call this at 09:15 AM every day to record opening prices.
 */
export async function initializeDayClassifier(): Promise<void> {
  console.log('[DayClassifier] Initializing — recording open prices at 09:15...');
  await recordOpeningPrices();
  currentDayProfile = null;
  classificationScheduled = false;

  // Schedule classification at 10:20 AM
  const now = new Date();
  const classifyAt = new Date(now);
  classifyAt.setHours(10, 20, 0, 0);
  const msUntilClassify = classifyAt.getTime() - now.getTime();

  if (msUntilClassify > 0 && !classificationScheduled) {
    classificationScheduled = true;
    console.log(`[DayClassifier] Will classify day type at 10:20 AM (in ${Math.round(msUntilClassify / 60000)}m)`);
    setTimeout(async () => {
      await classifyDayType();
    }, msUntilClassify);
  } else if (msUntilClassify <= 0) {
    // Market already past 10:20 — classify immediately
    await classifyDayType();
  }
}

/**
 * Core classification logic — runs at 10:20 AM using real breadth data.
 */
export async function classifyDayType(): Promise<DayProfile> {
  console.log('[DayClassifier] Classifying day type at 10:20 AM...');

  let breadth: BreadthSnapshot;
  try {
    breadth = await getMarketBreadth();
  } catch (err) {
    console.error('[DayClassifier] Breadth fetch failed, defaulting to UNKNOWN:', err);
    currentDayProfile = buildProfile('UNKNOWN', 50, 0, 'Breadth fetch failed');
    return currentDayProfile;
  }

  const niftyMove = breadth.niftyMoveFromOpen; // %
  const breadthPct = breadth.breadthPct;

  let dayType: DayType;
  let reason: string;

  // ── Classification Rules ──────────────────────────────────────────────────
  // Check VOLATILE first (gap open or extreme breadth)
  if (Math.abs(niftyMove) > 0.8 && (breadthPct > 75 || breadthPct < 25)) {
    dayType = 'VOLATILE';
    reason = `NIFTY gap ${niftyMove > 0 ? '+' : ''}${niftyMove.toFixed(2)}% with extreme breadth ${breadthPct}%`;
  }
  // TRENDING UP
  else if (niftyMove >= 0.4 && breadthPct >= 60) {
    dayType = 'TRENDING_UP';
    reason = `NIFTY +${niftyMove.toFixed(2)}% | Breadth ${breadthPct}% (bullish)`;
  }
  // TRENDING DOWN
  else if (niftyMove <= -0.4 && breadthPct <= 40) {
    dayType = 'TRENDING_DOWN';
    reason = `NIFTY ${niftyMove.toFixed(2)}% | Breadth ${breadthPct}% (bearish)`;
  }
  // CHOPPY (like 18-Nov-2026 — NIFTY only -0.37% but no clear direction)
  else if (Math.abs(niftyMove) < 0.35 || (breadthPct >= 42 && breadthPct <= 58)) {
    dayType = 'CHOPPY';
    reason = `NIFTY move only ${niftyMove.toFixed(2)}% | Mixed breadth ${breadthPct}% — WHIPSAW DAY`;
  }
  // Borderline — classify as CHOPPY to be safe
  else {
    dayType = 'CHOPPY';
    reason = `Borderline — NIFTY ${niftyMove.toFixed(2)}% | Breadth ${breadthPct}% → defaulting to CHOPPY (safe)`;
  }

  currentDayProfile = buildProfile(dayType, breadthPct, niftyMove, reason);

  console.log(`\n${'═'.repeat(60)}`);
  console.log(`📊 DAY TYPE CLASSIFIED: ${currentDayProfile.strategy.emoji} ${dayType}`);
  console.log(`   Reason: ${reason}`);
  console.log(`   Strategy: ${currentDayProfile.strategy.label}`);
  console.log(`   Max Seats: ${currentDayProfile.strategy.allowedSeats} | Stock Options: ${currentDayProfile.strategy.allowStockOptions ? '✅' : '❌ INDEX ONLY'}`);
  console.log(`   Lot Multiplier: ${currentDayProfile.strategy.lotSizeMultiplier}x | Exit at TP1: ${currentDayProfile.strategy.exitAtTP1 ? '✅' : '❌'}`);
  console.log(`${'═'.repeat(60)}\n`);

  return currentDayProfile;
}

function buildProfile(dayType: DayType, breadthPct: number, niftyMovePct: number, reason: string): DayProfile {
  return {
    dayType,
    classifiedAt: new Date(),
    breadthPct,
    niftyMovePct,
    strategy: STRATEGIES[dayType],
    reason,
  };
}

/**
 * Get current day profile (returns UNKNOWN with conservative strategy if not yet classified)
 */
export function getCurrentDayProfile(): DayProfile {
  if (!currentDayProfile) {
    return buildProfile('UNKNOWN', 50, 0, 'Not yet classified — market open < 10:20 AM');
  }
  return currentDayProfile;
}

/**
 * Force-reclassify (call if market conditions change drastically mid-day)
 */
export async function reclassifyDayType(): Promise<DayProfile> {
  console.log('[DayClassifier] Force reclassifying day type...');
  currentDayProfile = null;
  return classifyDayType();
}

/**
 * Check if a proposed trade is allowed under current day's strategy
 */
export interface TradeAllowedResult {
  allowed: boolean;
  reason: string;
  adjustedLots?: number;
}

export function isTradeAllowedToday(
  symbol: string,
  proposedLots: number,
  currentActiveSeats: number,
  isIndexSymbol: boolean,  // true for NIFTY, BANKNIFTY
): TradeAllowedResult {
  const profile = getCurrentDayProfile();
  const strat = profile.strategy;

  // Check seat capacity
  if (currentActiveSeats >= strat.allowedSeats) {
    return {
      allowed: false,
      reason: `${profile.strategy.emoji} ${profile.dayType} day — Max seats reached (${strat.allowedSeats}/${strat.allowedSeats}). Capital protection active.`,
    };
  }

  // Check stock options restriction
  if (!isIndexSymbol && !strat.allowStockOptions) {
    return {
      allowed: false,
      reason: `${profile.strategy.emoji} ${profile.dayType} day — Stock options BLOCKED. Only NIFTY/BANKNIFTY allowed today!`,
    };
  }

  // Adjust lot size
  const adjustedLots = Math.max(1, Math.round(proposedLots * strat.lotSizeMultiplier));

  return {
    allowed: true,
    reason: `${profile.strategy.emoji} ${profile.dayType} — Trade allowed | Lots adjusted: ${proposedLots} → ${adjustedLots}`,
    adjustedLots,
  };
}

/**
 * Should we skip this minute? (For volatile day — skip first 30 min)
 */
export function shouldSkipCurrentMinute(): boolean {
  const profile = getCurrentDayProfile();
  if (profile.strategy.skipFirstMinutes <= 0) return false;

  const now = new Date();
  const marketOpen = new Date(now);
  marketOpen.setHours(9, 15, 0, 0);
  const minutesSinceOpen = (now.getTime() - marketOpen.getTime()) / 60000;
  return minutesSinceOpen < profile.strategy.skipFirstMinutes;
}

export { STRATEGIES, DayStrategy };
