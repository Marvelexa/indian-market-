import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  FastForward,
  Clock,
  Calendar,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Layers,
  BarChart2,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Shield,
  ShieldCheck,
  ShieldAlert,
  ArrowUpRight,
  ArrowDownRight,
  Target,
} from 'lucide-react';

interface MonthCheckpoint {
  label: string;
  barIndex: number;
  dateStr: string;
}

interface ReplayPosition {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  seatBucket: 'CHOP_PING_PONG_SEAT' | 'NORMAL_TREND_RUNNER_SEAT' | 'NIFTY_BANKNIFTY_OPTION_SEAT' | 'CHOP_15PCT_SEAT' | 'NORMAL_23_TO_40PCT_SEAT' | 'BTC_ETH_OPTION_MIRROR_SEAT';
  isOption?: boolean;
  optionType?: 'CALL' | 'PUT';
  optionStrike?: number;
  entryPrice: number;
  currentPrice: number;
  initialSlPrice: number;
  slPrice: number;
  initialTpPrice: number;
  tpPrice: number;
  quantity?: number;
  stage?: number;
  marginInr?: number;
  notionalInr?: number;
  floatingPnlInr?: number;
  currentNetRoePct: number;
  peakRoePct: number;
  barsHeld: number;
  openedAtBarIndex?: number;
  openedAtTime: number;
  openedAtFormatted: string;
  reason: string;
  strategyName: string;
  // Legacy aliases
  marginUsd?: number;
  notionalUsd?: number;
  floatingPnlUsd?: number;
  ratchetLevel?: number;
}

interface ReplayClosedTrade {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  seatBucket: string;
  isOption?: boolean;
  optionType?: 'CALL' | 'PUT';
  optionStrike?: number;
  entryPrice: number;
  exitPrice: number;
  entryTime: number;
  exitTime: number;
  entryDateFormatted: string;
  exitDateFormatted: string;
  initialSlPrice: number;
  finalSlPrice: number;
  initialTpPrice: number;
  finalTpPrice: number;
  quantity?: number;
  barsHeld: number;
  notionalInr?: number;
  marginInr?: number;
  netPnlInr?: number;
  netRoePct: number;
  exitReason: 'TARGET_TP_HIT' | 'PROFIT_LOCKED_EXIT' | 'BREAKEVEN_SCRATCH_EXIT' | 'STOP_LOSS_HIT' | 'INTRADAY_AUTO_SQUARE_OFF' | 'STAGE2_RUNNER_TP_HIT' | 'PROFIT_LOCK_HIT';
  strategyName: string;
  // Legacy aliases
  netPnlUsd?: number;
  marginUsd?: number;
  notionalUsd?: number;
  ratchetLevel?: number;
}

interface CoinScorecard {
  symbol: string;
  currentPrice?: number;
  totalTrades: number;
  wins: number;
  losses: number;
  winRatePct: number;
  netPnlInr?: number;
  netPnlUsd?: number;
  tpHits: number;
  profitLockHits: number;
  slHits: number;
  activeTrade?: {
    side: 'BUY' | 'SELL';
    entryPrice: number;
    currentPrice: number;
    floatingPnlInr: number;
    currentNetRoePct: number;
    slPrice: number;
    tpPrice: number;
    stage: number;
  } | null;
}

interface ReplayEngineState {
  isRunning: boolean;
  speed: number;
  currentTimestamp: number;
  formattedDate: string;
  monthBanner: string;
  barIndex: number;
  subTickIndex: number;
  totalBars: number;
  progressPct: number;
  availableMonths: MonthCheckpoint[];
  wallet: {
    startingCapitalInr?: number;
    balanceInr?: number;
    realizedPnlInr?: number;
    floatingPnlInr?: number;
    startingCapitalUsd?: number;
    balanceUsd?: number;
    realizedPnlUsd?: number;
    floatingPnlUsd?: number;
    totalTrades: number;
    wins: number;
    losses: number;
    winRatePct: number;
    tpHits: number;
    profitLockHits: number;
    slHits: number;
  };
  seatBreakdown?: Record<string, {
    seatBucket: string;
    totalTrades: number;
    wins: number;
    losses: number;
    winRatePct: number;
    tpHits: number;
    profitLockHits: number;
    slHits: number;
    netPnlInr?: number;
    netPnlUsd?: number;
  }>;
  livePrices: Record<string, number>;
  activePositions: ReplayPosition[];
  coinStats: Record<string, CoinScorecard>;
  closedLedger: ReplayClosedTrade[];
}

const SPEED_OPTIONS = [1, 2, 5, 10, 25, 100];

