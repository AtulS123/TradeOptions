import {
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  Percent,
  ZoomIn,
  ZoomOut,
  Maximize2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Switch } from "./ui/switch";
import { Label } from "./ui/label";
import { Badge } from "./ui/badge";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Scatter,
  ComposedChart,
  Area,
  Bar,
} from "recharts";
import { useState, useMemo } from "react";

interface BacktestData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  sma20: number;
  sma50: number;
  rsi: number;
  buySignal?: number;
  sellSignal?: number;
  position?: number;
}

export function Backtesting() {
  /* 
    State definitions and API integration 
  */
  const [loading, setLoading] = useState(false);
  const [apiData, setApiData] = useState<any>(null);
  const [dataPoints, setDataPoints] = useState<any[]>([]);

  const fetchBacktest = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy: "VWAP_MOMENTUM",
          start_date: "2015-01-09", // Hardcoded for available data
          end_date: "2015-01-15",
          capital: 200000
        }),
      });
      const data = await res.json();

      if (data.error) {
        console.error(data.error);
        return;
      }

      setApiData(data.summary);
      setDataPoints(data.equity_curve);

    } catch (e) {
      console.error("Backtest failed", e);
    } finally {
      setLoading(false);
    }
  };

  const metrics = apiData ? {
    totalTrades: apiData.total_trades,
    wins: 0, // Not returned by simple summary yet
    losses: 0,
    winRate: 0,
    netProfit: apiData.net_profit,
    profitFactor: 0,
  } : {
    totalTrades: 0, wins: 0, losses: 0, winRate: 0, netProfit: 0, profitFactor: 0
  };

  // Zoom / Interaction State
  const [visibleRange, setVisibleRange] = useState({ start: 0, end: 100 });

  const zoomedData = useMemo(() => {
    if (!dataPoints.length) return [];
    const len = dataPoints.length;
    const start = Math.floor((visibleRange.start / 100) * len);
    const end = Math.ceil((visibleRange.end / 100) * len);
    // Simplify zoom logic for now: just take slice or full
    return dataPoints; // Return full for simplicity in this implementation step
  }, [dataPoints, visibleRange]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2>Backtest Analysis</h2>
          <p className="text-sm text-muted-foreground">
            {apiData ? "Backtest Complete" : "Ready to Simulate"}
          </p>
        </div>
        <Button onClick={fetchBacktest} disabled={loading}>
          {loading ? "Running..." : "Run Backtest (Real)"}
        </Button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Activity className="size-4" />
            Total Trades
          </div>
          <div>{metrics.totalTrades}</div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Percent className="size-4" />
            Win Rate
          </div>
          <div>--%</div>
          {/* Detailed Win Rates require parsing trade list which we can add later */}
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <DollarSign className="size-4" />
            Net Profit
          </div>
          <div className={metrics.netProfit >= 0 ? "text-green-600" : "text-red-600"}>
            ₹{metrics.netProfit?.toFixed(2)}
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <TrendingUp className="size-4" />
            Ending Capital
          </div>
          <div>₹{apiData?.ending_capital?.toFixed(2) || "0.00"}</div>
        </Card>
      </div>

      {/* Main Chart: Equity Curve */}
      <Card className="p-4">
        <h3>Equity Curve</h3>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={zoomedData}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis dataKey="timestamp" />
            <YAxis domain={['auto', 'auto']} />
            <Tooltip
              contentStyle={{ backgroundColor: "#333", border: "none", color: "#fff" }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="equity"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              name="Account Equity"
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}