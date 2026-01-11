
import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./ui/accordion";
import { ScrollArea } from "./ui/scroll-area";
import { Zap, ShieldAlert, Info } from "lucide-react";
import { Alert, AlertDescription } from "./ui/alert";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./ui/tooltip";
import { Slider } from "./ui/slider";

// Strategy Descriptions (same as Backtesting component)
const STRATEGY_DESCRIPTIONS: Record<string, string> = {
    "vwap": "VWAP Momentum: Enters trades when price crosses the Volume Weighted Average Price with confirmation. Uses Futures data for Volume.",
    "rsi_reversal": "RSI Reversal: Mean reversion. Buys PUT when RSI > 80 (Overbought). Buys CALL when RSI < 20 (Oversold).",
    "gamma_snap": "Gamma Snap: High-frequency scalping. Combines VWAP, RSI, and Volume for rapid entries. BUY when Close > VWAP AND RSI > 50 AND Volume > 1.2x avg.",
    "test_timer": "Test Timer: Opens CALL positions every 2 minutes, closes after 4 minutes. Max 2 concurrent positions. For testing and demonstration only.",
    "short_straddle": "Short Straddle: Sells both a Call and a Put at the ATM strike. Profits from low volatility and time decay.",
    "iron_condor": "Iron Condor: Sells an OTM Put and OTM Call, and buys further OTM wings for protection. Delta neutral strategy.",
};

interface DeploymentFormState {
    // Strategy Config
    strategyType: string;
    underlying: string;
    strikeSelection: string;

    // Position Sizing
    positionSizing: string;
    riskPerTrade: number;
    lotsCount: number;

    // Entry & Exit
    entryTime: string;
    exitTime: string;
    targetProfit: number;
    stopLoss: number;
    spotCondition: string;

    // Greeks
    targetDelta: number;
    minTheta: number;
    maxVega: number;
}

const DEFAULT_VALUES: DeploymentFormState = {
    strategyType: "vwap",
    underlying: "NIFTY 50",
    strikeSelection: "atm",
    positionSizing: "fixed",
    riskPerTrade: 1.0,
    lotsCount: 1,
    entryTime: "09:15",
    exitTime: "15:30",
    targetProfit: 50,
    stopLoss: 25,
    spotCondition: "any",
    targetDelta: 0.50,
    minTheta: 500,
    maxVega: 1000
};

