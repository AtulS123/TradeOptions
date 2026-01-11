/**
 * Telescope Dashboard - Main Container
 * 
 * Layout:
 * - Top: PatternChart with timeframe controls
 * - Bottom: SignalMatrix with active/historical signals
 * 
 * Features:
 * - Real-time data fetching from API
 * - Timeframe switching
 * - Auto-refresh every 60 seconds
 */

import React, { useState, useEffect, useCallback } from 'react';
import PatternChart from './PatternChart';
import SignalMatrix from './SignalMatrix';

interface Candle {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

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
    candle_index: number;
}

interface TelescopeStats {
    total_active: number;
    total_historical: number;
    win_rate: number;
    avg_pnl: number;
    by_timeframe: Record<string, number>;
}

export default function TelescopeDashboard() {
    const [timeframe, setTimeframe] = useState<string>('1h');
    const [candles, setCandles] = useState<Candle[]>([]);
    const [activeSignals, setActiveSignals] = useState<Signal[]>([]);
    const [stats, setStats] = useState<TelescopeStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const timeframes = [
        { value: '1m', label: '1 Min' },
        { value: '5m', label: '5 Min' },
        { value: '15m', label: '15 Min' },
        { value: '1h', label: '1 Hour' },
        { value: '1d', label: '1 Day' }
    ];

    // Fetch candles for current timeframe
    const fetchCandles = useCallback(async () => {
        try {
            console.log(`Fetching candles for ${timeframe}...`);
            const response = await fetch(
                `http://localhost:8001/api/telescope/candles?timeframe=${timeframe}&lookback=200`
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('Candles response:', data);

            if (data.status === 'success' && Array.isArray(data.candles)) {
                setCandles(data.candles);
                setError(null);
            } else {
                console.warn('Invalid candles data:', data);
                setCandles([]);
            }
        } catch (err: any) {
            console.error('Error fetching candles:', err);
            setError(err.message || 'Failed to load chart data');
            setCandles([]);
        }
    }, [timeframe]);

    // Fetch active signals
    const fetchActiveSignals = useCallback(async () => {
        try {
            console.log('Fetching active signals...');
            const response = await fetch(
                'http://localhost:8001/api/telescope/signals/active'
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('Signals response:', data);

            if (data.status === 'success' && Array.isArray(data.signals)) {
                setActiveSignals(data.signals);
            } else {
                setActiveSignals([]);
            }
        } catch (err: any) {
            console.error('Error fetching signals:', err);
            setActiveSignals([]);
        }
    }, []);

    // Fetch stats
    const fetchStats = useCallback(async () => {
        try {
            console.log('Fetching stats...');
            const response = await fetch(
                'http://localhost:8001/api/telescope/stats'
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('Stats response:', data);

            if (data.status === 'success' && data.stats) {
                setStats(data.stats);
            }
        } catch (err: any) {
            console.error('Error fetching stats:', err);
        }
    }, []);

    // Initial load
    useEffect(() => {
        const loadAll = async () => {
            setLoading(true);
            setError(null);

            try {
                await Promise.all([
                    fetchCandles(),
                    fetchActiveSignals(),
                    fetchStats()
                ]);
            } catch (err) {
                console.error('Failed to load Telescope data:', err);
            } finally {
                setLoading(false);
            }
        };

        loadAll();
    }, [fetchCandles, fetchActiveSignals, fetchStats]);

    // Auto-refresh every 60 seconds
    useEffect(() => {
        const interval = setInterval(() => {
            fetchCandles();
            fetchActiveSignals();
            fetchStats();
        }, 60000);

        return () => clearInterval(interval);
    }, [fetchCandles, fetchActiveSignals, fetchStats]);

    // Manual scan trigger
    const triggerScan = async () => {
        try {
            console.log(`Triggering scan for ${timeframe}...`);
            const response = await fetch(
                `http://localhost:8001/api/telescope/scan?timeframe=${timeframe}`,
                { method: 'POST' }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('Scan result:', data);

            if (data.status === 'success') {
                alert(`Scan complete: ${data.patterns_detected} patterns detected`);
                await fetchActiveSignals();
            }
        } catch (err: any) {
            console.error('Error triggering scan:', err);
            alert('Scan failed: ' + err.message);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen bg-slate-900">
                <div className="text-center">
                    <div className="text-white text-xl mb-2">Loading Telescope...</div>
                    <div className="text-slate-400 text-sm">Fetching pattern data from backend</div>
                </div>
            </div>
        );
    }

    return (
        <div className="telescope-dashboard min-h-screen bg-slate-900 p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-3xl font-bold text-white">Project Telescope</h1>
                    <p className="text-slate-400 mt-1">
                        Multi-Timeframe Pattern Detection Engine
                    </p>
                </div>

                {stats && (
                    <div className="flex gap-6 bg-slate-800 rounded-lg p-4">
                        <div>
                            <div className="text-xs text-slate-400">Active Signals</div>
                            <div className="text-2xl font-bold text-white">{stats.total_active}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-400">Win Rate</div>
                            <div className="text-2xl font-bold text-green-400">{stats.win_rate.toFixed(1)}%</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-400">Avg P&L</div>
                            <div className={`text-2xl font-bold ${stats.avg_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                ₹{stats.avg_pnl.toFixed(2)}
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Error Banner */}
            {error && (
                <div className="mb-4 bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded">
                    <strong>Error:</strong> {error}
                    <br />
                    <span className="text-sm text-red-300">Make sure the backend server is running on port 8001</span>
                </div>
            )}

            {/* Main Content Grid */}
            <div className="grid grid-cols-12 gap-4">
                {/* Left: Indicator Summary */}
                <div className="col-span-3 space-y-4">
                    <div className="bg-slate-800 rounded-lg p-4">
                        <h3 className="text-sm font-bold text-white mb-3 flex items-center">
                            <span className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></span>
                            Active Patterns
                        </h3>
                        <div className="space-y-2 text-xs text-slate-300">
                            <div className="flex justify-between">
                                <span>Candlestick</span>
                                <span className="text-green-400">8</span>
                            </div>
                            <div className="pl-3 space-y-1 text-slate-400">
                                <div>• Hammer, Shooting Star</div>
                                <div>• Engulfing (Bull/Bear)</div>
                                <div>• Morning/Evening Star</div>
                                <div>• Doji Variations</div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-slate-800 rounded-lg p-4">
                        <h3 className="text-sm font-bold text-white mb-3">Geometric</h3>
                        <div className="space-y-1 text-xs text-slate-400">
                            <div>• Head & Shoulders</div>
                            <div>• Double Top/Bottom</div>
                            <div>• Triangle Breakout</div>
                        </div>
                    </div>

                    <div className="bg-slate-800 rounded-lg p-4">
                        <h3 className="text-sm font-bold text-white mb-3">Indicators</h3>
                        <div className="space-y-1 text-xs text-slate-400">
                            <div>• RSI Divergence</div>
                            <div>• MA Cross (50/200)</div>
                            <div>• BB Squeeze</div>
                        </div>
                    </div>

                    <div className="bg-slate-800 rounded-lg p-4">
                        <h3 className="text-sm font-bold text-white mb-3">Settings</h3>
                        <div className="space-y-2 text-xs">
                            <div className="flex justify-between text-slate-400">
                                <span>ATR Period</span>
                                <span className="text-white">14</span>
                            </div>
                            <div className="flex justify-between text-slate-400">
                                <span>Risk Reward</span>
                                <span className="text-white">1:2</span>
                            </div>
                            <div className="flex justify-between text-slate-400">
                                <span>Min Confidence</span>
                                <span className="text-white">0.7</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right: Chart and Controls */}
                <div className="col-span-9 space-y-4">
                    {/* Timeframe Controls */}
                    <div className="flex items-center justify-between bg-slate-800 rounded-lg p-3">
                        <div className="flex gap-2">
                            {timeframes.map(tf => (
                                <button
                                    key={tf.value}
                                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${timeframe === tf.value
                                            ? 'bg-blue-600 text-white'
                                            : 'text-slate-300 hover:text-white hover:bg-slate-700'
                                        }`}
                                    onClick={() => setTimeframe(tf.value)}
                                >
                                    {tf.label}
                                </button>
                            ))}
                        </div>

                        <button
                            className="px-4 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-md text-sm font-medium transition-colors"
                            onClick={triggerScan}
                        >
                            Scan Now
                        </button>
                    </div>

                    {/* Chart */}
                    {candles.length > 0 ? (
                        <PatternChart
                            timeframe={timeframe}
                            candles={candles}
                            patterns={[]}
                            overlays={{}}
                        />
                    ) : (
                        <div className="bg-slate-800 rounded-lg p-12 text-center">
                            <div className="text-slate-400 text-lg">No candle data available</div>
                            <div className="text-slate-500 text-sm mt-2">
                                {error ? 'Check backend connection' : 'Loading historical data...'}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Signals Matrix */}
            <div>
                <h2 className="text-xl font-bold text-white mb-4">Active Signals</h2>
                <SignalMatrix
                    signals={activeSignals}
                    onSignalClick={(id) => console.log('Signal clicked:', id)}
                />
            </div>
        </div>
    );
}
