import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Activity } from "lucide-react";
import { SmartDeploymentModal } from "./SmartDeploymentModal";

interface Strategy {
    name: string;
    status: string;
}

interface StrategyPanelProps {
    strategies: Strategy[];
}

export function StrategyPanel({ strategies }: StrategyPanelProps) {
    return (
        <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Activity className="size-5 text-blue-500" />
                    <h3 className="font-semibold">Active Strategies</h3>
                </div>
                <div className="w-1/2">
                    <SmartDeploymentModal />
                </div>
            </div>

            {strategies.length === 0 ? (
                <p className="text-sm text-muted-foreground">No active strategies.</p>
            ) : (
                <div className="space-y-3">
                    {strategies.map((strat, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 bg-secondary/20 rounded-lg">
                            <span className="font-medium text-sm">{strat.name}</span>
                            <Badge variant="outline" className="bg-green-500/10 text-green-600 border-green-200">
                                {strat.status}
                            </Badge>
                        </div>
                    ))}
                </div>
            )}

            <div className="mt-4 pt-4 border-t text-xs text-muted-foreground">
                <p>Criteria: VWAP Crossover + Volume &gt; 1.5x Avg</p>
            </div>
        </Card>
    );
}
