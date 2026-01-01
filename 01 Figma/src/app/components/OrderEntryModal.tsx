import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { AlertCircle, Wallet } from "lucide-react";
import { Alert, AlertDescription } from "./ui/alert";

interface OrderEntryModalProps {
    isOpen: boolean;
    onClose: () => void;
    symbol: string; // e.g., "NIFTY 24500 CE"
    ltp: number;
    type: "CE" | "PE";
}

export function OrderEntryModal({ isOpen, onClose, symbol, ltp, type }: OrderEntryModalProps) {
    const [side, setSide] = useState<"BUY" | "SELL">("BUY");
    const [orderType, setOrderType] = useState<"MARKET" | "LIMIT" | "SL">("MARKET");
    const [product, setProduct] = useState<"MIS" | "NRML">("MIS");

    const [lots, setLots] = useState<string>("1");
    const [price, setPrice] = useState<string>(ltp.toString());
    const [trigger, setTrigger] = useState<string>("");

    // Margin State
    const [margin, setMargin] = useState<{ required: number; available: number; shortfall: number } | null>(null);
    const [loadingMargin, setLoadingMargin] = useState(false);

    // Execution State
    const [executing, setExecuting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Reset on Open
    useEffect(() => {
        if (isOpen) {
            setPrice(ltp.toString());
            setTrigger("");
            setError(null);
            checkMargin();
        }
    }, [isOpen, symbol, ltp]);

    // Check Margin Debounce or Effect
    useEffect(() => {
        const timer = setTimeout(() => {
            if (isOpen) checkMargin();
        }, 500);
        return () => clearTimeout(timer);
    }, [lots, price, side, isOpen]);

    const checkMargin = async () => {
        if (!isOpen) return;
        setLoadingMargin(true);
        try {
            const qty = parseInt(lots) * 75; // Assuming Nifty 75 lot size for calc, backend has real logic
            const limitPrice = parseFloat(price) || ltp;

            const res = await fetch("http://localhost:8001/api/check-margin", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    symbol,
                    ltp: limitPrice,
                    quantity: qty,
                    product,
                    side
                })
            });
            const data = await res.json();
            if (data.status === "success") {
                setMargin({
                    required: data.required_margin,
                    available: data.available_margin,
                    shortfall: data.shortfall
                });
            }
        } catch (e) {
            console.error("Margin check failed", e);
        } finally {
            setLoadingMargin(false);
        }
    };

    const handleExecute = async () => {
        setExecuting(true);
        setError(null);
        try {
            const qty = parseInt(lots) * 75; // Backend expects total quantity or lots? 
            // PaperBroker expects Total Quantity. Deployment uses Lots.
            // Let's settle on: Frontend sends Total Quantity for Manual Trade.
            // Wait, previous conv said user enters "Lots".
            // SmartDeploymentModal sent `lots_count` to `/deploy-strategy`.
            // Here we send `quantity` to `/manual-trade`.
            // So we must convert.

            const payload = {
                symbol,
                quantity: qty,
                side,
                product,
                order_type: orderType,
                price: parseFloat(price) || 0,
                trigger_price: parseFloat(trigger) || 0,
                ltp: ltp
            };

            const res = await fetch("http://localhost:8001/api/place-order", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (data.status === "success") {
                onClose();
                // We should trigger a refresh in parent, but for now just close
            } else {
                setError(data.message);
            }
        } catch (e) {
            setError("Execution Failed");
        } finally {
            setExecuting(false);
        }
    };

    const themeColor = side === "BUY" ? "bg-blue-600 hover:bg-blue-700" : "bg-orange-600 hover:bg-orange-700";

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-[400px]">
                <DialogHeader>
                    <div className="flex justify-between items-center">
                        <DialogTitle>{symbol}</DialogTitle>
                        <span className={`text-sm font-bold ${ltp > 0 ? "text-green-600" : ""}`}>
                            {ltp.toFixed(2)}
                        </span>
                    </div>
                </DialogHeader>

                <Tabs value={side} onValueChange={(v) => setSide(v as any)} className="w-full">
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="BUY" className="data-[state=active]:bg-blue-100 data-[state=active]:text-blue-700">BUY</TabsTrigger>
                        <TabsTrigger value="SELL" className="data-[state=active]:bg-orange-100 data-[state=active]:text-orange-700">SELL</TabsTrigger>
                    </TabsList>
                </Tabs>

                <div className="grid gap-4 py-4">
                    {/* Order Type Toggles */}
                    <div className="flex space-x-2 text-xs">
                        {["MARKET", "LIMIT", "SL", "SL-M"].map((t) => (
                            <button
                                key={t}
                                onClick={() => {
                                    setOrderType(t as any);
                                    if (t === "MARKET") setPrice("0");
                                }}
                                className={`px-2 py-1 rounded border ${orderType === t ? "bg-secondary text-secondary-foreground font-bold" : "text-muted-foreground"}`}
                            >
                                {t}
                            </button>
                        ))}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <Label>Lots</Label>
                            <Input
                                type="number"
                                value={lots}
                                onChange={(e) => setLots(e.target.value)}
                                min={1}
                            />
                            <span className="text-[10px] text-muted-foreground">Qty: {(parseInt(lots) || 0) * 75}</span>
                        </div>
                        <div className="space-y-1">
                            <Label>Price</Label>
                            <Input
                                type="number"
                                value={orderType === "MARKET" ? "" : price}
                                placeholder={orderType === "MARKET" ? "Market Price" : "0.00"}
                                onChange={(e) => setPrice(e.target.value)}
                                disabled={orderType === "MARKET" || orderType === "SL-M"}
                            />
                        </div>
                    </div>

                    {(orderType === "SL" || orderType === "SL-M") && (
                        <div className="space-y-1">
                            <Label>Trigger Price</Label>
                            <Input
                                type="number"
                                value={trigger}
                                onChange={(e) => setTrigger(e.target.value)}
                                placeholder="Trigger Price"
                            />
                        </div>
                    )}


                    {/* Margin Panel */}
                    <div className="rounded bg-muted/50 p-2 text-xs space-y-1">
                        <div className="flex justify-between">
                            <span>Margin Required:</span>
                            <span className={loadingMargin ? "opacity-50" : "font-mono"}>
                                {margin ? `₹${margin.required.toLocaleString()}` : "..."}
                            </span>
                        </div>
                        <div className="flex justify-between text-muted-foreground">
                            <span>Available:</span>
                            <span>{margin ? `₹${margin.available.toLocaleString()}` : "..."}</span>
                        </div>
                        {margin && margin.shortfall > 0 && (
                            <div className="flex justify-between text-red-600 font-bold">
                                <span>Shortfall:</span>
                                <span>₹{margin.shortfall.toLocaleString()}</span>
                            </div>
                        )}
                    </div>

                    {error && (
                        <Alert variant="destructive">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button
                        className={`w-full ${themeColor}`}
                        onClick={handleExecute}
                        disabled={executing || (margin?.shortfall || 0) > 0 || parseInt(lots) <= 0}
                    >
                        {executing ? "Placing..." : side}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
