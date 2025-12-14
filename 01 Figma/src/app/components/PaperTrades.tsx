import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { TrendingUp, TrendingDown, PlayCircle, StopCircle, XCircle, RefreshCw } from "lucide-react";
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
  pnl: number;
}

export function PaperTrades() {
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [virtualBalance, setVirtualBalance] = useState(100000); // Fixed for now, can be fetched from API later
  const [isOffline, setIsOffline] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const fetchTrades = async () => {
    try {
      const response = await fetch("http://localhost:8000/paper-trades");
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      const data = await response.json();
      setTrades(data);
      setIsOffline(false);
    } catch (error) {
      console.error("Failed to fetch trades:", error);
      setIsOffline(true);
      // Keep old data to prevent flickering
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchTrades();

    // Poll every 1 second
    const interval = setInterval(fetchTrades, 1000);

    return () => clearInterval(interval);
  }, []);

  const handleClosePosition = async (token: string) => {
    try {
      const response = await fetch(`http://localhost:8000/trade/${token}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        // Immediate optimistic UI update (optional, or just wait for next poll)
        fetchTrades();
      } else {
        alert("Failed to close position");
      }
    } catch (e) {
      alert("Error closing position");
    }
  }

  const getTotalPnL = () => {
    return trades.reduce((acc, trade) => acc + (trade.pnl || 0), 0);
  };

  const getActiveTrades = () => {
    return trades.length; // API returns active only
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
            Active Simulator
          </div>
          <div className="flex items-center gap-2">
            {getActiveTrades()}
            {isOffline && <Badge variant="destructive" className="ml-2">Offline</Badge>}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-muted-foreground">Total P&L</div>
          <div
            className={`${getTotalPnL() >= 0 ? "text-green-600" : "text-red-600"
              } font-bold`}
          >
            ₹{getTotalPnL().toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </Card>
      </div>

      <div className="space-y-3">
        {trades.length === 0 && !isOffline && (
          <Card className="p-8 flex flex-col items-center justify-center text-muted-foreground">
            <p>No active live trades.</p>
          </Card>
        )}

        {trades.map((trade) => {
          const isProfit = (trade.pnl || 0) >= 0;
          const pnlPercent = (trade.pnl / (trade.entryPrice * trade.quantity)) * 100;

          return (
            <Card
              key={trade.id}
              className={`p-4 transition-all duration-200 ${isOffline ? "opacity-50" : ""
                }`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">
                        {trade.symbol}
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
                  variant="destructive"
                  size="sm"
                  onClick={() => handleClosePosition(trade.id)}
                  className="hover:bg-red-600"
                >
                  <XCircle className="size-4 mr-1" />
                  Close
                </Button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
                <div>
                  <div className="text-sm text-muted-foreground">LTP</div>
                  <div className="font-mono">₹{trade.currentPrice.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">P&L</div>
                  <div
                    className={`flex items-center gap-1 font-mono font-medium ${isProfit ? "text-green-600" : "text-red-600"
                      }`}
                  >
                    {isProfit ? (
                      <TrendingUp className="size-4" />
                    ) : (
                      <TrendingDown className="size-4" />
                    )}
                    ₹{trade.pnl.toFixed(2)} ({pnlPercent.toFixed(2)}%)
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
                  <Badge variant="default" className="bg-green-500 hover:bg-green-600">
                    Active
                  </Badge>
                </div>
              </div>

              <div className="text-xs text-muted-foreground flex justify-between">
                <span>{new Date(trade.timestamp).toLocaleString()}</span>
                {isOffline && <span className="text-red-400 flex items-center gap-1"><RefreshCw className="w-3 h-3 animate-spin" /> Reconnecting...</span>}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
