"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Slider } from "./ui/slider";
import { Badge } from "./ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Switch } from "./ui/switch";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "./ui/accordion";
import { ScrollArea } from "./ui/scroll-area";
import { Progress } from "./ui/progress";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "./ui/hover-card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import {
  Play,
  Download,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Activity,
  History,
  Settings2,
  Filter,
  Info, // Added Info Icon
  BarChart2,
  ArrowUpRight,
  ArrowDownRight
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { cn } from "./ui/utils";

// --- FORM SCHEMA ---
const formSchema = z.object({
  // Section A: Strategy Logic
  strategyType: z.string(),
  underlying: z.string(),
  strikeSelection: z.string(),
  entryDays: z.array(z.string()).default(["All Days"]),

  // Section B: Capital & Backtest
  startDate: z.string(),
  endDate: z.string(),
  initialCapital: z.coerce.number().min(10000),
  positionSizing: z.string(),
  riskPerTrade: z.number().min(0.5).max(10),

  // Section C: Entry & Exit Rules
  entryTime: z.string(),
  exitTime: z.string(),
  targetProfit: z.coerce.number().optional(),
  stopLoss: z.coerce.number().optional(),
  spotCondition: z.string(),

  // Section D: Greeks & Risk
  targetDelta: z.coerce.number().optional(),
  minTheta: z.coerce.number().optional(),
  maxVega: z.coerce.number().optional(),

  // Section E: Advanced Execution
  slippage: z.coerce.number(),
  commission: z.coerce.number(),
  marketFilter: z.string(),
});

type FormValues = z.infer<typeof formSchema>;

const DEFAULT_VALUES: FormValues = {
  strategyType: "vwap",
  underlying: "NIFTY 50",
  strikeSelection: "atm",
  entryDays: ["All Days"],
  startDate: "2024-01-01",
  endDate: "2024-12-31", // Full Year 2024
  initialCapital: 100000, // Explicitly set to 100k
  positionSizing: "fixed",
  riskPerTrade: 1.0,
  entryTime: "09:20",
  exitTime: "15:15",
  targetProfit: 50,
  stopLoss: 25,
  spotCondition: "any",
  targetDelta: 0.30,
  minTheta: 500,
  maxVega: 1000,
  slippage: 0.5,
  commission: 20,
  marketFilter: "all",
};

// --- MOCK DATA FOR VISUALIZATION (REQUESTED SCENARIO) ---
const MOCK_RESULTS = {
  summary: {
    initial_capital: 100000,
    final_capital: 222945,
    total_return_pct: 138.10,
    total_trades: 103,
    win_rate: 62.1,
    profit_factor: 2.97,
    sharpe_ratio: 1.85,
    calmar_ratio: 0.93,
    max_drawdown_pct: 0.00,
  },
  trade_stats: {
    avg_win: 3251,
    avg_loss: 1794,
    largest_win: 4210,
    largest_loss: 2319,
    avg_days_in_trade: 2.0,
  },
  greeks: {
    avg_delta: 0.257,
    avg_theta: -98.61,
    avg_vega: 35.64,
    avg_iv: 20.37,
  }
};

const MOCK_EQUITY_CURVE = Array.from({ length: 50 }, (_, i) => ({
  trade: i + 1,
  equity: 100000 + (i * 2400) + (Math.random() - 0.4) * 8000, // Roughly leads to ~220k
  drawdown: Math.min(0, (Math.random() - 0.8) * 5) // Fake drawdown data
}));


