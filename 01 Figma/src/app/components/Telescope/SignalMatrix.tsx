/**
 * Signal Matrix Component
 * 
 * Two view modes:
 * 1. Combined Stream: All signals from all timeframes in one list
 * 2. Split Matrix: 5-column grid, one column per timeframe
 */

import React, { useState } from 'react';
import SignalCard from './SignalCard';

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

interface SignalMatrixProps {
    signals: Signal[];
    onSignalClick?: (signalId: string) => void;
}

export default function SignalMatrix({ signals, onSignalClick }: SignalMatrixProps) {
    const [viewMode, setViewMode] = useState<'combined' | 'matrix'>('combined');

    const timeframes = ['1m', '5m', '15m', '1h', '1d'];

    const getSignalsByTimeframe = (tf: string) => {
        return signals.filter(s => s.timeframe === tf);
    };

    return (
        <div className="signal-matrix">
            {/* Tab Controls */}
            <div className="flex items-center gap-4 mb-4">
                <button
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${viewMode === 'combined'
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                    onClick={() => setViewMode('combined')}
                >
                    Combined Stream
                </button>
                <button
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${viewMode === 'matrix'
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                    onClick={() => setViewMode('matrix')}
                >
                    Split Matrix
                </button>

                <div className="ml-auto text-sm text-slate-400">
                    {signals.length} Active Signal{signals.length !== 1 ? 's' : ''}
                </div>
            </div>

            {/* Combined View */}
            {viewMode === 'combined' && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {signals.length === 0 ? (
                        <div className="col-span-full text-center py-12 text-slate-400">
                            No active signals detected yet
                        </div>
                    ) : (
                        signals.map(signal => (
                            <SignalCard
                                key={signal.id}
                                signal={signal}
                                onZoom={onSignalClick}
                            />
                        ))
                    )}
                </div>
            )}

            {/* Matrix View */}
            {viewMode === 'matrix' && (
                <div className="grid grid-cols-5 gap-4">
                    {timeframes.map(tf => {
                        const tfSignals = getSignalsByTimeframe(tf);

                        return (
                            <div key={tf} className="timeframe-column">
                                <div className="sticky top-0 bg-slate-900 z-10 pb-2">
                                    <h3 className="font-bold text-white text-center py-2 bg-slate-800 rounded-lg">
                                        {tf.toUpperCase()}
                                    </h3>
                                    <div className="text-xs text-center text-slate-400 mt-1">
                                        {tfSignals.length} signal{tfSignals.length !== 1 ? 's' : ''}
                                    </div>
                                </div>

                                <div className="flex flex-col gap-3 mt-3">
                                    {tfSignals.length === 0 ? (
                                        <div className="text-center py-8 text-slate-500 text-sm">
                                            No signals
                                        </div>
                                    ) : (
                                        tfSignals.map(signal => (
                                            <SignalCard
                                                key={signal.id}
                                                signal={signal}
                                                onZoom={onSignalClick}
                                            />
                                        ))
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
