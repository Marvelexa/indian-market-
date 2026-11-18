import { McxCommodityOptionSniperEngine } from '../lib/mcx/mcxCommodityOptionSniperEngine.ts';
import { aggregateMcx5mTo15m } from '../mcxServer.ts';

async function main() {
  const res = await fetch('http://127.0.0.1:8000/api/mcx/candles-batch');
  const data = await res.json();
  const crude = data['CRUDEOIL'];
  console.log('--- CRUDE OIL CHECK (13:30 to 14:30) ---');
  for (let i = 0; i < crude.length; i++) {
    const d = new Date(crude[i].timestamp + 5.5 * 3600000);
    const t = d.toISOString().substr(11, 5);
    const dt = d.toISOString().substr(0, 10);
    if (dt === '2026-11-16' && t >= '13:30' && t <= '14:30') {
      const w5m = crude.slice(0, i + 1);
      const w15m = aggregateMcx5mTo15m(w5m);
      const dec = McxCommodityOptionSniperEngine.evaluateSetup({
        commoditySymbol: 'CRUDEOIL',
        candles15m: w15m,
        candles5m: w5m,
      });
      console.log(`${t} | Close: ${crude[i].close.toFixed(1)} | Approved: ${dec.approved} | Action: ${dec.action} | Reason: ${dec.reason}`);
    }
  }

  const silver = data['SILVER'];
  console.log('\n--- SILVER CHECK (10:30 to 11:30) ---');
  for (let i = 0; i < silver.length; i++) {
    const d = new Date(silver[i].timestamp + 5.5 * 3600000);
    const t = d.toISOString().substr(11, 5);
    const dt = d.toISOString().substr(0, 10);
    if (dt === '2026-11-16' && t >= '10:30' && t <= '11:30') {
      const w5m = silver.slice(0, i + 1);
      const w15m = aggregateMcx5mTo15m(w5m);
      const dec = McxCommodityOptionSniperEngine.evaluateSetup({
        commoditySymbol: 'SILVER',
        candles15m: w15m,
        candles5m: w5m,
      });
      console.log(`${t} | Close: ${silver[i].close.toFixed(1)} | Approved: ${dec.approved} | Action: ${dec.action} | Reason: ${dec.reason}`);
    }
  }
}

main().catch(console.error);
