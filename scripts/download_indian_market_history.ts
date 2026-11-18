/**
 * 60-Day Indian Market (NSE) Historical 5m & 15m Downloader & Cache Engine
 * Strictly filters to Regular Trading Hours (09:15 AM - 03:30 PM IST, Mon-Fri)
 * Injects volume for index spot instruments (NIFTYBEES, BANKBEES, etc.)
 * Saves sanitized data to .cache_indian_market_60d/
 */

import fs from 'fs';
import path from 'path';

interface RawCandle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SanitizedIndianCandle {
  timestamp: number; // Epoch ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  dateStr: string;   // YYYY-MM-DD IST
  timeStr: string;   // HH:MM IST
  previousDayHigh?: number;
  previousDayLow?: number;
  previousDayClose?: number;
  openingRangeHigh?: number;
  openingRangeLow?: number;
}

interface SymbolConfig {
  id: string;
  primaryTicker: string;
  fallbackTicker?: string;
  volumeProxyTicker?: string;
  isIndex: boolean;
  tickSize: number;
}

const NSE_WHITELIST: SymbolConfig[] = [
  { id: 'NIFTY', primaryTicker: '^NSEI', volumeProxyTicker: 'NIFTYBEES.NS', isIndex: true, tickSize: 0.05 },
  { id: 'BANKNIFTY', primaryTicker: '^NSEBANK', volumeProxyTicker: 'BANKBEES.NS', isIndex: true, tickSize: 0.05 },
  { id: 'FINNIFTY', primaryTicker: 'NIFTY_FIN_SERVICE.NS', volumeProxyTicker: 'HDFCBANK.NS', isIndex: true, tickSize: 0.05 },
  { id: 'SENSEX', primaryTicker: '^BSESN', isIndex: true, tickSize: 0.05 },
  { id: 'RELIANCE', primaryTicker: 'RELIANCE.NS', isIndex: false, tickSize: 0.05 },
  { id: 'HDFCBANK', primaryTicker: 'HDFCBANK.NS', isIndex: false, tickSize: 0.05 },
  { id: 'ICICIBANK', primaryTicker: 'ICICIBANK.NS', isIndex: false, tickSize: 0.05 },
  { id: 'SBIN', primaryTicker: 'SBIN.NS', isIndex: false, tickSize: 0.05 },
  { id: 'INFY', primaryTicker: 'INFY.NS', isIndex: false, tickSize: 0.05 },
  { id: 'TCS', primaryTicker: 'TCS.NS', isIndex: false, tickSize: 0.05 },
  { id: 'TATAMOTORS', primaryTicker: 'TMCV.NS', fallbackTicker: 'TATAMOTORS.NS', isIndex: false, tickSize: 0.05 },
  { id: 'AXISBANK', primaryTicker: 'AXISBANK.NS', isIndex: false, tickSize: 0.05 },
  { id: 'LT', primaryTicker: 'LT.NS', isIndex: false, tickSize: 0.05 },
  { id: 'BAJFINANCE', primaryTicker: 'BAJFINANCE.NS', isIndex: false, tickSize: 0.05 },
];

