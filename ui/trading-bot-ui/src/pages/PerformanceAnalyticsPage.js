import React, { useState, useEffect, useCallback, useMemo } from 'react';
import apiClient from '../services/api';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  Legend,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine
} from 'recharts';

import PnLHeatMap from '../components/analytics/PnLHeatMap';

/**
 * Performance Analytics Page - Premium Financial Dashboard
 * Optimized for smooth UX with zero lag, rich visuals, and polished interactions
 */
const PerformanceAnalyticsPage = () => {
  const [timeframe, setTimeframe] = useState('summary');
  const [tradingMode, setTradingMode] = useState('paper');
  const [performanceData, setPerformanceData] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [tradeList, setTradeList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchingData, setFetchingData] = useState(false);
  const [error, setError] = useState(null);
  
  // Date filtering state
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const fetch_system_health = useCallback(async () => {
    try {
      const response = await apiClient.get('/v1/trading/execution/performance/system-health');
      if (response.data && response.data.success) {
        setSystemHealth(response.data);
      }
    } catch (err) {
      console.error('Error fetching system health:', err);
    }
  }, []);

  const fetch_trade_list = useCallback(async () => {
    try {
      const params = { limit: 100, trading_mode: tradingMode };
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const response = await apiClient.get('/v1/trading/execution/trade-history', {
        params: params
      });
      if (response.data.success) {
        setTradeList(response.data.trades || []);
      }
    } catch (err) {
      console.error('Error fetching trade list:', err);
    }
  }, [tradingMode, startDate, endDate]);

  const handleExport = useCallback(() => {
    if (!tradeList || tradeList.length === 0) return;

    // CSV Headers
    const headers = [
      'Date', 'Time', 'Symbol', 'Instrument Key', 'Type', 'Strike Price', 'Expiry Date',
      'Signal', 'Quantity', 'Entry Price', 'Exit Price', 
      'Stop Loss', 'Target', 'Gross PnL', 'Net PnL', 'Status', 'Exit Reason'
    ];

    // CSV Rows
    const rows = tradeList.map(trade => {
      const grossPnl = trade.gross_pnl || (trade.exit_price - trade.entry_price) * trade.quantity;
      const charges = trade.gross_pnl && trade.net_pnl 
        ? trade.gross_pnl - trade.net_pnl 
        : Math.abs(grossPnl * 0.005); 
      const netPnl = trade.net_pnl || (grossPnl - charges);

      return [
        trade.entry_date || '',
        trade.entry_time_str || '',
        trade.symbol || '',
        trade.instrument_key || '',
        trade.signal_type?.includes('CE') ? 'CALL' : trade.signal_type?.includes('PE') ? 'PUT' : 'EQUITY',
        trade.strike_price || 0,
        trade.expiry_date || '',
        trade.signal_type || '',
        trade.quantity || 0,
        trade.entry_price || 0,
        trade.exit_price || 0,
        trade.stop_loss || 0,
        trade.target || 0,
        grossPnl.toFixed(2),
        netPnl.toFixed(2),
        netPnl >= 0 ? 'WIN' : 'LOSS',
        trade.exit_reason || ''
      ].join(',');
    });

    const csvContent = "data:text/csv;charset=utf-8," 
      + headers.join(',') + "\n" 
      + rows.join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `trade_ledger_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [tradeList]);

  const fetch_performance_data = useCallback(async () => {
    setFetchingData(true);
    setError(null);

    try {
      const endpoint_map = {
        'daily': '/v1/trading/execution/performance/daily',
        'weekly': '/v1/trading/execution/performance/weekly',
        'monthly': '/v1/trading/execution/performance/monthly',
        'six_month': '/v1/trading/execution/performance/six-month',
        'yearly': '/v1/trading/execution/performance/yearly',
        'summary': '/v1/trading/execution/performance/summary'
      };

      // Pass trading_mode as query param
      const response = await apiClient.get(endpoint_map[timeframe], {
        params: { trading_mode: tradingMode }
      });
      console.log('Backend response:', response.data);

      if (response.data) {
        // Merge metrics and other data (chart_data, breakdowns) into a single object
        const mergedData = {
          ...response.data,
          ...(response.data.metrics || {})
        };
        setPerformanceData(mergedData);
      }
      
      // Fetch trade list as well
      await fetch_trade_list();

      setLoading(false);
    } catch (err) {
      console.error('Error fetching performance data:', err);
      const error_message = err.response?.data?.detail || err.message || 'Failed to fetch performance data';
      setError(error_message);
      setLoading(false);
    } finally {
      setFetchingData(false);
    }
  }, [timeframe, tradingMode, fetch_trade_list]);

  useEffect(() => {
    fetch_performance_data();
    fetch_system_health();
  }, [fetch_performance_data, fetch_system_health]);

  const handle_timeframe_change = useCallback((new_timeframe) => {
    if (new_timeframe !== timeframe && !fetchingData) {
      setTimeframe(new_timeframe);
    }
  }, [timeframe, fetchingData]);

  const toggleTradingMode = useCallback(() => {
    setTradingMode(prev => prev === 'paper' ? 'live' : 'paper');
  }, []);

  const format_currency = useCallback((value) => {
    const formatted = new Intl.NumberFormat('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(Math.abs(value || 0));
    return `${value < 0 ? '-' : ''}₹${formatted}`;
  }, []);

  const format_percentage = useCallback((value) => {
    return `${value >= 0 ? '+' : ''}${(value || 0).toFixed(2)}%`;
  }, []);

  const get_color_class = useCallback((value) => {
    if (value > 0) return 'tw-text-emerald-400';
    if (value < 0) return 'tw-text-rose-400';
    return 'tw-text-slate-400';
  }, []);

  const get_bg_color_class = useCallback((value) => {
    if (value > 0) return 'tw-bg-emerald-500/10 tw-border-emerald-500/30';
    if (value < 0) return 'tw-bg-rose-500/10 tw-border-rose-500/30';
    return 'tw-bg-slate-500/10 tw-border-slate-500/30';
  }, []);

  const timeframe_options = useMemo(() => [
    { value: 'daily', label: 'Today', icon: '1D' },
    { value: 'weekly', label: 'Week', icon: '1W' },
    { value: 'monthly', label: 'Month', icon: '1M' },
    { value: 'six_month', label: '6 Months', icon: '6M' },
    { value: 'yearly', label: 'Year', icon: '1Y' },
    { value: 'summary', label: 'All Time', icon: 'ALL' }
  ], []);

  const profit_factor_badge = useMemo(() => {
    const pf = performanceData?.profit_factor || 0;
    if (pf >= 2) return { text: 'Exceptional', color: 'tw-bg-emerald-500/20 tw-text-emerald-300' };
    if (pf >= 1.5) return { text: 'Excellent', color: 'tw-bg-cyan-500/20 tw-text-cyan-300' };
    if (pf >= 1) return { text: 'Good', color: 'tw-bg-amber-500/20 tw-text-amber-300' };
    return { text: 'Needs Work', color: 'tw-bg-rose-500/20 tw-text-rose-300' };
  }, [performanceData]);

  if (loading) {
    return (
      <div className="tw-min-h-screen tw-bg-gradient-to-br tw-from-slate-950 tw-via-slate-900 tw-to-slate-950 tw-flex tw-items-center tw-justify-center">
        <div className="tw-text-center tw-space-y-4">
          <div className="tw-relative tw-w-20 tw-h-20 tw-mx-auto">
            <div className="tw-absolute tw-inset-0 tw-border-4 tw-border-slate-700/30 tw-rounded-full"></div>
            <div className="tw-absolute tw-inset-0 tw-border-4 tw-border-cyan-500 tw-rounded-full tw-border-t-transparent tw-animate-spin"></div>
          </div>
          <div>
            <p className="tw-text-slate-300 tw-text-lg tw-font-semibold">Loading Analytics</p>
            <p className="tw-text-slate-500 tw-text-sm">Fetching performance metrics...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tw-min-h-screen tw-bg-gradient-to-br tw-from-slate-950 tw-via-slate-900 tw-to-slate-950 tw-flex tw-items-center tw-justify-center tw-p-6">
        <div className="tw-max-w-md tw-w-full">
          <div className="tw-bg-slate-900/50 tw-backdrop-blur-xl tw-border tw-border-rose-500/30 tw-rounded-2xl tw-p-8 tw-shadow-2xl tw-space-y-6">
            <div className="tw-w-16 tw-h-16 tw-bg-rose-500/10 tw-rounded-full tw-flex tw-items-center tw-justify-center tw-mx-auto">
              <svg className="tw-w-8 tw-h-8 tw-text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="tw-text-center tw-space-y-2">
              <h2 className="tw-text-rose-400 tw-text-xl tw-font-bold">Unable to Load Data</h2>
              <p className="tw-text-slate-300">{error}</p>
            </div>
            <button
              onClick={fetch_performance_data}
              disabled={fetchingData}
              className="tw-w-full tw-px-6 tw-py-3 tw-bg-gradient-to-r tw-from-rose-600 tw-to-rose-500 hover:tw-from-rose-500 hover:tw-to-rose-400 tw-text-white tw-rounded-xl tw-font-semibold tw-transition-all tw-duration-300 tw-shadow-lg hover:tw-shadow-rose-500/25 disabled:tw-opacity-50 disabled:tw-cursor-not-allowed"
            >
              {fetchingData ? 'Retrying...' : 'Retry Connection'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="tw-min-h-screen tw-bg-gradient-to-br tw-from-slate-950 tw-via-slate-900 tw-to-slate-950 tw-text-white">
      {/* Sticky Header */}
      <div className="tw-sticky tw-top-0 tw-z-50 tw-bg-slate-900/80 tw-backdrop-blur-xl tw-border-b tw-border-slate-800/50 tw-shadow-lg">
        <div className="tw-max-w-7xl tw-mx-auto tw-px-4 sm:tw-px-6 tw-py-6">
          <div className="tw-flex tw-flex-col md:tw-flex-row md:tw-items-center md:tw-justify-between tw-gap-4">
            <div>
              <h1 className="tw-text-3xl md:tw-text-4xl tw-font-bold tw-mb-1 tw-bg-gradient-to-r tw-from-cyan-400 tw-via-blue-400 tw-to-purple-400 tw-bg-clip-text tw-text-transparent">
                Performance Analytics
              </h1>
              <p className="tw-text-slate-400 tw-text-sm md:tw-text-base">
                Real-time trading performance and risk analysis
              </p>
            </div>

            <div className="tw-flex tw-items-center tw-gap-4">
              {/* Trading Mode Toggle */}
              <button
                onClick={toggleTradingMode}
                className={`tw-flex tw-items-center tw-gap-2 tw-px-4 tw-py-2 tw-rounded-xl tw-font-bold tw-text-sm tw-transition-all tw-duration-300 ${
                  tradingMode === 'live'
                    ? 'tw-bg-rose-500/20 tw-text-rose-400 tw-border tw-border-rose-500/30 hover:tw-bg-rose-500/30'
                    : 'tw-bg-cyan-500/20 tw-text-cyan-400 tw-border tw-border-cyan-500/30 hover:tw-bg-cyan-500/30'
                }`}
              >
                <div className={`tw-w-2 tw-h-2 tw-rounded-full ${tradingMode === 'live' ? 'tw-bg-rose-500 tw-animate-pulse' : 'tw-bg-cyan-500'}`}></div>
                {tradingMode === 'live' ? 'LIVE DATA' : 'PAPER TRADING'}
              </button>

              <button
                onClick={fetch_performance_data}
                disabled={fetchingData}
                className="tw-px-5 tw-py-2.5 tw-bg-slate-800 hover:tw-bg-slate-700 tw-border tw-border-slate-700 hover:tw-border-cyan-500/50 tw-text-slate-200 tw-rounded-xl tw-font-semibold tw-transition-all tw-duration-200 tw-flex tw-items-center tw-gap-2 tw-self-start disabled:tw-opacity-50 disabled:tw-cursor-not-allowed tw-shadow-lg hover:tw-shadow-cyan-500/10"
              >
                <svg className={`tw-w-5 tw-h-5 ${fetchingData ? 'tw-animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                <span className="tw-hidden sm:tw-inline">{fetchingData ? 'Updating' : 'Refresh'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="tw-max-w-7xl tw-mx-auto tw-px-4 sm:tw-px-6 tw-py-6 tw-space-y-6">
        {/* Timeframe Selector */}
        <div className="tw-bg-slate-900/30 tw-p-2 tw-rounded-2xl tw-border tw-border-slate-800/50">
          <div className="tw-flex tw-flex-wrap tw-gap-2">
            {timeframe_options.map(option => (
              <button
                key={option.value}
                onClick={() => handle_timeframe_change(option.value)}
                disabled={fetchingData}
                className={`tw-px-4 tw-py-2.5 tw-rounded-xl tw-font-semibold tw-text-sm tw-transition-all tw-duration-200 tw-flex tw-items-center tw-gap-2 disabled:tw-opacity-50 disabled:tw-cursor-not-allowed ${
                  timeframe === option.value
                    ? 'tw-bg-gradient-to-r tw-from-cyan-600 tw-to-blue-600 tw-text-white tw-shadow-lg tw-shadow-cyan-500/30 tw-scale-105'
                    : 'tw-bg-slate-800/50 tw-text-slate-300 hover:tw-bg-slate-700/50 hover:tw-text-white hover:tw-scale-105'
                }`}
              >
                <span className="tw-font-mono tw-text-xs tw-opacity-75">{option.icon}</span>
                <span className="tw-hidden sm:tw-inline">{option.label}</span>
              </button>
            ))}
          </div>
        </div>

        {performanceData && (
          <div className="tw-space-y-6">
            {/* Hero Metrics */}
            <div className="tw-grid tw-grid-cols-1 sm:tw-grid-cols-2 lg:tw-grid-cols-4 tw-gap-4">
              {/* Total P&L */}
              <div className={`tw-group tw-relative tw-overflow-hidden tw-rounded-2xl tw-border tw-transition-all tw-duration-300 hover:tw-scale-105 hover:tw-shadow-2xl ${get_bg_color_class(parseFloat(performanceData.total_pnl || 0))}`}>
                <div className="tw-absolute tw-inset-0 tw-bg-gradient-to-br tw-from-slate-800/50 tw-to-slate-900/50"></div>
                <div className="tw-relative tw-p-5">
                  <div className="tw-flex tw-items-center tw-justify-between tw-mb-3">
                    <span className="tw-text-slate-400 tw-text-xs tw-font-semibold tw-uppercase tw-tracking-wider">Total P&L</span>
                    <div className="tw-w-9 tw-h-9 tw-bg-amber-500/10 tw-rounded-lg tw-flex tw-items-center tw-justify-center">
                      <span className="tw-text-amber-400 tw-font-bold tw-text-lg">₹</span>
                    </div>
                  </div>
                  <p className={`tw-text-2xl md:tw-text-3xl tw-font-bold tw-mb-1 ${get_color_class(parseFloat(performanceData.total_pnl || 0))}`}>
                    {format_currency(performanceData.total_pnl)}
                  </p>
                  {performanceData.roi !== undefined && (
                    <div className="tw-flex tw-items-center tw-gap-2">
                      <span className={`tw-text-sm tw-font-semibold ${get_color_class(parseFloat(performanceData.roi || 0))}`}>
                        {format_percentage(performanceData.roi)}
                      </span>
                      <span className="tw-text-slate-500 tw-text-xs">ROI</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Win Rate */}
              <div className="tw-group tw-relative tw-overflow-hidden tw-rounded-2xl tw-border tw-bg-cyan-500/10 tw-border-cyan-500/30 tw-transition-all tw-duration-300 hover:tw-scale-105 hover:tw-shadow-2xl hover:tw-shadow-cyan-500/20">
                <div className="tw-absolute tw-inset-0 tw-bg-gradient-to-br tw-from-slate-800/50 tw-to-slate-900/50"></div>
                <div className="tw-relative tw-p-5">
                  <div className="tw-flex tw-items-center tw-justify-between tw-mb-3">
                    <span className="tw-text-slate-400 tw-text-xs tw-font-semibold tw-uppercase tw-tracking-wider">Win Rate</span>
                    <div className="tw-w-9 tw-h-9 tw-bg-cyan-500/10 tw-rounded-lg tw-flex tw-items-center tw-justify-center">
                      <svg className="tw-w-5 tw-h-5 tw-text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                      </svg>
                    </div>
                  </div>
                  <p className="tw-text-2xl md:tw-text-3xl tw-font-bold tw-text-cyan-400 tw-mb-1">
                    {performanceData.win_rate ? `${performanceData.win_rate.toFixed(1)}%` : '0%'}
                  </p>
                  <div className="tw-flex tw-items-center tw-gap-2 tw-text-xs">
                    <span className="tw-text-emerald-400 tw-font-semibold">{performanceData.winning_trades || 0}W</span>
                    <span className="tw-text-slate-600">/</span>
                    <span className="tw-text-rose-400 tw-font-semibold">{performanceData.losing_trades || 0}L</span>
                  </div>
                </div>
              </div>

              {/* Profit Factor */}
              <div className="tw-group tw-relative tw-overflow-hidden tw-rounded-2xl tw-border tw-bg-emerald-500/10 tw-border-emerald-500/30 tw-transition-all tw-duration-300 hover:tw-scale-105 hover:tw-shadow-2xl hover:tw-shadow-emerald-500/20">
                <div className="tw-absolute tw-inset-0 tw-bg-gradient-to-br tw-from-slate-800/50 tw-to-slate-900/50"></div>
                <div className="tw-relative tw-p-5">
                  <div className="tw-flex tw-items-center tw-justify-between tw-mb-3">
                    <span className="tw-text-slate-400 tw-text-xs tw-font-semibold tw-uppercase tw-tracking-wider">Profit Factor</span>
                    <div className="tw-w-9 tw-h-9 tw-bg-emerald-500/10 tw-rounded-lg tw-flex tw-items-center tw-justify-center">
                      <svg className="tw-w-5 tw-h-5 tw-text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                      </svg>
                    </div>
                  </div>
                  <p className={`tw-text-2xl md:tw-text-3xl tw-font-bold tw-mb-1 ${
                    (performanceData.profit_factor || 0) >= 2 ? 'tw-text-emerald-400' :
                    (performanceData.profit_factor || 0) >= 1.5 ? 'tw-text-cyan-400' :
                    (performanceData.profit_factor || 0) >= 1 ? 'tw-text-amber-400' : 'tw-text-rose-400'
                  }`}>
                    {performanceData.profit_factor ? performanceData.profit_factor.toFixed(2) : '0.00'}
                  </p>
                  <span className={`tw-text-xs tw-font-medium tw-px-2 tw-py-1 tw-rounded-full ${profit_factor_badge.color}`}>
                    {profit_factor_badge.text}
                  </span>
                </div>
              </div>

              {/* Max Drawdown */}
              <div className="tw-group tw-relative tw-overflow-hidden tw-rounded-2xl tw-border tw-bg-rose-500/10 tw-border-rose-500/30 tw-transition-all tw-duration-300 hover:tw-scale-105 hover:tw-shadow-2xl hover:tw-shadow-rose-500/20">
                <div className="tw-absolute tw-inset-0 tw-bg-gradient-to-br tw-from-slate-800/50 tw-to-slate-900/50"></div>
                <div className="tw-relative tw-p-5">
                  <div className="tw-flex tw-items-center tw-justify-between tw-mb-3">
                    <span className="tw-text-slate-400 tw-text-xs tw-font-semibold tw-uppercase tw-tracking-wider">Max Drawdown</span>
                    <div className="tw-w-9 tw-h-9 tw-bg-rose-500/10 tw-rounded-lg tw-flex tw-items-center tw-justify-center">
                      <svg className="tw-w-5 tw-h-5 tw-text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"/>
                      </svg>
                    </div>
                  </div>
                  <p className="tw-text-2xl md:tw-text-3xl tw-font-bold tw-text-rose-400 tw-mb-1">
                    {format_currency(Math.abs(performanceData.max_drawdown || 0))}
                  </p>
                  <span className="tw-text-xs tw-text-slate-500">Risk Exposure</span>
                </div>
              </div>
            </div>

            {/* Detailed Stats */}
            <div className="tw-grid tw-grid-cols-1 lg:tw-grid-cols-2 tw-gap-6">
              {/* Trading Performance */}
              <div className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-xl">
                <div className="tw-flex tw-items-center tw-gap-3 tw-mb-6 tw-pb-4 tw-border-b tw-border-slate-800">
                  <div className="tw-w-10 tw-h-10 tw-bg-gradient-to-br tw-from-cyan-600 tw-to-blue-600 tw-rounded-lg tw-flex tw-items-center tw-justify-center">
                    <svg className="tw-w-5 tw-h-5 tw-text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                  </div>
                  <h2 className="tw-text-xl tw-font-bold tw-text-white">Trading Performance</h2>
                </div>
                <div className="tw-space-y-3">
                  {[
                    { label: 'Total Trades', value: performanceData.total_trades || 0, color: 'tw-text-white' },
                    { label: 'Winning Trades', value: performanceData.winning_trades || 0, color: 'tw-text-emerald-400' },
                    { label: 'Losing Trades', value: performanceData.losing_trades || 0, color: 'tw-text-rose-400' },
                    { label: 'Average Win', value: format_currency(performanceData.avg_win || 0), color: 'tw-text-emerald-400' },
                    { label: 'Average Loss', value: format_currency(performanceData.avg_loss || 0), color: 'tw-text-rose-400' },
                    { label: 'Best Trade', value: format_currency(performanceData.best_trade || 0), color: 'tw-text-emerald-400', highlight: true },
                    { label: 'Worst Trade', value: format_currency(performanceData.worst_trade || 0), color: 'tw-text-rose-400', highlight: true }
                  ].map((item, idx) => (
                    <div
                      key={idx}
                      className={`tw-flex tw-justify-between tw-items-center tw-py-3 tw-px-4 tw-rounded-lg tw-transition-colors ${
                        item.highlight
                          ? `tw-bg-${item.color.includes('emerald') ? 'emerald' : 'rose'}-500/5 tw-border tw-border-${item.color.includes('emerald') ? 'emerald' : 'rose'}-500/20`
                          : 'tw-bg-slate-800/30 hover:tw-bg-slate-800/50'
                      }`}
                    >
                      <span className="tw-text-slate-300 tw-font-medium tw-text-sm">{item.label}</span>
                      <span className={`tw-font-bold ${item.color} tw-text-base`}>{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Financial Metrics */}
              <div className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-xl">
                <div className="tw-flex tw-items-center tw-gap-3 tw-mb-6 tw-pb-4 tw-border-b tw-border-slate-800">
                  <div className="tw-w-10 tw-h-10 tw-bg-gradient-to-br tw-from-purple-600 tw-to-pink-600 tw-rounded-lg tw-flex tw-items-center tw-justify-center">
                    <svg className="tw-w-5 tw-h-5 tw-text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
                    </svg>
                  </div>
                  <h2 className="tw-text-xl tw-font-bold tw-text-white">Financial Metrics</h2>
                </div>
                <div className="tw-space-y-3">
                  {[
                    { label: 'Total Profit', value: format_currency(performanceData.total_profit || 0), color: 'tw-text-emerald-400' },
                    { label: 'Total Loss', value: format_currency(performanceData.total_loss || 0), color: 'tw-text-rose-400' },
                    performanceData.sharpe_ratio !== undefined && { label: 'Sharpe Ratio', value: performanceData.sharpe_ratio.toFixed(2), color: performanceData.sharpe_ratio >= 2 ? 'tw-text-emerald-400' : performanceData.sharpe_ratio >= 1 ? 'tw-text-cyan-400' : 'tw-text-amber-400' },
                    performanceData.roi !== undefined && { label: 'ROI', value: format_percentage(performanceData.roi), color: get_color_class(parseFloat(performanceData.roi || 0)) },
                    { label: 'Expectancy', value: format_currency(performanceData.expectancy || 0), color: get_color_class(parseFloat(performanceData.expectancy || 0)) },
                    performanceData.total_fees !== undefined && { label: 'Total Fees', value: format_currency(performanceData.total_fees || 0), color: 'tw-text-amber-400', highlight: true }
                  ].filter(Boolean).map((item, idx) => (
                    <div
                      key={idx}
                      className={`tw-flex tw-justify-between tw-items-center tw-py-3 tw-px-4 tw-rounded-lg tw-transition-colors ${
                        item.highlight
                          ? 'tw-bg-amber-500/5 tw-border tw-border-amber-500/20'
                          : 'tw-bg-slate-800/30 hover:tw-bg-slate-800/50'
                      }`}
                    >
                      <span className="tw-text-slate-300 tw-font-medium tw-text-sm">{item.label}</span>
                      <span className={`tw-font-bold ${item.color} tw-text-base`}>{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Strategy Performance */}
            {performanceData.strategy_breakdown && performanceData.strategy_breakdown.length > 0 && (
              <div className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-xl">
                <div className="tw-flex tw-items-center tw-gap-3 tw-mb-6 tw-pb-4 tw-border-b tw-border-slate-800">
                  <div className="tw-w-10 tw-h-10 tw-bg-gradient-to-br tw-from-violet-600 tw-to-fuchsia-600 tw-rounded-lg tw-flex tw-items-center tw-justify-center">
                    <svg className="tw-w-5 tw-h-5 tw-text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                  </div>
                  <div>
                    <h2 className="tw-text-xl tw-font-bold tw-text-white">Strategy Performance</h2>
                    <p className="tw-text-xs tw-text-slate-400">ROI & Accuracy by Strategy</p>
                  </div>
                </div>
                <div className="tw-grid tw-grid-cols-1 md:tw-grid-cols-2 lg:tw-grid-cols-3 tw-gap-4">
                  {performanceData.strategy_breakdown.map((strategy, idx) => (
                    <div key={idx} className="tw-bg-slate-800/30 tw-border tw-border-slate-700/50 tw-rounded-xl tw-p-4 tw-transition-all hover:tw-border-violet-500/30 hover:tw-shadow-lg hover:tw-shadow-violet-500/10">
                      <div className="tw-flex tw-justify-between tw-items-start tw-mb-3">
                        <div>
                          <h3 className="tw-font-bold tw-text-white tw-text-base tw-capitalize">{strategy.strategy.replace(/_/g, ' ')}</h3>
                          <span className="tw-text-xs tw-text-slate-500">{strategy.trades_count} Trades</span>
                        </div>
                        <span className={`tw-px-2 tw-py-1 tw-rounded-lg tw-text-xs tw-font-bold ${
                          strategy.total_pnl >= 0 ? 'tw-bg-emerald-500/10 tw-text-emerald-400' : 'tw-bg-rose-500/10 tw-text-rose-400'
                        }`}>
                          {format_currency(strategy.total_pnl)}
                        </span>
                      </div>
                      
                      <div className="tw-grid tw-grid-cols-2 tw-gap-2 tw-mb-3">
                        <div className="tw-bg-slate-900/50 tw-rounded-lg tw-p-2">
                          <p className="tw-text-[10px] tw-text-slate-500 tw-uppercase">Win Rate</p>
                          <p className={`tw-text-sm tw-font-bold ${strategy.win_rate >= 50 ? 'tw-text-emerald-400' : 'tw-text-amber-400'}`}>
                            {strategy.win_rate}%
                          </p>
                        </div>
                        <div className="tw-bg-slate-900/50 tw-rounded-lg tw-p-2">
                          <p className="tw-text-[10px] tw-text-slate-500 tw-uppercase">Avg PnL</p>
                          <p className={`tw-text-sm tw-font-bold ${strategy.avg_pnl >= 0 ? 'tw-text-emerald-400' : 'tw-text-rose-400'}`}>
                            {format_currency(strategy.avg_pnl)}
                          </p>
                        </div>
                      </div>

                      <div className="tw-w-full tw-bg-slate-700/50 tw-rounded-full tw-h-1.5 tw-overflow-hidden">
                        <div 
                          className={`tw-h-full tw-rounded-full ${strategy.win_rate >= 50 ? 'tw-bg-emerald-500' : 'tw-bg-amber-500'}`}
                          style={{ width: `${strategy.win_rate}%` }}
                        ></div>
                      </div>
                      <div className="tw-flex tw-justify-between tw-mt-1">
                        <span className="tw-text-[10px] tw-text-emerald-400">{strategy.wins} Wins</span>
                        <span className="tw-text-[10px] tw-text-rose-400">{strategy.losses} Losses</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Risk Analysis */}
            {performanceData.max_drawdown !== undefined && (
              <div className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-xl">
                <div className="tw-flex tw-items-center tw-gap-3 tw-mb-6 tw-pb-4 tw-border-b tw-border-slate-800">
                  <div className="tw-w-10 tw-h-10 tw-bg-gradient-to-br tw-from-rose-600 tw-to-orange-600 tw-rounded-lg tw-flex tw-items-center tw-justify-center">
                    <svg className="tw-w-5 tw-h-5 tw-text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                    </svg>
                  </div>
                  <h2 className="tw-text-xl tw-font-bold tw-text-white">Risk Analysis</h2>
                </div>
                <div className="tw-grid tw-grid-cols-1 md:tw-grid-cols-3 tw-gap-6">
                  <div className="tw-bg-gradient-to-br tw-from-rose-500/10 tw-to-rose-600/5 tw-border tw-border-rose-500/20 tw-rounded-xl tw-p-5 tw-transition-all hover:tw-border-rose-500/40">
                    <p className="tw-text-slate-400 tw-text-xs tw-font-semibold tw-uppercase tw-tracking-wider tw-mb-3">Maximum Drawdown</p>
                    <p className="tw-text-3xl tw-font-bold tw-text-rose-400 tw-mb-1">
                      {format_currency(Math.abs(performanceData.max_drawdown))}
                    </p>
                    <p className="tw-text-xs tw-text-slate-500">Peak to trough decline</p>
                  </div>
                  <div className="tw-bg-gradient-to-br tw-from-amber-500/10 tw-to-amber-600/5 tw-border tw-border-amber-500/20 tw-rounded-xl tw-p-5 tw-transition-all hover:tw-border-amber-500/40">
                    <p className="tw-text-slate-400 tw-text-xs tw-font-semibold tw-uppercase tw-tracking-wider tw-mb-3">Avg Risk/Trade</p>
                    <p className="tw-text-3xl tw-font-bold tw-text-amber-400 tw-mb-1">
                      {performanceData.total_trades > 0
                        ? format_currency(Math.abs(performanceData.total_loss || 0) / performanceData.total_trades)
                        : format_currency(0)
                      }
                    </p>
                    <p className="tw-text-xs tw-text-slate-500">Per trade exposure</p>
                  </div>
                  <div className="tw-bg-gradient-to-br tw-from-cyan-500/10 tw-to-cyan-600/5 tw-border tw-border-cyan-500/20 tw-rounded-xl tw-p-5 tw-transition-all hover:tw-border-cyan-500/40">
                    <p className="tw-text-slate-400 tw-text-xs tw-font-semibold tw-uppercase tw-tracking-wider tw-mb-3">Risk/Reward</p>
                    <p className="tw-text-3xl tw-font-bold tw-text-cyan-400 tw-mb-1">
                      {performanceData.avg_loss !== 0
                        ? `1:${Math.abs((performanceData.avg_win || 0) / (performanceData.avg_loss || 1)).toFixed(2)}`
                        : 'N/A'
                      }
                    </p>
                    <p className="tw-text-xs tw-text-slate-500">Profit vs loss ratio</p>
                  </div>
                </div>
              </div>
            )}

            {/* Period Info */}
            {performanceData.period_start && performanceData.period_end && (
              <div className="tw-bg-gradient-to-r tw-from-cyan-900/20 tw-to-blue-900/20 tw-border tw-border-cyan-500/30 tw-rounded-2xl tw-p-6">
                <div className="tw-flex tw-items-center tw-gap-4">
                  <div className="tw-w-12 tw-h-12 tw-bg-cyan-500/10 tw-rounded-xl tw-flex tw-items-center tw-justify-center">
                    <svg className="tw-w-6 tw-h-6 tw-text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                    </svg>
                  </div>
                  <div>
                    <p className="tw-font-semibold tw-text-lg tw-text-cyan-300 tw-mb-1">Analysis Period</p>
                    <p className="tw-text-sm tw-text-slate-300">
                      {new Date(performanceData.period_start).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                      {' '}-{' '}
                      {new Date(performanceData.period_end).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* System Health & Insights */}
            {systemHealth && (
              <div className="tw-grid tw-grid-cols-1 lg:tw-grid-cols-3 tw-gap-6">
                {/* Latency & Broker Stats */}
                <div className="tw-space-y-6">
                  {/* Latency */}
                  <div className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-xl">
                    <h2 className="tw-text-lg tw-font-bold tw-text-white tw-mb-4">System Latency</h2>
                    <div className="tw-space-y-4">
                      <div className="tw-flex tw-justify-between tw-items-center">
                        <span className="tw-text-slate-400 tw-text-sm">Signal Gen</span>
                        <span className="tw-text-cyan-400 tw-font-mono tw-font-bold">
                          {systemHealth.latency_metrics?.avg_signal_latency_ms || 0} ms
                        </span>
                      </div>
                      <div className="tw-w-full tw-bg-slate-800 tw-rounded-full tw-h-2">
                        <div 
                          className="tw-bg-cyan-500 tw-h-2 tw-rounded-full" 
                          style={{ width: `${Math.min((systemHealth.latency_metrics?.avg_signal_latency_ms || 0) / 5, 100)}%` }}
                        ></div>
                      </div>
                      
                      <div className="tw-flex tw-justify-between tw-items-center">
                        <span className="tw-text-slate-400 tw-text-sm">Order Exec</span>
                        <span className="tw-text-purple-400 tw-font-mono tw-font-bold">
                          {systemHealth.latency_metrics?.avg_execution_latency_ms || 0} ms
                        </span>
                      </div>
                      <div className="tw-w-full tw-bg-slate-800 tw-rounded-full tw-h-2">
                        <div 
                          className="tw-bg-purple-500 tw-h-2 tw-rounded-full" 
                          style={{ width: `${Math.min((systemHealth.latency_metrics?.avg_execution_latency_ms || 0) / 5, 100)}%` }}
                        ></div>
                      </div>
                    </div>
                  </div>

                  {/* Broker Performance */}
                  <div className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-xl">
                    <h2 className="tw-text-lg tw-font-bold tw-text-white tw-mb-4">Broker Analysis</h2>
                    <div className="tw-space-y-3">
                      {systemHealth.broker_performance?.map((broker, idx) => (
                        <div key={idx} className="tw-flex tw-justify-between tw-items-center tw-p-3 tw-bg-slate-800/30 tw-rounded-lg">
                          <div>
                            <p className="tw-text-white tw-font-semibold tw-text-sm">{broker.broker}</p>
                            <p className="tw-text-slate-500 tw-text-xs">{broker.trades} trades</p>
                          </div>
                          <span className={`tw-font-bold ${get_color_class(broker.pnl)}`}>
                            {format_currency(broker.pnl)}
                          </span>
                        </div>
                      ))}
                      {(!systemHealth.broker_performance || systemHealth.broker_performance.length === 0) && (
                        <p className="tw-text-slate-500 tw-text-sm tw-text-center">No broker data available</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Hourly Distribution Chart */}
                <div className="lg:tw-col-span-2 tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-xl">
                  <h2 className="tw-text-lg tw-font-bold tw-text-white tw-mb-4">Hourly Performance</h2>
                  <div className="tw-h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={systemHealth.hourly_distribution || []}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} vertical={false} />
                        <XAxis dataKey="hour" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                        <YAxis yAxisId="left" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                        <YAxis yAxisId="right" orientation="right" stroke="#94a3b8" tick={{ fontSize: 12 }} hide />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }}
                          cursor={{ fill: '#334155', opacity: 0.2 }}
                        />
                        <Legend />
                        <Bar yAxisId="left" dataKey="wins" name="Wins" fill="#10b981" radius={[4, 4, 0, 0]} stackId="a" />
                        <Bar yAxisId="left" dataKey="trades" name="Total Trades" fill="#3b82f6" radius={[4, 4, 0, 0]} stackId="b" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {/* PnL Chart */}
            <div className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-xl tw-h-96">
              <h2 className="tw-text-xl tw-font-bold tw-text-white tw-mb-4">Cumulative PnL</h2>
              {performanceData.pnl_chart_data && performanceData.pnl_chart_data.length > 0 ? (
                <div className="tw-w-full tw-h-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={performanceData.pnl_chart_data}
                      margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorLoss" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} vertical={false} />
                      <XAxis 
                        dataKey="timestamp" 
                        stroke="#94a3b8" 
                        tick={{ fontSize: 12 }} 
                        tickFormatter={(time) => {
                          const date = new Date(time);
                          if (timeframe === 'daily') {
                            return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' });
                          }
                          return date.toLocaleDateString('en-IN', { month: 'short', day: 'numeric', timeZone: 'Asia/Kolkata' });
                        }}
                        minTickGap={30}
                      />
                      <YAxis 
                        stroke="#94a3b8" 
                        tick={{ fontSize: 12 }}
                        tickFormatter={(value) => `₹${value >= 1000 ? (value/1000).toFixed(1) + 'k' : value}`}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }}
                        itemStyle={{ color: '#f8fafc' }}
                        formatter={(value) => [format_currency(value), 'Cumulative PnL']}
                        labelFormatter={(label) => new Date(label).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                      />
                      <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
                      <Area
                        type="monotone"
                        dataKey="cumulative_pnl"
                        stroke={performanceData.total_pnl >= 0 ? "#10b981" : "#f43f5e"}
                        fillOpacity={1}
                        fill={`url(#${performanceData.total_pnl >= 0 ? 'colorPnl' : 'colorLoss'})`}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="tw-w-full tw-h-full tw-flex tw-items-center tw-justify-center tw-bg-slate-800/20 tw-rounded-xl tw-border tw-border-dashed tw-border-slate-700">
                  <div className="tw-text-center">
                    <svg className="tw-w-10 tw-h-10 tw-text-slate-600 tw-mx-auto tw-mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
                    </svg>
                    <p className="tw-text-slate-500">Not enough data to visualize chart</p>
                  </div>
                </div>
              )}
            </div>

            {/* Daily PnL Chart */}
            {performanceData.daily_breakdown && performanceData.daily_breakdown.length > 0 && (
              <div className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-xl tw-h-96">
                <h2 className="tw-text-xl tw-font-bold tw-text-white tw-mb-4">Daily PnL Analysis</h2>
                <div className="tw-w-full tw-h-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={performanceData.daily_breakdown}
                      margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} vertical={false} />
                      <XAxis 
                        dataKey="date" 
                        stroke="#94a3b8" 
                        tick={{ fontSize: 12 }} 
                        tickFormatter={(time) => new Date(time).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', timeZone: 'Asia/Kolkata' })}
                        minTickGap={30}
                      />
                      <YAxis 
                        stroke="#94a3b8" 
                        tick={{ fontSize: 12 }}
                        tickFormatter={(value) => `₹${value >= 1000 ? (value/1000).toFixed(1) + 'k' : value}`}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }}
                        itemStyle={{ color: '#f8fafc' }}
                        formatter={(value) => [format_currency(value), 'Net PnL']}
                        labelFormatter={(label) => new Date(label).toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Asia/Kolkata' })}
                        cursor={{ fill: '#334155', opacity: 0.2 }}
                      />
                      <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
                      <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                        {performanceData.daily_breakdown.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? '#10b981' : '#f43f5e'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* PnL Heat Map */}
            {performanceData && (
              <div className="tw-mb-6">
                <PnLHeatMap dailyData={performanceData.daily_breakdown || []} startDate={performanceData.period_start} />
              </div>
            )}

            {/* Segment Summary Cards */}
            <div className="tw-grid tw-grid-cols-2 md:tw-grid-cols-4 tw-gap-4">
               {['Equity', 'F&O', 'Currency', 'Commodity'].map((segmentName) => {
                 const segmentData = performanceData.segment_breakdown?.find(
                   s => s.segment?.toUpperCase() === segmentName.toUpperCase()
                 );
                 const pnl = segmentData ? segmentData.total_pnl : 0;
                 return (
                  <div key={segmentName} className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-p-6 tw-shadow-sm">
                    <p className="tw-text-slate-400 tw-text-sm tw-font-semibold tw-mb-2">{segmentName}</p>
                    <p className={`tw-text-xl tw-font-bold ${get_color_class(pnl)}`}>
                      {format_currency(pnl)}
                    </p>
                  </div>
                 );
               })}
            </div>

            {/* Trade Ledger - Real Demat Style */}
            <div className="tw-bg-slate-900/30 tw-backdrop-blur-xl tw-border tw-border-slate-800/50 tw-rounded-2xl tw-overflow-hidden tw-shadow-xl">
              <div className="tw-p-6 tw-border-b tw-border-slate-800 tw-flex tw-flex-col sm:tw-flex-row tw-justify-between tw-items-center tw-gap-4">
                <div>
                  <h2 className="tw-text-xl tw-font-bold tw-text-white">Trade Ledger</h2>
                  <span className="tw-text-xs tw-text-slate-500 tw-uppercase tw-tracking-wider">Statement & Audit Trail</span>
                </div>
                
                <div className="tw-flex tw-flex-wrap tw-items-center tw-gap-3">
                  <div className="tw-flex tw-items-center tw-gap-2 tw-bg-slate-800/50 tw-p-1.5 tw-rounded-xl tw-border tw-border-slate-700">
                    <input 
                      type="date" 
                      value={startDate} 
                      onChange={(e) => setStartDate(e.target.value)}
                      className="tw-bg-transparent tw-text-xs tw-text-white tw-border-none focus:tw-ring-0 tw-p-1"
                    />
                    <span className="tw-text-slate-500">-</span>
                    <input 
                      type="date" 
                      value={endDate} 
                      onChange={(e) => setEndDate(e.target.value)}
                      className="tw-bg-transparent tw-text-xs tw-text-white tw-border-none focus:tw-ring-0 tw-p-1"
                    />
                  </div>
                  
                  <button 
                    onClick={handleExport}
                    disabled={tradeList.length === 0}
                    className="tw-flex tw-items-center tw-gap-2 tw-px-4 tw-py-2 tw-bg-emerald-500/10 tw-text-emerald-400 tw-border tw-border-emerald-500/20 tw-rounded-xl hover:tw-bg-emerald-500/20 tw-transition-all disabled:tw-opacity-50 disabled:tw-cursor-not-allowed"
                  >
                    <svg className="tw-w-4 tw-h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    <span className="tw-text-xs tw-font-bold">Export CSV</span>
                  </button>
                </div>
              </div>

              {/* Mobile View: Trade Cards (Visible only on mobile md:hidden) */}
              <div className="md:tw-hidden tw-p-4 tw-space-y-3">
                {tradeList.length > 0 ? (
                  tradeList.map((trade, idx) => {
                    const grossPnl = trade.gross_pnl || (trade.exit_price - trade.entry_price) * trade.quantity;
                    const charges = trade.gross_pnl && trade.net_pnl 
                      ? trade.gross_pnl - trade.net_pnl 
                      : Math.abs(grossPnl * 0.005); 
                    const netPnl = trade.net_pnl || (grossPnl - charges);
                    const isProfit = netPnl >= 0;
                    const optionType = trade.signal_type?.includes('CE') ? 'CE' : trade.signal_type?.includes('PE') ? 'PE' : 'EQ';
                    const exitType = trade.exit_type || (netPnl > 0 ? 'TARGET' : 'SL');

                    return (
                      <div key={idx} className="tw-bg-slate-900/60 tw-border tw-border-slate-800/80 tw-rounded-xl tw-p-4 tw-space-y-3">
                        <div className="tw-flex tw-items-center tw-justify-between">
                          <div className="tw-flex tw-items-center tw-gap-2">
                            <span className="tw-font-bold tw-text-white tw-text-sm">{trade.symbol}</span>
                            <span className={`tw-px-2 tw-py-0.5 tw-rounded tw-text-[10px] tw-font-bold ${
                              optionType === 'CE' ? 'tw-bg-emerald-500/20 tw-text-emerald-400' : 'tw-bg-rose-500/20 tw-text-rose-400'
                            }`}>
                              {trade.strike_price ? `${trade.strike_price} ${optionType}` : optionType}
                            </span>
                          </div>
                          <span className={`tw-font-bold tw-text-sm ${isProfit ? 'tw-text-emerald-400' : 'tw-text-rose-400'}`}>
                            {format_currency(netPnl)}
                          </span>
                        </div>

                        <div className="tw-grid tw-grid-cols-2 tw-gap-2 tw-text-xs tw-text-slate-400">
                          <div>Buy: <span className="tw-text-slate-200 tw-font-semibold">{format_currency(trade.entry_price)}</span></div>
                          <div>Sell: <span className="tw-text-slate-200 tw-font-semibold">{format_currency(trade.exit_price)}</span></div>
                          <div>Qty: <span className="tw-text-slate-200 tw-font-semibold">{trade.quantity}</span></div>
                          <div>Status: <span className={`tw-font-bold ${isProfit ? 'tw-text-emerald-400' : 'tw-text-rose-400'}`}>{exitType}</span></div>
                        </div>

                        <div className="tw-text-[10px] tw-text-slate-500 tw-flex tw-items-center tw-justify-between tw-pt-2 tw-border-t tw-border-slate-800">
                          <span>{trade.entry_date}</span>
                          <span>{trade.entry_time_str?.split(' ')[0]}</span>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="tw-text-center tw-py-8 tw-text-slate-500 tw-text-xs">No trades found in ledger</div>
                )}
              </div>

              {/* Desktop View: Full Demat Table (Hidden on mobile hidden md:block) */}
              <div className="tw-hidden md:tw-block tw-overflow-x-auto">
                <table className="tw-w-full tw-text-xs md:tw-text-sm tw-text-left">
                  <thead className="tw-text-xs tw-text-slate-400 tw-uppercase tw-bg-slate-800/80">
                    <tr>
                      <th className="tw-px-4 tw-py-3 tw-whitespace-nowrap">Date</th>
                      <th className="tw-px-4 tw-py-3 tw-whitespace-nowrap">Instrument</th>
                      <th className="tw-px-4 tw-py-3 tw-whitespace-nowrap">Strike</th>
                      <th className="tw-px-4 tw-py-3 tw-whitespace-nowrap">Expiry</th>
                      <th className="tw-px-4 tw-py-3 tw-whitespace-nowrap">Type</th>
                      <th className="tw-px-4 tw-py-3 tw-text-right">Qty</th>
                      <th className="tw-px-4 tw-py-3 tw-text-right">Buy Avg</th>
                      <th className="tw-px-4 tw-py-3 tw-text-right">Buy Value</th>
                      <th className="tw-px-4 tw-py-3 tw-text-right">Sell Avg</th>
                      <th className="tw-px-4 tw-py-3 tw-text-right">Sell Value</th>
                      <th className="tw-px-4 tw-py-3 tw-text-right">Net P&L</th>
                      <th className="tw-px-4 tw-py-3 tw-text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="tw-divide-y tw-divide-slate-800">
                    {tradeList.length > 0 ? (
                      tradeList.map((trade, idx) => {
                        const grossPnl = trade.gross_pnl || (trade.exit_price - trade.entry_price) * trade.quantity;
                        const charges = trade.gross_pnl && trade.net_pnl 
                          ? trade.gross_pnl - trade.net_pnl 
                          : Math.abs(grossPnl * 0.005); 
                        const netPnl = trade.net_pnl || (grossPnl - charges);
                        const isProfit = netPnl >= 0;
                        const exitType = trade.exit_type || (netPnl > 0 ? 'TARGET' : 'SL');
                        
                        const buyValue = trade.entry_price * trade.quantity;
                        const sellValue = trade.exit_price * trade.quantity;
                        const pnlPercent = trade.pnl_percentage || (buyValue > 0 ? (netPnl / buyValue) * 100 : 0);
                        
                        // Format Strike Price
                        let strikeDisplay = '-';
                        if (trade.strike_price && trade.strike_price > 0) {
                          const optionType = trade.signal_type?.includes('CE') ? 'CE' : trade.signal_type?.includes('PE') ? 'PE' : '';
                          strikeDisplay = `${trade.strike_price} ${optionType}`;
                        }
                        
                        // Date grouping logic
                        const showDateHeader = idx === 0 || trade.entry_date !== tradeList[idx - 1].entry_date;

                        return (
                          <React.Fragment key={idx}>
                           {showDateHeader && (
                             <tr key={`header-${idx}`} className="tw-bg-slate-800/50">
                               <td colSpan="12" className="tw-px-4 tw-py-2 tw-text-xs tw-font-bold tw-text-cyan-400 tw-uppercase tw-tracking-wider">
                                 {trade.entry_date}
                               </td>
                             </tr>
                           )}
                          <tr className="tw-hover:bg-slate-800/30 tw-transition-colors">
                            <td className="tw-px-4 tw-py-3 tw-text-slate-400 tw-whitespace-nowrap">
                              <div className="tw-text-[10px] tw-text-slate-600">{trade.entry_time_str?.split(' ')[0]}</div>
                            </td>
                            <td className="tw-px-4 tw-py-3">
                              <div className="tw-font-bold tw-text-white">{trade.symbol}</div>
                            </td>
                            <td className="tw-px-4 tw-py-3">
                              <div className="tw-text-slate-300 tw-font-mono">{strikeDisplay}</div>
                            </td>
                            <td className="tw-px-4 tw-py-3">
                              <div className="tw-text-slate-400 tw-text-[10px]">{trade.expiry_date || '-'}</div>
                            </td>
                            <td className="tw-px-4 tw-py-3">
                              <span className={`tw-px-2 tw-py-0.5 tw-rounded tw-text-[10px] tw-font-bold tw-uppercase ${
                                trade.signal_type?.includes('CE') ? 'tw-bg-emerald-500/10 tw-text-emerald-400' : 
                                trade.signal_type?.includes('PE') ? 'tw-bg-rose-500/10 tw-text-rose-400' :
                                'tw-bg-blue-500/10 tw-text-blue-400'
                              }`}>
                                {trade.signal_type?.includes('CE') ? 'CALL' : trade.signal_type?.includes('PE') ? 'PUT' : 'EQUITY'}
                              </span>
                            </td>
                            <td className="tw-px-4 tw-py-3 tw-text-right tw-font-medium tw-text-slate-300">{trade.quantity}</td>
                            <td className="tw-px-4 tw-py-3 tw-text-right tw-text-slate-300">{format_currency(trade.entry_price)}</td>
                            <td className="tw-px-4 tw-py-3 tw-text-right tw-text-slate-400 tw-text-xs">{format_currency(buyValue)}</td>
                            <td className="tw-px-4 tw-py-3 tw-text-right tw-text-slate-300">{format_currency(trade.exit_price)}</td>
                            <td className="tw-px-4 tw-py-3 tw-text-right tw-text-slate-400 tw-text-xs">{format_currency(sellValue)}</td>
                            <td className={`tw-px-4 tw-py-3 tw-text-right tw-font-bold ${isProfit ? 'tw-text-emerald-400' : 'tw-text-rose-400'}`}>
                              <div>{format_currency(netPnl)}</div>
                              <div className="tw-text-[10px] tw-opacity-80">{pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%</div>
                            </td>
                            <td className="tw-px-4 tw-py-3 tw-text-center">
                              <span className={`tw-px-2 tw-py-0.5 tw-rounded tw-text-[10px] tw-font-bold ${
                                exitType === 'TARGET_HIT' ? 'tw-bg-emerald-500/20 tw-text-emerald-300' :
                                exitType === 'SL_HIT' ? 'tw-bg-rose-500/20 tw-text-rose-300' : 'tw-bg-slate-500/20 tw-text-slate-300'
                              }`}>
                                {exitType}
                              </span>
                            </td>
                          </tr>
                          </React.Fragment>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan="12" className="tw-px-6 tw-py-12 tw-text-center tw-text-slate-500">
                          <div className="tw-flex tw-flex-col tw-items-center tw-justify-center">
                            <svg className="tw-w-12 tw-h-12 tw-mb-3 tw-opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                            <p>No trades found in ledger</p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

        )}
      </div>
    </div>
  );
};

export default PerformanceAnalyticsPage;
