import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Download, Search, TrendingUp, TrendingDown } from "lucide-react";
import { useState } from "react";

interface HistoricalTrade {
  id: string;
  date: string;
  symbol: string;
  strike: number;
  type: "CE" | "PE";
  action: "BUY" | "SELL";
  quantity: number;
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  pnlPercent: number;
  strategy: string;
  exitReason: string;
  duration: string;
}

export function TradeHistory() {
  const [filterType, setFilterType] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  const historicalTrades: HistoricalTrade[] = [
    {
      id: "1",
      date: "2025-12-14 14:30",
      symbol: "NIFTY",
      strike: 21500,
      type: "CE",
      action: "BUY",
      quantity: 50,
      entryPrice: 145.50,
      exitPrice: 168.30,
      pnl: 1140.0,
      pnlPercent: 15.67,
      strategy: "Momentum",
      exitReason: "Target Hit",
      duration: "2h 15m",
    },
    {
      id: "2",
      date: "2025-12-14 11:15",
      symbol: "NIFTY",
      strike: 21400,
      type: "PE",
      action: "SELL",
      quantity: 25,
      entryPrice: 89.20,
      exitPrice: 72.50,
      pnl: 417.5,
      pnlPercent: 18.72,
      strategy: "IV Crush",
      exitReason: "Target Hit",
      duration: "1h 45m",
    },
    {
      id: "3",
      date: "2025-12-13 15:00",
      symbol: "NIFTY",
      strike: 21600,
      type: "CE",
      action: "BUY",
      quantity: 75,
      entryPrice: 132.00,
      exitPrice: 125.00,
      pnl: -525.0,
      pnlPercent: -5.3,
      strategy: "Breakout",
      exitReason: "Stop Loss",
      duration: "3h 20m",
    },
    {
      id: "4",
      date: "2025-12-13 10:30",
      symbol: "NIFTY",
      strike: 21300,
      type: "PE",
      action: "BUY",
      quantity: 100,
      entryPrice: 78.50,
      exitPrice: 95.20,
      pnl: 1670.0,
      pnlPercent: 21.27,
      strategy: "Mean Reversion",
      exitReason: "Target Hit",
      duration: "4h 10m",
    },
    {
      id: "5",
      date: "2025-12-12 14:45",
      symbol: "NIFTY",
      strike: 21550,
      type: "CE",
      action: "SELL",
      quantity: 50,
      entryPrice: 155.00,
      exitPrice: 148.30,
      pnl: 335.0,
      pnlPercent: 4.32,
      strategy: "Theta Decay",
      exitReason: "Time Exit",
      duration: "5h 30m",
    },
    {
      id: "6",
      date: "2025-12-12 09:30",
      symbol: "NIFTY",
      strike: 21450,
      type: "PE",
      action: "BUY",
      quantity: 60,
      entryPrice: 92.00,
      exitPrice: 85.00,
      pnl: -420.0,
      pnlPercent: -7.61,
      strategy: "Support Bounce",
      exitReason: "Stop Loss",
      duration: "2h 00m",
    },
    {
      id: "7",
      date: "2025-12-11 13:20",
      symbol: "NIFTY",
      strike: 21500,
      type: "CE",
      action: "BUY",
      quantity: 80,
      entryPrice: 138.50,
      exitPrice: 162.00,
      pnl: 1880.0,
      pnlPercent: 16.97,
      strategy: "Momentum",
      exitReason: "Target Hit",
      duration: "3h 15m",
    },
    {
      id: "8",
      date: "2025-12-11 10:00",
      symbol: "NIFTY",
      strike: 21350,
      type: "PE",
      action: "SELL",
      quantity: 40,
      entryPrice: 102.00,
      exitPrice: 95.50,
      pnl: 260.0,
      pnlPercent: 6.37,
      strategy: "Range Bound",
      exitReason: "Target Hit",
      duration: "1h 30m",
    },
  ];

  const filteredTrades = historicalTrades.filter((trade) => {
    const matchesType =
      filterType === "all" ||
      (filterType === "profitable" && trade.pnl > 0) ||
      (filterType === "loss" && trade.pnl < 0);

    const matchesSearch =
      searchTerm === "" ||
      trade.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      trade.strategy.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesType && matchesSearch;
  });

  const totalPnL = filteredTrades.reduce((sum, trade) => sum + trade.pnl, 0);
  const winningTrades = filteredTrades.filter((t) => t.pnl > 0).length;
  const winRate =
    filteredTrades.length > 0
      ? (winningTrades / filteredTrades.length) * 100
      : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2>Trade History</h2>
          <p className="text-sm text-muted-foreground">
            {filteredTrades.length} trades
          </p>
        </div>
        <Button variant="outline">
          <Download className="size-4 mr-2" />
          Export CSV
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-sm text-muted-foreground">Total P&L</div>
          <div
            className={`${totalPnL >= 0 ? "text-green-600" : "text-red-600"}`}
          >
            ₹{totalPnL.toFixed(2)}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-muted-foreground">Win Rate</div>
          <div>{winRate.toFixed(1)}%</div>
          <div className="text-xs text-muted-foreground mt-1">
            {winningTrades} wins / {filteredTrades.length - winningTrades}{" "}
            losses
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-muted-foreground">Avg Trade P&L</div>
          <div>
            ₹
            {filteredTrades.length > 0
              ? (totalPnL / filteredTrades.length).toFixed(2)
              : "0.00"}
          </div>
        </Card>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search by symbol or strategy..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
          <Select value={filterType} onValueChange={setFilterType}>
            <SelectTrigger className="w-full md:w-[200px]">
              <SelectValue placeholder="Filter trades" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Trades</SelectItem>
              <SelectItem value="profitable">Profitable Only</SelectItem>
              <SelectItem value="loss">Loss Only</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </Card>

      {/* Trades Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date/Time</TableHead>
              <TableHead>Symbol</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Entry</TableHead>
              <TableHead>Exit</TableHead>
              <TableHead>P&L</TableHead>
              <TableHead>Strategy</TableHead>
              <TableHead>Exit Reason</TableHead>
              <TableHead>Duration</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTrades.map((trade) => (
              <TableRow key={trade.id}>
                <TableCell className="text-sm">{trade.date}</TableCell>
                <TableCell>
                  {trade.symbol} {trade.strike} {trade.type}
                  <div className="text-xs text-muted-foreground">
                    {trade.action} {trade.quantity}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={trade.action === "BUY" ? "default" : "secondary"}
                  >
                    {trade.action}
                  </Badge>
                </TableCell>
                <TableCell>₹{trade.entryPrice.toFixed(2)}</TableCell>
                <TableCell>₹{trade.exitPrice.toFixed(2)}</TableCell>
                <TableCell>
                  <div
                    className={`flex items-center gap-1 ${
                      trade.pnl >= 0 ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {trade.pnl >= 0 ? (
                      <TrendingUp className="size-4" />
                    ) : (
                      <TrendingDown className="size-4" />
                    )}
                    <div>
                      ₹{trade.pnl.toFixed(2)}
                      <div className="text-xs">
                        ({trade.pnlPercent > 0 ? "+" : ""}
                        {trade.pnlPercent.toFixed(2)}%)
                      </div>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{trade.strategy}</Badge>
                </TableCell>
                <TableCell className="text-sm">{trade.exitReason}</TableCell>
                <TableCell className="text-sm">{trade.duration}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
