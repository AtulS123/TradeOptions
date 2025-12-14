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
  const [timeframe, setTimeframe] = useState<"1D" | "1W" | "1M" | "3M" | "6M">("1M");
  const [visibleRange, setVisibleRange] = useState({ start: 0, end: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartX, setDragStartX] = useState(0);
  const [dragStartRange, setDragStartRange] = useState({ start: 0, end: 100 });

  const [layers, setLayers] = useState({
    candlestick: true,
    sma20: true,
    sma50: true,
    rsi: true,
    buySignals: true,
    sellSignals: true,
    volume: true,
  });

  // Generate mock backtest data with candlesticks
  const generateBacktestData = (period: string): BacktestData[] => {
    const data: BacktestData[] = [];

    const periods: Record<string, { count: number; interval: number }> = {
      "1D": { count: 78, interval: 5 * 60 * 1000 },
      "1W": { count: 140, interval: 30 * 60 * 1000 },
      "1M": { count: 120, interval: 4 * 60 * 60 * 1000 },
      "3M": { count: 90, interval: 24 * 60 * 60 * 1000 },
      "6M": { count: 180, interval: 24 * 60 * 60 * 1000 },
    };

    const { count, interval } = periods[period];

    let basePrice = 21500;
    let sma20 = 21500;
    let sma50 = 21500;

    for (let i = 0; i < count; i++) {
      const open = basePrice + (Math.random() - 0.5) * 50;
      const close = open + (Math.random() - 0.5) * 100;
      const high = Math.max(open, close) + Math.random() * 40;
      const low = Math.min(open, close) - Math.random() * 40;

      basePrice = close;
      sma20 = sma20 * 0.95 + close * 0.05;
      sma50 = sma50 * 0.98 + close * 0.02;
      const rsi = 30 + Math.random() * 40;

      const timestamp = Date.now() - (count - i) * interval;
      let timeFormat: Intl.DateTimeFormatOptions;

      if (period === "1D") {
        timeFormat = { hour: "2-digit", minute: "2-digit" };
      } else if (period === "1W") {
        timeFormat = { month: "short", day: "numeric", hour: "2-digit" };
      } else {
        timeFormat = { month: "short", day: "numeric" };
      }

      const entry: BacktestData = {
        timestamp: new Date(timestamp).toLocaleString([], timeFormat),
        open: Math.round(open),
        high: Math.round(high),
        low: Math.round(low),
        close: Math.round(close),
        volume: Math.floor(Math.random() * 1000000) + 500000,
        sma20: Math.round(sma20),
        sma50: Math.round(sma50),
        rsi: Math.round(rsi),
      };

      // Generate buy/sell signals
      if (sma20 > sma50 && rsi < 35 && Math.random() > 0.92) {
        entry.buySignal = close;
      }
      if (sma20 < sma50 && rsi > 65 && Math.random() > 0.92) {
        entry.sellSignal = close;
      }

      data.push(entry);
    }

    return data;
  };

  const [backtestData, setBacktestData] = useState(() => generateBacktestData("1M"));

  // Update data when timeframe changes
  const handleTimeframeChange = (tf: typeof timeframe) => {
    setTimeframe(tf);
    setBacktestData(generateBacktestData(tf));
    setVisibleRange({ start: 0, end: 100 });
  };

  // Zoom functionality
  const zoomedData = useMemo(() => {
    const dataLength = backtestData.length;
    const visibleCount = Math.max(20, Math.floor(dataLength / 5));
    const startIndex = Math.max(0, dataLength - visibleCount);
    return backtestData.slice(startIndex);
  }, [backtestData]);

  const handleZoomIn = () => {
    const newEnd = Math.min(visibleRange.end + 10, 100);
    setVisibleRange({ start: visibleRange.start, end: newEnd });
  };

  const handleZoomOut = () => {
    const newStart = Math.max(visibleRange.start - 10, 0);
    const newEnd = Math.min(visibleRange.end + 10, 100);
    setVisibleRange({ start: newStart, end: newEnd });
  };

  const handleResetZoom = () => {
    setVisibleRange({ start: 0, end: 100 });
  };

  const toggleLayer = (layer: keyof typeof layers) => {
    setLayers({ ...layers, [layer]: !layers[layer] });
  };

  // Calculate backtest metrics
  const calculateMetrics = () => {
    let wins = 0;
    let losses = 0;
    let totalProfit = 0;
    let totalLoss = 0;
    let inPosition = false;
    let entryPrice = 0;

    backtestData.forEach((d) => {
      if (d.buySignal && !inPosition) {
        inPosition = true;
        entryPrice = d.buySignal;
      } else if (d.sellSignal && inPosition) {
        const pnl = d.sellSignal - entryPrice;
        if (pnl > 0) {
          wins++;
          totalProfit += pnl;
        } else {
          losses++;
          totalLoss += Math.abs(pnl);
        }
        inPosition = false;
      }
    });

    const totalTrades = wins + losses;
    const winRate = totalTrades > 0 ? (wins / totalTrades) * 100 : 0;
    const avgWin = wins > 0 ? totalProfit / wins : 0;
    const avgLoss = losses > 0 ? totalLoss / losses : 0;
    const profitFactor = totalLoss > 0 ? totalProfit / totalLoss : 0;

    return {
      totalTrades,
      wins,
      losses,
      winRate,
      avgWin,
      avgLoss,
      profitFactor,
      netProfit: totalProfit - totalLoss,
    };
  };

  const metrics = calculateMetrics();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2>Backtest Analysis</h2>
          <p className="text-sm text-muted-foreground">
            NIFTY Options Strategy - Historical Performance
          </p>
        </div>
        <Button>Run New Backtest</Button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Activity className="size-4" />
            Total Trades
          </div>
          <div>{metrics.totalTrades}</div>
          <div className="text-xs text-muted-foreground mt-1">
            W: {metrics.wins} / L: {metrics.losses}
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Percent className="size-4" />
            Win Rate
          </div>
          <div
            className={
              metrics.winRate >= 50 ? "text-green-600" : "text-red-600"
            }
          >
            {metrics.winRate.toFixed(1)}%
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Target: 60%
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <DollarSign className="size-4" />
            Net Profit
          </div>
          <div
            className={
              metrics.netProfit >= 0 ? "text-green-600" : "text-red-600"
            }
          >
            ₹{metrics.netProfit.toFixed(2)}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Per trade: ₹
            {(metrics.netProfit / metrics.totalTrades || 0).toFixed(2)}
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <TrendingUp className="size-4" />
            Profit Factor
          </div>
          <div
            className={
              metrics.profitFactor >= 1.5 ? "text-green-600" : "text-red-600"
            }
          >
            {metrics.profitFactor.toFixed(2)}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Avg W/L: {(metrics.avgWin / metrics.avgLoss || 0).toFixed(2)}
          </div>
        </Card>
      </div>

      {/* Layer Controls */}
      <Card className="p-4">
        <h3 className="mb-3">Chart Layers</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="flex items-center space-x-2">
            <Switch
              id="candlestick"
              checked={layers.candlestick}
              onCheckedChange={() => toggleLayer("candlestick")}
            />
            <Label htmlFor="candlestick" className="cursor-pointer">
              Candlestick
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="sma20"
              checked={layers.sma20}
              onCheckedChange={() => toggleLayer("sma20")}
            />
            <Label htmlFor="sma20" className="cursor-pointer">
              SMA 20
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="sma50"
              checked={layers.sma50}
              onCheckedChange={() => toggleLayer("sma50")}
            />
            <Label htmlFor="sma50" className="cursor-pointer">
              SMA 50
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="rsi"
              checked={layers.rsi}
              onCheckedChange={() => toggleLayer("rsi")}
            />
            <Label htmlFor="rsi" className="cursor-pointer">
              RSI
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="buySignals"
              checked={layers.buySignals}
              onCheckedChange={() => toggleLayer("buySignals")}
            />
            <Label htmlFor="buySignals" className="cursor-pointer">
              Buy Signals
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="sellSignals"
              checked={layers.sellSignals}
              onCheckedChange={() => toggleLayer("sellSignals")}
            />
            <Label htmlFor="sellSignals" className="cursor-pointer">
              Sell Signals
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="volume"
              checked={layers.volume}
              onCheckedChange={() => toggleLayer("volume")}
            />
            <Label htmlFor="volume" className="cursor-pointer">
              Volume
            </Label>
          </div>
        </div>
      </Card>

      {/* Main Chart */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3>Price & Indicators</h3>
          <div className="flex items-center gap-2">
            {/* Timeframe Selection */}
            <div className="flex gap-1 border rounded-md p-1">
              {(["1D", "1W", "1M", "3M", "6M"] as const).map((tf) => (
                <Button
                  key={tf}
                  variant={timeframe === tf ? "default" : "ghost"}
                  size="sm"
                  onClick={() => handleTimeframeChange(tf)}
                  className="px-3 py-1"
                >
                  {tf}
                </Button>
              ))}
            </div>

            {/* Zoom Controls */}
            <div className="flex gap-1 border rounded-md p-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleZoomOut}
                disabled={visibleRange.start === 0 && visibleRange.end === 100}
                className="px-2"
              >
                <ZoomOut className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResetZoom}
                className="px-2"
              >
                <Maximize2 className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleZoomIn}
                disabled={visibleRange.end === 100}
                className="px-2"
              >
                <ZoomIn className="size-4" />
              </Button>
            </div>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={500}>
          <ComposedChart data={zoomedData}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis
              dataKey="timestamp"
              tick={{ fontSize: 12 }}
              interval="preserveStartEnd"
            />
            <YAxis yAxisId="price" domain={["auto", "auto"]} />
            {layers.rsi && (
              <YAxis
                yAxisId="rsi"
                orientation="right"
                domain={[0, 100]}
                tick={{ fontSize: 12 }}
              />
            )}
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length > 0) {
                  const data = payload[0].payload;
                  const isGreen = data.close >= data.open;
                  return (
                    <div className="bg-black/90 border border-gray-700 p-3 rounded-lg text-white text-sm">
                      <div className="mb-2">{data.timestamp}</div>
                      <div className="space-y-1">
                        <div>O: <span className="font-mono">{data.open.toFixed(2)}</span></div>
                        <div>H: <span className="font-mono">{data.high.toFixed(2)}</span></div>
                        <div>L: <span className="font-mono">{data.low.toFixed(2)}</span></div>
                        <div>C: <span className={`font-mono ${isGreen ? 'text-green-400' : 'text-red-400'}`}>
                          {data.close.toFixed(2)}
                        </span></div>
                        {layers.rsi && <div className="pt-1 border-t border-gray-700">RSI: {data.rsi}</div>}
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend />

            {/* Candlesticks */}
            {layers.candlestick && (
              <Bar
                yAxisId="price"
                dataKey={(data: BacktestData) => [data.open, data.close]}
                fill="#000"
                name="Price"
                shape={(props: any) => {
                  const { x, y, width, height, payload } = props;
                  const isGreen = payload.close >= payload.open;
                  const candleY = isGreen ? y : y - height;
                  const candleHeight = Math.abs(height) || 1;

                  // Calculate wick positions
                  const priceRange = payload.close - payload.open || 1;
                  const pixelsPerPoint = height / priceRange;
                  const highWickLength =
                    (payload.high - Math.max(payload.open, payload.close)) *
                    Math.abs(pixelsPerPoint);
                  const lowWickLength =
                    (Math.min(payload.open, payload.close) - payload.low) *
                    Math.abs(pixelsPerPoint);

                  return (
                    <g>
                      {/* High wick */}
                      <line
                        x1={x + width / 2}
                        y1={isGreen ? y - highWickLength : candleY - highWickLength}
                        x2={x + width / 2}
                        y2={isGreen ? y : candleY}
                        stroke={isGreen ? "#10b981" : "#ef4444"}
                        strokeWidth={1}
                      />
                      {/* Low wick */}
                      <line
                        x1={x + width / 2}
                        y1={isGreen ? y + height : candleY + candleHeight}
                        x2={x + width / 2}
                        y2={
                          isGreen
                            ? y + height + lowWickLength
                            : candleY + candleHeight + lowWickLength
                        }
                        stroke={isGreen ? "#10b981" : "#ef4444"}
                        strokeWidth={1}
                      />
                      {/* Candle body */}
                      <rect
                        x={x + width * 0.2}
                        y={candleY}
                        width={width * 0.6}
                        height={candleHeight}
                        fill={isGreen ? "#10b981" : "#ef4444"}
                        stroke={isGreen ? "#10b981" : "#ef4444"}
                        strokeWidth={1}
                      />
                    </g>
                  );
                }}
              />
            )}

            {layers.sma20 && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="sma20"
                stroke="#10b981"
                strokeWidth={1.5}
                dot={false}
                strokeDasharray="5 5"
                name="SMA 20"
              />
            )}

            {layers.sma50 && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="sma50"
                stroke="#f59e0b"
                strokeWidth={1.5}
                dot={false}
                strokeDasharray="5 5"
                name="SMA 50"
              />
            )}

            {layers.rsi && (
              <Area
                yAxisId="rsi"
                type="monotone"
                dataKey="rsi"
                fill="#8b5cf6"
                fillOpacity={0.2}
                stroke="#8b5cf6"
                strokeWidth={1.5}
                name="RSI"
              />
            )}

            {layers.buySignals && (
              <Scatter
                yAxisId="price"
                dataKey="buySignal"
                fill="#10b981"
                shape="triangle"
                name="Buy Signal"
              />
            )}

            {layers.sellSignals && (
              <Scatter
                yAxisId="price"
                dataKey="sellSignal"
                fill="#ef4444"
                shape="triangle"
                name="Sell Signal"
              />
            )}

            {layers.rsi && (
              <>
                <ReferenceLine
                  yAxisId="rsi"
                  y={70}
                  stroke="#ef4444"
                  strokeDasharray="3 3"
                  opacity={0.5}
                />
                <ReferenceLine
                  yAxisId="rsi"
                  y={30}
                  stroke="#10b981"
                  strokeDasharray="3 3"
                  opacity={0.5}
                />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      {/* Volume Chart */}
      {layers.volume && (
        <Card className="p-4">
          <h3 className="mb-4">Volume</h3>
          <ResponsiveContainer width="100%" height={150}>
            <ComposedChart data={zoomedData}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="timestamp"
                tick={{ fontSize: 12 }}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "rgba(0, 0, 0, 0.8)",
                  border: "none",
                  borderRadius: "4px",
                  color: "#fff",
                }}
              />
              <Bar
                dataKey="volume"
                fill="#10b981"
                opacity={0.6}
                shape={(props: any) => {
                  const { x, y, width, height, payload } = props;
                  const isGreen = payload.close >= payload.open;
                  return (
                    <rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      fill={isGreen ? "#10b981" : "#ef4444"}
                      opacity={0.6}
                    />
                  );
                }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Strategy Details */}
      <Card className="p-4">
        <h3 className="mb-3">Strategy Parameters</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-muted-foreground">Entry Condition</div>
            <div className="text-sm mt-1">SMA20 &gt; SMA50 & RSI &lt; 35</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Exit Condition</div>
            <div className="text-sm mt-1">SMA20 &lt; SMA50 & RSI &gt; 65</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Position Size</div>
            <div className="text-sm mt-1">50 lots per trade</div>
          </div>
        </div>
      </Card>
    </div>
  );
}