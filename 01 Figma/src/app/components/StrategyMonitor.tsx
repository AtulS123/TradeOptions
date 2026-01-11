import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Activity, Clock, Target, TrendingUp, ChevronDown } from "lucide-react";
import { useState, useEffect } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./ui/collapsible";
import { SmartDeploymentModal } from "./SmartDeploymentModal";

interface StrategyMonitorProps {
    strategies: any[];
}

export function StrategyMonitor({ strategies }: StrategyMonitorProps) {
    const [openStrategies, setOpenStrategies] = useState<Set<string>>(new Set());
    const [currentTime, setCurrentTime] = useState(new Date());

    // Update time every second for countdown timers
    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentTime(new Date());
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    const toggleStrategy = (id: string) => {
        const newOpen = new Set(openStrategies);
        if (newOpen.has(id)) {
            newOpen.delete(id);
        } else {
            newOpen.add(id);
        }
        setOpenStrategies(newOpen);
    };

    if (!strategies || strategies.length === 0) {
        return (
            <div className="space-y-3">
                <SmartDeploymentModal />
                <Card className="p-6 text-center text-muted-foreground border-dashed">
                    <Activity className="mx-auto h-8 w-8 mb-2 opacity-50" />
                    <p className="text-sm">No active strategies deployed</p>
                    <p className="text-xs mt-1">Deploy a strategy to start monitoring</p>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            <SmartDeploymentModal />
            {strategies.map((strategy) => {
                const isOpen = openStrategies.has(strategy.id || strategy.name);
                const config = strategy.config || {};
                const monitoring = strategy.monitoring || {};

                return (
                    <Card key={strategy.id || strategy.name} className="overflow-hidden">
                        <Collapsible open={isOpen} onOpenChange={() => toggleStrategy(strategy.id || strategy.name)}>
                            {/* Header */}
                            <CollapsibleTrigger className="w-full">
                                <div className="p-4 hover:bg-accent/50 transition-colors">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <Activity className="h-4 w-4 text-primary" />
                                            <div className="text-left">
                                                <div className="font-medium text-sm">{strategy.name}</div>
                                                <div className="text-xs text-muted-foreground mt-0.5">
                                                    {config.underlying || "NIFTY 50"} • {config.lots_count || 1} lot(s)
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Badge variant={strategy.status === "active" ? "default" : "secondary"} className="text-xs">
                                                {strategy.status || "active"}
                                            </Badge>
                                            <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                                        </div>
                                    </div>
                                </div>
                            </CollapsibleTrigger>

                            {/* Expandable Details */}
                            <CollapsibleContent>
                                <div className="px-4 pb-4 pt-2 border-t bg-muted/30 space-y-4">
                                    {/* Configuration Summary */}
                                    <div>
                                        <div className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1">
                                            <Target className="h-3 w-3" />
                                            Configuration
                                        </div>
                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                            <div>
                                                <span className="text-muted-foreground">Entry Time:</span>
                                                <span className="ml-2 font-mono">{config.entry_time || "09:15"}</span>
                                            </div>
                                            <div>
                                                <span className="text-muted-foreground">Exit Time:</span>
                                                <span className="ml-2 font-mono">{config.exit_time || "15:30"}</span>
                                            </div>
                                            <div>
                                                <span className="text-muted-foreground">Stop Loss:</span>
                                                <span className="ml-2 font-semibold text-red-600">{config.stop_loss_pct || 0}%</span>
                                            </div>
                                            <div>
                                                <span className="text-muted-foreground">Target:</span>
                                                <span className="ml-2 font-semibold text-green-600">{config.target_profit_pct || 0}%</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Entry Conditions */}
                                    {monitoring.entry_conditions && monitoring.entry_conditions.length > 0 && (
                                        <div>
                                            <div className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1">
                                                <TrendingUp className="h-3 w-3" />
                                                Entry Conditions
                                            </div>
                                            <div className="space-y-2">
                                                {monitoring.entry_conditions.map((condition: any, idx: number) => (
                                                    <div key={idx} className="bg-background rounded-md p-2 text-xs">
                                                        <div className="flex items-center justify-between mb-1">
                                                            <span className="font-medium">{condition.condition}</span>
                                                            <Badge
                                                                variant={condition.status === "ready" ? "default" : "secondary"}
                                                                className="text-xs h-5"
                                                            >
                                                                {condition.status}
                                                            </Badge>
                                                        </div>
                                                        <div className="text-muted-foreground space-y-0.5">
                                                            <div>
                                                                Current: <span className="font-mono">{condition.current}</span>
                                                            </div>
                                                            <div>
                                                                Target: <span className="font-mono">{condition.target}</span>
                                                            </div>
                                                            {condition.next_action_in && (
                                                                <div className="text-primary font-medium">
                                                                    Next: {condition.next_action_in}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Exit Conditions / Position Timers */}
                                    {monitoring.exit_conditions && monitoring.exit_conditions.length > 0 && (
                                        <div>
                                            <div className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1">
                                                <Clock className="h-3 w-3" />
                                                Active Position Timers
                                            </div>
                                            <div className="space-y-2">
                                                {monitoring.exit_conditions.map((position: any, idx: number) => (
                                                    <div key={idx} className="bg-background rounded-md p-2 text-xs">
                                                        <div className="flex items-center justify-between">
                                                            <span className="font-medium">{position.symbol}</span>
                                                            <span className="font-mono text-primary">{position.will_close_in}</span>
                                                        </div>
                                                        <div className="text-muted-foreground mt-1">
                                                            Elapsed: {Math.floor(position.elapsed_seconds / 60)}m {position.elapsed_seconds % 60}s
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Fallback if no monitoring data */}
                                    {(!monitoring.entry_conditions || monitoring.entry_conditions.length === 0) &&
                                        (!monitoring.exit_conditions || monitoring.exit_conditions.length === 0) && (
                                            <div className="text-xs text-muted-foreground text-center py-2">
                                                {monitoring.next_action || "Monitoring conditions..."}
                                            </div>
                                        )}
                                </div>
                            </CollapsibleContent>
                        </Collapsible>
                    </Card>
                );
            })}
        </div>
    );
}
