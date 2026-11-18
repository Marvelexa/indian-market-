import express from 'express';
import http from 'http';
import { Server } from 'socket.io';
import cors from 'cors';
import { TradeStore, TradeRecord } from './tradeStore';

const app = express();
app.use(cors());
app.use(express.json());

const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' } });

// REST API to fetch historical trades on reload
app.get('/api/trades', (req, res) => {
  const trades = TradeStore.loadTrades();
  res.json({ success: true, trades });
});

// Live tick receiver from your trading engine
app.post('/api/webhook/tick', (req, res) => {
  const { symbol, ltp, openPositions, closedTrades } = req.body;
  
  // Broadcast real-time updates to all connected UI clients instantly
  io.emit('market_update', {
    symbol,
    ltp,
    openPositions,
    closedTrades,
    timestamp: Date.now()
  });

  res.json({ success: true });
});

io.on('connection', (socket) => {
  console.log('UI Client connected for real-time P&L');
  // Send existing history immediately on connection
  socket.emit('init_history', TradeStore.loadTrades());
});

server.listen(4000, () => {
  console.log('P&L Real-Time Server running on port 4000');
});
