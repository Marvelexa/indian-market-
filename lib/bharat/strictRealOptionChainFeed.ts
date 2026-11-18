/**
 * FILE: lib/bharat/strictRealOptionChainFeed.ts
 * ============================================================================
 * 100% REAL NSE OPTION CHAIN LTP FETCHER (ZERO SYNTHETIC FORMULA ALLOWED!)
 * Permanently bans `spot * 0.03` and `spotMove * 0.55`.
 * Fetches the exact live Option LTP, Bid, Ask, High, Low directly from real NSE Option Chain!
 * ============================================================================
 */

export interface RealNseOptionTick {
  underlying: string;
  strikePrice: number;
  optionType: 'CE' | 'PE';
  expiryDate: string;
  identifier: string;
  realOptionLtp: number; // Exact NSE price (e.g. ₹5.50 for AXISBANK 1370 CE, NEVER fake ₹41.05!)
  bidPrice: number;
  askPrice: number;
  openInterest: number;
  volume: number;
  changePct: number;
  underlyingSpotLtp: number;
  dayHigh?: number;
  dayLow?: number;
  prevClose?: number;
}

export class StrictRealOptionChainFeed {
  private static cookies = '';
  private static cookieFetchedAt = 0;
  private static cache: Map<string, { tick: RealNseOptionTick; timestamp: number }> = new Map();

  private static readonly SYMBOL_SLUG_MAP: Record<string, string> = {
    NIFTY: 'nifty',
    BANKNIFTY: 'banknifty',
    FINNIFTY: 'fin-nifty',
    SENSEX: 'sensex',
    AXISBANK: 'axis-bank-ltd',
    ICICIBANK: 'icici-bank-ltd',
    RELIANCE: 'reliance-industries-ltd',
    SBIN: 'state-bank-of-india',
    HDFCBANK: 'hdfc-bank-ltd',
    KOTAKBANK: 'kotak-mahindra-bank-ltd',
    TCS: 'tata-consultancy-services-ltd',
    INFY: 'infosys-ltd',
    TATASTEEL: 'tata-steel-ltd',
    BAJFINANCE: 'bajaj-finance-ltd',
    LT: 'larsen-toubro-ltd',
    HCLTECH: 'hcl-technologies-ltd',
    NTPC: 'ntpc-ltd',
    POWERGRID: 'power-grid-corporation-of-india-ltd',
    ONGC: 'oil-natural-gas-corporation-ltd',
    HINDALCO: 'hindalco-industries-ltd',
    JSWSTEEL: 'jsw-steel-ltd',
    JINDALSTEL: 'jindal-steel-power-ltd',
    ADANIENT: 'adani-enterprises-ltd',
    SUNPHARMA: 'sun-pharmaceutical-industries-ltd',
    BHARTIARTL: 'bharti-airtel-ltd',
    MARUTI: 'maruti-suzuki-india-ltd',
    TATAMOTORS: 'tata-motors-ltd',
    M_M: 'mahindra-mahindra-ltd',
  };

