import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  Line,
} from "recharts";
import { useState, useEffect, useMemo } from "react";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  Target,
  AlertCircle,
  ZoomIn,
  ZoomOut,
  Maximize2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";

interface OptionChainRow {
  strike: number;
  callOI: number;
  callVolume: number;
  callLTP: number;
  callIV: number;
  putLTP: number;
  putIV: number;
  putVolume: number;
  putOI: number;
}

interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface PriceData {
  time: string;
  price: number;
  volume: number;
}

export function MarketData() {
  const [livePrice, setLivePrice] = useState(21534.75);
  const [priceChange, setPriceChange] = useState(125.3);
  const [priceChangePercent, setPriceChangePercent] = useState(0.58);
  const [timeframe, setTimeframe] = useState<"1D" | "1W" | "1M" | "3M" | "1Y">("1D");
  const [visibleRange, setVisibleRange] = useState({ start: 0, end: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartX, setDragStartX] = useState(0);
  const [dragStartRange, setDragStartRange] = useState({ start: 0, end: 100 });

  // Generate candlestick data based on timeframe
  const generateCandleData = (period: string): CandleData[] => {
    const data: CandleData[] = [];
    let basePrice = 21400;
    
    const periods: Record<string, { count: number; interval: number }> = {
      "1D": { count: 200, interval: 5 * 60 * 1000 }, // More data for scrolling
      "1W": { count: 300, interval: 30 * 60 * 1000 },
      "1M": { count: 250, interval: 4 * 60 * 60 * 1000 },
      "3M": { count: 300, interval: 24 * 60 * 60 * 1000 },
      "1Y": { count: 365, interval: 24 * 60 * 60 * 1000 },
    };

    const { count, interval } = periods[period];
    
    for (let i = 0; i < count; i++) {
      const open = basePrice + (Math.random() - 0.5) * 50;
      const close = open + (Math.random() - 0.5) * 80;
      const high = Math.max(open, close) + Math.random() * 30;
      const low = Math.min(open, close) - Math.random() * 30;
      
      const timestamp = Date.now() - (count - i) * interval;
      let timeFormat: Intl.DateTimeFormatOptions;
      
      if (period === "1D") {
        timeFormat = { hour: "2-digit", minute: "2-digit" };
      } else if (period === "1W") {
        timeFormat = { month: "short", day: "numeric", hour: "2-digit" };
      } else {
        timeFormat = { month: "short", day: "numeric" };
      }
      
      data.push({
        time: new Date(timestamp).toLocaleString([], timeFormat),
        open: Math.round(open * 100) / 100,
        high: Math.round(high * 100) / 100,
        low: Math.round(low * 100) / 100,
        close: Math.round(close * 100) / 100,
        volume: Math.floor(Math.random() * 1000000) + 500000,
      });
      
      basePrice = close;
    }
    
    return data;
  };

  const [candleData, setCandleData] = useState<CandleData[]>(() => generateCandleData("1D"));

  // Update candle data when timeframe changes
  useEffect(() => {
    const newData = generateCandleData(timeframe);
    setCandleData(newData);
    // Show last 100 candles by default
    setVisibleRange({ start: Math.max(0, newData.length - 100), end: newData.length });
  }, [timeframe]);

  // Zoomed data based on visible range
  const zoomedData = useMemo(() => {
    return candleData.slice(visibleRange.start, visibleRange.end);
  }, [candleData, visibleRange]);

  const handleZoomIn = () => {
    const currentCount = visibleRange.end - visibleRange.start;
    const newCount = Math.max(20, Math.floor(currentCount * 0.7));
    const center = Math.floor((visibleRange.start + visibleRange.end) / 2);
    const newStart = Math.max(0, center - Math.floor(newCount / 2));
    const newEnd = Math.min(candleData.length, newStart + newCount);
    setVisibleRange({ start: newStart, end: newEnd });
  };

  const handleZoomOut = () => {
    const currentCount = visibleRange.end - visibleRange.start;
    const newCount = Math.min(candleData.length, Math.floor(currentCount * 1.4));
    const center = Math.floor((visibleRange.start + visibleRange.end) / 2);
    const newStart = Math.max(0, center - Math.floor(newCount / 2));
    const newEnd = Math.min(candleData.length, newStart + newCount);
    setVisibleRange({ start: newStart, end: newEnd });
  };

  const handleResetZoom = () => {
    setVisibleRange({ start: Math.max(0, candleData.length - 100), end: candleData.length });
  };

  const handlePanLeft = () => {
    const currentCount = visibleRange.end - visibleRange.start;
    const panAmount = Math.floor(currentCount * 0.2);
    const newStart = Math.max(0, visibleRange.start - panAmount);
    const newEnd = newStart + currentCount;
    setVisibleRange({ start: newStart, end: newEnd });
  };

  const handlePanRight = () => {
    const currentCount = visibleRange.end - visibleRange.start;
    const panAmount = Math.floor(currentCount * 0.2);
    const newEnd = Math.min(candleData.length, visibleRange.end + panAmount);
    const newStart = newEnd - currentCount;
    setVisibleRange({ start: newStart, end: newEnd });
  };

  // Mouse drag handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStartX(e.clientX);
    setDragStartRange({ ...visibleRange });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    
    const deltaX = e.clientX - dragStartX;
    const chartWidth = 800; // Approximate chart width
    const currentCount = visibleRange.end - visibleRange.start;
    const panAmount = Math.floor((deltaX / chartWidth) * currentCount);
    
    const newStart = Math.max(0, Math.min(candleData.length - currentCount, dragStartRange.start - panAmount));
    const newEnd = newStart + currentCount;
    
    setVisibleRange({ start: newStart, end: newEnd });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Wheel zoom handler
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (e.deltaY < 0) {
      handleZoomIn();
    } else {
      handleZoomOut();
    }
  };

  // Option chain data
  const optionChain: OptionChainRow[] = [
    {
      strike: 21300,
      callOI: 45000,
      callVolume: 12500,
      callLTP: 285.5,
      callIV: 15.2,
      putLTP: 52.3,
      putIV: 16.8,
      putVolume: 8900,
      putOI: 38000,
    },
    {
      strike: 21400,
      callOI: 52000,
      callVolume: 15200,
      callLTP: 215.8,
      callIV: 14.8,
      putLTP: 78.5,
      putIV: 16.2,
      putVolume: 11200,
      putOI: 45000,
    },
    {
      strike: 21500,
      callOI: 68000,
      callVolume: 22500,
      callLTP: 162.3,
      callIV: 14.5,
      putLTP: 118.7,
      putIV: 15.8,
      putVolume: 19800,
      putOI: 72000,
    },
    {
      strike: 21600,
      callOI: 55000,
      callVolume: 18900,
      callLTP: 125.4,
      callIV: 14.9,
      putLTP: 175.2,
      putIV: 15.5,
      putVolume: 15600,
      putOI: 58000,
    },
    {
      strike: 21700,
      callOI: 42000,
      callVolume: 13800,
      callLTP: 89.6,
      callIV: 15.3,
      putLTP: 245.8,
      putIV: 15.2,
      putVolume: 10500,
      putOI: 39000,
    },
  ];

  // Update live price
  useEffect(() => {
    const interval = setInterval(() => {
      setLivePrice((prev) => {
        const newPrice = prev + (Math.random() - 0.5) * 10;
        const change = newPrice - 21409.45;
        setPriceChange(change);
        setPriceChangePercent((change / 21409.45) * 100);

        // Update latest candle
        setCandleData((prevData) => {
          if (prevData.length === 0) return prevData;
          
          const newData = [...prevData];
          const lastCandle = { ...newData[newData.length - 1] };
          lastCandle.close = Math.round(newPrice * 100) / 100;
          lastCandle.high = Math.max(lastCandle.high, lastCandle.close);
          lastCandle.low = Math.min(lastCandle.low, lastCandle.close);
          newData[newData.length - 1] = lastCandle;
          
          return newData;
        });

        return newPrice;
      });
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  // Calculate metrics
  const calculatePCR = () => {
    const totalPutOI = optionChain.reduce((sum, row) => sum + row.putOI, 0);
    const totalCallOI = optionChain.reduce((sum, row) => sum + row.callOI, 0);
    return totalPutOI / totalCallOI;
  };

  const findMaxPain = () => {
    // Simplified max pain calculation - strike with highest OI
    let maxOI = 0;
    let maxPainStrike = 0;
    optionChain.forEach((row) => {
      const totalOI = row.callOI + row.putOI;
      if (totalOI > maxOI) {
        maxOI = totalOI;
        maxPainStrike = row.strike;
      }
    });
    return maxPainStrike;
  };

  const findBestStrike = () => {
    // Find strike closest to current price with good liquidity
    const currentPrice = livePrice;
    let bestStrike = optionChain[0];
    let minDiff = Math.abs(optionChain[0].strike - currentPrice);

    optionChain.forEach((row) => {
      const diff = Math.abs(row.strike - currentPrice);
      if (diff < minDiff && row.callVolume > 10000) {
        minDiff = diff;
        bestStrike = row;
      }
    });

    return bestStrike.strike;
  };

  const pcr = calculatePCR();
  const maxPain = findMaxPain();
  const bestStrike = findBestStrike();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2>Market Data</h2>
          <p className="text-sm text-muted-foreground">Live market overview</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="size-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm text-muted-foreground">Live</span>
        </div>
      </div>

      {/* Live Price Card */}
      <Card className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-sm text-muted-foreground mb-1">
              NIFTY 50 Index
            </div>
            <div className="flex items-baseline gap-3">
              <span className="text-3xl">
                {livePrice.toFixed(2)}
              </span>
              <div
                className={`flex items-center gap-1 ${
                  priceChange >= 0 ? "text-green-600" : "text-red-600"
                }`}
              >
                {priceChange >= 0 ? (
                  <TrendingUp className="size-5" />
                ) : (
                  <TrendingDown className="size-5" />
                )}
                <span>
                  {priceChange >= 0 ? "+" : ""}
                  {priceChange.toFixed(2)} ({priceChangePercent.toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>
          <Badge variant={priceChange >= 0 ? "default" : "destructive"}>
            {priceChange >= 0 ? "Bullish" : "Bearish"}
          </Badge>
        </div>
      </Card>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <BarChart3 className="size-4" />
            PCR (OI)
          </div>
          <div className="text-xl">{pcr.toFixed(3)}</div>
          <div className="text-xs text-muted-foreground mt-1">
            {pcr > 1.2
              ? "Bullish"
              : pcr < 0.8
              ? "Bearish"
              : "Neutral"}
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Target className="size-4" />
            Max Pain
          </div>
          <div className="text-xl">{maxPain}</div>
          <div className="text-xs text-muted-foreground mt-1">
            Strike level
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <AlertCircle className="size-4" />
            Best Strike
          </div>
          <div className="text-xl">{bestStrike}</div>
          <div className="text-xs text-muted-foreground mt-1">
            High liquidity
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Activity className="size-4" />
            Avg IV
          </div>
          <div className="text-xl">
            {(
              optionChain.reduce(
                (sum, row) => sum + (row.callIV + row.putIV) / 2,
                0
              ) / optionChain.length
            ).toFixed(1)}
            %
          </div>
          <div className="text-xs text-muted-foreground mt-1">Implied Vol</div>
        </Card>
      </div>

      <Tabs defaultValue="chart" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="chart">Live Chart</TabsTrigger>
          <TabsTrigger value="chain">Option Chain</TabsTrigger>
        </TabsList>

        <TabsContent value="chart" className="space-y-4">
          <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3>NIFTY Candlestick Chart</h3>
              <div className="flex items-center gap-2">
                {/* Timeframe Selection */}
                <div className="flex gap-1 border rounded-md p-1">
                  {(["1D", "1W", "1M", "3M", "1Y"] as const).map((tf) => (
                    <Button
                      key={tf}
                      variant={timeframe === tf ? "default" : "ghost"}
                      size="sm"
                      onClick={() => setTimeframe(tf)}
                      className="px-3 py-1"
                    >
                      {tf}
                    </Button>
                  ))}
                </div>
                
                {/* Pan Controls */}
                <div className="flex gap-1 border rounded-md p-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handlePanLeft}
                    disabled={visibleRange.start === 0}
                    className="px-2"
                  >
                    <ChevronLeft className="size-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handlePanRight}
                    disabled={visibleRange.end >= candleData.length}
                    className="px-2"
                  >
                    <ChevronRight className="size-4" />
                  </Button>
                </div>
                
                {/* Zoom Controls */}
                <div className="flex gap-1 border rounded-md p-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleZoomOut}
                    disabled={visibleRange.end - visibleRange.start >= candleData.length}
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
                    disabled={visibleRange.end - visibleRange.start <= 20}
                    className="px-2"
                  >
                    <ZoomIn className="size-4" />
                  </Button>
                </div>
              </div>
            </div>
            
            <div className="mb-2 text-xs text-muted-foreground text-center">
              Drag chart to pan • Scroll to zoom • Showing {zoomedData.length} of {candleData.length} candles
            </div>
            
            <ResponsiveContainer width="100%" height={500}>
              <ComposedChart
                data={zoomedData}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onWheel={handleWheel}
              >
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 12 }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 12 }}
                  tickFormatter={(value) => value.toFixed(0)}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length > 0) {
                      const data = payload[0].payload;
                      const isGreen = data.close >= data.open;
                      return (
                        <div className="bg-black/90 border border-gray-700 p-3 rounded-lg text-white text-sm">
                          <div className="mb-2">{data.time}</div>
                          <div className="space-y-1">
                            <div>O: <span className="font-mono">{data.open.toFixed(2)}</span></div>
                            <div>H: <span className="font-mono">{data.high.toFixed(2)}</span></div>
                            <div>L: <span className="font-mono">{data.low.toFixed(2)}</span></div>
                            <div>C: <span className={`font-mono ${isGreen ? 'text-green-400' : 'text-red-400'}`}>
                              {data.close.toFixed(2)}
                            </span></div>
                            <div className="pt-1 border-t border-gray-700">
                              Vol: <span className="font-mono">{(data.volume / 1000).toFixed(0)}K</span>
                            </div>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                
                {/* Candlestick bodies */}
                <Bar
                  dataKey={(data: CandleData) => [data.open, data.close]}
                  fill="#000"
                  shape={(props: any) => {
                    const { x, y, width, height, payload } = props;
                    const isGreen = payload.close >= payload.open;
                    const candleY = isGreen ? y : y - height;
                    const candleHeight = Math.abs(height) || 1;
                    
                    return (
                      <g>
                        {/* Wick (high-low line) */}
                        <line
                          x1={x + width / 2}
                          y1={y - (payload.high - Math.max(payload.open, payload.close)) * (height / (payload.close - payload.open || 1))}
                          x2={x + width / 2}
                          y2={y + height + (Math.min(payload.open, payload.close) - payload.low) * (height / (payload.close - payload.open || 1))}
                          stroke={isGreen ? "#10b981" : "#ef4444"}
                          strokeWidth={1}
                        />
                        {/* Candle body */}
                        <rect
                          x={x + width * 0.25}
                          y={candleY}
                          width={width * 0.5}
                          height={candleHeight}
                          fill={isGreen ? "#10b981" : "#ef4444"}
                          stroke={isGreen ? "#10b981" : "#ef4444"}
                          strokeWidth={1}
                        />
                      </g>
                    );
                  }}
                />
                
                {/* Moving average line */}
                <Line
                  type="monotone"
                  dataKey={(data: CandleData, index: number) => {
                    if (index < 20) return null;
                    const slice = zoomedData.slice(Math.max(0, index - 19), index + 1);
                    const avg = slice.reduce((sum, d) => sum + d.close, 0) / slice.length;
                    return avg;
                  }}
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  name="MA(20)"
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          </Card>

          <Card className="p-4">
            <h3 className="mb-4">Volume</h3>
            <ResponsiveContainer width="100%" height={150}>
              <ComposedChart data={zoomedData}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis
                  dataKey="time"
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
        </TabsContent>

        <TabsContent value="chain">
          <Card>
            <div className="p-4 border-b">
              <h3>Option Chain - NIFTY</h3>
              <p className="text-sm text-muted-foreground">
                Current expiry: 21 Dec 2025
              </p>
            </div>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-center" colSpan={4}>
                      CALLS
                    </TableHead>
                    <TableHead className="text-center">STRIKE</TableHead>
                    <TableHead className="text-center" colSpan={4}>
                      PUTS
                    </TableHead>
                  </TableRow>
                  <TableRow>
                    <TableHead>OI</TableHead>
                    <TableHead>Volume</TableHead>
                    <TableHead>LTP</TableHead>
                    <TableHead>IV</TableHead>
                    <TableHead className="text-center bg-muted"></TableHead>
                    <TableHead>IV</TableHead>
                    <TableHead>LTP</TableHead>
                    <TableHead>Volume</TableHead>
                    <TableHead>OI</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {optionChain.map((row) => {
                    const isATM =
                      Math.abs(row.strike - livePrice) ===
                      Math.min(
                        ...optionChain.map((r) => Math.abs(r.strike - livePrice))
                      );

                    return (
                      <TableRow
                        key={row.strike}
                        className={isATM ? "bg-muted/50" : ""}
                      >
                        <TableCell>
                          {(row.callOI / 1000).toFixed(1)}K
                        </TableCell>
                        <TableCell>
                          {(row.callVolume / 1000).toFixed(1)}K
                        </TableCell>
                        <TableCell>₹{row.callLTP.toFixed(2)}</TableCell>
                        <TableCell>{row.callIV.toFixed(1)}%</TableCell>
                        <TableCell className="text-center bg-muted">
                          {row.strike}
                          {isATM && (
                            <Badge variant="outline" className="ml-2">
                              ATM
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>{row.putIV.toFixed(1)}%</TableCell>
                        <TableCell>₹{row.putLTP.toFixed(2)}</TableCell>
                        <TableCell>
                          {(row.putVolume / 1000).toFixed(1)}K
                        </TableCell>
                        <TableCell>
                          {(row.putOI / 1000).toFixed(1)}K
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Trading Insights */}
      <Card className="p-4">
        <h3 className="mb-3">Trading Insights</h3>
        <div className="space-y-2">
          <div className="flex items-start gap-2 p-3 bg-muted rounded-lg">
            <AlertCircle className="size-5 text-blue-500 mt-0.5" />
            <div>
              <div className="text-sm">Recommended Strike: {bestStrike}</div>
              <p className="text-xs text-muted-foreground">
                Based on liquidity and proximity to current price
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2 p-3 bg-muted rounded-lg">
            <Activity className="size-5 text-green-500 mt-0.5" />
            <div>
              <div className="text-sm">
                Market Sentiment:{" "}
                {pcr > 1.2 ? "Bullish" : pcr < 0.8 ? "Bearish" : "Neutral"}
              </div>
              <p className="text-xs text-muted-foreground">
                PCR ratio indicates{" "}
                {pcr > 1
                  ? "more put buying (bullish)"
                  : "more call buying (bearish)"}
              </p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}