export const TimeMachineReplayTab: React.FC = () => {
  const [state, setState] = useState<ReplayEngineState | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [controlling, setControlling] = useState<boolean>(false);
  const isPollingRef = useRef<boolean>(false);

  const fetchState = async () => {
    if (isPollingRef.current) return;
    isPollingRef.current = true;
    try {
      const res = await fetch(`/api/replay/state?_t=${Date.now()}`, {
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
      });
      if (res.ok) {
        const data = await res.json();
        if (data && typeof data === 'object') {
          setState(data);
        }
      }
    } catch (e) {
      console.error('Failed to fetch replay state:', e);
    } finally {
      isPollingRef.current = false;
      setLoading(false);
    }
  };

  const sendControl = async (action: 'PLAY' | 'PAUSE' | 'RESET' | 'SET_SPEED' | 'JUMP_TO_BAR', payload?: { speed?: number; barIndex?: number }) => {
    setControlling(true);
    // Instant optimistic tactile response
    if (action === 'PLAY') {
      setState(prev => prev ? { ...prev, isRunning: true } : prev);
    } else if (action === 'PAUSE') {
      setState(prev => prev ? { ...prev, isRunning: false } : prev);
    } else if (action === 'SET_SPEED' && payload?.speed) {
      setState(prev => prev ? { ...prev, speed: payload.speed! } : prev);
    } else if (action === 'RESET') {
      setState(prev => prev ? { ...prev, barIndex: 45, progressPct: 0 } : prev);
    }

    try {
      const res = await fetch('/api/replay/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...payload }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data?.state) {
          setState(data.state);
        }
      }
    } catch (e) {
      console.error('Failed to control replay:', e);
    } finally {
      setControlling(false);
    }
  };

  // Ultra-resilient 200ms polling loop that never stalls or caches
  useEffect(() => {
    let isMounted = true;
    const tickLoop = async () => {
      await fetchState();
      if (isMounted) {
        setTimeout(tickLoop, 200);
      }
    };
    tickLoop();

    return () => {
      isMounted = false;
    };
  }, []);

  // Safe Loading Screen
  if (!state) {
    return (
      <div className="flex flex-col items-center justify-center p-16 space-y-4 text-emerald-400">
        <Sparkles className="w-8 h-8 animate-spin" />
        <span className="text-sm font-semibold tracking-wider font-mono uppercase">
          Initializing 60-Day Indian Market (NSE) Replay Matrix...
        </span>
      </div>
    );
  }

  const wallet = state.wallet || {
    startingCapitalInr: 100000,
    balanceInr: 100000,
    realizedPnlInr: 0,
    floatingPnlInr: 0,
    totalTrades: 0,
    wins: 0,
    losses: 0,
    winRatePct: 0,
    tpHits: 0,
    profitLockHits: 0,
    slHits: 0,
  };

  const startingCapitalInr = Number(wallet.startingCapitalInr ?? (wallet.startingCapitalUsd ? wallet.startingCapitalUsd * 88.75 : 100000));
  const balanceInr = Number(wallet.balanceInr ?? (wallet.balanceUsd ? wallet.balanceUsd * 88.75 : 100000));
  const realizedPnlInr = Number(wallet.realizedPnlInr ?? (wallet.realizedPnlUsd ? wallet.realizedPnlUsd * 88.75 : 0));
  const floatingPnlInr = Number(wallet.floatingPnlInr ?? (wallet.floatingPnlUsd ? wallet.floatingPnlUsd * 88.75 : 0));
  const winRatePct = Number(wallet.winRatePct ?? 0);
  const totalTrades = Number(wallet.totalTrades ?? 0);
  const wins = Number(wallet.wins ?? 0);
  const losses = Number(wallet.losses ?? 0);
  const progressPct = Number(state.progressPct ?? 0);

  const activePositions = Array.isArray(state.activePositions) ? state.activePositions : [];
  const livePrices = state.livePrices || {};
  const closedLedger = Array.isArray(state.closedLedger) ? state.closedLedger : [];
  const availableMonths = Array.isArray(state.availableMonths) ? state.availableMonths : [];

  // Sort Symbol Scoreboard so symbols with active positions and trades appear at top
  const coinStats = (() => {
    try {
      const raw = Object.values(state.coinStats || {});
      return raw.sort((a: any, b: any) => {
        const aSym = String(a?.symbol || '');
        const bSym = String(b?.symbol || '');
        const aActive = activePositions.some(p => p?.symbol === aSym);
        const bActive = activePositions.some(p => p?.symbol === bSym);
        if (aActive && !bActive) return -1;
        if (!aActive && bActive) return 1;
        const bTrades = Number(b?.totalTrades || 0);
        const aTrades = Number(a?.totalTrades || 0);
        if (bTrades !== aTrades) return bTrades - aTrades;
        return Number(b?.netPnlInr ?? b?.netPnlUsd ?? 0) - Number(a?.netPnlInr ?? a?.netPnlUsd ?? 0);
      });
    } catch {
      return [];
    }
  })();

  const formatRupee = (num: number, decimals: number = 2) => {
    const isNeg = num < 0;
    const absVal = Math.abs(num);
    const formatted = absVal.toLocaleString('en-IN', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    return `${isNeg ? '-' : ''}₹${formatted}`;
  };

  return (
    <div className="w-full space-y-4 font-sans text-slate-100">
      
      {/* ========================================================================= */}
      {/* SECTION 1: TOP STICKY TIME-MACHINE CONTROL BAR */}
      {/* ========================================================================= */}
      <div className="sticky top-14 z-40 rounded-2xl bg-[#090F0C]/95 border border-emerald-500/30 p-4 shadow-[0_8px_32px_rgba(0,0,0,0.8)] backdrop-blur-2xl space-y-3">
        
        {/* Top Header Row: Banner Date & Master Progress */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          
          {/* Glowing Indian Market Banner Badge */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-[#00FFA3] shadow-[0_0_15px_rgba(0,255,163,0.3)]">
              <Clock className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-black tracking-widest text-emerald-400 uppercase bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-500/30 flex items-center gap-1">
                  <span>🇮🇳</span> {state.monthBanner || 'NSE LIVE REPLAY'}
                </span>
                <span className="text-xs font-mono font-bold text-white bg-black/40 px-2 py-0.5 rounded border border-white/10">
                  ⏰ {state.formattedDate || '09:30 AM IST'}
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-slate-400">
                  Tick {state.subTickIndex ?? 0}/3
                </span>
              </div>
              <span className="text-[11px] text-slate-400 font-medium">
                14 NSE Symbols • 9:15 AM – 3:30 PM IST • 2+2+2 Seat Institutional Sniper Engine
              </span>
            </div>
          </div>

          {/* Play / Pause / Reset Controls */}
          <div className="flex items-center flex-wrap gap-2">
            {state.isRunning ? (
              <button
                disabled={controlling}
                onClick={() => sendControl('PAUSE')}
                className="px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 transition-all cursor-pointer shadow-sm"
              >
                <Pause className="w-4 h-4 fill-amber-300" />
                <span>Pause Replay</span>
              </button>
            ) : (
              <button
                disabled={controlling}
                onClick={() => sendControl('PLAY')}
                className="px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 bg-emerald-500/25 text-[#00FFA3] border border-emerald-500/50 hover:bg-emerald-500/35 transition-all cursor-pointer shadow-[0_0_15px_rgba(0,255,163,0.3)]"
              >
                <Play className="w-4 h-4 fill-[#00FFA3]" />
                <span>Play Replay</span>
              </button>
            )}

            <button
              disabled={controlling}
              onClick={() => sendControl('RESET')}
              className="px-3.5 py-2 rounded-xl text-xs font-medium flex items-center gap-1.5 bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 hover:text-white transition-all cursor-pointer"
              title="Reset to bar 45"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          </div>
        </div>

        {/* Timeline Bar & Progress */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>
              Bar <strong className="text-white">{state.barIndex ?? 45}</strong> of {state.totalBars ?? 1500}
            </span>
            <span className="text-[#00FFA3] font-bold">
              {progressPct.toFixed(1)}% Complete
            </span>
          </div>

          {/* Smooth Progress Bar */}
          <div className="w-full h-2 rounded-full bg-black/60 border border-white/10 overflow-hidden relative">
            <div
              className="h-full bg-gradient-to-r from-emerald-600 via-[#00FFA3] to-teal-400 transition-all duration-300 rounded-full shadow-[0_0_10px_rgba(0,255,163,0.5)]"
              style={{ width: `${Math.min(100, Math.max(0, progressPct))}%` }}
            />
          </div>
        </div>

        {/* Speed & Month Jump Controls */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pt-1 border-t border-white/5">
          
          {/* Jump-to-Month Quick Jump Buttons */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mr-1 flex items-center gap-1">
              <Calendar className="w-3 h-3 text-emerald-400" />
              Checkpoints:
            </span>
            {availableMonths.map((m) => {
              const isCurrent = Math.abs((state.barIndex || 0) - m.barIndex) < 40;
              return (
                <button
                  key={m.barIndex}
                  onClick={() => sendControl('JUMP_TO_BAR', { barIndex: m.barIndex })}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold font-mono transition-all cursor-pointer ${
                    isCurrent
                      ? 'bg-emerald-500/25 text-[#00FFA3] border border-emerald-500/50 shadow-sm'
                      : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                  }`}
                >
                  {m.label}
                </button>
              );
            })}
          </div>

          {/* Speed Selector Pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mr-1 flex items-center gap-1">
              <FastForward className="w-3 h-3 text-emerald-400" />
              Speed:
            </span>
            {SPEED_OPTIONS.map((spd) => {
              const isActive = state.speed === spd;
              return (
                <button
                  key={spd}
                  onClick={() => sendControl('SET_SPEED', { speed: spd })}
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold font-mono transition-all cursor-pointer ${
                    isActive
                      ? 'bg-[#00FFA3] text-black font-extrabold shadow-[0_0_12px_rgba(0,255,163,0.4)] scale-105'
                      : 'bg-white/5 text-slate-300 hover:text-white hover:bg-white/10 border border-white/5'
                  }`}
                >
                  {spd === 100 ? '100x Turbo' : `${spd}x`}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SECTION 2: 2+2+2 SEAT ARCHITECTURE BAR */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
        <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#090F0C]/90 border border-cyan-500/20">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <div>
              <span className="text-xs font-bold text-white block">2 Chop Ping-Pong Seats</span>
              <span className="text-[10px] text-slate-400">Mean Reversion • Bollinger 2.1 SD Sweeps</span>
            </div>
          </div>
          <span className="text-[10px] font-mono font-bold text-cyan-300 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30">
            R:R ≥ 1:1.8
          </span>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#090F0C]/90 border border-indigo-500/20">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse" />
            <div>
              <span className="text-xs font-bold text-white block">2 Trend Runner Seats</span>
              <span className="text-[10px] text-slate-400">EMA 9/21/50 + VWAP Pullback Continuations</span>
            </div>
          </div>
          <span className="text-[10px] font-mono font-bold text-indigo-300 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-500/30">
            R:R ≥ 1:2.5
          </span>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#090F0C]/90 border border-amber-500/20">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
            <div>
              <span className="text-xs font-bold text-white block">2 Index Option Seats</span>
              <span className="text-[10px] text-slate-400">NIFTY/BANKNIFTY 0.60Δ ITM CE / PE</span>
            </div>
          </div>
          <span className="text-[10px] font-mono font-bold text-amber-300 bg-amber-950/60 px-2 py-0.5 rounded border border-amber-500/30">
            1 Lot • ₹1.6K Max SL
          </span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SECTION 3: REPLAY PORTFOLIO KPI CARDS (NATIVE INR) */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        
        {/* Card 1: Starting Capital */}
        <div className="rounded-xl bg-[#090F0C]/90 border border-white/10 p-3 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Base Capital</span>
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-black text-white font-mono">{formatRupee(startingCapitalInr, 0)}</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono block">Max Risk: ₹1,600 / trade</span>
        </div>

        {/* Card 2: Replay Balance */}
        <div className="rounded-xl bg-[#090F0C]/90 border border-white/10 p-3 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Replay Balance</span>
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-black text-white font-mono">{formatRupee(balanceInr, 0)}</span>
          </div>
          <span className="text-[10px] text-emerald-400 font-mono block">
            Net Return: {startingCapitalInr > 0 ? (((balanceInr - startingCapitalInr) / startingCapitalInr) * 100).toFixed(1) : 0}%
          </span>
        </div>

        {/* Card 3: Realized PnL */}
        <div className={`rounded-xl bg-[#090F0C]/90 border p-3 space-y-1 ${
          realizedPnlInr >= 0 ? 'border-emerald-500/30' : 'border-rose-500/30'
        }`}>
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Realized Net PnL</span>
          <div className="flex items-baseline gap-1.5">
            <span className={`text-xl font-black font-mono ${
              realizedPnlInr >= 0 ? 'text-[#00FFA3]' : 'text-rose-400'
            }`}>
              {realizedPnlInr >= 0 ? '+' : ''}{formatRupee(realizedPnlInr, 0)}
            </span>
          </div>
          <span className="text-[10px] text-slate-400 font-mono block">
            {totalTrades} Trades Executed
          </span>
        </div>

        {/* Card 4: Floating PnL */}
        <div className={`rounded-xl bg-[#090F0C]/90 border p-3 space-y-1 ${
          floatingPnlInr >= 0 ? 'border-emerald-500/20' : 'border-rose-500/20'
        }`}>
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Floating Unrealized</span>
          <div className="flex items-baseline gap-1.5">
            <span className={`text-xl font-black font-mono ${
              floatingPnlInr >= 0 ? 'text-[#00FFA3]' : 'text-rose-400'
            }`}>
              {floatingPnlInr >= 0 ? '+' : ''}{formatRupee(floatingPnlInr, 0)}
            </span>
          </div>
          <span className="text-[10px] text-slate-400 font-mono block">
            {activePositions.length} Active Positions
          </span>
        </div>

        {/* Card 5: Win Rate & Exits */}
        <div className="rounded-xl bg-[#090F0C]/90 border border-emerald-500/30 p-3 space-y-1 col-span-2 md:col-span-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Win Rate</span>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-black text-[#00FFA3] font-mono">{winRatePct.toFixed(1)}%</span>
            <span className="text-[10px] font-mono text-slate-400">({wins}W / {losses}L)</span>
          </div>
          <div className="flex items-center gap-1.5 text-[9px] font-mono text-slate-400 pt-0.5">
            <span className="text-emerald-400" title="Target Take-Profit Hits">🎯 {wallet.tpHits ?? 0}</span>
            <span className="text-cyan-400" title="Profit Lock Hits">🔒 {wallet.profitLockHits ?? 0}</span>
            <span className="text-rose-400" title="Stop Loss Hits">🛡️ {wallet.slHits ?? 0}</span>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SECTION 4: LIVE 14 NSE WHITELIST SYMBOLS TICKER STRIP */}
      {/* ========================================================================= */}
      <div className="rounded-xl bg-[#090F0C]/80 border border-white/5 p-2.5 overflow-x-auto scrollbar-thin">
        <div className="flex items-center gap-2 min-w-max">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 px-2 py-1 bg-white/5 rounded flex items-center gap-1">
            <span>🇮🇳</span> 14 NSE Whitelist:
          </span>
          {Object.entries(livePrices).map(([sym, price]) => {
            const hasPosition = activePositions.some(p => p.symbol === sym);
            const numPrice = Number(price || 0);
            return (
              <div
                key={sym}
                className={`flex items-center gap-2 px-2.5 py-1 rounded-lg border text-xs font-mono transition-all ${
                  hasPosition
                    ? 'bg-emerald-500/20 border-emerald-500/50 text-[#00FFA3] shadow-sm'
                    : 'bg-white/5 border-white/5 text-slate-300'
                }`}
              >
                <span className="font-bold">{sym}</span>
                <span className="font-mono text-white">
                  {numPrice > 0 ? `₹${numPrice >= 1000 ? numPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : numPrice.toFixed(2)}` : '—'}
                </span>
                {hasPosition && (
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00FFA3] animate-ping" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SECTION 5: ACTIVE REPLAY POSITIONS GRID (MAX 6 SEATS) */}
      {/* ========================================================================= */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-[#00FFA3]" />
              Active Replay Positions ({activePositions.length}/6 Seats)
            </span>
            <span className="text-[10px] font-mono text-slate-400 px-2 py-0.5 rounded bg-white/5">
              2 Chop + 2 Trend + 2 Options
            </span>
          </div>
        </div>

        {activePositions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-white/10 bg-black/30 p-8 text-center space-y-2">
            <Activity className="w-6 h-6 text-slate-500 mx-auto" />
            <span className="text-xs font-semibold text-slate-400 block">
              All 6 Seats Available — Sniper Engine Scanning 5m &amp; 15m Candles for Institutional Confluence
            </span>
            <span className="text-[11px] text-slate-500 block">
              Trades trigger during regular session (09:25–15:10 IST) when VWAP, EMA 9/21, Box Sweeps &amp; RVOL align.
            </span>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {activePositions.map((pos) => {
              const isBuy = pos.side === 'BUY';
              const pnlInr = Number(pos.floatingPnlInr ?? (pos.floatingPnlUsd ? pos.floatingPnlUsd * 88.75 : 0));
              const isProfit = pnlInr >= 0;
              const entry = Number(pos.entryPrice || 0);
              const current = Number(pos.currentPrice || entry);
              const initialTp = Number(pos.initialTpPrice || entry);
              const totalTarget = Math.abs(initialTp - entry);
              const profitDist = isBuy ? (current - entry) : (entry - current);
              const progress = totalTarget > 0
                ? Math.max(0, Math.min(100, (profitDist / totalTarget) * 100))
                : 0;

              const isOptionSeat = pos.seatBucket === 'NIFTY_BANKNIFTY_OPTION_SEAT' || pos.isOption;
              const isChopSeat = pos.seatBucket === 'CHOP_PING_PONG_SEAT' || pos.seatBucket === 'CHOP_15PCT_SEAT';

              return (
                <div
                  key={pos.id}
                  className="rounded-xl bg-[#090F0C] border border-emerald-500/30 p-3.5 space-y-2.5 shadow-lg relative overflow-hidden"
                >
                  {/* Glowing Side Indicator Line */}
                  <div className={`absolute top-0 left-0 right-0 h-1 ${
                    isBuy ? 'bg-[#00FFA3]' : 'bg-rose-500'
                  }`} />

                  {/* Top Row: Symbol, Side, Bucket */}
                  <div className="flex items-center justify-between pt-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-base font-black text-white font-mono">
                        {pos.symbol}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                        isBuy ? 'bg-emerald-500/20 text-[#00FFA3]' : 'bg-rose-500/20 text-rose-400'
                      }`}>
                        {pos.side}
                      </span>
                      {isOptionSeat && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          {pos.optionType === 'CALL' ? 'CE (Call)' : 'PE (Put)'} {pos.optionStrike ? `₹${pos.optionStrike}` : ''}
                        </span>
                      )}
                    </div>

                    <span className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded border ${
                      isOptionSeat
                        ? 'bg-amber-950/40 text-amber-300 border-amber-500/30'
                        : isChopSeat
                        ? 'bg-cyan-950/40 text-cyan-300 border-cyan-500/30'
                        : 'bg-indigo-950/40 text-indigo-300 border-indigo-500/30'
                    }`}>
                      {isOptionSeat ? 'OPTION SEAT (0.60Δ)' : isChopSeat ? 'CHOP SEAT' : 'TREND RUNNER'}
                    </span>
                  </div>

                  {/* PnL & ROE Display */}
                  <div className="flex items-baseline justify-between p-2 rounded-lg bg-black/50 border border-white/5">
                    <div>
                      <span className="text-[10px] uppercase font-bold text-slate-400 block">Floating PnL</span>
                      <span className={`text-lg font-black font-mono ${
                        isProfit ? 'text-[#00FFA3]' : 'text-rose-400'
                      }`}>
                        {isProfit ? '+' : ''}{formatRupee(pnlInr)}
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] uppercase font-bold text-slate-400 block">Net ROE</span>
                      <span className={`text-base font-black font-mono ${
                        (pos.currentNetRoePct || 0) >= 0 ? 'text-[#00FFA3]' : 'text-rose-400'
                      }`}>
                        {(pos.currentNetRoePct || 0) >= 0 ? '+' : ''}{Number(pos.currentNetRoePct || 0).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {/* Execution Levels */}
                  <div className="grid grid-cols-4 gap-1 text-[10px] font-mono">
                    <div className="p-1 rounded bg-white/5">
                      <span className="text-slate-400 block">Entry</span>
                      <span className="font-bold text-white">{formatRupee(entry)}</span>
                    </div>
                    <div className="p-1 rounded bg-cyan-950/40 border border-cyan-500/20">
                      <span className="text-cyan-400 block">Mark</span>
                      <span className="font-bold text-cyan-200">{formatRupee(current)}</span>
                    </div>
                    <div className="p-1 rounded bg-rose-950/40 border border-rose-500/20">
                      <span className="text-rose-400 block">SL (Tight)</span>
                      <span className="font-bold text-rose-300">{formatRupee(Number(pos.slPrice || 0))}</span>
                    </div>
                    <div className="p-1 rounded bg-emerald-950/40 border border-emerald-500/20">
                      <span className="text-emerald-400 block">Pre-Rev TP</span>
                      <span className="font-bold text-emerald-300">{formatRupee(Number(pos.tpPrice || 0))}</span>
                    </div>
                  </div>

                  {/* Bracket Ladder Progress Bar */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-[9px] font-mono text-slate-400">
                      <span>Target Progress</span>
                      <span className={`font-bold ${progress > 0 ? 'text-[#00FFA3]' : 'text-slate-500'}`}>
                        {progress.toFixed(0)}% to TP Wall
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-[#00FFA3] rounded-full"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>

                  {/* 2-Stage Ladder Status */}
                  <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-white/5">
                    <span className="text-[10px] font-mono font-bold text-cyan-300">
                      {pos.stage === 0 || !pos.stage
                        ? 'Stage 0: Untouched (<35% TP)'
                        : pos.stage === 1
                        ? 'Stage 1: Breakeven Locked (≥35%)'
                        : 'Stage 2: 55% Profit Locked (≥70%)'}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">
                      Held {pos.barsHeld ?? 0} bars
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* SECTION 6: TWO-COLUMN BOTTOM ANALYTICS (SCORECARD + CLOSED TRADES LEDGER) */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        
        {/* Left Column: Symbol Scorecard Table (6 cols) */}
        <div className="lg:col-span-6 rounded-2xl bg-[#090F0C]/90 border border-white/10 p-4 space-y-3 shadow-xl">
          <div className="flex items-center justify-between pb-2 border-b border-white/5">
            <span className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-1.5">
              <BarChart2 className="w-4 h-4 text-[#00FFA3]" />
              14 NSE Symbols Scorecard
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              Live IST Mark Prices
            </span>
          </div>

          <div className="overflow-x-auto max-h-[440px] overflow-y-auto scrollbar-thin">
            <table className="w-full text-left text-xs font-mono">
              <thead className="text-[10px] uppercase text-slate-400 border-b border-white/5 sticky top-0 bg-[#090F0C] z-10">
                <tr>
                  <th className="pb-2">Symbol</th>
                  <th className="pb-2 text-right">Price (₹)</th>
                  <th className="pb-2 text-center">Active Status</th>
                  <th className="pb-2 text-center">Trades (W/L)</th>
                  <th className="pb-2 text-center">WR%</th>
                  <th className="pb-2 text-right">Net PnL (₹)</th>
                  <th className="pb-2 text-right">TP / Lock / SL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {coinStats.map((coin: any) => {
                  const sym = String(coin.symbol || '');
                  const activePos = activePositions.find(p => p?.symbol === sym);
                  const rawPrice = Number(livePrices[sym] || coin.currentPrice || (activePos ? activePos.currentPrice : 0));
                  const formattedPrice = rawPrice > 0
                    ? `₹${rawPrice >= 1000 ? rawPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : rawPrice.toFixed(2)}`
                    : '—';
                  const hasActive = Boolean(activePos);
                  const floatingPnl = Number(activePos?.floatingPnlInr ?? (activePos?.floatingPnlUsd ? activePos.floatingPnlUsd * 88.75 : 0));
                  const floatingRoe = Number(activePos?.currentNetRoePct || 0);
                  const isFloatingProfit = floatingPnl >= 0;

                  const cWinRate = Number(coin.winRatePct || 0);
                  const cNetPnl = Number(coin.netPnlInr ?? (coin.netPnlUsd ? coin.netPnlUsd * 88.75 : 0));
                  const cTrades = Number(coin.totalTrades || 0);
                  const cWins = Number(coin.wins || 0);
                  const cLosses = Number(coin.losses || 0);

                  return (
                    <tr key={coin.symbol} className={`transition-colors ${hasActive ? 'bg-emerald-500/10 border-l-2 border-[#00FFA3]' : 'hover:bg-white/5'}`}>
                      <td className="py-2.5 font-bold text-white flex items-center gap-1.5 whitespace-nowrap">
                        <span className="text-xs">{sym}</span>
                        {hasActive && (
                          <span className="px-1.5 py-0.2 rounded text-[8px] font-black bg-emerald-500/25 text-[#00FFA3] border border-emerald-500/40 animate-pulse">
                            ACTIVE
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 text-right font-mono font-bold text-white text-xs whitespace-nowrap">
                        {formattedPrice}
                      </td>
                      <td className="py-2.5 text-center whitespace-nowrap">
                        {hasActive ? (
                          <div className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-black/50 border border-emerald-500/30">
                            <span className={`px-1 rounded text-[8px] font-black uppercase ${
                              activePos.side === 'BUY' ? 'bg-emerald-500/20 text-[#00FFA3]' : 'bg-rose-500/20 text-rose-400'
                            }`}>
                              {activePos.side}
                            </span>
                            <span className={`text-[10px] font-mono font-black ${
                              isFloatingProfit ? 'text-[#00FFA3]' : 'text-rose-400'
                            }`}>
                              {isFloatingProfit ? '+' : ''}{formatRupee(floatingPnl, 0)} ({isFloatingProfit ? '+' : ''}{floatingRoe.toFixed(1)}%)
                            </span>
                          </div>
                        ) : (
                          <span className="text-[10px] text-slate-500 font-mono">5m/15m Armed</span>
                        )}
                      </td>
                      <td className="py-2.5 text-center text-slate-300 font-mono text-[11px] whitespace-nowrap">
                        {cTrades} {cTrades > 0 && <span className="text-slate-400 text-[10px]">({cWins}W/{cLosses}L)</span>}
                      </td>
                      <td className="py-2.5 text-center font-mono whitespace-nowrap">
                        <span className={cWinRate >= 70 ? 'text-[#00FFA3] font-bold' : cWinRate >= 50 ? 'text-amber-300' : 'text-slate-400'}>
                          {cTrades > 0 ? `${cWinRate.toFixed(0)}%` : '—'}
                        </span>
                      </td>
                      <td className={`py-2.5 text-right font-bold font-mono whitespace-nowrap ${
                        cNetPnl >= 0 ? 'text-[#00FFA3]' : 'text-rose-400'
                      }`}>
                        {cNetPnl >= 0 ? '+' : ''}{formatRupee(cNetPnl, 0)}
                      </td>
                      <td className="py-2.5 text-right text-[10px] text-slate-400 font-mono whitespace-nowrap">
                        <span className="text-emerald-400">{coin.tpHits ?? 0}</span> /{' '}
                        <span className="text-cyan-400">{coin.profitLockHits ?? 0}</span> /{' '}
                        <span className="text-rose-400">{coin.slHits ?? 0}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Live Scrolling Closed Trades Audit Ledger (6 cols) */}
        <div className="lg:col-span-6 rounded-2xl bg-[#090F0C]/90 border border-white/10 p-4 space-y-3 shadow-xl">
          <div className="flex items-center justify-between pb-2 border-b border-white/5">
            <span className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-[#00FFA3]" />
              Closed Trades Audit Ledger ({closedLedger.length} executed)
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              Latest Executions
            </span>
          </div>

          <div className="overflow-x-auto max-h-[420px] overflow-y-auto scrollbar-thin">
            {closedLedger.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 font-mono">
                No closed trades yet in current replay simulation.
              </div>
            ) : (
              <table className="w-full text-left text-xs font-mono">
                <thead className="text-[10px] uppercase text-slate-400 border-b border-white/5 sticky top-0 bg-[#090F0C]">
                  <tr>
                    <th className="pb-2">Time (IST)</th>
                    <th className="pb-2">Symbol</th>
                    <th className="pb-2">Side</th>
                    <th className="pb-2 text-right">Entry → Exit (₹)</th>
                    <th className="pb-2 text-right">Net PnL (₹)</th>
                    <th className="pb-2 text-right">Outcome</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {closedLedger.map((trade) => {
                    const tNetPnl = Number(trade.netPnlInr ?? (trade.netPnlUsd ? trade.netPnlUsd * 88.75 : 0));
                    const isWin = tNetPnl > 0;
                    const entry = Number(trade.entryPrice || 0);
                    const exit = Number(trade.exitPrice || 0);

                    const isOpt = trade.isOption || trade.seatBucket === 'NIFTY_BANKNIFTY_OPTION_SEAT';

                    const exitLabel = (() => {
                      if (trade.exitReason === 'TARGET_TP_HIT') return '🎯 REVERSAL TP';
                      if (trade.exitReason === 'PROFIT_LOCKED_EXIT' || trade.exitReason === 'PROFIT_LOCK_HIT') return '🔒 55% PROFIT LOCK';
                      if (trade.exitReason === 'BREAKEVEN_SCRATCH_EXIT') return '⚖️ BREAKEVEN';
                      if (trade.exitReason === 'INTRADAY_AUTO_SQUARE_OFF') return '⏰ 03:18 PM CLOSE';
                      return '🛡️ STOP LOSS';
                    })();

                    const exitBadgeClass = (() => {
                      if (trade.exitReason === 'TARGET_TP_HIT') return 'bg-emerald-500/20 text-[#00FFA3] border border-emerald-500/30';
                      if (trade.exitReason === 'PROFIT_LOCKED_EXIT' || trade.exitReason === 'PROFIT_LOCK_HIT') return 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30';
                      if (trade.exitReason === 'BREAKEVEN_SCRATCH_EXIT') return 'bg-amber-500/20 text-amber-300 border border-amber-500/30';
                      if (trade.exitReason === 'INTRADAY_AUTO_SQUARE_OFF') return 'bg-purple-500/20 text-purple-300 border border-purple-500/30';
                      return 'bg-rose-500/20 text-rose-400 border border-rose-500/30';
                    })();

                    return (
                      <tr key={trade.id} className="hover:bg-white/5 transition-colors">
                        <td className="py-2 text-[10px] text-slate-400 whitespace-nowrap">
                          {trade.exitDateFormatted || '—'}
                        </td>
                        <td className="py-2 font-bold text-white">
                          <div className="flex items-center gap-1">
                            <span>{trade.symbol}</span>
                            {isOpt && (
                              <span className="text-[9px] text-amber-300 font-mono">
                                {trade.optionType || 'OPT'}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                            trade.side === 'BUY' ? 'bg-emerald-500/20 text-[#00FFA3]' : 'bg-rose-500/20 text-rose-400'
                          }`}>
                            {trade.side}
                          </span>
                        </td>
                        <td className="py-2 text-right text-slate-300">
                          {formatRupee(entry, 1)} → {formatRupee(exit, 1)}
                        </td>
                        <td className={`py-2 text-right font-bold ${
                          isWin ? 'text-[#00FFA3]' : 'text-rose-400'
                        }`}>
                          {isWin ? '+' : ''}{formatRupee(tNetPnl, 0)}
                          <span className="text-[9px] block text-slate-400 font-normal">
                            {trade.netRoePct >= 0 ? '+' : ''}{trade.netRoePct.toFixed(1)}% ROE
                          </span>
                        </td>
                        <td className="py-2 text-right">
                          <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase inline-block ${exitBadgeClass}`}>
                            {exitLabel}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

    </div>
  );
};
