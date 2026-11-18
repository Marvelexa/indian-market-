import fs from 'fs';
import path from 'path';

export interface TradeRecord {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  qty: number;
  entryPrice: number;
  exitPrice?: number;
  status: 'OPEN' | 'CLOSED';
  realizedPnl: number;
  floatingPnl: number;
  openedAt: string;
  closedAt?: string;
  exitReason?: string;
}

const DB_PATH = path.join(process.cwd(), '.trade_history.json');

export class TradeStore {
  public static loadTrades(): TradeRecord[] {
    try {
      if (fs.existsSync(DB_PATH)) {
        const data = fs.readFileSync(DB_PATH, 'utf-8');
        return JSON.parse(data);
      }
    } catch (e) {
      console.error('Error loading trade history:', e);
    }
    return [];
  }

  public static saveTrades(trades: TradeRecord[]): void {
    try {
      fs.writeFileSync(DB_PATH, JSON.stringify(trades, null, 2));
    } catch (e) {
      console.error('Error saving trade history:', e);
    }
  }

  public static upsertTrade(newTrade: TradeRecord): void {
    const trades = this.loadTrades();
    const index = trades.findIndex(t => t.id === newTrade.id);
    if (index >= 0) {
      trades[index] = { ...trades[index], ...newTrade };
    } else {
      trades.unshift(newTrade); // Newest first
    }
    this.saveTrades(trades);
  }
}
