/**
 * Pattern Chart Component - lightweight-charts v5 compatible
 */

import React, { useEffect, useRef } from 'react';
import type { IChartApi } from 'lightweight-charts';

interface Candle {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

interface PatternChartProps {
    timeframe: string;
    candles: Candle[];
    patterns?: any[];
    overlays?: any;
}

export default function PatternChart({ timeframe, candles }: PatternChartProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<any>(null);
    const seriesRef = useRef<any>(null);

    // Initialize chart ONCE
    useEffect(() => {
        if (!chartContainerRef.current) return;

        let chart: any = null;
        let cleanup: (() => void) | undefined;

        const initChart = async () => {
            try {
                const lw = await import('lightweight-charts');

                if (!chartContainerRef.current) return;

                chart = lw.createChart(chartContainerRef.current, {
                    width: chartContainerRef.current.clientWidth,
                    height: 500,
                    layout: { background: { color: '#0f172a' }, textColor: '#94a3b8' },
                    grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
                    timeScale: { borderColor: '#334155', timeVisible: true },
                    rightPriceScale: { borderColor: '#334155' },
                });

                chartRef.current = chart;

                // V5 API: addSeries with class reference
                const series = chart.addSeries(lw.CandlestickSeries, {
                    upColor: '#22c55e',
                    downColor: '#ef4444',
                    borderUpColor: '#22c55e',
                    borderDownColor: '#ef4444',
                    wickUpColor: '#22c55e',
                    wickDownColor: '#ef4444',
                });

                seriesRef.current = series;

                const handleResize = () => {
                    if (chartContainerRef.current && chart) {
                        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
                    }
                };

                window.addEventListener('resize', handleResize);
                cleanup = () => {
                    window.removeEventListener('resize', handleResize);
                    chart.remove();
                };
            } catch (error) {
                console.error('Chart error:', error);
            }
        };

        initChart();

        return () => {
            cleanup?.();
            chartRef.current = null;
            seriesRef.current = null;
        };
    }, []); // ONLY run on mount

    // Update data when candles change
    useEffect(() => {
        if (!seriesRef.current || !candles?.length) return;

        try {
            const chartData = candles
                .map(c => ({
                    time: Math.floor(new Date(c.date).getTime() / 1000),
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                }))
                .filter(d => !isNaN(d.time))
                .sort((a, b) => a.time - b.time);

            if (chartData.length > 0) {
                seriesRef.current.setData(chartData);

                // CRITICAL: Scroll to show the most recent data
                if (chartRef.current) {
                    chartRef.current.timeScale().fitContent();
                    // Force scroll to the latest candle
                    chartRef.current.timeScale().scrollToRealTime();
                }

                console.log(`PatternChart: Updated ${chartData.length} candles, latest: ${candles[candles.length - 1]?.date}`);
            }
        } catch (error) {
            console.error('Error updating chart data:', error);
        }
    }, [candles]); // Update whenever candles change

    return (
        <div className="pattern-chart">
            <div className="chart-header flex items-center justify-between p-4 bg-slate-800 rounded-t-lg">
                <h3 className="text-lg font-bold text-white">NIFTY 50 - {timeframe.toUpperCase()}</h3>
                <div className="text-sm text-slate-400">{candles?.length || 0} candles</div>
            </div>
            <div
                ref={chartContainerRef}
                className="chart-container bg-slate-900 rounded-b-lg relative overflow-hidden"
                style={{ height: '500px', width: '100%' }}
            />
        </div>
    );
}
