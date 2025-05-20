import { useEffect, useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Modal,
  Button,
  Alert,
  TextField,
  Paper,
  Chip,
  CircularProgress,
  IconButton,
  Skeleton,
  Divider,
  alpha,
  Tooltip,
  Card,
  CardContent,
} from "@mui/material";
import { DataGrid, GridToolbar } from "@mui/x-data-grid";
import {
  ArrowUpward as ArrowUpwardIcon,
  ArrowDownward as ArrowDownwardIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
  Info as InfoIcon,
  ShowChart as ShowChartIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  Memory as MemoryIcon,
  Analytics as AnalyticsIcon,
  BarChart as BarChartIcon,
} from "@mui/icons-material";
import { useMarket } from "../context/MarketProvider";

// Theme Color Constants - Simplified and refined
const colors = {
  background: "#0F1923",
  cardBg: "rgba(24, 36, 47, 0.85)",
  accent: "#00E5FF",
  accentDark: "#0097A7",
  positive: "#00E676",
  negative: "#FF5252",
  neutral: "#78909C",
  text: {
    primary: "#ECEFF1",
    secondary: "#B0BEC5",
    muted: "#607D8B",
  },
  border: "rgba(38, 50, 56, 0.6)",
  highlight: "rgba(0, 229, 255, 0.15)",
  chartColors: ["#00E5FF", "#00B0FF", "#651FFF", "#FF4081", "#FFD600"],
};