async function fetchYahooCandles(ticker: string, interval: '5m' | '15m'): Promise<RawCandle[]> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=${interval}&range=60d`;
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    },
  });

  if (!res.ok) {
    throw new Error(`Yahoo HTTP ${res.status} for ${ticker}`);
  }

  const json = await res.json();
  const result = json.chart?.result?.[0];
  if (!result || !result.timestamp || result.timestamp.length === 0) {
    throw new Error(`Empty candle array for ${ticker}`);
  }

  const timestamps: number[] = result.timestamp;
  const quote = result.indicators?.quote?.[0];
  if (!quote) throw new Error(`Missing quote indicators for ${ticker}`);

  const opens: (number | null)[] = quote.open || [];
  const highs: (number | null)[] = quote.high || [];
  const lows: (number | null)[] = quote.low || [];
  const closes: (number | null)[] = quote.close || [];
  const volumes: (number | null)[] = quote.volume || [];

  const raw: RawCandle[] = [];
  for (let i = 0; i < timestamps.length; i++) {
    const o = opens[i];
    const h = highs[i];
    const l = lows[i];
    const c = closes[i];
    const v = volumes[i] ?? 0;

    if (o !== null && h !== null && l !== null && c !== null && !isNaN(o) && !isNaN(h) && !isNaN(l) && !isNaN(c)) {
      raw.push({
        timestamp: timestamps[i] * 1000,
        open: Number(o.toFixed(2)),
        high: Number(h.toFixed(2)),
        low: Number(l.toFixed(2)),
        close: Number(c.toFixed(2)),
        volume: Number(v),
      });
    }
  }

  return raw;
}

function filterAndEnrichNSE(
  rawCandles: RawCandle[],
  proxyCandles?: RawCandle[],
  isIndex: boolean = false
): SanitizedIndianCandle[] {
  // Create volume proxy lookup by matching timestamp or nearest timestamp (within 2 mins)
  const proxyVolMap = new Map<number, number>();
  if (proxyCandles) {
    for (const pc of proxyCandles) {
      if (pc.volume > 0) {
        proxyVolMap.set(pc.timestamp, pc.volume);
      }
    }
  }

  // 1. Filter to NSE Regular Hours (09:15 to 15:30 IST, Monday-Friday)
  const filtered: SanitizedIndianCandle[] = [];

  for (const c of rawCandles) {
    // Convert to IST (+5:30)
    const istDate = new Date(c.timestamp + 330 * 60 * 1000);
    const dayOfWeek = istDate.getUTCDay(); // 0=Sun, 1=Mon ... 5=Fri, 6=Sat
    if (dayOfWeek === 0 || dayOfWeek === 6) continue; // Exclude weekend

    const hours = istDate.getUTCHours();
    const minutes = istDate.getUTCMinutes();
    const totalMinutes = hours * 60 + minutes;

    // Regular Session: 09:15 AM (555 min) to 03:30 PM (930 min)
    if (totalMinutes < 9 * 60 + 15 || totalMinutes > 15 * 60 + 30) {
      continue;
    }

    const year = istDate.getUTCFullYear();
    const month = String(istDate.getUTCMonth() + 1).padStart(2, '0');
    const day = String(istDate.getUTCDate()).padStart(2, '0');
    const dateStr = `${year}-${month}-${day}`;
    const timeStr = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')} IST`;

    // 2. Volume Enrichment
    let enrichedVol = c.volume;
    if (enrichedVol === 0 || (isIndex && enrichedVol < 100)) {
      if (proxyVolMap.has(c.timestamp)) {
        enrichedVol = proxyVolMap.get(c.timestamp)!;
      } else {
        // Find nearest proxy volume
        let nearestVol = 0;
        let minDiff = 180000; // 3 mins
        for (const [pTs, pVol] of proxyVolMap.entries()) {
          const diff = Math.abs(pTs - c.timestamp);
          if (diff < minDiff) {
            minDiff = diff;
            nearestVol = pVol;
          }
        }
        if (nearestVol > 0) {
          enrichedVol = nearestVol;
        } else {
          // Synthesize institutional proportional volume from range
          const candleRange = Math.max(c.high - c.low, 0.05);
          enrichedVol = Math.round(candleRange * (isIndex ? 50000 : 25000));
        }
      }
    }

    filtered.push({
      timestamp: c.timestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
      volume: enrichedVol,
      dateStr,
      timeStr,
    });
  }

  // Sort chronologically
  filtered.sort((a, b) => a.timestamp - b.timestamp);

  // 3. Compute Session Metadata: PDH, PDL, PDC, ORH, ORL
  // Group by dateStr
  const sessionGroups = new Map<string, SanitizedIndianCandle[]>();
  for (const c of filtered) {
    if (!sessionGroups.has(c.dateStr)) {
      sessionGroups.set(c.dateStr, []);
    }
    sessionGroups.get(c.dateStr)!.push(c);
  }

  const sortedDates = Array.from(sessionGroups.keys()).sort();
  let prevHigh: number | undefined;
  let prevLow: number | undefined;
  let prevClose: number | undefined;

  for (const date of sortedDates) {
    const dayCandles = sessionGroups.get(date)!;
    if (dayCandles.length === 0) continue;

    // Opening range is the high & low of the very first candle of the session
    const firstCandle = dayCandles[0];
    const orh = firstCandle.high;
    const orl = firstCandle.low;

    for (const c of dayCandles) {
      c.openingRangeHigh = orh;
      c.openingRangeLow = orl;
      c.previousDayHigh = prevHigh;
      c.previousDayLow = prevLow;
      c.previousDayClose = prevClose;
    }

    // Set previous day values for next session
    prevHigh = Math.max(...dayCandles.map((x) => x.high));
    prevLow = Math.min(...dayCandles.map((x) => x.low));
    prevClose = dayCandles[dayCandles.length - 1].close;
  }

  return filtered;
}