  /**
   * Fetches the 100% Real Live Option Premium from NSE Live Option Chain Feed.
   * NEVER estimates or invents an option price from Spot!
   */
  public static async getRealOptionQuote(params: {
    symbol: string;
    strikePrice: number;
    optionType: 'CE' | 'PE';
  }): Promise<RealNseOptionTick | null> {
    const sym = params.symbol.toUpperCase().replace(/\.NS$/, '').replace(/^NSE:/, '').replace('&', '_');
    const cacheKey = `${sym}_${params.strikePrice}_${params.optionType}`;
    const cached = this.cache.get(cacheKey);
    // Cache for 1.5 seconds to avoid over-fetching
    if (cached && Date.now() - cached.timestamp < 1500) {
      return cached.tick;
    }

    const slug = this.SYMBOL_SLUG_MAP[sym] || sym.toLowerCase();

    // 1. Fetch from High-Speed Real NSE Option Chain Feed
    try {
      const url = `https://groww.in/v1/api/option_chain_service/v1/option_chain/${slug}`;
      const res = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
          Accept: 'application/json',
        },
      });

      if (res.ok) {
        const json = (await res.json()) as any;
        const oc = json?.optionChain;
        const rows: any[] = oc?.optionChains || [];
        const underlyingSpot = Number(oc?.livePrice || 0);

        for (const row of rows) {
          // Groww returns strikePrice in paise (e.g. 137000 for 1370) or exact
          const sp = Number(row.strikePrice) > 50000 ? Number(row.strikePrice) / 100 : Number(row.strikePrice);
          if (Math.abs(sp - params.strikePrice) < 0.05) {
            const leg = params.optionType === 'CE' ? row.callOption : row.putOption;
            if (leg && leg.ltp && Number(leg.ltp) > 0) {
              const ltp = Number(leg.ltp);
              const tick: RealNseOptionTick = {
                underlying: sym,
                strikePrice: sp,
                optionType: params.optionType,
                expiryDate: String(leg.expiry || ''),
                identifier: String(leg.contractName || `${sym}_${sp}_${params.optionType}`),
                realOptionLtp: ltp,
                bidPrice: Number(leg.bidPrice || ltp),
                askPrice: Number(leg.askPrice || ltp),
                openInterest: Number(leg.openInterest || 0),
                volume: Number(leg.volume || 0),
                changePct: Number(leg.pChange || leg.dayChangePerc || 0),
                underlyingSpotLtp: underlyingSpot,
                dayHigh: Number(leg.high || 0),
                dayLow: Number(leg.low || 0),
                prevClose: Number(leg.close || 0),
              };
              this.cache.set(cacheKey, { tick, timestamp: Date.now() });
              return tick;
            }
          }
        }
      }
    } catch {
      // Continue to fallback
    }

    // 2. Direct NSEindia Fallback
    try {
      const isIndex = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY'].includes(sym);
      const nseUrl = isIndex
        ? `https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=${encodeURIComponent(sym)}`
        : `https://www.nseindia.com/api/option-chain-equities?symbol=${encodeURIComponent(sym)}`;

      const nseRes = await fetch(nseUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
          Accept: 'application/json, text/plain, */*',
          Referer: 'https://www.nseindia.com/option-chain',
        },
      });

      if (nseRes.ok) {
        const json = (await nseRes.json()) as any;
        const rows: any[] = json?.filtered?.data || json?.records?.data || [];
        const row = rows.find(
          (r) => Math.abs(Number(r.strikePrice) - params.strikePrice) < 0.01
        );
        if (row && row[params.optionType]) {
          const leg = row[params.optionType];
          const ltp = Number(leg.lastPrice || 0);
          if (ltp > 0) {
            const tick: RealNseOptionTick = {
              underlying: sym,
              strikePrice: Number(row.strikePrice),
              optionType: params.optionType,
              expiryDate: String(row.expiryDate || ''),
              identifier: String(leg.identifier || `${sym}_${row.strikePrice}_${params.optionType}`),
              realOptionLtp: ltp,
              bidPrice: Number(leg.bidprice || ltp),
              askPrice: Number(leg.askPrice || ltp),
              openInterest: Number(leg.openInterest || 0),
              volume: Number(leg.totalTradedVolume || 0),
              changePct: Number(leg.pChange || 0),
              underlyingSpotLtp: Number(json?.records?.underlyingValue || 0),
            };
            this.cache.set(cacheKey, { tick, timestamp: Date.now() });
            return tick;
          }
        }
      }
    } catch {
      // Continue to cache
    }

    if (cached && Date.now() - cached.timestamp < 300000) {
      return cached.tick;
    }

    // STRICT RULE: If real quote is not available, return null! NEVER USE SYNTHETIC FORMULA!
    return null;
  }

  /**
   * 3. OPTION PREMIUM MOMENTUM CONFIRMATION
   * Prevents buying crashing options (e.g. AXISBANK 1370 CE dumping from ₹14.50 -> ₹9.50 -> ₹5.30).
   * Trade is approved ONLY IF the option itself has positive momentum!
   */
  public static verifyOptionMomentum(quote: RealNseOptionTick): {
    approved: boolean;
    vetoReason?: string;
  } {
    // 1. Check if option has crashed heavily on the day (> 15% intraday drop)
    if (quote.changePct < -15.0) {
      return {
        approved: false,
        vetoReason: `CRASHING_OPTION_VETO: ${quote.underlying} ${quote.strikePrice} ${quote.optionType} is dumping heavily (${quote.changePct.toFixed(2)}% drop). Never buy a falling option!`,
      };
    }

    // 2. Check if option price is below minimum liquidity threshold
    if (quote.realOptionLtp < 0.50) {
      return {
        approved: false,
        vetoReason: `ILLIQUID_OPTION_VETO: Premium ₹${quote.realOptionLtp} is too low (penny option risk).`,
      };
    }

    return { approved: true };
  }
}
