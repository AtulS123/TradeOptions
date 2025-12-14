import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { LiveTrades } from "./components/LiveTrades";
import { PaperTrades } from "./components/PaperTrades";
import { Backtesting } from "./components/Backtesting";
import { TradeHistory } from "./components/TradeHistory";
import { MarketData } from "./components/MarketData";
import { Card } from "./components/ui/card";
import {
  Activity,
  TrendingUp,
  Beaker,
  History,
  BarChart3,
} from "lucide-react";

export default function App() {
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
              <div className="flex items-center gap-2 text-green-600">
                <div className="size-2 rounded-full bg-green-500 animate-pulse" />
                Open
              </div>
            </Card>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-6">
        <Tabs defaultValue="market" className="w-full">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="market" className="flex items-center gap-2">
              <BarChart3 className="size-4" />
              Market Data
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
    </div>
  );
}
