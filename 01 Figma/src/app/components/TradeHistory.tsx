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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "./ui/tabs"
import { Download, Search, TrendingUp, TrendingDown, Trash2 } from "lucide-react";
import { useState, useEffect } from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";

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
  mode?: "PAPER" | "LIVE";
  charges?: {
    brokerage: number;
    stt: number;
    exchange_charges: number;
    stamp_duty: number;
    sebi_fees: number;
    gst: number;
    total: number;
  };
}

export function TradeHistory() {
  const [filterType, setFilterType] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [trades, setTrades] = useState<HistoricalTrade[]>([]);
  const [loading, setLoading] = useState(false);

  // Fetch History
  const fetchHistory = async () => {
    setLoading(true);
    try {
      // Point to Python Backend (Port 8001)
      const res = await fetch("http://localhost:8001/api/history");
      if (res.ok) {
        const data = await res.json();
        // Sort by date desc
        const sorted = data.sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime());
        setTrades(sorted);
      }
    } catch (error) {
      console.error("Failed to fetch history:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    // Poll every 5 seconds for updates
    const interval = setInterval(fetchHistory, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleDeleteOrder = async (orderId: string) => {
    if (!confirm("Are you sure you want to remove this order from the logs?")) return;
    // Backend delete not fully implemented for history yet, but let's assume we would call an endpoint
    alert("Delete from history not yet supported by backend API (Requires Order ID lookup in closed_trades)");
  };

  const getFilteredTrades = (mode: "PAPER" | "LIVE") => {
    return trades.filter((trade) => {
      // Mode Filter
      // Default to PAPER if mode is undefined (legacy support)
      const tradeMode = trade.mode || "PAPER";
      if (tradeMode !== mode) return false;

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
  };

  const renderTradeTable = (mode: "PAPER" | "LIVE") => {
    const filtered = getFilteredTrades(mode);

    // Calculate Stats for this View
    const totalPnL = filtered.reduce((sum, trade) => sum + trade.pnl, 0);
    const winningTrades = filtered.filter((t) => t.pnl > 0).length;
    const winRate = filtered.length > 0 ? (winningTrades / filtered.length) * 100 : 0;

    return (
      <div className="space-y-4">
        {/* Summary Cards for this Tab */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Total P&L ({mode})</div>
            <div className={`text-2xl font-bold ${totalPnL >= 0 ? "text-green-600" : "text-red-600"}`}>
              ₹{totalPnL.toFixed(2)}
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Win Rate</div>
            <div className="text-2xl font-bold">{winRate.toFixed(1)}%</div>
            <div className="text-xs text-muted-foreground mt-1">
              {winningTrades} wins / {filtered.length - winningTrades} losses
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground">Avg Trade P&L</div>
            <div className="text-2xl font-bold">
              ₹{filtered.length > 0 ? (totalPnL / filtered.length).toFixed(2) : "0.00"}
            </div>
          </Card>
        </div>

        {/* Table */}
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date/Time</TableHead>
                <TableHead>Symbol</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Entry</TableHead>
                <TableHead>Exit</TableHead>
                <TableHead>Charges</TableHead>
                <TableHead>Net P&L</TableHead>
                <TableHead>Strategy</TableHead>
                <TableHead>Exit Reason</TableHead>
                <TableHead className="w-[50px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={11} className="text-center py-8 text-muted-foreground">
                    No closed trades found in {mode} mode.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((trade) => (
                  <TableRow key={trade.id}>
                    <TableCell className="text-sm">{trade.date}</TableCell>
                    <TableCell>
                      {trade.symbol}
                      <div className="text-xs text-muted-foreground">
                        {trade.action} {trade.quantity}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={trade.action === "BUY" ? "default" : "secondary"}
                      >
                        {trade.type}
                      </Badge>
                    </TableCell>
                    <TableCell>₹{trade.entryPrice.toFixed(2)}</TableCell>
                    <TableCell>₹{trade.exitPrice.toFixed(2)}</TableCell>
                    <TableCell>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger className="cursor-help underline decoration-dotted text-muted-foreground">
                            {trade.charges ? `₹${trade.charges.total.toFixed(2)}` : "-"}
                          </TooltipTrigger>
                          <TooltipContent>
                            {trade.charges ? (
                              <div className="text-xs space-y-1">
                                <div className="font-semibold border-b pb-1 mb-1">Charge Breakdown</div>
                                <div className="flex justify-between gap-4"><span>Brokerage:</span> <span>₹{trade.charges.brokerage}</span></div>
                                <div className="flex justify-between gap-4"><span>STT:</span> <span>₹{trade.charges.stt}</span></div>
                                <div className="flex justify-between gap-4"><span>Exch Txn:</span> <span>₹{trade.charges.exchange_charges}</span></div>
                                <div className="flex justify-between gap-4"><span>Stamp Duty:</span> <span>₹{trade.charges.stamp_duty}</span></div>
                                <div className="flex justify-between gap-4"><span>SEBI:</span> <span>₹{trade.charges.sebi_fees}</span></div>
                                <div className="flex justify-between gap-4"><span>GST:</span> <span>₹{trade.charges.gst}</span></div>
                              </div>
                            ) : ("No details")}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </TableCell>
                    <TableCell>
                      <div className={`flex items-center gap-1 ${trade.pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {trade.pnl >= 0 ? <TrendingUp className="size-4" /> : <TrendingDown className="size-4" />}
                        <div>
                          ₹{trade.pnl.toFixed(2)}
                          <div className="text-xs">
                            ({trade.pnlPercent > 0 ? "+" : ""}{trade.pnlPercent.toFixed(2)}%)
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{trade.strategy}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">{trade.exitReason}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" onClick={() => handleDeleteOrder(trade.id)}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Card>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2>Trade History</h2>
          <p className="text-sm text-muted-foreground">
            View your past performance
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchHistory}>
            Refresh
          </Button>
          <Button variant="outline">
            <Download className="size-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Filters (Global) */}
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

      {/* Tabs */}
      <Tabs defaultValue="paper" className="w-full">
        <TabsList>
          <TabsTrigger value="paper">Paper Trades</TabsTrigger>
          <TabsTrigger value="live">Live Trades</TabsTrigger>
        </TabsList>

        <TabsContent value="paper">
          {renderTradeTable("PAPER")}
        </TabsContent>

        <TabsContent value="live">
          {renderTradeTable("LIVE")}
        </TabsContent>
      </Tabs>

    </div>
  );
}
