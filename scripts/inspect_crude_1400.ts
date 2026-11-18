import { McxCommodityOptionSniperEngine } from '../lib/mcx/mcxCommodityOptionSniperEngine.ts';
import { aggregateMcx5mTo15m } from '../mcxServer.ts';

async function main() {
  const res = await fetch('http://127.0.0.1:8000/api/mcx/candles-batch');
  const data = await res.json();
  const crude = data['CRUDEOIL'];

  for (let i = 0; i < crude.length; i++) {
    const d = new Date(crude[i].timestamp + 5.5 * 3600000);
    const t = d.toISOString().substr(11, 5);
    const dt = d.toISOString().substr(0, 10);
    if (dt === '2026-11-16' && t === '14:00') {
      const w5m = crude.slice(0, i + 1);
      const w15m = aggregateMcx5mTo15m(w5m);

      const c0 = w5m[w5m.length - 1];
      const c1 = w5m[w5m.length - 2];
      const spotPrice = c0.close;
      const sr15m = McxCommodityOptionSniperEngine.calculate15mSupportResistance(w15m);

      const validResistances = sr15m.swingHighs.filter((h) => h >= spotPrice);
      const nearestResistance = validResistances.length > 0 ? validResistances[0] : sr15m.majorResistance;
      const validSupports = sr15m.swingLows.filter((l) => l <= spotPrice);
      const nearestSupport = validSupports.length > 0 ? validSupports[validSupports.length - 1] : sr15m.majorSupport;

      const targetResistanceWall = Math.max(nearestResistance, sr15m.majorResistance);
      const targetSupportWall = Math.min(nearestSupport, sr15m.majorSupport);

      const runwayToResistance = targetResistanceWall - spotPrice;
      const runwayToSupport = spotPrice - targetSupportWall;

      const distToResistancePct = runwayToResistance / spotPrice;
      const distToSupportPct = runwayToSupport / spotPrice;

      const range0 = Math.max(c0.high - c0.low, 1e-8);
      const body0 = Math.abs(c0.close - c0.open);
      const lowerWick0 = (Math.min(c0.open, c0.close) - c0.low) / range0;
      const upperWick0 = (c0.high - Math.max(c0.open, c0.close)) / range0;

      const isBearishPinbar = c0.close < c0.open && upperWick0 >= 0.35 && lowerWick0 <= 0.25;
      const isBearishEngulfing = c0.close < c0.open && c1.close > c1.open && c0.close < (c1.open + c1.close) / 2 && body0 / range0 >= 0.42;
      const isBearishBreakdown = c0.close < c0.open && c0.close < c1.low && body0 / range0 >= 0.45;
      const hasBearishPa = isBearishPinbar || isBearishEngulfing || isBearishBreakdown;

      const recent3High = Math.max(c0.high, c1.high, w5m[w5m.length - 3]?.high ?? c0.high);
      const isAt15mResistance = distToResistancePct <= 0.0045 || sr15m.rangePosPct >= 0.65 || recent3High >= nearestResistance * 0.9980;

      const closes5m = w5m.map((c: any) => c.close);
      const rsi14 = (McxCommodityOptionSniperEngine as any).computeRsi(closes5m, 14);
      const rsiPrev = (McxCommodityOptionSniperEngine as any).computeRsi(closes5m.slice(0, -1), 14);

      const prior20 = w5m.slice(-21, -1);
      const avgVol = prior20.reduce((sum: number, b: any) => sum + (b.volume || 1), 0) / Math.max(1, prior20.length);
      const rvol = avgVol > 0 ? (c0.volume || avgVol) / avgVol : 1.0;

      console.log('CRUDE AT 14:00 IST:');
      console.log('sr15m:', JSON.stringify(sr15m, null, 2));
      console.log('c0: open=', c0.open, 'high=', c0.high, 'low=', c0.low, 'close=', c0.close);
      console.log('c1: open=', c1.open, 'high=', c1.high, 'low=', c1.low, 'close=', c1.close);
      console.log('spotPrice:', spotPrice);
      console.log('nearestResistance:', nearestResistance);
      console.log('nearestSupport:', nearestSupport);
      console.log('distToResistancePct:', distToResistancePct);
      console.log('distToSupportPct:', distToSupportPct);
      console.log('sr15m.rangePosPct:', sr15m.rangePosPct);
      console.log('isAt15mResistance:', isAt15mResistance);
      console.log('isBearishPinbar:', isBearishPinbar, 'isBearishEngulfing:', isBearishEngulfing, 'isBearishBreakdown:', isBearishBreakdown);
      console.log('hasBearishPa:', hasBearishPa);
      console.log('rsi14:', rsi14, 'rsiPrev:', rsiPrev);
      console.log('rvol:', rvol);

      const mode1ResistanceReversalSell =
        isAt15mResistance &&
        hasBearishPa &&
        rsi14 >= 38 &&
        rsi14 <= 75 &&
        rsi14 <= rsiPrev + 1.0 &&
        rvol >= 0.65;
      console.log('mode1ResistanceReversalSell:', mode1ResistanceReversalSell);
      console.log('distToSupportPct >= 0.0055:', distToSupportPct >= 0.0055);
    }
  }
}

main().catch(console.error);
