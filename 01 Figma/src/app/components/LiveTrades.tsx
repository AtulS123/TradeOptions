import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { TrendingUp, TrendingDown, X } from "lucide-react";
import { useState, useEffect } from "react";

interface LiveTrade {
  id: string;
  symbol: string;
  strike: number;
  type: "CE" | "PE";
  action: "BUY" | "SELL";
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  stopLoss: number;
  target: number;
  timestamp: string;
  iv: number;
  delta: number;
  theta: number;
}

export function LiveTrades() {
  const [trades, setTrades] = useState<LiveTrade[]>([
    {
      id: "1",
      symbol: "NIFTY",
      strike: 21500,
      type: "CE",
      action: "BUY",
      quantity: 50,
      entryPrice: 145.50,
      currentPrice: 152.30,
      stopLoss: 130.00,
      target: 170.00,
      timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
      iv: 18.5,
      delta: 0.45,
      theta: -12.3,
    },
    {
      id: "2",
      symbol: "NIFTY",
      strike: 21400,
      type: "PE",
      action: "SELL",
      quantity: 25,
      entryPrice: 89.20,
      currentPrice: 84.10,
      stopLoss: 100.00,
      target: 70.00,
      timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      iv: 16.8,
      delta: -0.38,
      theta: -8.7,
    },
  ]);

  // Simulate live price updates
  useEffect(() => {
    const interval = setInterval(() => {
      setTrades((prevTrades) =>
        prevTrades.map((trade) => ({
          ...trade,
          currentPrice: trade.currentPrice + (Math.random() - 0.5) * 2,
        }))
      );
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const calculatePnL = (trade: LiveTrade) => {
    const multiplier = trade.action === "BUY" ? 1 : -1;
    return (
      multiplier *
      (trade.currentPrice - trade.entryPrice) *
      trade.quantity
    );
  };

  const calculatePnLPercent = (trade: LiveTrade) => {
    const multiplier = trade.action === "BUY" ? 1 : -1;
    return (
      (multiplier * (trade.currentPrice - trade.entryPrice) * 100) /
      trade.entryPrice
    );
  };

  const closeTrade = (id: string) => {
    setTrades(trades.filter((t) => t.id !== id));
  };

  const getTotalPnL = () => {
    return trades.reduce((acc, trade) => acc + calculatePnL(trade), 0);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2>Live Trades</h2>
          <p className="text-muted-foreground">
            Active positions: {trades.length}
          </p>
        </div>
        <Card className="p-4">
          <div className="text-sm text-muted-foreground">Total P&L</div>
          <div
            className={`${
              getTotalPnL() >= 0 ? "text-green-600" : "text-red-600"
            }`}
          >
            ₹{getTotalPnL().toFixed(2)}
          </div>
        </Card>
      </div>

      <div className="space-y-3">
        {trades.map((trade) => {
          const pnl = calculatePnL(trade);
          const pnlPercent = calculatePnLPercent(trade);
          const isProfit = pnl >= 0;

          return (
            <Card key={trade.id} className="p-4">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span>
                        {trade.symbol} {trade.strike} {trade.type}
                      </span>
                      <Badge
                        variant={
                          trade.action === "BUY" ? "default" : "secondary"
                        }
                      >
                        {trade.action}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Qty: {trade.quantity} | Entry: ₹{trade.entryPrice.toFixed(2)}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => closeTrade(trade.id)}
                >
                  <X className="size-4" />
                </Button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
                <div>
                  <div className="text-sm text-muted-foreground">LTP</div>
                  <div>₹{trade.currentPrice.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">P&L</div>
                  <div
                    className={`flex items-center gap-1 ${
                      isProfit ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {isProfit ? (
                      <TrendingUp className="size-4" />
                    ) : (
                      <TrendingDown className="size-4" />
                    )}
                    ₹{pnl.toFixed(2)} ({pnlPercent.toFixed(2)}%)
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">SL/Target</div>
                  <div className="text-sm">
                    ₹{trade.stopLoss} / ₹{trade.target}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Greeks</div>
                  <div className="text-sm">
                    Δ {trade.delta.toFixed(2)} | θ {trade.theta.toFixed(1)}
                  </div>
                </div>
              </div>

              <div className="flex gap-2 text-xs text-muted-foreground">
                <span>IV: {trade.iv}%</span>
                <span>•</span>
                <span>
                  {new Date(trade.timestamp).toLocaleTimeString()}
                </span>
              </div>
            </Card>
          );
        })}

        {trades.length === 0 && (
          <Card className="p-8 text-center text-muted-foreground">
            No active live trades
          </Card>
        )}
      </div>
    </div>
  );
}