export function Backtesting() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<typeof MOCK_RESULTS | null>(null);
  const [activeTab, setActiveTab] = useState("simulate");
  const [chartTab, setChartTab] = useState("equity");

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: DEFAULT_VALUES,
  });

  // Force-set values individually to ensure UI updates
  useEffect(() => {
    const defaults = {
      strategyType: "vwap",
      underlying: "NIFTY 50",
      strikeSelection: "atm",
      entryDays: ["All Days"],
      startDate: "2024-01-01",
      endDate: "2024-12-31",
      initialCapital: 100000,
      positionSizing: "fixed",
      riskPerTrade: 1.0,
      entryTime: "09:20",
      exitTime: "15:15",
      targetProfit: 50,
      stopLoss: 25,
      spotCondition: "any",
      targetDelta: 0.30,
      minTheta: 500,
      maxVega: 1000,
      slippage: 0.5,
      commission: 20,
      marketFilter: "all"
    };

    Object.entries(defaults).forEach(([key, value]) => {
      // @ts-ignore
      form.setValue(key, value);
    });
  }, [form]);

  // DEBUG: Watch state to see if it's populated internally
  const values = form.watch();

  useEffect(() => {
    // Force reset form to defaults on mount to ensure Inputs display values
    const timer = setTimeout(() => {
      form.reset(DEFAULT_VALUES);
    }, 100);
    return () => clearTimeout(timer);
  }, []); // Run once on mount

  const onSubmit = async (data: FormValues) => {
    console.log("Form Submitted:", data);
    setIsLoading(true);
    setResult(null);

    // Construct Payload for Backend (Pydantic Model)
    const payload = {
      strategy_config: {
        strategy_type: data.strategyType,
        underlying: data.underlying,
        strike_selection: data.strikeSelection,
        entry_days: data.entryDays,
        entry_time: data.entryTime,
        exit_time: data.exitTime,
        target_profit_pct: Number(data.targetProfit) || 0,
        stopLoss_pct: Number(data.stopLoss) || 0, // Typo in frontend state vs backend? Let's assume stopLoss map to stop_loss_pct
        stop_loss_pct: Number(data.stopLoss) || 0,
        spot_condition: data.spotCondition
      },
      risk_config: {
        capital: Number(data.initialCapital),
        position_sizing: data.positionSizing,
        risk_per_trade_pct: Number(data.riskPerTrade),
        max_slippage_pct: Number(data.slippage),
        commission_per_lot: Number(data.commission)
      },
      start_date: data.startDate,
      end_date: data.endDate,
      timeframe: "1m",
      data_source: "CSV" // Enforce CSV for now as per smoke test plan
    };

    try {
      const response = await fetch('/api/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const json = await response.json();

      if (json.status === "success" || json.data) {
        // NORMALIZE RESULT (Handle CamelCase / Legacy Backend Responses)
        const raw = json.data || json;
        const normalized: any = {
          summary: raw.summary || {},
          trade_stats: raw.trade_stats || {},
          greeks: raw.greeks || { avg_delta: 0, avg_theta: 0, avg_vega: 0, avg_iv: 0 },
          equity_curve: raw.equity_curve || raw.equityCurve || [],
          trades: raw.trades || []
        };

        // 1. Fill Summary if missing
        if (!raw.summary) {
          // Attempt to derive from flat keys (netProfit, winRate)
          const initialCap = values.initialCapital || 100000;
          const netProfit = raw.netProfit || 0;
          const finalCap = initialCap + netProfit;

          normalized.summary = {
            initial_capital: initialCap,
            final_capital: finalCap,
            total_return_pct: (netProfit / initialCap) * 100,
            win_rate: raw.winRate || 0,
            total_trades: raw.trades ? raw.trades.length : 0,
            profit_factor: 0, // Hard to calc without trade list
            sharpe_ratio: 0,
            calmar_ratio: 0,
            max_drawdown_pct: 0
          };
        }

        // 2. Fill Trade Stats if missing
        if (!raw.trade_stats) {
          // Basic placeholders
          normalized.trade_stats = {
            avg_win: 0, avg_loss: 0, largest_win: 0, largest_loss: 0, avg_days_in_trade: 0
          };
        }

        setResult(normalized);
      } else {
        console.error("Backtest Failed:", json);
        alert(`Backtest Failed: ${json.message || JSON.stringify(json)}`);
      }
    } catch (err) {
      console.error("API Error:", err);
      alert("Failed to connect to backend.");
    } finally {
      setIsLoading(false);
    }
  };

  // Format currency safely
  const formatCurrency = (val: number | undefined | null) => {
    if (val === undefined || val === null || isNaN(val)) return "₹0";
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
  };

  const safeFixed = (val: number | undefined, digits = 2) => {
    return (val || 0).toFixed(digits);
  }

  // Transform backend equity curve for Recharts with DOWNSAMPLING
  const rawData = result?.equity_curve || [];
  const MAX_POINTS = 500;
  const step = Math.ceil(rawData.length / MAX_POINTS);

  const chartData = rawData
    .filter((_: any, i: number) => i % step === 0)
    .map((pt: any, i: number) => ({
      ...pt,
      trade: i,
      equity: Number(pt.equity),
      drawdown: Number(pt.drawdown || 0)
    }));

  return (
    <div className="grid grid-cols-12 gap-6 h-[calc(100vh-100px)] p-2">
      {/* --- LEFT PANEL: CONFIGURATION DECK --- */}
      <div className="col-span-12 md:col-span-3 h-full min-h-0 flex flex-col bg-card border rounded-lg overflow-hidden shadow-sm">
        <div className="p-3 border-b bg-muted/40">
          <h2 className="font-semibold text-sm flex items-center gap-2">
            <Settings2 className="h-4 w-4" />
            Strategy Configuration
          </h2>
        </div>

        <ScrollArea className="flex-1 h-px w-full">
          <form id="backtest-form" onSubmit={form.handleSubmit(onSubmit)} className="p-4 space-y-6">
            <Accordion type="multiple" defaultValue={["section-a", "section-b"]} className="w-full">

              {/* SECTION A: STRATEGY LOGIC */}
              <AccordionItem value="section-a">
                <AccordionTrigger className="text-sm font-semibold hover:no-underline">
                  A. Strategy Logic
                </AccordionTrigger>
                <AccordionContent className="space-y-4 pt-2">
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">Strategy Type <span className="text-red-500">*</span></label>
                    <Select
                      onValueChange={(val) => form.setValue("strategyType", val)}
                      defaultValue={form.getValues("strategyType")}
                    >
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue placeholder="Select Strategy" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="vwap">VWAP Momentum (Live)</SelectItem>
                        <SelectItem value="short_straddle" disabled>Short Straddle (Coming Soon)</SelectItem>
                        <SelectItem value="iron_condor" disabled>Iron Condor (Coming Soon)</SelectItem>
                        <SelectItem value="bull_call" disabled>Bull Call Spread (Coming Soon)</SelectItem>
                        <SelectItem value="long_straddle" disabled>Long Straddle (Coming Soon)</SelectItem>
                        <SelectItem value="covered_call" disabled>Covered Call (Coming Soon)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">Underlying <span className="text-red-500">*</span></label>
                    <Select
                      onValueChange={(val) => form.setValue("underlying", val)}
                      defaultValue={form.getValues("underlying")}
                    >
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="NIFTY 50">NIFTY 50</SelectItem>
                        <SelectItem value="BANK NIFTY">BANK NIFTY</SelectItem>
                        <SelectItem value="FIN NIFTY">FIN NIFTY</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">Strike Selection <span className="text-red-500">*</span></label>
                    <Select
                      onValueChange={(val) => form.setValue("strikeSelection", val)}
                      defaultValue={form.getValues("strikeSelection")}
                    >
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="atm">ATM (At The Money)</SelectItem>
                        <SelectItem value="itm">ITM (In The Money)</SelectItem>
                        <SelectItem value="otm">OTM (Out The Money)</SelectItem>
                        <SelectItem value="delta">Delta Based</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* SECTION B: CAPITAL & BACKTEST */}
              <AccordionItem value="section-b">
                <AccordionTrigger className="text-sm font-semibold hover:no-underline">
                  B. Capital & Period
                </AccordionTrigger>
                <AccordionContent className="space-y-4 pt-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase text-muted-foreground font-bold">Start Date <span className="text-red-500">*</span></label>
                      <Input type="date" className="h-8 text-xs" {...form.register("startDate")} defaultValue="2024-01-01" />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase text-muted-foreground font-bold">End Date <span className="text-red-500">*</span></label>
                      <Input type="date" className="h-8 text-xs" {...form.register("endDate")} defaultValue="2024-12-31" />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">Initial Capital (₹) <span className="text-red-500">*</span></label>
                    <Input type="number" className="h-8 text-xs font-mono" {...form.register("initialCapital")} defaultValue={100000} />
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <label className="text-xs font-medium text-muted-foreground">Risk Per Trade <span className="text-red-500">*</span></label>
                      <span className="text-xs font-bold text-primary">{form.watch("riskPerTrade")}%</span>
                    </div>
                    <Slider
                      min={0.5} max={5} step={0.5}
                      defaultValue={[1]}
                      onValueChange={(val) => form.setValue("riskPerTrade", val[0])}
                    />
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* SECTION C: ENTRY & EXIT */}
              <AccordionItem value="section-c">
                <AccordionTrigger className="text-sm font-semibold hover:no-underline">
                  C. Entry & Exit Rules
                </AccordionTrigger>
                <AccordionContent className="space-y-4 pt-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Entry Time <span className="text-red-500">*</span></label>
                      <Input type="time" className="h-8 text-xs" {...form.register("entryTime")} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase text-muted-foreground font-bold">Exit Time <span className="text-red-500">*</span></label>
                      <Input type="time" className="h-8 text-xs" {...form.register("exitTime")} />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase text-muted-foreground font-bold">Target (%)</label>
                      <Input type="number" step="0.1" className="h-8 text-xs" {...form.register("targetProfit")} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase text-muted-foreground font-bold">Stop Loss (%)</label>
                      <Input type="number" step="0.1" className="h-8 text-xs" {...form.register("stopLoss")} />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">Spot Condition</label>
                    <Select
                      onValueChange={(val) => form.setValue("spotCondition", val)}
                      defaultValue="any"
                    >
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue placeholder="Condition" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="any">Any Condition</SelectItem>
                        <SelectItem value="above_sma">Above SMA 20</SelectItem>
                        <SelectItem value="trending_up">Trending Up (Supertrend)</SelectItem>
                        <SelectItem value="high_vol">High Volatility (IV)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* SECTION D: GREEKS & RISK */}
              <AccordionItem value="section-d">
                <AccordionTrigger className="text-sm font-semibold hover:no-underline">
                  D. Greeks & Risk
                </AccordionTrigger>
                <AccordionContent className="space-y-4 pt-2">
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">Target Delta</label>
                    <Input type="number" step="0.01" className="h-8 text-xs" {...form.register("targetDelta")} />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase text-muted-foreground font-bold">Min Theta</label>
                      <Input type="number" className="h-8 text-xs" {...form.register("minTheta")} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase text-muted-foreground font-bold">Max Vega</label>
                      <Input type="number" className="h-8 text-xs" {...form.register("maxVega")} />
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>

              {/* SECTION E: ADVANCED EXECUTION */}
              <AccordionItem value="section-e">
                <AccordionTrigger className="text-sm font-semibold hover:no-underline">
                  E. Advanced Execution
                </AccordionTrigger>
                <AccordionContent className="space-y-4 pt-2">
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">Slippage (%)</label>
                    <Input type="number" step="0.1" className="h-8 text-xs" {...form.register("slippage")} />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">Commission / Lot (₹)</label>
                    <Input type="number" className="h-8 text-xs" {...form.register("commission")} />
                  </div>
                </AccordionContent>
              </AccordionItem>

            </Accordion>

            {/* DEBUG STATE */}
            <div className="text-[10px] font-mono text-muted-foreground mt-4 border-t pt-2">
              DEBUG STATE: {JSON.stringify(values.startDate)} | {JSON.stringify(values.initialCapital)}
            </div>
          </form>
        </ScrollArea>

        {/* STICKY FOOTER ACTION */}
        <div className="p-4 border-t bg-background sticky bottom-0 z-10">
          <Button
            className="w-full font-bold shadow-md"
            size="lg"
            onClick={form.handleSubmit(onSubmit)}
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                Running Backtest...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2 fill-current" />
                Run Backtest
              </>
            )}
          </Button>
        </div>
      </div>

      {/* --- RIGHT PANEL: RESULTS & ANALYSIS --- */}
      <div className="col-span-12 md:col-span-9 h-full flex flex-col">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <TabsList>
              <TabsTrigger value="simulate" className="w-32">Simulate</TabsTrigger>
              <TabsTrigger value="compare" className="w-32">Compare</TabsTrigger>
            </TabsList>
            {result && (
              <Button variant="outline" size="sm" className="gap-2">
                <Download className="h-4 w-4" /> Export Report
              </Button>
            )}
          </div>

          <TabsContent value="simulate" className="flex-1 h-full min-h-0 overflow-auto pr-2 pb-10">
            {/* EMPTY STATE */}
            {!result && !isLoading && (
              <div className="h-full flex flex-col items-center justify-center border-2 border-dashed rounded-lg bg-muted/10">
                <BarChart2 className="h-16 w-16 text-muted-foreground/30 mb-4" />
                <h3 className="text-xl font-semibold text-muted-foreground">Ready to Simulate</h3>
                <p className="text-sm text-muted-foreground max-w-sm text-center mt-2">
                  Set your edge in the strategy lab on the left and validate it against historical data.
                </p>
              </div>
            )}

            {/* LOADING STATE */}
            {isLoading && (
              <div className="h-full flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                  <div className="h-12 w-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
                  <span className="text-lg font-mono animate-pulse">Computing Greeks & PnL...</span>
                </div>
              </div>
            )}

            {/* DASHBOARD RESULT STATE */}
            {result && !isLoading && (
              <div className="space-y-6">

                {/* SECTION A: HERO METRICS */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <Card className="p-4 bg-muted/20">
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Total Return</div>
                    <div className="text-3xl font-bold text-green-600 mt-1 flex items-baseline gap-2">
                      {result.summary?.total_return_pct?.toFixed(2) || "0.00"}%
                      <TrendingUp className="h-4 w-4" />
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {formatCurrency(result.summary?.final_capital)}
                    </div>
                  </Card>

                  <Card className="p-4">
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex justify-between">
                      Win Rate
                      <span className="text-foreground">{result.summary?.win_rate || 0}%</span>
                    </div>
                    <div className="mt-3">
                      <Progress value={result.summary?.win_rate || 0} className="h-2" />
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground mt-2">
                      <span>{result.summary?.total_trades || 0} Trades</span>
                    </div>
                  </Card>

                  <Card className="p-4 flex flex-col justify-between">
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Net Profit</div>
                    <div className={`text-2xl font-bold ${(result.summary?.final_capital - result.summary?.initial_capital) >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {formatCurrency((result.summary?.final_capital || 0) - (result.summary?.initial_capital || 0))}
                    </div>
                  </Card>

                  <Card className="p-4 flex flex-col justify-between relatives overflow-hidden">
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Profit Factor</div>
                    <div className="text-3xl font-bold flex items-center gap-2">
                      {result.summary?.profit_factor || 0}
                      {(result.summary?.profit_factor || 0) > 2 && (
                        <Badge className="bg-green-600 text-[10px]">EXCELLENT</Badge>
                      )}
                    </div>
                  </Card>
                </div>

                {/* SECTION B: TRADE ANALYSIS */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Card className="p-4">
                    <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-4">Trade Performance</h4>
                    <div className="space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="text-sm">Avg Win</span>
                        <span className="font-mono text-green-600 font-bold">{formatCurrency(result.trade_stats?.avg_win)}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm">Avg Loss</span>
                        <span className="font-mono text-red-600 font-bold">{formatCurrency(result.trade_stats?.avg_loss)}</span>
                      </div>
                    </div>
                  </Card>

                  <Card className="p-4">
                    <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-4">Extremes</h4>
                    <div className="space-y-3">
                      <div>
                        <span className="text-[10px] uppercase text-muted-foreground">Largest Win</span>
                        <div className="font-mono text-green-600 font-bold">{formatCurrency(result.trade_stats?.largest_win)}</div>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase text-muted-foreground">Largest Loss</span>
                        <div className="font-mono text-red-600 font-bold">{formatCurrency(result.trade_stats?.largest_loss)}</div>
                      </div>
                    </div>
                  </Card>

                  <Card className="p-4">
                    <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-4">Efficiency Metrics</h4>
                    <div className="space-y-4">
                      <div className="flex justify-between">
                        <span className="text-sm">Sharpe Ratio</span>
                        <span className="font-bold">{result.summary?.sharpe_ratio || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm">Calmar Ratio</span>
                        <span className="font-bold">{result.summary?.calmar_ratio || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm">Max Drawdown</span>
                        <span className="font-bold text-red-600">{result.summary?.max_drawdown_pct || 0}%</span>
                      </div>
                    </div>
                  </Card>
                </div>

                {/* SECTION C: GREEKS ANALYSIS (THE ENGINE ROOM) */}
                <Card className="bg-muted/10 border-dashed">
                  <div className="p-3 border-b flex items-center justify-between">
                    <h3 className="font-semibold text-sm flex items-center gap-2">
                      <Activity className="h-4 w-4" /> The Engine Room (Average Greeks)
                    </h3>
                  </div>
                  <div className="grid grid-cols-4 p-4 gap-4 divide-x">
                    <div className="px-2">
                      <HoverCard>
                        <HoverCardTrigger className="cursor-help flex items-center gap-1 text-xs text-muted-foreground uppercase font-semibold mb-1">
                          Avg Delta <Info className="h-3 w-3" />
                        </HoverCardTrigger>
                        <HoverCardContent className="w-64 text-xs">
                          Directional Sensitivity. 0.25 suggests conservative OTM buying. (Benchmark: ATM ~0.5).
                        </HoverCardContent>
                      </HoverCard>
                      <div className="text-xl font-mono font-bold">{result.greeks.avg_delta}</div>
                    </div>

                    <div className="px-4">
                      <HoverCard>
                        <HoverCardTrigger className="cursor-help flex items-center gap-1 text-xs text-muted-foreground uppercase font-semibold mb-1">
                          Avg Theta <Info className="h-3 w-3" />
                        </HoverCardTrigger>
                        <HoverCardContent className="w-64 text-xs">
                          Time Decay Risk. You pay ₹{Math.abs(result.greeks.avg_theta).toFixed(0)}/day to hold these positions.
                        </HoverCardContent>
                      </HoverCard>
                      <div className="text-xl font-mono font-bold text-red-500">{result.greeks.avg_theta}</div>
                    </div>

                    <div className="px-4">
                      <HoverCard>
                        <HoverCardTrigger className="cursor-help flex items-center gap-1 text-xs text-muted-foreground uppercase font-semibold mb-1">
                          Avg Vega <Info className="h-3 w-3" />
                        </HoverCardTrigger>
                        <HoverCardContent className="w-64 text-xs">
                          Volatility Sensitivity. Positive values profit when VIX rises.
                        </HoverCardContent>
                      </HoverCard>
                      <div className="text-xl font-mono font-bold text-green-600">+{result.greeks.avg_vega}</div>
                    </div>

                    <div className="px-4">
                      <HoverCard>
                        <HoverCardTrigger className="cursor-help flex items-center gap-1 text-xs text-muted-foreground uppercase font-semibold mb-1">
                          Avg IV <Info className="h-3 w-3" />
                        </HoverCardTrigger>
                        <HoverCardContent className="w-64 text-xs">
                          Market Anxiety Level. &gt;20% implies a high-volatility environment.
                        </HoverCardContent>
                      </HoverCard>
                      <div className="text-xl font-mono font-bold text-orange-500">{result.greeks.avg_iv}%</div>
                    </div>
                  </div>
                </Card>

                {/* SECTION D: VISUALS (CHARTS) */}
                <Card className="min-h-[400px] flex flex-col p-4">
                  <Tabs value={chartTab} onValueChange={setChartTab}>
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold text-sm">Performance Visuals</h3>
                      <TabsList className="h-8">
                        <TabsTrigger value="equity" className="text-xs">Equity Curve</TabsTrigger>
                        <TabsTrigger value="drawdown" className="text-xs">Drawdown</TabsTrigger>
                      </TabsList>
                    </div>

                    <TabsContent value="equity" className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={result.equity_curve || []}>
                          <defs>
                            <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#16a34a" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                          <XAxis dataKey="timestamp" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => val.split('T')[0]} />
                          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                          <Tooltip contentStyle={{ borderRadius: '8px' }} />
                          <Area type="monotone" dataKey="equity" stroke="#16a34a" strokeWidth={2} fill="url(#colorEquity)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </TabsContent>

                    <TabsContent value="drawdown" className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                          <defs>
                            <linearGradient id="colorDD" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                          <XAxis dataKey="trade" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                          <Tooltip contentStyle={{ borderRadius: '8px' }} />
                          <Area type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={2} fill="url(#colorDD)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </TabsContent>
                  </Tabs>
                </Card>

                {/* SECTION: TRADE LOG */}
                <Card className="bg-muted/10 border-dashed">
                  <div className="p-3 border-b flex items-center justify-between">
                    <h3 className="font-semibold text-sm flex items-center gap-2">
                      <History className="h-4 w-4" /> Trade Log ({result.trades ? result.trades.length : 0})
                    </h3>
                  </div>
                  <ScrollArea className="h-[300px] w-full pt-2"> {/* Fixed height for scrolling */}
                    <div className="p-2">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-[100px]">Date/Time</TableHead>
                            <TableHead>Symbol</TableHead>
                            <TableHead>Side</TableHead>
                            <TableHead className="text-right">Price</TableHead>
                            <TableHead className="text-right">Qty</TableHead>
                            <TableHead className="text-right">PnL</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {!result.trades || result.trades.length === 0 ? (
                            <TableRow>
                              <TableCell colSpan={6} className="text-center h-24 text-muted-foreground">
                                No trades executed in this backtest.
                              </TableCell>
                            </TableRow>
                          ) : (
                            result.trades.map((trade: any, idx: number) => (
                              <TableRow key={idx}>
                                <TableCell className="font-mono text-xs text-muted-foreground">{trade.timestamp ? trade.timestamp.replace('T', ' ') : '-'}</TableCell>
                                <TableCell className="font-medium text-xs">{trade.symbol}</TableCell>
                                <TableCell>
                                  <Badge variant={trade.side === "BUY" ? "default" : "destructive"} className="text-[10px] h-5">
                                    {trade.side}
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-right font-mono text-xs">{formatCurrency(trade.price)}</TableCell>
                                <TableCell className="text-right font-mono text-xs">{trade.qty}</TableCell>
                                <TableCell className={cn("text-right font-mono text-xs font-bold", trade.pnl > 0 ? "text-green-600" : trade.pnl < 0 ? "text-red-500" : "")}>
                                  {formatCurrency(trade.pnl)}
                                </TableCell>
                              </TableRow>
                            ))
                          )}
                        </TableBody>
                      </Table>
                    </div>
                  </ScrollArea>
                </Card>

              </div>
            )}
          </TabsContent>

          <TabsContent value="compare">
            <div className="h-full flex items-center justify-center border-2 border-dashed rounded-lg">
              <p className="text-muted-foreground">Comparison Lab View</p>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div >
  );
}