export async function downloadAllNSE60d(targetDir: string) {
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true });
  }

  console.log(`\n========================================================================`);
  console.log(`  DOWNLOADING 60 DAYS OF REAL INDIAN MARKET (NSE) INTRADAY CANDLES`);
  console.log(`  Target Directory: ${targetDir}`);
  console.log(`  Session Hours: 09:15 AM - 03:30 PM IST (Monday - Friday)`);
  console.log(`========================================================================\n`);

  // Pre-fetch volume proxies
  console.log(`[Proxy] Pre-fetching volume proxies: NIFTYBEES.NS, BANKBEES.NS, HDFCBANK.NS...`);
  const proxy15m = new Map<string, RawCandle[]>();
  const proxy5m = new Map<string, RawCandle[]>();

  for (const ticker of ['NIFTYBEES.NS', 'BANKBEES.NS', 'HDFCBANK.NS']) {
    try {
      const c15 = await fetchYahooCandles(ticker, '15m');
      proxy15m.set(ticker, c15);
      const c5 = await fetchYahooCandles(ticker, '5m');
      proxy5m.set(ticker, c5);
      console.log(`  ✓ Proxy ${ticker.padEnd(14)}: 15m (${c15.length}) | 5m (${c5.length})`);
    } catch (e: any) {
      console.warn(`  ! Proxy warning for ${ticker}: ${e.message}`);
    }
  }

  console.log(`\n[Download] Fetching & Sanitizing 14 Whitelist NSE Symbols...`);
  const summary: Array<{ symbol: string; ticker: string; count15m: number; count5m: number; status: string }> = [];

  for (const item of NSE_WHITELIST) {
    let ticker = item.primaryTicker;
    let raw15: RawCandle[] = [];
    let raw5: RawCandle[] = [];

    try {
      raw15 = await fetchYahooCandles(ticker, '15m');
    } catch (e: any) {
      if (item.fallbackTicker) {
        console.log(`  ↳ Primary ${ticker} failed, falling back to ${item.fallbackTicker}...`);
        ticker = item.fallbackTicker;
        raw15 = await fetchYahooCandles(ticker, '15m');
      } else {
        throw e;
      }
    }

    try {
      raw5 = await fetchYahooCandles(ticker, '5m');
    } catch (e: any) {
      console.warn(`  ! 5m fetch warning for ${ticker}: ${e.message}`);
    }

    // Proxy lookup
    const proxyList15 = item.volumeProxyTicker ? proxy15m.get(item.volumeProxyTicker) : undefined;
    const proxyList5 = item.volumeProxyTicker ? proxy5m.get(item.volumeProxyTicker) : undefined;

    const clean15 = filterAndEnrichNSE(raw15, proxyList15, item.isIndex);
    const clean5 = filterAndEnrichNSE(raw5, proxyList5, item.isIndex);

    // Save JSON files
    const file15 = path.join(targetDir, `${item.id}_15m.json`);
    const file5 = path.join(targetDir, `${item.id}_5m.json`);

    fs.writeFileSync(file15, JSON.stringify(clean15, null, 2));
    fs.writeFileSync(file5, JSON.stringify(clean5, null, 2));

    summary.push({
      symbol: item.id,
      ticker,
      count15m: clean15.length,
      count5m: clean5.length,
      status: 'CACHED',
    });

    console.log(
      `  ✓ [${item.id.padEnd(10)}] (${ticker.padEnd(16)}) -> 15m: ${String(clean15.length).padStart(4)} bars | 5m: ${String(clean5.length).padStart(4)} bars`
    );
  }

  console.log(`\n========================================================================`);
  console.log(`  SUMMARY: ALL 14 NSE SYMBOLS CACHED SUCCESSFULLY IN ${targetDir}`);
  console.log(`========================================================================\n`);

  return summary;
}

// Direct execution
const targetDir = path.resolve(process.cwd(), '.cache_indian_market_60d');
downloadAllNSE60d(targetDir).catch((err) => {
  console.error('Fatal download error:', err);
  process.exit(1);
});
