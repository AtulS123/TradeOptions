import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";
import { OrderEntryModal } from "./OrderEntryModal";

interface OptionRow {
  strike: number;
  callOI: number;
  callVolume: number;
  callLTP: number;
  callIV: number;
  callDelta: number;
  putLTP: number;
  putIV: number;
  putVolume: number;
  putOI: number;
  putDelta: number;
}

interface MarketStatus {
  status: string;
  nifty_price: number;
  pcr: number;
}

export function MarketData() {
  const [optionChain, setOptionChain] = useState<OptionRow[]>([]);
  const [marketStatus, setMarketStatus] = useState<MarketStatus>({
    status: "Disconnected",
    nifty_price: 0,
    pcr: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  // Modal State
  const [selectedOption, setSelectedOption] = useState<{ symbol: string; ltp: number; type: "CE" | "PE" } | null>(null);

  const fetchData = async () => {
    try {
      // Parallel fetch
      const [statusRes, chainRes] = await Promise.all([
        fetch("http://localhost:8001/market-status"),
        fetch("http://localhost:8001/option-chain"),
      ]);

      if (!statusRes.ok || !chainRes.ok) {
        throw new Error("Failed to fetch data");
      }

      const statusData = await statusRes.json();
      const chainData = await chainRes.json();

      setMarketStatus(statusData);
      setOptionChain(chainData);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      console.error("Fetch error:", err);
      // Don't clear old data, just set error/status
      setMarketStatus((prev) => ({ ...prev, status: "Disconnected" }));
      setError("Backend unreachable. Retrying...");
    }
  };

  useEffect(() => {
    fetchData(); // Initial fetch
    const interval = setInterval(fetchData, 2000); // Poll every 2s

    return () => clearInterval(interval);
  }, []);

  const handleOptionClick = (strike: number, type: "CE" | "PE", ltp: number) => {
    const symbol = `NIFTY ${strike} ${type}`;
    setSelectedOption({ symbol, ltp, type });
  };

  return (
    <div className="space-y-6">
      {/* Header Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">NIFTY 50 Spot</CardTitle>
            <Badge
              variant={marketStatus.status === "Connected" ? "default" : "destructive"}
            >
              {marketStatus.status}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {marketStatus.nifty_price.toFixed(2)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">PCR (Put/Call Ratio)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{marketStatus.pcr}</div>
            <p className="text-xs text-muted-foreground">
              {marketStatus.pcr > 1 ? "Bullish" : "Bearish/Neutral"} Sentiment
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Last Updated</CardTitle>
            <RefreshCw className="h-4 w-4 text-muted-foreground animate-spin" style={{ animationDuration: '2s' }} />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {lastUpdated.toLocaleTimeString()}
            </div>
          </CardContent>
        </Card>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Connection Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Option Chain Table */}
      <Card>
        <CardHeader>
          <CardTitle>Virtual Option Chain (Near ATM)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/50">
                  <TableHead className="text-center" colSpan={5}>CALLS (CE)</TableHead>
                  <TableHead className="text-center font-bold bg-background">STRIKE</TableHead>
                  <TableHead className="text-center" colSpan={5}>PUTS (PE)</TableHead>
                </TableRow>
                <TableRow>
                  <TableHead className="text-right">OI</TableHead>
                  <TableHead className="text-right">Vol</TableHead>
                  <TableHead className="text-right">IV</TableHead>
                  <TableHead className="text-right">Delta</TableHead>
                  <TableHead className="text-right">LTP</TableHead>

                  <TableHead className="text-center">Strike</TableHead>

                  <TableHead className="text-left">LTP</TableHead>
                  <TableHead className="text-left">Delta</TableHead>
                  <TableHead className="text-left">IV</TableHead>
                  <TableHead className="text-left">Vol</TableHead>
                  <TableHead className="text-left">OI</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {optionChain.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={11} className="h-24 text-center">
                      Waiting for data...
                    </TableCell>
                  </TableRow>
                ) : (
                  optionChain.map((row) => (
                    <TableRow key={row.strike} className={
                      // Highlight ATM roughly
                      Math.abs(row.strike - marketStatus.nifty_price) < 50 ? "bg-blue-50/10" : ""
                    }>
                      {/* CALLS */}
                      <TableCell className="text-right font-mono">{row.callOI.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-xs text-muted-foreground">{row.callVolume.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-xs">{row.callIV}%</TableCell>
                      <TableCell className="text-right font-mono text-xs">{row.callDelta}</TableCell>
                      <TableCell
                        className="text-right font-mono font-bold text-green-600 cursor-pointer hover:bg-green-100"
                        onClick={() => handleOptionClick(row.strike, "CE", row.callLTP)}
                      >
                        {row.callLTP.toFixed(2)}
                      </TableCell>

                      {/* STRIKE */}
                      <TableCell className="text-center font-bold bg-muted/20">{row.strike}</TableCell>

                      {/* PUTS */}
                      <TableCell
                        className="text-left font-mono font-bold text-red-600 cursor-pointer hover:bg-red-100"
                        onClick={() => handleOptionClick(row.strike, "PE", row.putLTP)}
                      >
                        {row.putLTP.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-left font-mono text-xs">{row.putDelta}</TableCell>
                      <TableCell className="text-left font-mono text-xs">{row.putIV}%</TableCell>
                      <TableCell className="text-left font-mono text-xs text-muted-foreground">{row.putVolume.toLocaleString()}</TableCell>
                      <TableCell className="text-left font-mono">{row.putOI.toLocaleString()}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Order Entry Modal */}
      {selectedOption && (
        <OrderEntryModal
          isOpen={!!selectedOption}
          onClose={() => setSelectedOption(null)}
          symbol={selectedOption.symbol}
          ltp={selectedOption.ltp}
          type={selectedOption.type}
        />
      )}
    </div>
  );
}
