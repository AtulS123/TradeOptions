
import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Zap, ShieldAlert, BadgeCheck } from "lucide-react";
import { Alert, AlertDescription } from "./ui/alert";

interface StrategyDef {
    id: string;
    name: string;
    description: string;
}

interface Definitions {
    entry_strategies: StrategyDef[];
    risk_strategies: StrategyDef[];
}

export function SmartDeploymentModal() {
    const [open, setOpen] = useState(false);
    const [defs, setDefs] = useState<Definitions>({ entry_strategies: [], risk_strategies: [] });

    // Form State
    const [entryId, setEntryId] = useState<string>("");
    const [riskId, setRiskId] = useState<string>(""); // Optional
    const [lots, setLots] = useState<string>("1");
    const [stopLoss, setStopLoss] = useState<string>("");

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Fetch Definitions
    useEffect(() => {
        if (open) {
            fetch("http://localhost:8001/definitions/strategies")
                .then(res => res.json())
                .then(data => setDefs(data))
                .catch(err => console.error(err));
        }
    }, [open]);

    // Validation
    const isRiskSelected = !!riskId && riskId !== "none";
    const isStopLossMandatory = !isRiskSelected;

    const isValid = () => {
        if (!entryId) return false;
        if (!lots || parseInt(lots) <= 0) return false;
        if (isStopLossMandatory && (!stopLoss || parseFloat(stopLoss) <= 0)) return false;
        return true;
    };

    const handleDeploy = async () => {
        setLoading(true);
        setError(null);
        try {
            const payload = {
                entry_strategy_id: entryId,
                risk_strategy_id: isRiskSelected ? riskId : null,
                lots_count: parseInt(lots),
                manual_stop_loss_pct: stopLoss ? parseFloat(stopLoss) : null
            };

            const res = await fetch("http://localhost:8001/deploy-strategy", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (data.status === "success") {
                setOpen(false);
                // Ideally refresh parent or show toast
                alert("Strategy Deployed!");
            } else {
                setError(data.message);
            }
        } catch (e) {
            setError("Failed to deploy strategy.");
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
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Deploy Strategy</DialogTitle>
                    <DialogDescription>
                        Configure your execution engine.
                    </DialogDescription>
                </DialogHeader>

                <div className="grid gap-6 py-4">
                    {/* 1. Entry Strategy */}
                    <div className="space-y-2">
                        <Label>Entry Strategy (Signal Generator)</Label>
                        <Select onValueChange={setEntryId} value={entryId}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select Entry Logic..." />
                            </SelectTrigger>
                            <SelectContent>
                                {defs.entry_strategies.map(s => (
                                    <SelectItem key={s.id} value={s.id}>
                                        <span className="font-medium">{s.name}</span>
                                        <span className="ml-2 text-xs text-muted-foreground">- {s.description}</span>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* 2. Risk Strategy */}
                    <div className="space-y-2">
                        <Label className="flex items-center justify-between">
                            Risk Management (Optional)
                            {isRiskSelected && <BadgeCheck className="h-4 w-4 text-green-500" />}
                        </Label>
                        <Select onValueChange={setRiskId} value={riskId || "none"}>
                            <SelectTrigger className="border-dashed">
                                <SelectValue placeholder="Manual / None" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">Manual / Default</SelectItem>
                                {defs.risk_strategies.map(s => (
                                    <SelectItem key={s.id} value={s.id}>
                                        <span className="font-medium">{s.name}</span>
                                        <span className="ml-2 text-xs text-muted-foreground">- {s.description}</span>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        {/* 3. Number of Lots */}
                        <div className="space-y-2">
                            <Label>Number of Lots</Label>
                            <Input
                                type="number"
                                value={lots}
                                onChange={(e) => setLots(e.target.value)}
                                min={1}
                                step={1}
                            />
                            <p className="text-[10px] text-muted-foreground">
                                System calculates total shares (1 Lot ≈ 65 qty).
                            </p>
                        </div>

                        {/* 4. Stop Loss */}
                        <div className="space-y-2">
                            <Label className={isStopLossMandatory ? "text-red-500 font-semibold" : ""}>
                                Stop Loss % {isStopLossMandatory && "*"}
                            </Label>
                            <Input
                                type="number"
                                placeholder={isRiskSelected ? "Managed by Strategy" : "Required (e.g. 10)"}
                                value={stopLoss}
                                onChange={(e) => setStopLoss(e.target.value)}
                                disabled={isRiskSelected} // Scenario B
                                className={isStopLossMandatory && !stopLoss ? "border-red-300 ring-red-200" : ""}
                            />
                            {isRiskSelected && <span className="text-[10px] text-green-600">Auto-managed by Risk Engine</span>}
                        </div>
                    </div>

                    {error && (
                        <Alert variant="destructive">
                            <ShieldAlert className="h-4 w-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}
                </div>

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