export function SmartDeploymentModal() {
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Form State - comprehensive parameters
    const [formData, setFormData] = useState<DeploymentFormState>(DEFAULT_VALUES);

    // Helper to update form data
    const updateField = (field: keyof DeploymentFormState, value: any) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    // Validation
    const isValid = () => {
        if (!formData.strategyType) return false;
        if (!formData.underlying) return false;
        if (formData.lotsCount < 1) return false;
        if (!formData.stopLoss || formData.stopLoss <= 0) return false;
        return true;
    };

    const handleDeploy = async () => {
        setLoading(true);
        setError(null);
        try {
            const payload = {
                // Strategy Configuration
                strategy_type: formData.strategyType,
                underlying: formData.underlying,
                strike_selection: formData.strikeSelection,

                // Position Sizing
                position_sizing: formData.positionSizing,
                risk_per_trade_pct: formData.riskPerTrade,
                lots_count: formData.lotsCount,

                // Entry & Exit Rules
                entry_time: formData.entryTime,
                exit_time: formData.exitTime,
                target_profit_pct: formData.targetProfit,
                stop_loss_pct: formData.stopLoss,
                spot_condition: formData.spotCondition,

                // Greeks & Risk
                target_delta: formData.targetDelta,
                min_theta: formData.minTheta,
                max_vega: formData.maxVega
            };

            const res = await fetch("http://localhost:8001/deploy-strategy", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (data.status === "success") {
                setOpen(false);
                alert("Strategy Deployed Successfully!");
                // Reset form
                setFormData(DEFAULT_VALUES);
            } else {
                setError(data.message || "Deployment failed");
            }
        } catch (e) {
            setError("Failed to deploy strategy. Check server connection.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button className="w-full bg-blue-600 hover:bg-blue-700">
                    <Zap className="mr-2 h-4 w-4" /> Deploy New Strategy
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[600px] max-h-[90vh]">
                <DialogHeader>
                    <DialogTitle>Deploy New Strategy</DialogTitle>
                    <DialogDescription>
                        Configure strategy parameters for paper trading. Capital, slippage, and commission are inherited from your paper trading account settings.
                    </DialogDescription>
                </DialogHeader>

                <ScrollArea className="max-h-[60vh] pr-4">
                    <div className="space-y-4 py-4">
                        <Accordion type="multiple" defaultValue={["strategy-config"]} className="w-full">

                            {/* SECTION 1: Strategy Configuration */}
                            <AccordionItem value="strategy-config">
                                <AccordionTrigger className="text-sm font-semibold">
                                    Strategy Configuration *
                                </AccordionTrigger>
                                <AccordionContent className="space-y-4 pt-2">
                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between">
                                            <Label className="text-xs">Strategy Type *</Label>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger>
                                                        <Info className="h-3 w-3 text-muted-foreground" />
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p className="text-xs max-w-[250px]">
                                                            {STRATEGY_DESCRIPTIONS[formData.strategyType] || "Select a strategy"}
                                                        </p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        </div>
                                        <Select
                                            value={formData.strategyType}
                                            onValueChange={(val) => updateField('strategyType', val)}
                                        >
                                            <SelectTrigger className="h-9 text-xs">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="vwap">VWAP Momentum</SelectItem>
                                                <SelectItem value="rsi_reversal">RSI Reversal</SelectItem>
                                                <SelectItem value="gamma_snap">Gamma Snap</SelectItem>
                                                <SelectItem value="test_timer">Test Timer (Every 2min)</SelectItem>
                                                <SelectItem value="short_straddle" disabled>Short Straddle (Coming Soon)</SelectItem>
                                                <SelectItem value="iron_condor" disabled>Iron Condor (Coming Soon)</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-xs">Underlying *</Label>
                                        <Select
                                            value={formData.underlying}
                                            onValueChange={(val) => updateField('underlying', val)}
                                        >
                                            <SelectTrigger className="h-9 text-xs">
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
                                        <Label className="text-xs">Strike Selection *</Label>
                                        <Select
                                            value={formData.strikeSelection}
                                            onValueChange={(val) => updateField('strikeSelection', val)}
                                        >
                                            <SelectTrigger className="h-9 text-xs">
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

                            {/* SECTION 2: Position Sizing */}
                            <AccordionItem value="position-sizing">
                                <AccordionTrigger className="text-sm font-semibold">
                                    Position Sizing *
                                </AccordionTrigger>
                                <AccordionContent className="space-y-4 pt-2">
                                    <div className="space-y-2">
                                        <Label className="text-xs">Position Sizing Method</Label>
                                        <Select
                                            value={formData.positionSizing}
                                            onValueChange={(val) => updateField('positionSizing', val)}
                                        >
                                            <SelectTrigger className="h-9 text-xs">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="fixed">Fixed</SelectItem>
                                                <SelectItem value="kelly">Kelly Criterion</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label className="text-xs">Risk Per Trade *</Label>
                                            <span className="text-xs font-bold text-primary">{formData.riskPerTrade}%</span>
                                        </div>
                                        <Slider
                                            min={0.5}
                                            max={5}
                                            step={0.5}
                                            value={[formData.riskPerTrade]}
                                            onValueChange={(val) => updateField('riskPerTrade', val[0])}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-xs">Number of Lots *</Label>
                                        <Input
                                            type="number"
                                            className="h-9 text-xs"
                                            value={formData.lotsCount}
                                            onChange={(e) => updateField('lotsCount', Number(e.target.value))}
                                            min={1}
                                            step={1}
                                        />
                                    </div>
                                </AccordionContent>
                            </AccordionItem>

                            {/* SECTION 3: Entry & Exit Rules */}
                            <AccordionItem value="entry-exit">
                                <AccordionTrigger className="text-sm font-semibold">
                                    Entry & Exit Rules *
                                </AccordionTrigger>
                                <AccordionContent className="space-y-4 pt-2">
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="space-y-2">
                                            <Label className="text-xs">Entry Time *</Label>
                                            <Input
                                                type="time"
                                                className="h-9 text-xs"
                                                value={formData.entryTime}
                                                onChange={(e) => updateField('entryTime', e.target.value)}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label className="text-xs">Exit Time *</Label>
                                            <Input
                                                type="time"
                                                className="h-9 text-xs"
                                                value={formData.exitTime}
                                                onChange={(e) => updateField('exitTime', e.target.value)}
                                            />
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="space-y-2">
                                            <Label className="text-xs">Target Profit (%)</Label>
                                            <Input
                                                type="number"
                                                step="0.1"
                                                className="h-9 text-xs"
                                                value={formData.targetProfit}
                                                onChange={(e) => updateField('targetProfit', Number(e.target.value))}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label className="text-xs text-red-600">Stop Loss (%) *</Label>
                                            <Input
                                                type="number"
                                                step="0.1"
                                                className="h-9 text-xs border-red-200"
                                                value={formData.stopLoss}
                                                onChange={(e) => updateField('stopLoss', Number(e.target.value))}
                                            />
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-xs">Spot Condition</Label>
                                        <Select
                                            value={formData.spotCondition}
                                            onValueChange={(val) => updateField('spotCondition', val)}
                                        >
                                            <SelectTrigger className="h-9 text-xs">
                                                <SelectValue />
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

                            {/* SECTION 4: Greeks & Risk Filters */}
                            <AccordionItem value="greeks-risk">
                                <AccordionTrigger className="text-sm font-semibold">
                                    Greeks & Risk Filters
                                </AccordionTrigger>
                                <AccordionContent className="space-y-4 pt-2">
                                    {/* Only show Target Delta when using delta-based strike selection */}
                                    {formData.strikeSelection === "delta" && (
                                        <div className="space-y-2">
                                            <div className="flex items-center justify-between">
                                                <Label className="text-xs">Target Delta *</Label>
                                                <TooltipProvider>
                                                    <Tooltip>
                                                        <TooltipTrigger>
                                                            <Info className="h-3 w-3 text-muted-foreground" />
                                                        </TooltipTrigger>
                                                        <TooltipContent>
                                                            <p className="text-xs max-w-[250px]">
                                                                ATM ≈ 0.50, Slightly OTM ≈ 0.30-0.40, Deep OTM ≈ 0.10-0.20
                                                            </p>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </TooltipProvider>
                                            </div>
                                            <Input
                                                type="number"
                                                step="0.01"
                                                min="0.05"
                                                max="0.95"
                                                className="h-9 text-xs"
                                                value={formData.targetDelta}
                                                onChange={(e) => updateField('targetDelta', Number(e.target.value))}
                                            />
                                        </div>
                                    )}

                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="space-y-2">
                                            <Label className="text-xs">Min Theta</Label>
                                            <Input
                                                type="number"
                                                className="h-9 text-xs"
                                                value={formData.minTheta}
                                                onChange={(e) => updateField('minTheta', Number(e.target.value))}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label className="text-xs">Max Vega</Label>
                                            <Input
                                                type="number"
                                                className="h-9 text-xs"
                                                value={formData.maxVega}
                                                onChange={(e) => updateField('maxVega', Number(e.target.value))}
                                            />
                                        </div>
                                    </div>
                                </AccordionContent>
                            </AccordionItem>

                        </Accordion>

                        {error && (
                            <Alert variant="destructive">
                                <ShieldAlert className="h-4 w-4" />
                                <AlertDescription>{error}</AlertDescription>
                            </Alert>
                        )}
                    </div>
                </ScrollArea>

                <DialogFooter>
                    <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                    <Button onClick={handleDeploy} disabled={!isValid() || loading}>
                        {loading ? "Deploying..." : "Confirm Deployment"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
