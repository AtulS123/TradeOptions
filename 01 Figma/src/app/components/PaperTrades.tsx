import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { TrendingUp, TrendingDown, PlayCircle, StopCircle } from "lucide-react";
import { useState, useEffect } from "react";

interface PaperTrade {
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
  status: "active" | "stopped";
  strategy: string;
}

export function PaperTrades() {
  const [trades, setTrades] = useState<PaperTrade[]>([
    {
      id: "1",
      symbol: "NIFTY",
      strike: 21600,
      type: "CE",
      action: "BUY",
      quantity: 100,
      entryPrice: 125.80,
      currentPrice: 128.40,
      stopLoss: 115.00,
      target: 150.00,
      timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      status: "active",
      strategy: "Momentum Breakout",
    },
    {
      id: "2",
      symbol: "NIFTY",
      strike: 21300,
      type: "PE",
      action: "BUY",
      quantity: 75,
      entryPrice: 95.50,
      currentPrice: 92.30,
      stopLoss: 85.00,
      target: 110.00,
      timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
      status: "active",
      strategy: "Mean Reversion",
    },
    {
      id: "3",
      symbol: "NIFTY",
      strike: 21500,
      type: "CE",
      action: "SELL",
      quantity: 50,
      entryPrice: 140.00,
      currentPrice: 138.20,
      stopLoss: 155.00,
      target: 120.00,
      timestamp: new Date(Date.now() - 1000 * 60 * 20).toISOString(),
      status: "stopped",
      strategy: "IV Crush",
    },
  ]);

  const [virtualBalance, setVirtualBalance] = useState(100000);

  useEffect(() => {
    const interval = setInterval(() => {
      setTrades((prevTrades) =>
        prevTrades.map((trade) =>
          trade.status === "active"
            ? {
                ...trade,
                currentPrice: trade.currentPrice + (Math.random() - 0.5) * 1.5,
              }
            : trade
        )
      );
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const calculatePnL = (trade: PaperTrade) => {
    const multiplier = trade.action === "BUY" ? 1 : -1;
    return (
      multiplier *
      (trade.currentPrice - trade.entryPrice) *
      trade.quantity
    );
  };

  const calculatePnLPercent = (trade: PaperTrade) => {
    const multiplier = trade.action === "BUY" ? 1 : -1;
    return (
      (multiplier * (trade.currentPrice - trade.entryPrice) * 100) /
      trade.entryPrice
    );
  };

  const toggleTradeStatus = (id: string) => {
    setTrades(
      trades.map((t) =>
        t.id === id
          ? {
              ...t,
              status: t.status === "active" ? "stopped" : "active",
            }
          : t
      )
    );
  };

  const getTotalPnL = () => {
    return trades.reduce((acc, trade) => acc + calculatePnL(trade), 0);
  };

  const getActiveTrades = () => {
    return trades.filter((t) => t.status === "active").length;
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-sm text-muted-foreground">Virtual Balance</div>
          <div>₹{virtualBalance.toLocaleString()}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-muted-foreground">
            Active Simulations
          </div>
          <div>{getActiveTrades()}</div>
        </Card>
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
            <Card
              key={trade.id}
              className={`p-4 ${
                trade.status === "stopped" ? "opacity-60" : ""
              }`}
            >
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
                      <Badge variant="outline">{trade.strategy}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Qty: {trade.quantity} | Entry: ₹
                      {trade.entryPrice.toFixed(2)}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleTradeStatus(trade.id)}
                >
                  {trade.status === "active" ? (
                    <StopCircle className="size-4" />
                  ) : (
                    <PlayCircle className="size-4" />
                  )}
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
                  <div className="text-sm text-muted-foreground">Status</div>
                  <Badge
                    variant={trade.status === "active" ? "default" : "outline"}
                  >
                    {trade.status}
                  </Badge>
                </div>
              </div>

              <div className="text-xs text-muted-foreground">
                {new Date(trade.timestamp).toLocaleString()}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
