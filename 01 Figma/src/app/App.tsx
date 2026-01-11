import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { LiveTrades } from "./components/LiveTrades";
import { PaperTrades } from "./components/PaperTrades";
import { Backtesting } from "./components/Backtesting";
import { TradeHistory } from "./components/TradeHistory";
import { MarketData } from "./components/MarketData";
import TelescopeDashboard from "./components/Telescope/TelescopeDashboard";
import { Card } from "./components/ui/card";
import {
  Activity,
  TrendingUp,
  Beaker,
  History,
  BarChart3,
  Telescope,
} from "lucide-react";
import { Toaster } from "sonner";

import { useState, useEffect } from "react";

export default function App() {
  const [marketLabel, setMarketLabel] = useState<string>("Closed");

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch("http://localhost:8001/market-status");
        if (res.ok) {
          const data = await res.json();
          // Backend returns { market_label: "Open" | "Closed", ... }
          if (data.market_label) {
            setMarketLabel(data.market_label);
          }
        }
      } catch (e) {
        console.error("Failed to fetch market status", e);
      }
    };

    fetchStatus(); // Initial fetch
    const interval = setInterval(fetchStatus, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="flex items-center gap-2">
                <Activity className="size-8" />
                AlgoTrader Pro
              </h1>
              <p className="text-muted-foreground">
                Options Trading Dashboard
              </p>
            </div>
            <Card className="p-3">
              <div className="text-sm text-muted-foreground">Market Status</div>
              {marketLabel === "Open" ? (
                <div className="flex items-center gap-2 text-green-600">
                  <div className="size-2 rounded-full bg-green-500 animate-pulse" />
                  Open
                </div>
              ) : (
                <div className="flex items-center gap-2 text-red-600">
                  <div className="size-2 rounded-full bg-red-500" />
                  Closed
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-6">
        <Tabs defaultValue="market" className="w-full">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="market" className="flex items-center gap-2">
              <BarChart3 className="size-4" />
              Market Data
            </TabsTrigger>
            <TabsTrigger value="telescope" className="flex items-center gap-2">
              <Telescope className="size-4" />
              Telescope
            </TabsTrigger>
            <TabsTrigger value="live" className="flex items-center gap-2">
              <Activity className="size-4" />
              Live Trades
            </TabsTrigger>
            <TabsTrigger value="paper" className="flex items-center gap-2">
              <Beaker className="size-4" />
              Paper Trades
            </TabsTrigger>
            <TabsTrigger value="backtest" className="flex items-center gap-2">
              <TrendingUp className="size-4" />
              Backtesting
            </TabsTrigger>
            <TabsTrigger value="history" className="flex items-center gap-2">
              <History className="size-4" />
              History
            </TabsTrigger>
          </TabsList>

          <div className="mt-6">
            <TabsContent value="market">
              <MarketData />
            </TabsContent>
            <TabsContent value="telescope">
              <TelescopeDashboard />
            </TabsContent>

            <TabsContent value="live">
              <LiveTrades />
            </TabsContent>

            <TabsContent value="paper">
              <PaperTrades />
            </TabsContent>

            <TabsContent value="backtest">
              <Backtesting />
            </TabsContent>

            <TabsContent value="history">
              <TradeHistory />
            </TabsContent>
          </div>
        </Tabs>
      </div>
      <Toaster />
    </div>

  );
}
