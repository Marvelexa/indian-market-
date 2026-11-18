import { TradeStore, TradeRecord } from './tradeStore';

export class EngineExecutor {
  private activePositions: Map<string, any> = new Map();

  private evaluateSignal(symbol: string): { approved: boolean; action: 'BUY' | 'SELL'; qty: number } {
    // Core signal evaluation logic hooked to your multi-timeframe strategy
    return { approved: false, action: 'BUY', qty: 1 };
  }

  // Inside your engine executor loop:
  public async processTick(symbol: string, currentLtp: number) {
    // 1. Check if this symbol already has an active seat open
    const existingPosition = Array.from(this.activePositions.values()).find(p => p.symbol === symbol);

    if (existingPosition) {
      // DO NOT open a new trade! Only update floating P&L for the existing position.
      existingPosition.currentPrice = currentLtp;
      existingPosition.floatingPnl = existingPosition.side === 'BUY' 
        ? (currentLtp - existingPosition.entryPrice) * existingPosition.qty
        : (existingPosition.entryPrice - currentLtp) * existingPosition.qty;
      return;
    }

    // 2. Only check entry signals if NO position is currently open for this symbol
    const signal = this.evaluateSignal(symbol);
    if (signal.approved) {
      const newTrade: TradeRecord = {
        id: `${symbol}-${Date.now()}`,
        symbol,
        side: signal.action,
        qty: signal.qty,
        entryPrice: currentLtp,
        status: 'OPEN',
        realizedPnl: 0,
        floatingPnl: 0,
        openedAt: new Date().toLocaleTimeString()
      };
      
      this.activePositions.set(symbol, newTrade);

      // Save state so it never disappears on server restart or reload
      TradeStore.upsertTrade(newTrade);
    }
  }

  public async closePosition(symbol: string, exitPrice: number, exitReason: string) {
    const pos = this.activePositions.get(symbol);
    if (!pos) return;

    const realizedPnl = pos.side === 'BUY'
      ? (exitPrice - pos.entryPrice) * pos.qty
      : (pos.entryPrice - exitPrice) * pos.qty;

    const closedTrade: TradeRecord = {
      ...pos,
      status: 'CLOSED',
      exitPrice,
      realizedPnl,
      closedAt: new Date().toLocaleTimeString(),
      exitReason
    };

    TradeStore.upsertTrade(closedTrade);
    this.activePositions.delete(symbol);
  }
}