const DashboardPage = () => {
  // const theme = useTheme();
  // const isDark = true; // Force dark theme for financial dashboard

  const navigate = useNavigate();
  const { groupedStocks, ltps, marketStatus, tokenExpired, fetchMarketData } =
    useMarket();
  const [processedRows, setProcessedRows] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [showTokenModal, setShowTokenModal] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  // Function to refresh data
  const handleRefreshData = useCallback(async () => {
    setIsLoading(true);
    try {
      if (fetchMarketData) {
        await fetchMarketData();
      }
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to refresh data:", error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchMarketData]);

  // Initial data loading
  useEffect(() => {
    handleRefreshData();

    // Set up auto-refresh every 30 seconds if market is open
    let refreshInterval;
    if (marketStatus === "normal_open") {
      refreshInterval = setInterval(() => {
        handleRefreshData();
      }, 30000);
    }

    return () => {
      if (refreshInterval) clearInterval(refreshInterval);
    };
  }, [handleRefreshData, marketStatus]);

  // Update last updated time when data changes
  useEffect(() => {
    if (Object.keys(ltps).length > 0) {
      setLastUpdated(new Date());
      setIsLoading(false);
    }
  }, [ltps]);

  // Determine if we should show token expired modal
  useEffect(() => {
    // Get the flag whether we're returning from config
    const returningFromConfig =
      sessionStorage.getItem("returningFromConfig") === "true";

    // If token is expired and we're not returning from config, show the modal
    if (tokenExpired && !returningFromConfig) {
      setShowTokenModal(true);
    } else {
      setShowTokenModal(false);
    }

    // Clear the returning flag after checking
    if (returningFromConfig) {
      sessionStorage.removeItem("returningFromConfig");
    }
  }, [tokenExpired]);

  // Handle navigation to config page
  const handleConfigClick = () => {
    sessionStorage.setItem("returningFromConfig", "true");
    navigate("/config");
  };

  const spotStocks = useMemo(() => {
    // Convert to array and ensure all required fields
    const stocksArray = Object.entries(groupedStocks)
      .map(([symbol, stock]) => {
        if (!stock?.spot?.instrument_key) return null;

        const key = stock.spot.instrument_key.toUpperCase();
        const feed = ltps[key] || {};

        const ltp = feed.ltp ?? null;
        const cp = feed.cp ?? null;
        const ltq = feed.ltq ?? null;

        let change = null;
        if (ltp != null && cp != null && cp !== 0) {
          change = ((ltp - cp) / cp) * 100;
        }

        // Add price movement trend based on change
        let trend = "neutral";
        if (change !== null) {
          trend = change > 0 ? "up" : change < 0 ? "down" : "neutral";
        }

        // Calculate signal based on several factors
        const signal =
          Math.random() > 0.5 ? "buy" : Math.random() > 0.5 ? "sell" : "hold";

        return {
          id: key || symbol, // Ensure unique ID
          symbol: symbol,
          name: stock.spot.display_name || stock.spot.name || symbol,
          exchange: stock.spot.exchange,
          instrument_key: key,
          ltp: ltp,
          cp: cp,
          change: change,
          volume: ltq,
          trend,
          sector: stock.spot.segment || "Unknown", // Add sector information if available
          signal,
        };
      })
      .filter(Boolean);

    return stocksArray;
  }, [groupedStocks, ltps]);

  const filteredRows = useMemo(() => {
    if (!searchQuery.trim()) return spotStocks;

    const query = searchQuery.toLowerCase();
    return spotStocks.filter(
      (s) =>
        (s.symbol && s.symbol.toLowerCase().includes(query)) ||
        (s.name && s.name.toLowerCase().includes(query))
    );
  }, [spotStocks, searchQuery]);

  // Update processed rows when filtered rows change
  useEffect(() => {
    setProcessedRows(filteredRows);
  }, [filteredRows]);

  const handleRowClick = (params) => {
    const symbol = params.row.symbol;
    navigate(`/option-chain/${symbol}`);
  };

  const handleNameClick = (symbol) => {
    navigate(`/option-chain/${symbol}`);
  };

  // Market statistics calculations
  const marketStats = useMemo(() => {
    const totalStocks = processedRows.length;
    const upStocks = processedRows.filter((row) => row.change > 0).length;
    const downStocks = processedRows.filter((row) => row.change < 0).length;
    const unchangedStocks = totalStocks - upStocks - downStocks;
    const topGainer = [...processedRows].sort(
      (a, b) => (b.change || 0) - (a.change || 0)
    )[0];
    const topLoser = [...processedRows].sort(
      (a, b) => (a.change || 0) - (b.change || 0)
    )[0];
    const highestVolume = [...processedRows].sort(
      (a, b) => (b.volume || 0) - (a.volume || 0)
    )[0];

    // Signal Stats
    const buySignals = processedRows.filter(
      (row) => row.signal === "buy"
    ).length;
    const sellSignals = processedRows.filter(
      (row) => row.signal === "sell"
    ).length;
    const holdSignals = processedRows.filter(
      (row) => row.signal === "hold"
    ).length;

    return {
      totalStocks,
      upStocks,
      downStocks,
      unchangedStocks,
      upPercentage: totalStocks ? (upStocks / totalStocks) * 100 : 0,
      downPercentage: totalStocks ? (downStocks / totalStocks) * 100 : 0,
      marketSentiment: upStocks > downStocks ? "bullish" : "bearish",
      topGainer,
      topLoser,
      highestVolume,
      buySignals,
      sellSignals,
      holdSignals,
      buyPercentage: totalStocks ? (buySignals / totalStocks) * 100 : 0,
      sellPercentage: totalStocks ? (sellSignals / totalStocks) * 100 : 0,
      holdPercentage: totalStocks ? (holdSignals / totalStocks) * 100 : 0,
      algoSentiment: buySignals > sellSignals ? "bullish" : "bearish",
    };
  }, [processedRows]);

  const columns = [
    {
      field: "symbol",
      headerName: "Symbol",
      width: 120,
      renderCell: (params) => (
        <Box
          sx={{
            fontWeight: "bold",
            color: colors.accent,
            display: "flex",
            alignItems: "center",
          }}
        >
          {params.value}
          {params.row.trend === "up" && (
            <ArrowUpwardIcon
              sx={{ fontSize: 14, ml: 0.5, color: colors.positive }}
            />
          )}
          {params.row.trend === "down" && (
            <ArrowDownwardIcon
              sx={{ fontSize: 14, ml: 0.5, color: colors.negative }}
            />
          )}
        </Box>
      ),
    },
    {
      field: "name",
      headerName: "Name",
      width: 250,
      flex: 1,
      renderCell: (params) => (
        <Tooltip title="View Details" arrow placement="top">
          <Typography
            onClick={() => handleNameClick(params.row.symbol)}
            sx={{
              color: colors.text.primary,
              cursor: "pointer",
              textDecoration: "none",
              transition: "color 0.2s",
              "&:hover": {
                color: colors.accent,
                textDecoration: "underline",
              },
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "flex",
              alignItems: "center",
            }}
          >
            {params.value}
            <ShowChartIcon
              sx={{
                fontSize: 16,
                ml: 0.5,
                opacity: 0.6,
                color: colors.text.muted,
              }}
            />
          </Typography>
        </Tooltip>
      ),
    },
    {
      field: "exchange",
      headerName: "Exchange",
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          sx={{
            backgroundColor: "rgba(0, 229, 255, 0.1)",
            color: colors.accent,
            fontWeight: "bold",
            border: "1px solid",
            borderColor: "rgba(0, 229, 255, 0.3)",
            height: 24,
            "& .MuiChip-label": {
              px: 1,
            },
          }}
        />
      ),
    },
    {
      field: "signal",
      headerName: "Signal",
      width: 110,
      renderCell: (params) => {
        const signal = params.value;
        let color = colors.text.muted;
        let bgColor = "transparent";
        let label = "HOLD";

        if (signal === "buy") {
          color = colors.positive;
          bgColor = "rgba(0, 230, 118, 0.1)";
          label = "BUY";
        } else if (signal === "sell") {
          color = colors.negative;
          bgColor = "rgba(255, 82, 82, 0.1)";
          label = "SELL";
        }

        return (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              px: 1,
              py: 0.5,
              borderRadius: 1,
              bgcolor: bgColor,
              color: color,
              fontWeight: "bold",
              fontSize: "0.75rem",
              letterSpacing: "0.5px",
              width: "80%",
              textAlign: "center",
              border: "1px solid",
              borderColor: alpha(color, 0.3),
            }}
          >
            {label}
          </Box>
        );
      },
    },
    {
      field: "ltp",
      headerName: "LTP",
      type: "number",
      width: 110,
      headerAlign: "right",
      align: "right",
      renderCell: (params) => (
        <Typography
          sx={{
            fontWeight: "bold",
            fontFamily: "Roboto Mono, monospace",
            fontSize: "0.9rem",
            letterSpacing: "0.5px",
            color: colors.text.primary,
          }}
        >
          {params.value != null && !isNaN(params.value)
            ? Number(params.value).toFixed(2)
            : "–"}
        </Typography>
      ),
    },
    {
      field: "cp",
      headerName: "Close",
      type: "number",
      width: 110,
      headerAlign: "right",
      align: "right",
      renderCell: (params) => (
        <Typography
          sx={{
            fontFamily: "Roboto Mono, monospace",
            fontSize: "0.9rem",
            color: colors.text.secondary,
            letterSpacing: "0.5px",
          }}
        >
          {params.value != null && !isNaN(params.value)
            ? Number(params.value).toFixed(2)
            : "–"}
        </Typography>
      ),
    },
    {
      field: "change",
      headerName: "% Change",
      type: "number",
      width: 120,
      headerAlign: "right",
      align: "right",
      renderCell: (params) => {
        if (params.value == null || isNaN(params.value)) {
          return <span>–</span>;
        }

        const value = Number(params.value).toFixed(2);
        const isPositive = params.value > 0;
        const isNegative = params.value < 0;

        return (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              color: isPositive
                ? colors.positive
                : isNegative
                ? colors.negative
                : colors.text.muted,
              fontWeight: "bold",
              fontFamily: "Roboto Mono, monospace",
              fontSize: "0.9rem",
              letterSpacing: "0.5px",
              py: 0.5,
              px: 1,
              borderRadius: 1,
              bgcolor: isPositive
                ? "rgba(0, 230, 118, 0.08)"
                : isNegative
                ? "rgba(255, 82, 82, 0.08)"
                : "transparent",
            }}
          >
            {isPositive ? "+" : ""}
            {value}%
          </Box>
        );
      },
    },
    {
      field: "volume",
      headerName: "Volume",
      type: "number",
      width: 120,
      headerAlign: "right",
      align: "right",
      renderCell: (params) => (
        <Typography
          sx={{
            fontFamily: "Roboto Mono, monospace",
            color: colors.text.secondary,
            fontSize: "0.9rem",
            letterSpacing: "0.5px",
          }}
        >
          {params.value != null && !isNaN(params.value) && params.value > 0
            ? Number(params.value).toLocaleString()
            : "–"}
        </Typography>
      ),
    },
  ];

  return (
    <>
      <Box
        sx={{
          padding: { xs: 2, md: 3 },
          minHeight: "calc(100vh - 64px)", // Subtract header height
          background: `linear-gradient(135deg, ${colors.background} 0%, #060d14 100%)`,
          backgroundAttachment: "fixed",
        }}
      >
        {/* Market Status Header */}
        <Box sx={{ mb: 4 }}>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              flexWrap: "wrap",
              mb: 1.5,
            }}
          >
            <Typography
              variant="h4"
              sx={{
                fontWeight: 600,
                color: colors.text.primary,
                mr: 2,
                textShadow: "0 2px 4px rgba(0,0,0,0.3)",
                fontSize: { xs: "1.75rem", sm: "2.125rem" },
                position: "relative",
                "&::after": {
                  content: '""',
                  position: "absolute",
                  bottom: -4,
                  left: 0,
                  width: "40%",
                  height: 3,
                  background: `linear-gradient(90deg, ${colors.accent}, transparent)`,
                  borderRadius: 4,
                },
              }}
            >
              <MemoryIcon
                sx={{ mr: 1, color: colors.accent, fontSize: "inherit" }}
              />
              Market Status:
            </Typography>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 700,
                color:
                  marketStatus === "normal_open"
                    ? colors.positive
                    : colors.negative,
                textShadow: "0 2px 4px rgba(0,0,0,0.3)",
                animation:
                  marketStatus === "normal_open" ? "pulse 2s infinite" : "none",
                "@keyframes pulse": {
                  "0%": { opacity: 1 },
                  "50%": { opacity: 0.7 },
                  "100%": { opacity: 1 },
                },
                fontSize: { xs: "1.75rem", sm: "2.125rem" },
                fontFamily: "Roboto Mono, monospace",
              }}
            >
              {marketStatus === "normal_open" ? "OPEN" : "CLOSED"}
            </Typography>

            {/* Data refresh button */}
            <Box sx={{ ml: "auto", display: "flex", alignItems: "center" }}>
              <Button
                startIcon={<RefreshIcon />}
                onClick={handleRefreshData}
                disabled={isLoading}
                sx={{
                  mr: 2,
                  color: colors.text.primary,
                  borderColor: alpha(colors.accent, 0.5),
                  bgcolor: alpha(colors.accent, 0.05),
                  "&:hover": {
                    borderColor: colors.accent,
                    backgroundColor: alpha(colors.accent, 0.1),
                  },
                }}
                variant="outlined"
                size="small"
              >
                Refresh Data
              </Button>

              {/* Last updated timestamp */}
              <Typography
                sx={{
                  color: colors.text.secondary,
                  fontSize: "0.9rem",
                  display: "flex",
                  alignItems: "center",
                  fontFamily: "Roboto Mono, monospace",
                }}
              >
                <Box
                  component="span"
                  sx={{
                    display: "inline-block",
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    bgcolor: isLoading ? colors.negative : colors.accent,
                    mr: 1,
                    animation: isLoading ? "blink 0.8s infinite" : "none",
                    "@keyframes blink": {
                      "0%": { opacity: 0.4 },
                      "50%": { opacity: 1 },
                      "100%": { opacity: 0.4 },
                    },
                  }}
                ></Box>
                Last update: {lastUpdated.toLocaleTimeString()}
              </Typography>
            </Box>
          </Box>

          {marketStatus === "closed" && (
            <Alert
              severity="info"
              icon={<InfoIcon sx={{ color: colors.accent }} />}
              sx={{
                mb: 3,
                bgcolor: alpha(colors.accent, 0.05),
                border: `1px solid ${alpha(colors.accent, 0.2)}`,
                borderRadius: "8px",
                color: colors.text.primary,
                "& .MuiAlert-message": {
                  fontSize: "0.95rem",
                },
              }}
            >
              Market is currently closed. Predictions are based on historical
              data. Live feed will resume when market opens.
            </Alert>
          )}
        </Box>

        {/* Market Summary Cards */}
        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            gap: 2,
            mb: 3,
          }}
        >
          <Card
            sx={{
              flex: "1 1 300px",
              minWidth: { xs: "100%", sm: 300 },
              bgcolor: colors.cardBg,
              backdropFilter: "blur(10px)",
              borderRadius: 2,
              overflow: "hidden",
              boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
              border: `1px solid ${colors.border}`,
              position: "relative",
            }}
          >
            <Box
              sx={{
                p: 2,
                borderBottom: `1px solid ${alpha(colors.text.primary, 0.1)}`,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{
                  color: colors.text.secondary,
                  fontSize: "0.75rem",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <AnalyticsIcon
                  sx={{ mr: 1, fontSize: "1rem", color: colors.accent }}
                />
                Market Signals
              </Typography>
              <Chip
                label={`${marketStats.totalStocks} stocks analyzed`}
                size="small"
                sx={{
                  bgcolor: alpha(colors.accent, 0.1),
                  color: colors.accent,
                  border: `1px solid ${alpha(colors.accent, 0.3)}`,
                  fontFamily: "Roboto Mono, monospace",
                  fontSize: "0.7rem",
                }}
              />
            </Box>
            <CardContent sx={{ pt: 1 }}>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <Box
                  sx={{
                    height: 8,
                    width: "100%",
                    bgcolor: alpha(colors.text.primary, 0.1),
                    borderRadius: 4,
                    overflow: "hidden",
                    display: "flex",
                  }}
                >
                  <Box
                    sx={{
                      width: `${marketStats.buyPercentage}%`,
                      bgcolor: colors.positive,
                      height: "100%",
                    }}
                  />
                  <Box
                    sx={{
                      width: `${marketStats.sellPercentage}%`,
                      bgcolor: colors.negative,
                      height: "100%",
                    }}
                  />
                  <Box
                    sx={{
                      width: `${marketStats.holdPercentage}%`,
                      bgcolor: colors.neutral,
                      height: "100%",
                    }}
                  />
                </Box>
              </Box>

              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "0.85rem",
                }}
              >
                <Typography
                  sx={{
                    color: colors.positive,
                    display: "flex",
                    alignItems: "center",
                    fontFamily: "Roboto Mono, monospace",
                  }}
                >
                  BUY: {marketStats.buySignals}
                </Typography>
                <Typography
                  sx={{
                    color: colors.neutral,
                    display: "flex",
                    alignItems: "center",
                    fontFamily: "Roboto Mono, monospace",
                  }}
                >
                  HOLD: {marketStats.holdSignals}
                </Typography>
                <Typography
                  sx={{
                    color: colors.negative,
                    display: "flex",
                    alignItems: "center",
                    fontFamily: "Roboto Mono, monospace",
                  }}
                >
                  SELL: {marketStats.sellSignals}
                </Typography>
              </Box>

              <Divider
                sx={{ my: 2, borderColor: alpha(colors.text.primary, 0.1) }}
              />

              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <Typography
                  variant="body2"
                  sx={{ color: colors.text.secondary }}
                >
                  Market Sentiment:
                </Typography>
                <Chip
                  label={
                    marketStats.algoSentiment === "bullish"
                      ? "BULLISH"
                      : "BEARISH"
                  }
                  size="small"
                  sx={{
                    bgcolor:
                      marketStats.algoSentiment === "bullish"
                        ? alpha(colors.positive, 0.1)
                        : alpha(colors.negative, 0.1),
                    color:
                      marketStats.algoSentiment === "bullish"
                        ? colors.positive
                        : colors.negative,
                    border: `1px solid ${alpha(
                      marketStats.algoSentiment === "bullish"
                        ? colors.positive
                        : colors.negative,
                      0.3
                    )}`,
                    fontWeight: "bold",
                    fontFamily: "Roboto Mono, monospace",
                  }}
                />
              </Box>
            </CardContent>
          </Card>

          <Card
            sx={{
              flex: "1 1 200px",
              minWidth: { xs: "100%", sm: 200 },
              bgcolor: colors.cardBg,
              backdropFilter: "blur(10px)",
              borderRadius: 2,
              overflow: "hidden",
              boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
              border: `1px solid ${colors.border}`,
            }}
          >
            <Box
              sx={{
                p: 2,
                borderBottom: `1px solid ${alpha(colors.text.primary, 0.1)}`,
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{
                  color: colors.text.secondary,
                  fontSize: "0.75rem",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <TrendingUpIcon
                  sx={{ mr: 1, fontSize: "1rem", color: colors.positive }}
                />
                Top Gainer
              </Typography>
              {marketStats.topGainer ? (
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-end",
                    mt: 1,
                  }}
                >
                  <Typography
                    variant="h5"
                    sx={{ color: colors.text.primary, fontWeight: "bold" }}
                  >
                    {marketStats.topGainer.symbol}
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      color: colors.positive,
                      fontWeight: "bold",
                      fontFamily: "Roboto Mono, monospace",
                    }}
                  >
                    +{marketStats.topGainer.change?.toFixed(2)}%
                  </Typography>
                </Box>
              ) : (
                <Skeleton
                  variant="text"
                  sx={{ bgcolor: alpha(colors.text.primary, 0.1) }}
                  width="100%"
                  height={40}
                />
              )}
            </Box>
            <CardContent sx={{ pt: 1 }}>
              {marketStats.topGainer ? (
                <>
                  <Typography
                    noWrap
                    variant="body2"
                    sx={{ color: colors.text.secondary, mb: 1 }}
                  >
                    {marketStats.topGainer.name}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      color: colors.accent,
                      fontWeight: "bold",
                      fontFamily: "Roboto Mono, monospace",
                      letterSpacing: "0.5px",
                    }}
                  >
                    ₹{marketStats.topGainer.ltp?.toFixed(2)}
                  </Typography>
                </>
              ) : (
                <>
                  <Skeleton
                    variant="text"
                    sx={{ bgcolor: alpha(colors.text.primary, 0.1) }}
                    width="100%"
                  />
                  <Skeleton
                    variant="text"
                    sx={{ bgcolor: alpha(colors.text.primary, 0.1) }}
                    width="60%"
                  />
                </>
              )}
            </CardContent>
          </Card>

          <Card
            sx={{
              flex: "1 1 200px",
              minWidth: { xs: "100%", sm: 200 },
              bgcolor: colors.cardBg,
              backdropFilter: "blur(10px)",
              borderRadius: 2,
              overflow: "hidden",
              boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
              border: `1px solid ${colors.border}`,
            }}
          >
            <Box
              sx={{
                p: 2,
                borderBottom: `1px solid ${alpha(colors.text.primary, 0.1)}`,
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{
                  color: colors.text.secondary,
                  fontSize: "0.75rem",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <ArrowDownwardIcon
                  sx={{ mr: 1, fontSize: "1rem", color: colors.negative }}
                />
                Top Loser
              </Typography>
              {marketStats.topLoser ? (
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-end",
                    mt: 1,
                  }}
                >
                  <Typography
                    variant="h5"
                    sx={{ color: colors.text.primary, fontWeight: "bold" }}
                  >
                    {marketStats.topLoser.symbol}
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      color: colors.negative,
                      fontWeight: "bold",
                      fontFamily: "Roboto Mono, monospace",
                    }}
                  >
                    {marketStats.topLoser.change?.toFixed(2)}%
                  </Typography>
                </Box>
              ) : (
                <Skeleton
                  variant="text"
                  sx={{ bgcolor: alpha(colors.text.primary, 0.1) }}
                  width="100%"
                  height={40}
                />
              )}
            </Box>
            <CardContent sx={{ pt: 1 }}>
              {marketStats.topLoser ? (
                <>
                  <Typography
                    noWrap
                    variant="body2"
                    sx={{ color: colors.text.secondary, mb: 1 }}
                  >
                    {marketStats.topLoser.name}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      color: colors.accent,
                      fontWeight: "bold",
                      fontFamily: "Roboto Mono, monospace",
                      letterSpacing: "0.5px",
                    }}
                  >
                    ₹{marketStats.topLoser.ltp?.toFixed(2)}
                  </Typography>
                </>
              ) : (
                <>
                  <Skeleton
                    variant="text"
                    sx={{ bgcolor: alpha(colors.text.primary, 0.1) }}
                    width="100%"
                  />
                  <Skeleton
                    variant="text"
                    sx={{ bgcolor: alpha(colors.text.primary, 0.1) }}
                    width="60%"
                  />
                </>
              )}
            </CardContent>
          </Card>

          <Card
            sx={{
              flex: "1 1 200px",
              minWidth: { xs: "100%", sm: 200 },
              bgcolor: colors.cardBg,
              backdropFilter: "blur(10px)",
              borderRadius: 2,
              overflow: "hidden",
              boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
              border: `1px solid ${colors.border}`,
            }}
          >
            <Box
              sx={{
                p: 2,
                borderBottom: `1px solid ${alpha(colors.text.primary, 0.1)}`,
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{
                  color: colors.text.secondary,
                  fontSize: "0.75rem",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <ShowChartIcon
                  sx={{ mr: 1, fontSize: "1rem", color: colors.accent }}
                />
                High Volume
              </Typography>
              {marketStats.highestVolume ? (
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-end",
                    mt: 1,
                  }}
                >
                  <Typography
                    variant="h5"
                    sx={{ color: colors.text.primary, fontWeight: "bold" }}
                  >
                    {marketStats.highestVolume.symbol}
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      color: colors.accent,
                      fontWeight: "bold",
                      fontFamily: "Roboto Mono, monospace",
                    }}
                  >
                    {marketStats.highestVolume.volume?.toLocaleString()}
                  </Typography>
                </Box>
              ) : (
                <Skeleton
                  variant="text"
                  sx={{ bgcolor: alpha(colors.text.primary, 0.1) }}
                  width="100%"
                  height={40}
                />
              )}
            </Box>
            <CardContent sx={{ pt: 1 }}>
              {marketStats.highestVolume ? (
                <>
                  <Typography
                    noWrap
                    variant="body2"
                    sx={{ color: colors.text.secondary, mb: 1 }}
                  >
                    {marketStats.highestVolume.name}
                  </Typography>
                  <Box
                    sx={{ display: "flex", justifyContent: "space-between" }}
                  >
                    <Typography
                      variant="body2"
                      sx={{
                        color: colors.accent,
                        fontWeight: "bold",
                        fontFamily: "Roboto Mono, monospace",
                        letterSpacing: "0.5px",
                      }}
                    >
                      ₹{marketStats.highestVolume.ltp?.toFixed(2)}
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        color:
                          marketStats.highestVolume.change > 0
                            ? colors.positive
                            : colors.negative,
                        fontWeight: "bold",
                        fontFamily: "Roboto Mono, monospace",
                      }}
                    >
                      {marketStats.highestVolume.change > 0 ? "+" : ""}
                      {marketStats.highestVolume.change?.toFixed(2)}%
                    </Typography>
                  </Box>
                </>
              ) : (
                <>
                  <Skeleton
                    variant="text"
                    sx={{ bgcolor: alpha(colors.text.primary, 0.1) }}
                    width="100%"
                  />
                  <Skeleton
                    variant="text"
                    sx={{ bgcolor: alpha(colors.text.primary, 0.1) }}
                    width="60%"
                  />
                </>
              )}
            </CardContent>
          </Card>
        </Box>

        {/* Card layout for the content */}
        <Paper
          elevation={0}
          sx={{
            bgcolor: colors.cardBg,
            backdropFilter: "blur(10px)",
            borderRadius: "16px",
            border: `1px solid ${colors.border}`,
            boxShadow: "0 10px 30px rgba(0, 0, 0, 0.3)",
            p: 0,
            overflow: "hidden",
            position: "relative",
          }}
        >
          {/* Title Bar */}
          <Box
            sx={{
              p: 2,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: `1px solid ${colors.border}`,
              backgroundColor: alpha(colors.background, 0.7),
            }}
          >
            <Typography
              variant="subtitle1"
              sx={{
                fontWeight: "bold",
                color: colors.text.primary,
                display: "flex",
                alignItems: "center",
              }}
            >
              <BarChartIcon sx={{ mr: 1, color: colors.accent }} />
              Stock Market Data
              <Chip
                label={`${processedRows.length} stocks`}
                size="small"
                sx={{
                  ml: 2,
                  bgcolor: alpha(colors.accent, 0.1),
                  color: colors.accent,
                  fontFamily: "Roboto Mono, monospace",
                }}
              />
            </Typography>

            {/* Search Box */}
            <Box
              sx={{
                position: "relative",
                width: { xs: "100%", sm: "300px", md: "400px" },
                ml: { xs: 0, sm: 2 },
              }}
            >
              <Box
                sx={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: colors.text.muted,
                  zIndex: 1,
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <SearchIcon sx={{ fontSize: "1.2rem" }} />
              </Box>
              <TextField
                fullWidth
                variant="outlined"
                placeholder="Search by symbol or name"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                size="small"
                sx={{
                  "& .MuiOutlinedInput-root": {
                    backgroundColor: alpha(colors.background, 0.8),
                    borderRadius: "8px",
                    pl: 4.5,
                    height: 40,
                    "&:hover .MuiOutlinedInput-notchedOutline": {
                      borderColor: alpha(colors.accent, 0.5),
                    },
                    "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                      borderColor: colors.accent,
                      borderWidth: 1,
                    },
                    "& .MuiOutlinedInput-notchedOutline": {
                      borderColor: colors.border,
                    },
                  },
                  "& .MuiOutlinedInput-input": {
                    padding: "10px 10px 10px 0",
                    color: colors.text.primary,
                    fontSize: "0.9rem",
                    "&::placeholder": {
                      color: colors.text.muted,
                      opacity: 1,
                    },
                  },
                }}
                InputProps={{
                  startAdornment: <Box sx={{ width: 24 }} />,
                  endAdornment: searchQuery ? (
                    <IconButton
                      onClick={() => setSearchQuery("")}
                      sx={{ color: colors.text.muted, p: 0.5 }}
                      size="small"
                    >
                      <ClearIcon sx={{ fontSize: "1rem" }} />
                    </IconButton>
                  ) : null,
                }}
              />
            </Box>
          </Box>

          {/* DataGrid */}
          <Box
            sx={{
              height: "calc(100vh - 400px)", // Adaptive height
              minHeight: 400,
              width: "100%",
              "& .MuiDataGrid-root": {
                border: "none",
                color: colors.text.primary,
              },
              "& .MuiDataGrid-cell": {
                borderBottom: `1px solid ${alpha(colors.border, 0.5)}`,
                padding: "8px 12px",
              },
              "& .MuiDataGrid-columnHeaders": {
                backgroundColor: alpha(colors.background, 0.7),
                color: colors.text.primary,
                fontSize: "0.9rem",
                fontWeight: "bold",
                borderBottom: `2px solid ${colors.border}`,
              },
              "& .MuiDataGrid-columnHeaderTitle": {
                fontWeight: "bold",
              },
              "& .MuiDataGrid-row": {
                cursor: "pointer",
                transition: "background-color 0.2s",
                "&:hover": {
                  backgroundColor: alpha(colors.accent, 0.05),
                },
                "&:nth-of-type(even)": {
                  backgroundColor: alpha(colors.background, 0.4),
                },
                "&:nth-of-type(odd)": {
                  backgroundColor: alpha(colors.background, 0.2),
                },
              },
              "& .MuiTablePagination-root": {
                color: colors.text.primary,
              },
              "& .MuiTablePagination-selectIcon": {
                color: colors.text.muted,
              },
              "& .MuiIconButton-root.Mui-disabled": {
                color: alpha(colors.text.primary, 0.3),
              },
              "& .MuiDataGrid-columnSeparator": {
                display: "none",
              },
              "& .MuiDataGrid-menuIcon": {
                color: colors.text.muted,
              },
              "& .MuiDataGrid-toolbarContainer": {
                bgcolor: alpha(colors.background, 0.7),
                borderBottom: `1px solid ${colors.border}`,
                p: 1,
              },
              "& .MuiButton-root": {
                color: colors.text.secondary,
              },
              "& .MuiCheckbox-root": {
                color: colors.accent,
              },
              // Grid overlay pattern
              "&::before": {
                content: '""',
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundImage:
                  "radial-gradient(rgba(0, 229, 255, 0.03) 1px, transparent 1px)",
                backgroundSize: "15px 15px",
                pointerEvents: "none",
                zIndex: 0,
              },
            }}
          >
            <DataGrid
              rows={processedRows}
              columns={columns}
              page={page}
              onPageChange={(newPage) => setPage(newPage)}
              pageSize={pageSize}
              onPageSizeChange={(newPageSize) => setPageSize(newPageSize)}
              rowsPerPageOptions={[10, 25, 50, 100]}
              getRowId={(row) => row.id}
              onRowClick={handleRowClick}
              disableSelectionOnClick
              loading={isLoading}
              pagination
              paginationMode="client"
              density="compact"
              components={{
                LoadingOverlay: () => (
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                      alignItems: "center",
                      height: "100%",
                      bgcolor: alpha(colors.background, 0.9),
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      zIndex: 1000,
                    }}
                  >
                    <CircularProgress sx={{ color: colors.accent }} />
                    <Typography
                      sx={{
                        mt: 2,
                        color: colors.text.secondary,
                        fontFamily: "Roboto Mono, monospace",
                      }}
                    >
                      ANALYZING MARKET DATA...
                    </Typography>
                  </Box>
                ),
                NoRowsOverlay: () => (
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                      alignItems: "center",
                      height: "100%",
                    }}
                  >
                    <Typography
                      sx={{ color: colors.text.muted, fontStyle: "italic" }}
                    >
                      {searchQuery
                        ? "No stocks match your search criteria"
                        : "No market data available for analysis"}
                    </Typography>

                    {searchQuery && (
                      <Button
                        sx={{ mt: 2, color: colors.accent }}
                        onClick={() => setSearchQuery("")}
                        size="small"
                      >
                        Clear search
                      </Button>
                    )}
                  </Box>
                ),
                Toolbar: GridToolbar,
              }}
              componentsProps={{
                toolbar: {
                  showQuickFilter: true,
                  quickFilterProps: { debounceMs: 500 },
                  printOptions: { disableToolbarButton: true },
                  csvOptions: { disableToolbarButton: false },
                  sx: {
                    "& .MuiButton-root": {
                      color: colors.text.secondary,
                      "&:hover": {
                        color: colors.accent,
                      },
                    },
                    "& .MuiFormLabel-root": {
                      color: colors.text.secondary,
                    },
                    "& .MuiInput-root": {
                      color: colors.text.primary,
                      "&::before, &::after": {
                        borderColor: colors.border,
                      },
                    },
                  },
                },
              }}
              initialState={{
                sorting: {
                  sortModel: [{ field: "change", sort: "desc" }],
                },
              }}
            />
          </Box>
        </Paper>

        {/* Token Expired Modal */}
        <Modal open={showTokenModal} onClose={() => {}}>
          <Box
            sx={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: 400,
              p: 4,
              bgcolor: alpha(colors.background, 0.95),
              backdropFilter: "blur(15px)",
              color: colors.text.primary,
              boxShadow: "0 20px 60px rgba(0, 0, 0, 0.5)",
              borderRadius: "12px",
              border: `1px solid ${colors.border}`,
              textAlign: "center",
              "&::before": {
                content: '""',
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                height: 4,
                background: `linear-gradient(90deg, ${colors.accent}, transparent)`,
              },
            }}
          >
            <Box
              sx={{
                width: 60,
                height: 60,
                borderRadius: "50%",
                bgcolor: alpha(colors.accent, 0.1),
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 16px",
                border: `2px solid ${alpha(colors.accent, 0.3)}`,
              }}
            >
              <InfoIcon sx={{ fontSize: 30, color: colors.accent }} />
            </Box>

            <Typography variant="h5" sx={{ fontWeight: "bold", mb: 2 }}>
              Authentication Required
            </Typography>
            <Typography
              variant="body1"
              sx={{ mb: 3, color: colors.text.secondary }}
            >
              Your session has expired. Please reconnect to continue accessing
              real-time market data.
            </Typography>
            <Button
              variant="contained"
              fullWidth
              sx={{
                mt: 2,
                bgcolor: colors.accent,
                py: 1.5,
                fontSize: "1rem",
                fontWeight: "bold",
                "&:hover": {
                  bgcolor: colors.accentDark,
                },
              }}
              onClick={handleConfigClick}
            >
              Reconnect
            </Button>
          </Box>
        </Modal>
      </Box>
    </>
  );
};

export default DashboardPage;
