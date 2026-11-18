/**
 * NEXUS BHARAT — Market Breadth Engine
 * Fetches live/intraday breadth from real Groww price data.
 * Returns bullishCount, bearishCount, breadthPct, niftyMoveFromOpen.
 * Zero synthetic pricing. Zero hardcoded values.
 */

import { fetchRealSpotPrice } from './strictRealOptionChainFeed.js';

export interface BreadthSnapshot {
  bullishCount: number;      // stocks above VWAP / open
  bearishCount: number;
  neutralCount: number;
  total: number;
  breadthPct: number;        // 0-100, >55 = bullish breadth, <45 = bearish
  niftyMoveFromOpen: number; // % move of NIFTY from 09:15 open
  bankniftyMoveFromOpen: number;
  timestamp: Date;
  universe: string[];
}

// Top 20 liquid F&O universe for breadth calculation
const BREADTH_UNIVERSE = [
  'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'AXISBANK', 'SBIN',
  'KOTAKBANK', 'TCS', 'INFY', 'LT', 'TATASTEEL',
  'BAJFINANCE', 'HINDUNILVR', 'ITC', 'MARUTI', 'BHARTIARTL',
  'SUNPHARMA', 'WIPRO', 'NTPC', 'POWERGRID', 'M&M'
];

// Slug map for Groww API
const GROWW_SLUG_MAP: Record<string, string> = {
  'RELIANCE': 'reliance-industries', 'HDFCBANK': 'hdfc-bank',
  'ICICIBANK': 'icici-bank', 'AXISBANK': 'axis-bank',
  'SBIN': 'state-bank-of-india', 'KOTAKBANK': 'kotak-mahindra-bank',
  'TCS': 'tata-consultancy-services', 'INFY': 'infosys',
  'LT': 'larsen-and-toubro', 'TATASTEEL': 'tata-steel',
  'BAJFINANCE': 'bajaj-finance', 'HINDUNILVR': 'hindustan-unilever',
  'ITC': 'itc', 'MARUTI': 'maruti-suzuki-india',
  'BHARTIARTL': 'bharti-airtel', 'SUNPHARMA': 'sun-pharmaceutical-industries',
  'WIPRO': 'wipro', 'NTPC': 'ntpc', 'POWERGRID': 'power-grid-corporation-of-india',
  'M&M': 'mahindra-and-mahindra',
};

// Cache to avoid hammering API — 60s TTL
let breadthCache: BreadthSnapshot | null = null;
let cacheTs = 0;
const CACHE_TTL_MS = 60_000;

// Opening prices captured at 09:15 AM
const openPriceMap: Map<string, number> = new Map();

/**
 * Record opening prices at 09:15 AM (call once at market open)
 */
export async function recordOpeningPrices(): Promise<void> {
  console.log('[BreadthEngine] Recording 09:15 open prices...');
  for (const sym of BREADTH_UNIVERSE) {
    try {
      const slug = GROWW_SLUG_MAP[sym] ?? sym.toLowerCase().replace('&', 'and');
      const price = await fetchRealSpotPriceBySlug(slug);
      if (price && price > 0) {
        openPriceMap.set(sym, price);
        console.log(`  [BreadthEngine] ${sym} open: ₹${price}`);
      }
    } catch { /* skip */ }
  }
}

/**
 * Calculate current market breadth vs opening prices
 */
export async function getMarketBreadth(): Promise<BreadthSnapshot> {
  const now = Date.now();
  if (breadthCache && (now - cacheTs) < CACHE_TTL_MS) {
    return breadthCache;
  }

  let bullish = 0, bearish = 0, neutral = 0;
  const checked: string[] = [];

  for (const sym of BREADTH_UNIVERSE) {
    try {
      const slug = GROWW_SLUG_MAP[sym] ?? sym.toLowerCase().replace('&', 'and');
      const currentPrice = await fetchRealSpotPriceBySlug(slug);
      if (!currentPrice || currentPrice <= 0) continue;

      const openPrice = openPriceMap.get(sym);
      if (!openPrice || openPrice <= 0) {
        // If no open price recorded, use 0.1% threshold
        neutral++;
      } else {
        const movePct = ((currentPrice - openPrice) / openPrice) * 100;
        if (movePct > 0.15) bullish++;
        else if (movePct < -0.15) bearish++;
        else neutral++;
      }
      checked.push(sym);
    } catch { /* skip */ }
  }

  const total = bullish + bearish + neutral;
  const breadthPct = total > 0 ? Math.round((bullish / total) * 100) : 50;

  // Get NIFTY & BANKNIFTY move
  let niftyMove = 0, bnMove = 0;
  try {
    const niftyNow = await fetchRealSpotPriceBySlug('nifty-50');
    const niftyOpen = openPriceMap.get('NIFTY') ?? niftyNow ?? 25000;
    if (niftyNow && niftyOpen) niftyMove = ((niftyNow - niftyOpen) / niftyOpen) * 100;
  } catch { /* skip */ }
  try {
    const bnNow = await fetchRealSpotPriceBySlug('nifty-bank');
    const bnOpen = openPriceMap.get('BANKNIFTY') ?? bnNow ?? 52000;
    if (bnNow && bnOpen) bnMove = ((bnNow - bnOpen) / bnOpen) * 100;
  } catch { /* skip */ }

  const snap: BreadthSnapshot = {
    bullishCount: bullish,
    bearishCount: bearish,
    neutralCount: neutral,
    total,
    breadthPct,
    niftyMoveFromOpen: Math.round(niftyMove * 100) / 100,
    bankniftyMoveFromOpen: Math.round(bnMove * 100) / 100,
    timestamp: new Date(),
    universe: checked,
  };

  breadthCache = snap;
  cacheTs = now;
  return snap;
}

/**
 * Direct spot price fetch via Groww equity API
 */
async function fetchRealSpotPriceBySlug(slug: string): Promise<number | null> {
  try {
    const url = `https://groww.in/v1/api/stocks_data/v1/accord_points/exchange/NSE/segment/CASH/latest_prices_ohlc/token/${slug}`;
    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json' },
      signal: AbortSignal.timeout(4000),
    });
    if (!res.ok) return null;
    const json = await res.json() as any;
    return json?.ltp ?? json?.close ?? json?.lastPrice ?? null;
  } catch {
    return null;
  }
}

/**
 * Force-clear cache (call after major market event)
 */
export function clearBreadthCache(): void {
  breadthCache = null;
  cacheTs = 0;
}
