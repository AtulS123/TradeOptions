/**
 * Signal Card Component
 * 
 * Displays individual pattern signal with:
 * - Pattern name and timeframe
 * - Entry, SL, Target prices
 * - Running P&L
 * - Status badge
 * - Click to zoom chart
 */

import React from 'react';

interface Signal {
    id: string;
    pattern_name: string;
    timeframe: string;
    timestamp: string;
    signal_type: 'CE' | 'PE';
    entry_price: number;
    stop_loss: number;
    target: number;
    confidence: number;
    status: 'ACTIVE' | 'HIT_TARGET' | 'HIT_SL';
    pnl: number;
    pnl_percent: number;
    bars_held: number;
}

interface SignalCardProps {
    signal: Signal;
    onZoom?: (signalId: string) => void;
}

export default function SignalCard({ signal, onZoom }: SignalCardProps) {
    const statusColors = {
        'ACTIVE': 'bg-blue-500',
        'HIT_TARGET': 'bg-green-500',
        'HIT_SL': 'bg-red-500',
    };

    const typeColors = {
        'CE': 'text-green-400',
        'PE': 'text-red-400',
    };

    const formatTime = (timestamp: string) => {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    return (
        <div
            className="signal-card bg-slate-800 rounded-lg p-4 hover:bg-slate-700 transition-colors cursor-pointer"
            onClick={() => onZoom?.(signal.id)}
        >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
                <div>
                    <h4 className="font-semibold text-white">{signal.pattern_name}</h4>
                    <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-slate-400">{signal.timeframe.toUpperCase()}</span>
                        <span className="text-xs text-slate-500">•</span>
                        <span className="text-xs text-slate-400">{formatTime(signal.timestamp)}</span>
                    </div>
                </div>

                <div className="flex flex-col items-end gap-1">
                    <span className={`px-2 py-1 text-xs font-medium rounded ${statusColors[signal.status]} text-white`}>
                        {signal.status.replace('_', ' ')}
                    </span>
                    <span className={`text-sm font-bold ${typeColors[signal.signal_type]}`}>
                        {signal.signal_type}
                    </span>
                </div>
            </div>

            {/* Prices */}
            <div className="grid grid-cols-3 gap-2 mb-3">
                <div>
                    <div className="text-xs text-slate-400">Entry</div>
                    <div className="text-sm font-mono text-white">₹{signal.entry_price.toFixed(2)}</div>
                </div>
                <div>
                    <div className="text-xs text-slate-400">SL</div>
                    <div className="text-sm font-mono text-red-400">₹{signal.stop_loss.toFixed(2)}</div>
                </div>
                <div>
                    <div className="text-xs text-slate-400">Target</div>
                    <div className="text-sm font-mono text-green-400">₹{signal.target.toFixed(2)}</div>
                </div>
            </div>

            {/* P&L */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-700">
                <div>
                    <span className="text-xs text-slate-400">Confidence: </span>
                    <span className="text-xs text-white">{(signal.confidence * 100).toFixed(0)}%</span>
                </div>

                {signal.status === 'ACTIVE' && (
                    <div className="flex items-center gap-2">
                        <span className={`text-sm font-bold ${signal.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {signal.pnl >= 0 ? '+' : ''}{signal.pnl.toFixed(2)}
                        </span>
                        <span className={`text-xs ${signal.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            ({signal.pnl_percent >= 0 ? '+' : ''}{signal.pnl_percent.toFixed(2)}%)
                        </span>
                    </div>
                )}
            </div>

            {/* Bars held */}
            {signal.status === 'ACTIVE' && (
                <div className="mt-2 text-xs text-slate-500">
                    Held: {signal.bars_held} bars
                </div>
            )}
        </div>
    );
}
