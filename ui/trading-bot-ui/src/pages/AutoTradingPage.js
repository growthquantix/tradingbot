import React, { useState, useEffect, useCallback } from "react";
import {
  Box,
  Container,
  Grid,
  Paper,
  Typography,
  Button,
  Chip,
  Stack,
  Tab,
  Tabs,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Card,
  CardContent,
} from "@mui/material";
import {
  TrendingUp,
  TrendingDown,
  Play,
  Square,
  Zap,
  ShieldAlert,
  Activity,
  Layers,
  Clock,
  Plus,
} from "lucide-react";
import api from "../services/api";
import ActivePositionCard from "../components/ActivePositionCard";
import SelectedStockCard from "../components/SelectedStockCard";
import AddFundsModal from "../components/funds/AddFundsModal";

const formatCurrency = (val) => {
  const num = parseFloat(val || 0);
  const formatted = new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(num));
  return `${num < 0 ? "-" : ""}₹${formatted}`;
};

const formatPercent = (val) => {
  const num = parseFloat(val || 0);
  return `${num >= 0 ? "+" : ""}${num.toFixed(2)}%`;
};

const AutoTradingPage = () => {
  const [tradingMode, setTradingMode] = useState("paper");
  const [selectedStocks, setSelectedStocks] = useState([]);
  const [activePositions, setActivePositions] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [pnlSummary, setPnlSummary] = useState({
    total_pnl: 0,
    total_investment: 0,
    pnl_percent: 0,
    active_positions_count: 0,
  });
  const [activeTab, setActiveTab] = useState(0);
  const [emergencyStopLoading, setEmergencyStopLoading] = useState(false);
  const [autoTradingRunning, setAutoTradingRunning] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [showEmergencyModal, setShowEmergencyModal] = useState(false);
  const [isAddFundsOpen, setIsAddFundsOpen] = useState(false);
  const [chartModalSymbol, setChartModalSymbol] = useState(null);

  const [capitalData, setCapitalData] = useState({
    total_available_capital: 100000,
    total_used_margin: 0,
    total_free_margin: 100000,
    capital_utilization_percent: 0,
    trading_mode: "paper",
  });

  const fetchDashboardData = useCallback(async () => {
    try {
      const [stocksRes, posRes, pnlRes, historyRes, capRes, statusRes] =
        await Promise.allSettled([
          api.get("/v1/trading/execution/selected-stocks"),
          api.get("/v1/trading/execution/active-positions"),
          api.get("/v1/trading/execution/pnl-summary"),
          api.get("/v1/trading/execution/trade-history?limit=30"),
          api.get(`/v1/trading/capital/user-summary?trading_mode=${tradingMode}`),
          api.get("/v1/trading/execution/auto-trading-status"),
        ]);

      if (stocksRes.status === "fulfilled") {
        const stocks = stocksRes.value.data?.selected_stocks || stocksRes.value.data || [];
        setSelectedStocks(Array.isArray(stocks) ? stocks : []);
      }
      if (posRes.status === "fulfilled") {
        const positions = posRes.value.data?.active_positions || posRes.value.data || [];
        setActivePositions(Array.isArray(positions) ? positions : []);
      }
      if (pnlRes.status === "fulfilled") {
        setPnlSummary(pnlRes.value.data || {});
      }
      if (historyRes.status === "fulfilled") {
        const hist = historyRes.value.data?.trades || historyRes.value.data || [];
        setTradeHistory(Array.isArray(hist) ? hist : []);
      }
      if (capRes.status === "fulfilled" && capRes.value.data) {
        const cap = capRes.value.data;
        setCapitalData({
          total_available_capital: cap.total_available_capital || cap.current_balance || 100000,
          total_used_margin: cap.total_used_margin || cap.used_margin || 0,
          total_free_margin: cap.total_free_margin || cap.available_margin || 100000,
          capital_utilization_percent: cap.capital_utilization_percent || 0,
          trading_mode: cap.trading_mode || tradingMode,
        });
      }
      if (statusRes.status === "fulfilled") {
        setAutoTradingRunning(Boolean(statusRes.value.data?.is_running));
        setWsConnected(Boolean(statusRes.value.data?.is_running));
      }
    } catch (err) {
      console.error("Dashboard data error:", err);
    }
  }, [tradingMode]);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 4000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  const handleToggleAutoTrading = async () => {
    try {
      const endpoint = autoTradingRunning
        ? "/v1/trading/execution/stop-auto-trading"
        : "/v1/trading/execution/start-auto-trading";
      await api.post(endpoint, { trading_mode: tradingMode });
      setAutoTradingRunning(!autoTradingRunning);
      fetchDashboardData();
    } catch (err) {
      console.error("Toggle error:", err);
    }
  };

  const handleEmergencyExit = async () => {
    setEmergencyStopLoading(true);
    try {
      await api.post("/v1/trading/execution/emergency-exit-all");
      setShowEmergencyModal(false);
      fetchDashboardData();
    } catch (err) {
      console.error("Emergency exit error:", err);
    } finally {
      setEmergencyStopLoading(false);
    }
  };

  const handleManualSquareOff = async (positionId) => {
    try {
      await api.post(`/v1/trading/execution/close-position/${positionId}`);
      fetchDashboardData();
    } catch (err) {
      console.error("Square off error:", err);
    }
  };

  return (
    <Box sx={{ bgcolor: "#0b0f19", minHeight: "100vh", color: "#f8fafc", py: 3, px: { xs: 2, md: 4 } }}>
      <Container maxWidth="xl" disableGutters>
        
        {/* HERO CONTROL HEADER */}
        <Paper
          elevation={0}
          sx={{
            p: { xs: 2.5, md: 3 },
            mb: 3,
            borderRadius: "16px",
            background: "linear-gradient(135deg, rgba(19, 28, 46, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            backdropFilter: "blur(16px)",
          }}
        >
          <Grid container spacing={2} alignItems="center" justifyContent="space-between">
            <Grid item xs={12} md={5}>
              <Stack direction="row" spacing={2} alignItems="center">
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    borderRadius: "12px",
                    background: "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 0 20px rgba(59, 130, 246, 0.35)",
                  }}
                >
                  <Zap size={26} color="#ffffff" />
                </Box>
                <Box>
                  <Stack direction="row" spacing={1.5} alignItems="center">
                    <Typography variant="h5" sx={{ fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em" }}>
                      Auto-Trading Hub
                    </Typography>
                    <Chip
                      icon={<span className="live-pulse-dot" style={{ marginLeft: 6 }} />}
                      label={autoTradingRunning ? "ENGINE LIVE" : "ENGINE IDLE"}
                      size="small"
                      sx={{
                        bgcolor: autoTradingRunning ? "rgba(16, 185, 129, 0.15)" : "rgba(148, 163, 184, 0.15)",
                        color: autoTradingRunning ? "#34d399" : "#94a3b8",
                        border: `1px solid ${autoTradingRunning ? "rgba(16, 185, 129, 0.3)" : "rgba(148, 163, 184, 0.3)"}`,
                        fontWeight: 700,
                        fontSize: "0.75rem",
                      }}
                    />
                  </Stack>
                  <Typography variant="body2" sx={{ color: "#94a3b8", mt: 0.3 }}>
                    SuperTrend + EMA Spot Sentiment Strategy with Real-Time ATM Rolling
                  </Typography>
                </Box>
              </Stack>
            </Grid>

            <Grid item xs={12} md={7}>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={2}
                alignItems={{ xs: "stretch", sm: "center" }}
                justifyContent="flex-end"
              >
                <Box
                  sx={{
                    bgcolor: "rgba(15, 23, 42, 0.8)",
                    p: "4px",
                    borderRadius: "12px",
                    border: "1px solid rgba(51, 65, 85, 0.6)",
                    display: "flex",
                  }}
                >
                  <Button
                    size="small"
                    onClick={() => setTradingMode("paper")}
                    sx={{
                      px: 2,
                      py: 0.8,
                      borderRadius: "9px",
                      fontWeight: 700,
                      fontSize: "0.8rem",
                      bgcolor: tradingMode === "paper" ? "#3b82f6" : "transparent",
                      color: tradingMode === "paper" ? "#ffffff" : "#94a3b8",
                      "&:hover": { bgcolor: tradingMode === "paper" ? "#2563eb" : "rgba(255,255,255,0.05)" },
                    }}
                  >
                    📝 Paper Trading
                  </Button>
                  <Button
                    size="small"
                    onClick={() => setTradingMode("live")}
                    sx={{
                      px: 2,
                      py: 0.8,
                      borderRadius: "9px",
                      fontWeight: 700,
                      fontSize: "0.8rem",
                      bgcolor: tradingMode === "live" ? "#10b981" : "transparent",
                      color: tradingMode === "live" ? "#ffffff" : "#94a3b8",
                      "&:hover": { bgcolor: tradingMode === "live" ? "#059669" : "rgba(255,255,255,0.05)" },
                    }}
                  >
                    ⚡ Live Broker Mode
                  </Button>
                </Box>

                <Button
                  variant="contained"
                  onClick={handleToggleAutoTrading}
                  startIcon={autoTradingRunning ? <Square size={16} /> : <Play size={16} />}
                  sx={{
                    px: 3,
                    py: 1.1,
                    borderRadius: "12px",
                    fontWeight: 700,
                    fontSize: "0.85rem",
                    bgcolor: autoTradingRunning ? "#ef4444" : "#10b981",
                    "&:hover": { bgcolor: autoTradingRunning ? "#dc2626" : "#059669" },
                    boxShadow: autoTradingRunning
                      ? "0 0 15px rgba(239, 68, 68, 0.4)"
                      : "0 0 15px rgba(16, 185, 129, 0.4)",
                  }}
                >
                  {autoTradingRunning ? "Stop Engine" : "Start Auto-Trader"}
                </Button>

                <Button
                  variant="outlined"
                  color="error"
                  onClick={() => setShowEmergencyModal(true)}
                  startIcon={<ShieldAlert size={16} />}
                  sx={{
                    px: 2.5,
                    py: 1.1,
                    borderRadius: "12px",
                    fontWeight: 700,
                    fontSize: "0.85rem",
                    borderColor: "rgba(244, 63, 94, 0.4)",
                    color: "#f43f5e",
                    "&:hover": {
                      bgcolor: "rgba(244, 63, 94, 0.1)",
                      borderColor: "#f43f5e",
                    },
                  }}
                >
                  Emergency Exit
                </Button>
              </Stack>
            </Grid>
          </Grid>
        </Paper>

        {/* METRICS GRID CARDS */}
        <Grid container spacing={2.5} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card
              elevation={0}
              sx={{
                borderRadius: "16px",
                bgcolor: "#131c2e",
                border: `1px solid ${pnlSummary.total_pnl >= 0 ? "rgba(16, 185, 129, 0.3)" : "rgba(244, 63, 94, 0.3)"}`,
              }}
            >
              <CardContent sx={{ p: 2.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                  <Typography variant="caption" sx={{ color: "#94a3b8", fontWeight: 700, textTransform: "uppercase" }}>
                    Today's Net P&L
                  </Typography>
                  <Box
                    sx={{
                      p: 0.8,
                      borderRadius: "8px",
                      bgcolor: pnlSummary.total_pnl >= 0 ? "rgba(16, 185, 129, 0.15)" : "rgba(244, 63, 94, 0.15)",
                      color: pnlSummary.total_pnl >= 0 ? "#34d399" : "#f87171",
                    }}
                  >
                    {pnlSummary.total_pnl >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                  </Box>
                </Stack>
                <Typography
                  variant="h4"
                  sx={{
                    fontWeight: 900,
                    color: pnlSummary.total_pnl >= 0 ? "#10b981" : "#f43f5e",
                    letterSpacing: "-0.03em",
                  }}
                >
                  {formatCurrency(pnlSummary.total_pnl)}
                </Typography>
                <Typography variant="body2" sx={{ color: pnlSummary.total_pnl >= 0 ? "#34d399" : "#f87171", fontWeight: 700, mt: 0.5 }}>
                  {formatPercent(pnlSummary.pnl_percent)} return on capital
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card elevation={0} sx={{ borderRadius: "16px", bgcolor: "#131c2e", border: "1px solid rgba(255, 255, 255, 0.08)" }}>
              <CardContent sx={{ p: 2.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                  <Typography variant="caption" sx={{ color: "#94a3b8", fontWeight: 700, textTransform: "uppercase" }}>
                    Capital Utilization
                  </Typography>
                  <IconButton size="small" onClick={() => setIsAddFundsOpen(true)} sx={{ color: "#3b82f6" }}>
                    <Plus size={18} />
                  </IconButton>
                </Stack>
                <Typography variant="h5" sx={{ fontWeight: 800, color: "#ffffff" }}>
                  {formatCurrency(capitalData.total_free_margin)}
                </Typography>
                <Typography variant="caption" sx={{ color: "#94a3b8", display: "block", mb: 1 }}>
                  Available / {formatCurrency(capitalData.total_available_capital)} Total
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(100, Math.max(0, capitalData.capital_utilization_percent || 0))}
                  sx={{
                    height: 6,
                    borderRadius: 3,
                    bgcolor: "rgba(51, 65, 85, 0.5)",
                    "& .MuiLinearProgress-bar": { bgcolor: "#3b82f6", borderRadius: 3 },
                  }}
                />
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card elevation={0} sx={{ borderRadius: "16px", bgcolor: "#131c2e", border: "1px solid rgba(255, 255, 255, 0.08)" }}>
              <CardContent sx={{ p: 2.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                  <Typography variant="caption" sx={{ color: "#94a3b8", fontWeight: 700, textTransform: "uppercase" }}>
                    Active Positions
                  </Typography>
                  <Box sx={{ p: 0.8, borderRadius: "8px", bgcolor: "rgba(59, 130, 246, 0.15)", color: "#60a5fa" }}>
                    <Layers size={18} />
                  </Box>
                </Stack>
                <Typography variant="h4" sx={{ fontWeight: 900, color: "#ffffff" }}>
                  {activePositions.length} <Typography component="span" variant="body1" sx={{ color: "#94a3b8" }}>/ 5 max</Typography>
                </Typography>
                <Typography variant="body2" sx={{ color: "#94a3b8", mt: 0.5 }}>
                  {selectedStocks.length} Stocks Selected Today
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card elevation={0} sx={{ borderRadius: "16px", bgcolor: "#131c2e", border: "1px solid rgba(255, 255, 255, 0.08)" }}>
              <CardContent sx={{ p: 2.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                  <Typography variant="caption" sx={{ color: "#94a3b8", fontWeight: 700, textTransform: "uppercase" }}>
                    Engine Speed & Feed
                  </Typography>
                  <Box sx={{ p: 0.8, borderRadius: "8px", bgcolor: "rgba(16, 185, 129, 0.15)", color: "#34d399" }}>
                    <Activity size={18} />
                  </Box>
                </Stack>
                <Typography variant="h5" sx={{ fontWeight: 800, color: "#ffffff" }}>
                  {wsConnected ? "Connected" : "Reconnecting..."}
                </Typography>
                <Typography variant="body2" sx={{ color: wsConnected ? "#34d399" : "#f59e0b", fontWeight: 700, mt: 0.5 }}>
                  Upstox WebSocket V3 Feed
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* WORKTAB NAVIGATION */}
        <Paper
          elevation={0}
          sx={{
            borderRadius: "16px",
            bgcolor: "#131c2e",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            overflow: "hidden",
          }}
        >
          <Box sx={{ borderBottom: 1, borderColor: "rgba(51, 65, 85, 0.6)", px: 2, pt: 1 }}>
            <Tabs
              value={activeTab}
              onChange={(e, val) => setActiveTab(val)}
              textColor="primary"
              indicatorColor="primary"
              sx={{
                "& .MuiTab-root": {
                  textTransform: "none",
                  fontWeight: 700,
                  fontSize: "0.9rem",
                  color: "#94a3b8",
                  minHeight: 48,
                  "&.Mui-selected": { color: "#3b82f6" },
                },
              }}
            >
              <Tab label={`Active Positions (${activePositions.length})`} />
              <Tab label={`Selected Stocks Today (${selectedStocks.length})`} />
              <Tab label={`Execution History (${tradeHistory.length})`} />
            </Tabs>
          </Box>

          <Box sx={{ p: { xs: 2, md: 3 } }}>
            {activeTab === 0 && (
              <Box>
                {activePositions.length === 0 ? (
                  <Box sx={{ py: 6, textAlign: "center" }}>
                    <Layers size={40} color="#475569" style={{ marginBottom: 12 }} />
                    <Typography variant="h6" sx={{ color: "#94a3b8", fontWeight: 600 }}>
                      No Active Positions
                    </Typography>
                    <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5 }}>
                      The engine is monitoring the market and will enter trades on strategy signals.
                    </Typography>
                  </Box>
                ) : (
                  <Stack spacing={2}>
                    {activePositions.map((position) => (
                      <ActivePositionCard
                        key={position.position_id || position.id}
                        position={position}
                        onClose={handleManualSquareOff}
                      />
                    ))}
                  </Stack>
                )}
              </Box>
            )}

            {activeTab === 1 && (
              <Box>
                {selectedStocks.length === 0 ? (
                  <Box sx={{ py: 6, textAlign: "center" }}>
                    <Activity size={40} color="#475569" style={{ marginBottom: 12 }} />
                    <Typography variant="h6" sx={{ color: "#94a3b8", fontWeight: 600 }}>
                      No Stocks Selected Yet
                    </Typography>
                    <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5 }}>
                      Automated market scanner runs at 8:30 AM & 9:15 AM to select top liquid options.
                    </Typography>
                  </Box>
                ) : (
                  <Grid container spacing={2}>
                    {selectedStocks.map((stock, idx) => (
                      <Grid item xs={12} md={6} key={stock.symbol || idx}>
                        <SelectedStockCard stock={stock} onOpenChart={(sym) => setChartModalSymbol(sym)} />
                      </Grid>
                    ))}
                  </Grid>
                )}
              </Box>
            )}

            {activeTab === 2 && (
              <Box>
                {tradeHistory.length === 0 ? (
                  <Box sx={{ py: 6, textAlign: "center" }}>
                    <Clock size={40} color="#475569" style={{ marginBottom: 12 }} />
                    <Typography variant="h6" sx={{ color: "#94a3b8", fontWeight: 600 }}>
                      No Trade Executions Today
                    </Typography>
                  </Box>
                ) : (
                  <Stack spacing={1.5}>
                    {tradeHistory.map((trade, idx) => (
                      <Paper
                        key={trade.trade_id || idx}
                        elevation={0}
                        sx={{
                          p: 2,
                          bgcolor: "rgba(15, 23, 42, 0.6)",
                          borderRadius: "12px",
                          border: "1px solid rgba(51, 65, 85, 0.4)",
                        }}
                      >
                        <Grid container alignItems="center" spacing={2}>
                          <Grid item xs={12} sm={3}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 800, color: "#ffffff" }}>
                              {trade.symbol}
                            </Typography>
                            <Chip
                              label={trade.signal_type || "BUY"}
                              size="small"
                              sx={{
                                height: 20,
                                fontSize: "0.7rem",
                                fontWeight: 800,
                                bgcolor: trade.signal_type?.includes("BUY") ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
                                color: trade.signal_type?.includes("BUY") ? "#34d399" : "#f87171",
                              }}
                            />
                          </Grid>
                          <Grid item xs={6} sm={3}>
                            <Typography variant="caption" sx={{ color: "#64748b", display: "block" }}>
                              Entry / Exit Price
                            </Typography>
                            <Typography variant="body2" sx={{ fontWeight: 700, color: "#e2e8f0" }}>
                              ₹{parseFloat(trade.entry_price || 0).toFixed(2)} → ₹{parseFloat(trade.exit_price || trade.current_price || 0).toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={6} sm={3}>
                            <Typography variant="caption" sx={{ color: "#64748b", display: "block" }}>
                              Quantity (Lots)
                            </Typography>
                            <Typography variant="body2" sx={{ fontWeight: 700, color: "#e2e8f0" }}>
                              {trade.quantity} ({trade.lots_traded || Math.round(trade.quantity / (trade.lot_size || 1))} lots)
                            </Typography>
                          </Grid>
                          <Grid item xs={12} sm={3} sx={{ textAlign: { sm: "right" } }}>
                            <Typography
                              variant="subtitle1"
                              sx={{
                                fontWeight: 900,
                                color: (trade.pnl || trade.realized_pnl || 0) >= 0 ? "#10b981" : "#f43f5e",
                              }}
                            >
                              {formatCurrency(trade.pnl || trade.realized_pnl || 0)}
                            </Typography>
                            <Typography variant="caption" sx={{ color: "#64748b" }}>
                              {trade.entry_time ? new Date(trade.entry_time).toLocaleTimeString() : ""}
                            </Typography>
                          </Grid>
                        </Grid>
                      </Paper>
                    ))}
                  </Stack>
                )}
              </Box>
            )}
          </Box>
        </Paper>

        <AddFundsModal
          isOpen={isAddFundsOpen}
          onClose={() => setIsAddFundsOpen(false)}
          onSuccess={fetchDashboardData}
        />

        <Dialog open={showEmergencyModal} onClose={() => setShowEmergencyModal(false)}>
          <DialogTitle sx={{ bgcolor: "#131c2e", color: "#ffffff", fontWeight: 800 }}>
            Confirm Emergency Exit
          </DialogTitle>
          <DialogContent sx={{ bgcolor: "#131c2e", color: "#94a3b8", pt: 2 }}>
            This action will immediately square off ALL active option positions and cancel any pending orders. Are you sure?
          </DialogContent>
          <DialogActions sx={{ bgcolor: "#131c2e", p: 2 }}>
            <Button onClick={() => setShowEmergencyModal(false)} sx={{ color: "#94a3b8" }}>
              Cancel
            </Button>
            <Button
              variant="contained"
              color="error"
              onClick={handleEmergencyExit}
              disabled={emergencyStopLoading}
              sx={{ fontWeight: 700 }}
            >
              {emergencyStopLoading ? "Exiting..." : "Yes, Exit All Now"}
            </Button>
          </DialogActions>
        </Dialog>

        {/* TRADINGVIEW LIVE CHART OVERLAY MODAL */}
        <Dialog
          open={Boolean(chartModalSymbol)}
          onClose={() => setChartModalSymbol(null)}
          maxWidth="lg"
          fullWidth
          PaperProps={{
            sx: {
              bgcolor: "#0b0f19",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              borderRadius: "16px",
              height: "80vh",
            },
          }}
        >
          <DialogTitle sx={{ bgcolor: "#131c2e", color: "#ffffff", fontWeight: 800, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <Activity size={20} color="#3b82f6" />
              <Typography variant="h6" sx={{ fontWeight: 800 }}>
                {chartModalSymbol ? `${chartModalSymbol} Live Spot & Strategy Chart` : "Live Chart"}
              </Typography>
            </Stack>
            <Button size="small" onClick={() => setChartModalSymbol(null)} sx={{ color: "#94a3b8" }}>
              Close ✕
            </Button>
          </DialogTitle>
          <DialogContent sx={{ p: 0, bgcolor: "#0b0f19" }}>
            {chartModalSymbol && (
              <iframe
                title={`${chartModalSymbol} TradingView Chart`}
                src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview_chart&symbol=NSE:${chartModalSymbol}&interval=1&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=0b0f19&theme=dark&style=1&timezone=Asia/Kolkata`}
                style={{ width: "100%", height: "100%", border: "none" }}
              />
            )}
          </DialogContent>
        </Dialog>
      </Container>
    </Box>
  );
};

export default AutoTradingPage;
