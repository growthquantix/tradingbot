import React, { useState, useEffect } from "react";
import {
  Container,
  Paper,
  Typography,
  Box,
  TextField,
  Button,
  Stack,
  Grid,
  CardContent,
  Chip,
  useTheme,
  useMediaQuery,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogContentText,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Slider,
} from "@mui/material";
import {
  PlayArrow,
  Stop,
  TrendingUp,
  AccountBalance,
  ShowChart,
  Speed,
  Settings,
  Warning,
  ExpandMore,
  Security,
  Timeline,
} from "@mui/icons-material";
import apiClient from "../services/api";
import SelectedStocksPanel from "../components/trading/SelectedStocksPanel";


const TradeControlForm = () => {
  const [stockSymbol, setStockSymbol] = useState("");
  const [tradeAmount, setTradeAmount] = useState("");
  const [isTrading, setIsTrading] = useState(false);
  const [showLiveWarning, setShowLiveWarning] = useState(false);
  const [showTradeConfirm, setShowTradeConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedTradingStocks, setSelectedTradingStocks] = useState([]);
  
  // Trading Configuration State
  const [tradingConfig, setTradingConfig] = useState({
    trade_mode: "PAPER",
    default_qty: 1,
    stop_loss_percent: 2.0,
    target_percent: 4.0,
    max_positions: 3,
    risk_per_trade_percent: 1.0,
    default_strategy: "MOMENTUM",
    default_timeframe: "5M",
    option_strategy: "BUY",
    option_expiry_preference: "NEAREST",
    enable_option_trading: true,
    enable_auto_square_off: true,
    enable_bracket_orders: false,
    enable_trailing_stop: false,
    enable_trade_notifications: true,
    enable_profit_loss_alerts: true,
  });

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

  // Load trading config on component mount
  useEffect(() => {
    loadTradingConfig();
  }, []);

  const loadTradingConfig = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get("/config/current");
      if (response.data) {
        setTradingConfig(prev => ({ ...prev, ...response.data }));
      }
    } catch (error) {
      console.error("Error loading trading config:", error);
      // Use default config if API fails
      console.log("Using default trading configuration");
    } finally {
      setLoading(false);
    }
  };

  const saveTradingConfig = async () => {
    try {
      setLoading(true);
      await apiClient.post("/config/save", tradingConfig);
      alert("Trading configuration saved successfully!");
    } catch (error) {
      console.error("Error saving trading config:", error);
      alert("Error saving configuration. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleTradeModeChange = (newMode) => {
    if (newMode === "LIVE" && tradingConfig.trade_mode !== "LIVE") {
      setShowLiveWarning(true);
    } else {
      setTradingConfig({ ...tradingConfig, trade_mode: newMode });
    }
  };

  const confirmLiveMode = () => {
    setTradingConfig({ ...tradingConfig, trade_mode: "LIVE" });
    setShowLiveWarning(false);
  };

  const handleConfigChange = (field, value) => {
    setTradingConfig({ ...tradingConfig, [field]: value });
  };

  const handleStartTrade = () => {
    if (tradingConfig.trade_mode === "LIVE") {
      setShowTradeConfirm(true);
    } else {
      executeTradeStart();
    }
  };

  const executeTradeStart = () => {
    setIsTrading(true);
    console.log(
      "Starting trade for stock:",
      stockSymbol,
      "with amount:",
      tradeAmount,
      "in mode:",
      tradingConfig.trade_mode
    );
    // Simulate trade start
    setTimeout(() => setIsTrading(false), 3000);
  };

  const confirmTradeStart = () => {
    setShowTradeConfirm(false);
    executeTradeStart();
  };

  const handleStopTrade = () => {
    setIsTrading(false);
    console.log("Stopping trade for stock:", stockSymbol);
  };

  // Handle selected stocks from the SelectedStocksPanel
  const handleStocksSelected = (stocks) => {
    setSelectedTradingStocks(stocks);
    console.log("Selected stocks for trading:", stocks);
  };

  // Handle start trading with selected stocks
  const handleStartTradingWithSelectedStocks = async (stocks, mode) => {
    try {
      setLoading(true);
      
      if (mode === "LIVE") {
        // Store selected stocks for later use in confirmation
        setSelectedTradingStocks(stocks);
        setShowLiveWarning(true);
        setLoading(false);
        return;
      }
      
      // Prepare trading request with selected stocks
      const tradingRequest = {
        selected_stocks: stocks.map(stock => ({
          symbol: stock.symbol,
          instrument_key: stock.instrument_key,
          price_at_selection: stock.price_at_selection,
          option_contract: stock.option_contract,
          option_type: stock.option_type,
        })),
        strategy_config: {
          trade_mode: mode,
          default_qty: tradingConfig.default_qty,
          stop_loss_percent: tradingConfig.stop_loss_percent,
          target_percent: tradingConfig.target_percent,
          max_positions: tradingConfig.max_positions,
          option_strategy: tradingConfig.option_strategy,
          enable_option_trading: tradingConfig.enable_option_trading,
        },
        initial_balance: mode === "PAPER" ? 1000000 : 0, // 10L for paper trading
      };

      // Call the appropriate API based on trading mode
      const endpoint = mode === "LIVE" ? "/api/live-trading/start" : "/api/paper-trading/start";
      const response = await apiClient.post(endpoint, tradingRequest);
      
      if (response.data.success) {
        setIsTrading(true);
        alert(`${mode} trading started successfully with ${stocks.length} stocks!`);
      } else {
        alert(`Failed to start ${mode} trading: ${response.data.message}`);
      }
    } catch (error) {
      console.error("Error starting trading:", error);
      alert("Failed to start trading. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Confirm live trading
  const confirmLiveTrading = async () => {
    setShowLiveWarning(false);
    
    try {
      setLoading(true);
      
      // Prepare trading request with selected stocks
      const tradingRequest = {
        selected_stocks: selectedTradingStocks.map(stock => ({
          symbol: stock.symbol,
          instrument_key: stock.instrument_key,
          price_at_selection: stock.price_at_selection,
          option_contract: stock.option_contract,
          option_type: stock.option_type,
        })),
        strategy_config: {
          trade_mode: "LIVE",
          default_qty: tradingConfig.default_qty,
          stop_loss_percent: tradingConfig.stop_loss_percent,
          target_percent: tradingConfig.target_percent,
          max_positions: tradingConfig.max_positions,
          option_strategy: tradingConfig.option_strategy,
          enable_option_trading: tradingConfig.enable_option_trading,
        }
      };

      // Call live trading API
      const response = await apiClient.post("/api/live-trading/start", tradingRequest);
      
      if (response.data.success) {
        setIsTrading(true);
        alert(`LIVE trading started successfully with ${selectedTradingStocks.length} stocks!`);
      } else {
        alert(`Failed to start LIVE trading: ${response.data.message}`);
      }
    } catch (error) {
      console.error("Error starting live trading:", error);
      const errorMessage = error.response?.data?.detail || error.message || "Failed to start live trading";
      alert(`Failed to start LIVE trading: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 2, sm: 3 } }}>
      <Box component="form" noValidate>
        <Grid container spacing={3}>
          {/* Trading Mode Selection - Top Priority */}
          <Grid item xs={12}>
            <Alert 
              severity={tradingConfig.trade_mode === "LIVE" ? "error" : "info"} 
              icon={tradingConfig.trade_mode === "LIVE" ? <Warning /> : <Security />}
              sx={{ mb: 2 }}
            >
              <Typography variant="h6" gutterBottom>
                Current Trading Mode: {tradingConfig.trade_mode}
              </Typography>
              <Typography variant="body2">
                {tradingConfig.trade_mode === "LIVE" 
                  ? "⚠️ LIVE TRADING ACTIVE - Real money transactions will occur!"
                  : tradingConfig.trade_mode === "PAPER" 
                  ? "📊 Paper Trading Mode - Safe for testing strategies"
                  : "🔬 Simulation Mode - Historical data testing"}
              </Typography>
            </Alert>
          </Grid>

          {/* Selected Stocks Panel */}
          <Grid item xs={12}>
            <SelectedStocksPanel
              onStockSelect={handleStocksSelected}
              onStartTrading={handleStartTradingWithSelectedStocks}
              tradingMode={tradingConfig.trade_mode}
              showTradingControls={true}
            />
          </Grid>

          {/* Trade Configuration Section */}
          <Grid item xs={12} md={8}>
            <Card sx={{ borderRadius: 2, boxShadow: theme.shadows[4] }}>
              <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                <Typography
                  variant="h6"
                  gutterBottom
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                    fontSize: { xs: "1.1rem", sm: "1.25rem" },
                  }}
                >
                  <ShowChart color="primary" />
                  Trade Configuration
                </Typography>

                <Stack spacing={{ xs: 2, sm: 3 }}>
                  {/* Trading Mode Selector */}
                  <FormControl fullWidth>
                    <InputLabel>Trading Mode</InputLabel>
                    <Select
                      value={tradingConfig.trade_mode}
                      label="Trading Mode"
                      onChange={(e) => handleTradeModeChange(e.target.value)}
                    >
                      <MenuItem value="PAPER">📊 Paper Trading (Safe)</MenuItem>
                      <MenuItem value="SIMULATION">🔬 Simulation (Historical)</MenuItem>
                      <MenuItem value="LIVE" sx={{ color: 'error.main' }}>
                        ⚠️ LIVE Trading (Real Money)
                      </MenuItem>
                    </Select>
                  </FormControl>

                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Stock Symbol"
                        variant="outlined"
                        fullWidth
                        value={stockSymbol}
                        onChange={(e) => setStockSymbol(e.target.value.toUpperCase())}
                        placeholder="e.g., RELIANCE, INFY, TCS"
                      />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Default Quantity"
                        variant="outlined"
                        type="number"
                        fullWidth
                        value={tradingConfig.default_qty}
                        onChange={(e) => handleConfigChange('default_qty', parseInt(e.target.value))}
                      />
                    </Grid>
                  </Grid>

                  <TextField
                    label="Trade Amount (₹)"
                    variant="outlined"
                    type="number"
                    fullWidth
                    value={tradeAmount}
                    onChange={(e) => setTradeAmount(e.target.value)}
                    placeholder="Enter amount to invest"
                  />

                  {/* Advanced Configuration Accordion */}
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMore />}>
                      <Typography sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Settings /> Advanced Configuration
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Stack spacing={3}>
                        {/* Risk Management */}
                        <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <TrendingDown color="error" /> Risk Management
                        </Typography>
                        
                        <Grid container spacing={2}>
                          <Grid item xs={12} sm={6}>
                            <Typography gutterBottom>Stop Loss: {tradingConfig.stop_loss_percent}%</Typography>
                            <Slider
                              value={tradingConfig.stop_loss_percent}
                              onChange={(_, value) => handleConfigChange('stop_loss_percent', value)}
                              min={0.5}
                              max={10}
                              step={0.5}
                              marks={[{value: 2, label: '2%'}, {value: 5, label: '5%'}]}
                            />
                          </Grid>
                          <Grid item xs={12} sm={6}>
                            <Typography gutterBottom>Target: {tradingConfig.target_percent}%</Typography>
                            <Slider
                              value={tradingConfig.target_percent}
                              onChange={(_, value) => handleConfigChange('target_percent', value)}
                              min={1}
                              max={20}
                              step={0.5}
                              marks={[{value: 4, label: '4%'}, {value: 10, label: '10%'}]}
                            />
                          </Grid>
                        </Grid>

                        <Grid container spacing={2}>
                          <Grid item xs={12} sm={6}>
                            <TextField
                              label="Max Positions"
                              type="number"
                              value={tradingConfig.max_positions}
                              onChange={(e) => handleConfigChange('max_positions', parseInt(e.target.value))}
                              fullWidth
                            />
                          </Grid>
                          <Grid item xs={12} sm={6}>
                            <Typography gutterBottom>Risk per Trade: {tradingConfig.risk_per_trade_percent}%</Typography>
                            <Slider
                              value={tradingConfig.risk_per_trade_percent}
                              onChange={(_, value) => handleConfigChange('risk_per_trade_percent', value)}
                              min={0.5}
                              max={5}
                              step={0.1}
                              marks={[{value: 1, label: '1%'}, {value: 2, label: '2%'}]}
                            />
                          </Grid>
                        </Grid>

                        <Divider />

                        {/* Option Trading Settings */}
                        <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Timeline color="primary" /> Option Trading
                        </Typography>
                        
                        <FormControlLabel
                          control={
                            <Switch
                              checked={tradingConfig.enable_option_trading}
                              onChange={(e) => handleConfigChange('enable_option_trading', e.target.checked)}
                            />
                          }
                          label="Enable Option Trading"
                        />

                        {tradingConfig.enable_option_trading && (
                          <Grid container spacing={2}>
                            <Grid item xs={12} sm={6}>
                              <FormControl fullWidth>
                                <InputLabel>Option Strategy</InputLabel>
                                <Select
                                  value={tradingConfig.option_strategy}
                                  label="Option Strategy"
                                  onChange={(e) => handleConfigChange('option_strategy', e.target.value)}
                                >
                                  <MenuItem value="BUY">Buy Options</MenuItem>
                                  <MenuItem value="SELL">Sell Options</MenuItem>
                                  <MenuItem value="STRADDLE">Straddle</MenuItem>
                                  <MenuItem value="STRANGLE">Strangle</MenuItem>
                                </Select>
                              </FormControl>
                            </Grid>
                            <Grid item xs={12} sm={6}>
                              <FormControl fullWidth>
                                <InputLabel>Expiry Preference</InputLabel>
                                <Select
                                  value={tradingConfig.option_expiry_preference}
                                  label="Expiry Preference"
                                  onChange={(e) => handleConfigChange('option_expiry_preference', e.target.value)}
                                >
                                  <MenuItem value="NEAREST">Nearest Expiry</MenuItem>
                                  <MenuItem value="WEEKLY">Weekly</MenuItem>
                                  <MenuItem value="MONTHLY">Monthly</MenuItem>
                                </Select>
                              </FormControl>
                            </Grid>
                          </Grid>
                        )}

                        <Divider />

                        {/* Advanced Features */}
                        <Typography variant="subtitle1">Advanced Features</Typography>
                        <Grid container spacing={2}>
                          <Grid item xs={12} sm={6}>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={tradingConfig.enable_auto_square_off}
                                  onChange={(e) => handleConfigChange('enable_auto_square_off', e.target.checked)}
                                />
                              }
                              label="Auto Square Off"
                            />
                          </Grid>
                          <Grid item xs={12} sm={6}>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={tradingConfig.enable_bracket_orders}
                                  onChange={(e) => handleConfigChange('enable_bracket_orders', e.target.checked)}
                                />
                              }
                              label="Bracket Orders"
                            />
                          </Grid>
                          <Grid item xs={12} sm={6}>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={tradingConfig.enable_trailing_stop}
                                  onChange={(e) => handleConfigChange('enable_trailing_stop', e.target.checked)}
                                />
                              }
                              label="Trailing Stop Loss"
                            />
                          </Grid>
                          <Grid item xs={12} sm={6}>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={tradingConfig.enable_trade_notifications}
                                  onChange={(e) => handleConfigChange('enable_trade_notifications', e.target.checked)}
                                />
                              }
                              label="Trade Notifications"
                            />
                          </Grid>
                        </Grid>
                      </Stack>
                    </AccordionDetails>
                  </Accordion>

                  {/* Action Buttons */}
                  <Stack spacing={2}>
                    <Button
                      variant="outlined"
                      color="primary"
                      onClick={saveTradingConfig}
                      disabled={loading}
                      startIcon={<Settings />}
                      sx={{ alignSelf: 'flex-start' }}
                    >
                      {loading ? "Saving..." : "Save Configuration"}
                    </Button>

                    <Stack
                      direction={{ xs: "column", sm: "row" }}
                      spacing={{ xs: 1.5, sm: 2 }}
                    >
                      <Button
                        variant="contained"
                        color={tradingConfig.trade_mode === "LIVE" ? "error" : "success"}
                        onClick={handleStartTrade}
                        disabled={!stockSymbol || !tradeAmount || isTrading}
                        startIcon={<PlayArrow />}
                        fullWidth={isMobile}
                        sx={{
                          minHeight: { xs: 48, sm: 52 },
                          fontSize: { xs: "0.9rem", sm: "1rem" },
                          fontWeight: 600,
                        }}
                      >
                        {isTrading ? "Starting..." : 
                         tradingConfig.trade_mode === "LIVE" ? "⚠️ Start LIVE Trade" : "Start Trade"}
                      </Button>

                      <Button
                        variant="outlined"
                        color="error"
                        onClick={handleStopTrade}
                        startIcon={<Stop />}
                        fullWidth={isMobile}
                        sx={{
                          minHeight: { xs: 48, sm: 52 },
                          fontSize: { xs: "0.9rem", sm: "1rem" },
                          fontWeight: 600,
                        }}
                      >
                        Stop Trade
                      </Button>
                    </Stack>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          </Grid>

          {/* Status & Info Section */}
          <Grid item xs={12} md={4}>
            <Stack spacing={2}>
              {/* Trading Status */}
              <Card sx={{ borderRadius: 2, boxShadow: theme.shadows[4] }}>
                <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                  <Typography
                    variant="h6"
                    gutterBottom
                    sx={{
                      fontSize: { xs: "1.1rem", sm: "1.25rem" },
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                    }}
                  >
                    <Speed color="primary" />
                    Trading Status
                  </Typography>

                  <Box sx={{ textAlign: "center", py: 2 }}>
                    <Chip
                      label={isTrading ? "TRADING ACTIVE" : "TRADING IDLE"}
                      color={isTrading ? "success" : "default"}
                      variant={isTrading ? "filled" : "outlined"}
                      sx={{
                        fontSize: { xs: "0.8rem", sm: "0.9rem" },
                        fontWeight: 600,
                        px: 2,
                        py: 0.5,
                      }}
                    />
                    <Box sx={{ mt: 1 }}>
                      <Chip
                        label={`Mode: ${tradingConfig.trade_mode}`}
                        color={tradingConfig.trade_mode === "LIVE" ? "error" : "primary"}
                        size="small"
                        variant="outlined"
                      />
                    </Box>
                  </Box>

                  {stockSymbol && (
                    <Box sx={{ mt: 2 }}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        gutterBottom
                      >
                        Selected Symbol:
                      </Typography>
                      <Typography
                        variant="h6"
                        color="primary.main"
                        sx={{ fontSize: { xs: "1.1rem", sm: "1.25rem" } }}
                      >
                        {stockSymbol}
                      </Typography>
                    </Box>
                  )}

                  {tradeAmount && (
                    <Box sx={{ mt: 2 }}>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        gutterBottom
                      >
                        Trade Amount:
                      </Typography>
                      <Typography
                        variant="h6"
                        color="success.main"
                        sx={{ fontSize: { xs: "1.1rem", sm: "1.25rem" } }}
                      >
                        ₹{Number(tradeAmount).toLocaleString()}
                      </Typography>
                    </Box>
                  )}
                </CardContent>
              </Card>

              {/* Quick Stats */}
              <Card sx={{ borderRadius: 2, boxShadow: theme.shadows[4] }}>
                <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                  <Typography
                    variant="h6"
                    gutterBottom
                    sx={{
                      fontSize: { xs: "1.1rem", sm: "1.25rem" },
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                    }}
                  >
                    <TrendingUp color="primary" />
                    Quick Stats
                  </Typography>

                  <Stack spacing={1.5}>
                    <Box
                      sx={{ display: "flex", justifyContent: "space-between" }}
                    >
                      <Typography variant="body2" color="text.secondary">
                        Active Trades:
                      </Typography>
                      <Typography variant="body2" fontWeight={600}>
                        0
                      </Typography>
                    </Box>

                    <Box
                      sx={{ display: "flex", justifyContent: "space-between" }}
                    >
                      <Typography variant="body2" color="text.secondary">
                        Portfolio Value:
                      </Typography>
                      <Typography
                        variant="body2"
                        fontWeight={600}
                        color="success.main"
                      >
                        ₹0.00
                      </Typography>
                    </Box>

                    <Box
                      sx={{ display: "flex", justifyContent: "space-between" }}
                    >
                      <Typography variant="body2" color="text.secondary">
                        Today's P&L:
                      </Typography>
                      <Typography variant="body2" fontWeight={600}>
                        ₹0.00
                      </Typography>
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
            </Stack>
          </Grid>
        </Grid>

        {/* Mobile-specific alerts and tips */}
        {isMobile && (
          <Alert
            severity="info"
            sx={{ mt: 3, fontSize: "0.875rem" }}
            icon={<AccountBalance />}
          >
            <Typography variant="body2">
              <strong>Mobile Trading Tip:</strong> Ensure stable internet
              connection for real-time trading operations.
            </Typography>
          </Alert>
        )}

        {/* Live Trading Warning Dialog */}
        <Dialog
          open={showLiveWarning}
          onClose={() => setShowLiveWarning(false)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle sx={{ color: 'error.main', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Warning /> ⚠️ LIVE TRADING WARNING
          </DialogTitle>
          <DialogContent>
            <Alert severity="error" sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                🚨 REAL MONEY ALERT 🚨
              </Typography>
            </Alert>
            <DialogContentText>
              <Typography variant="body1" paragraph>
                <strong>You are about to enable LIVE TRADING mode.</strong>
              </Typography>
              <Typography variant="body2" paragraph>
                In LIVE mode:
              </Typography>
              <Box component="ul" sx={{ mt: 1, pl: 2 }}>
                <Typography component="li" variant="body2">💰 <strong>REAL MONEY</strong> will be used for trades</Typography>
                <Typography component="li" variant="body2">📈 Actual buy/sell orders will be placed</Typography>
                <Typography component="li" variant="body2">💸 You can lose money if trades go wrong</Typography>
                <Typography component="li" variant="body2">⚡ Orders execute immediately in the market</Typography>
                <Typography component="li" variant="body2">🔒 No undo option once orders are placed</Typography>
              </Box>
              <Typography variant="body2" sx={{ mt: 2, fontWeight: 'bold', color: 'error.main' }}>
                Are you absolutely sure you want to enable LIVE trading?
              </Typography>
            </DialogContentText>
          </DialogContent>
          <DialogActions sx={{ p: 3 }}>
            <Button 
              onClick={() => setShowLiveWarning(false)} 
              variant="outlined"
              color="primary"
              size="large"
            >
              Cancel (Stay Safe)
            </Button>
            <Button 
              onClick={selectedTradingStocks.length > 0 ? confirmLiveTrading : confirmLiveMode} 
              variant="contained"
              color="error"
              size="large"
              startIcon={<Warning />}
            >
              {selectedTradingStocks.length > 0 ? "Yes, Start LIVE Trading" : "Yes, Enable LIVE Trading"}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Trade Confirmation Dialog for LIVE trading */}
        <Dialog
          open={showTradeConfirm}
          onClose={() => setShowTradeConfirm(false)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle sx={{ color: 'error.main', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Warning /> 🚨 LIVE TRADE CONFIRMATION
          </DialogTitle>
          <DialogContent>
            <Alert severity="error" sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                FINAL WARNING - REAL MONEY TRADE
              </Typography>
            </Alert>
            <DialogContentText>
              <Typography variant="body1" paragraph>
                <strong>You are about to place a LIVE trade with real money!</strong>
              </Typography>
              
              <Box sx={{ bgcolor: 'grey.100', p: 2, borderRadius: 1, mb: 2 }}>
                <Typography variant="body2" gutterBottom><strong>Trade Details:</strong></Typography>
                <Typography variant="body2">• Symbol: <strong>{stockSymbol}</strong></Typography>
                <Typography variant="body2">• Amount: <strong>₹{Number(tradeAmount).toLocaleString()}</strong></Typography>
                <Typography variant="body2">• Mode: <strong style={{color: 'red'}}>LIVE TRADING</strong></Typography>
                <Typography variant="body2">• Quantity: <strong>{tradingConfig.default_qty}</strong></Typography>
              </Box>

              <Typography variant="body2" sx={{ color: 'error.main', fontWeight: 'bold' }}>
                ⚠️ This trade will use REAL MONEY and execute immediately in the market.
                There is NO UNDO once the order is placed!
              </Typography>
            </DialogContentText>
          </DialogContent>
          <DialogActions sx={{ p: 3 }}>
            <Button 
              onClick={() => setShowTradeConfirm(false)} 
              variant="outlined"
              color="primary"
              size="large"
              sx={{ flex: 1 }}
            >
              Cancel Trade
            </Button>
            <Button 
              onClick={confirmTradeStart} 
              variant="contained"
              color="error"
              size="large"
              startIcon={<Warning />}
              sx={{ flex: 1 }}
            >
              Execute LIVE Trade
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  );
};

const TradeControlPage = () => {
  const theme = useTheme();
  // const isMobile = useMediaQuery(theme.breakpoints.down("sm")); // Reserved for responsive features

  return (
    <Container
      maxWidth="lg"
      sx={{
        py: { xs: 2, sm: 3, md: 4 },
        px: { xs: 1, sm: 2 },
      }}
    >
      <Paper
        sx={{
          borderRadius: { xs: 2, sm: 3 },
          overflow: "hidden",
          p: 0,
        }}
      >
        {/* Header Section */}
        <Box
          sx={{
            background: `linear-gradient(135deg, ${theme.palette.primary.main}20, ${theme.palette.secondary.main}10)`,
            p: { xs: 2, sm: 3 },
            borderBottom: `1px solid ${theme.palette.divider}`,
          }}
        >
          <Typography
            variant="h4"
            align="center"
            gutterBottom
            sx={{
              fontSize: { xs: "1.75rem", sm: "2rem", md: "2.5rem" },
              fontWeight: 700,
              background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
              backgroundClip: "text",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              mb: 1,
            }}
          >
            Trade Control Center
          </Typography>

          <Typography
            variant="body1"
            align="center"
            color="text.secondary"
            sx={{
              fontSize: { xs: "0.875rem", sm: "1rem" },
              maxWidth: 600,
              mx: "auto",
            }}
          >
            Manage your automated trading operations with advanced controls and
            real-time monitoring
          </Typography>
        </Box>

        {/* Form Content */}
        <Box sx={{ p: { xs: 2, sm: 3 } }}>
          <TradeControlForm />
        </Box>
      </Paper>
    </Container>
  );
};

export default TradeControlPage;
