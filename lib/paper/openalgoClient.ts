import dotenv from 'dotenv';
dotenv.config();

export interface OpenAlgoOrderPayload {
  symbol: string;         // e.g. "AXISBANK26NOV261370PE" or "NIFTY26NOV25250PE"
  action: 'BUY' | 'SELL';
  exchange: 'NSE' | 'NFO' | 'BSE' | 'BFO' | 'MCX';
  priceType: 'LIMIT' | 'MARKET';
  product: 'MIS' | 'NRML';
  quantity: number;       // Exact quantity (Lots * LotSize)
  price?: number;         // Required if priceType is LIMIT
  triggerPrice?: number;
}

export interface OpenAlgoOrderResponse {
  status: 'success' | 'error';
  orderid?: string;
  message?: string;
  data?: any;
}

export class OpenAlgoClient {
  public static get baseUrl(): string {
    return process.env.OPENALGO_HOST_URL || 'http://localhost:5000';
  }

  public static get apiKey(): string {
    return process.env.OPENALGO_API_KEY || '';
  }

  public static get strategy(): string {
    return process.env.OPENALGO_STRATEGY_NAME || 'NexusBharat';
  }

  /**
   * Place a paper trade in OpenAlgo Analyzer mode
   */
  public static async placeOrder(order: OpenAlgoOrderPayload): Promise<OpenAlgoOrderResponse> {
    const url = `${this.baseUrl}/api/v1/placeorder`;
    const payload = {
      apikey: this.apiKey,
      strategy: this.strategy,
      symbol: order.symbol,
      action: order.action,
      exchange: order.exchange,
      pricetype: order.priceType,
      product: order.product || 'MIS',
      quantity: order.quantity,
      price: order.priceType === 'LIMIT' ? order.price : 0,
      trigger_price: order.triggerPrice || 0,
    };

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const json = (await res.json()) as any;
      if (!res.ok || json.status === 'error') {
        console.error('❌ [OpenAlgo] Order Placement Failed:', json.message || res.statusText);
        return { status: 'error', message: json.message || 'API request failed', data: json };
      }

      console.log(
        `✅ [OpenAlgo Paper] Order Placed: ${order.action} ${order.quantity}x ${order.symbol} @ ₹${order.price || 'MKT'} (ID: ${json.orderid})`
      );
      return { status: 'success', orderid: json.orderid, data: json };
    } catch (err: any) {
      console.error('⚠️ [OpenAlgo] Network connection error:', err.message);
      return { status: 'error', message: err.message };
    }
  }

  /**
   * Close or Square-off an open position
   */
  public static async closePosition(
    symbol: string,
    exchange: string,
    quantity: number
  ): Promise<OpenAlgoOrderResponse> {
    const url = `${this.baseUrl}/api/v1/closeposition`;
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          apikey: this.apiKey,
          strategy: this.strategy,
          symbol,
          exchange,
          quantity,
        }),
      });
      const json = (await res.json()) as any;
      if (res.ok && json.status !== 'error') {
        console.log(`✅ [OpenAlgo Paper] Position Closed: ${quantity}x ${symbol} on ${exchange}`);
        return { status: 'success', message: json.message, data: json };
      }
      return { status: 'error', message: json.message || res.statusText, data: json };
    } catch (err: any) {
      console.error('⚠️ [OpenAlgo] Close position error:', err.message);
      return { status: 'error', message: err.message };
    }
  }

  /**
   * Fetch current virtual open positions and P&L from OpenAlgo
   */
  public static async getOpenPositions(): Promise<any[]> {
    const url = `${this.baseUrl}/api/v1/positions?apikey=${encodeURIComponent(this.apiKey)}`;
    try {
      const res = await fetch(url);
      if (!res.ok) return [];
      const json = (await res.json()) as any;
      return json.data || [];
    } catch {
      return [];
    }
  }

  /**
   * Health check to confirm OpenAlgo is running
   */
  public static async checkConnection(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);
      const res = await fetch(`${this.baseUrl}/api/v1/ping`, { signal: controller.signal });
      clearTimeout(timeoutId);
      return res.ok;
    } catch {
      return false;
    }
  }
}
