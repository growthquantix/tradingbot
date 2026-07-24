// pages/DashboardPage.jsx - FULLY RESPONSIVE & REDESIGNED VERSION (SINGLE COLUMN FOR PAIRED SECTIONS)
import React, { useState, useMemo, useCallback, useEffect } from "react";
import {
  useTheme,
  useMediaQuery,
  Box,
  Grid,
  Stack,
  Paper,
  Typography,
  Chip,
  Button,
  Select,
  MenuItem,
  InputBase,
  AppBar,
  Toolbar,
  Container,
  IconButton,
  Card,
  CardContent,
  GlobalStyles,
} from "@mui/material";
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Refresh as RefreshIcon,
  Search as SearchIcon,
  DashboardRounded,
  CategoryRounded,
  TrendingUpRounded,
  ShowChartRounded,
  BoltRounded,
  AccountBalanceRounded,
  CurrencyRupeeRounded,
  ReceiptLongRounded,
  AnalyticsRounded,
  TrendingDownRounded,
  BarChartRounded,
  VerifiedRounded,
  VerticalAlignBottomRounded,
  SettingsSuggestRounded,
} from "@mui/icons-material";
import StocksList from "../components/common/StocksList";
import StocksListOptimized from "../components/common/StocksListOptimized";
import StocksListWithLivePrices from "../components/common/StocksListWithLivePrices";
import TipRanksHeatmap from "../components/common/TipRanksHeatmap";
import FinancialHeatmap from "../components/common/FinancialHeatmap";
import BreakoutAnalysisWidget from "../components/dashboard/BreakoutAnalysisWidget";
import EnhancedBreakoutWidget from "../components/dashboard/EnhancedBreakoutWidget";
import SystemHealthDashboard from "../components/dashboard/SystemHealthDashboard";
import { useMarket } from "../hooks/useUnifiedMarketData";
import useMarketStore from "../store/marketStore";
// PERFORMANCE FIX: Memoized components to prevent unnecessary re-renders
const MemoizedStocksList = React.memo(StocksList);
const MemoizedStocksListOptimized = React.memo(StocksListOptimized);
const MemoizedStocksListWithLivePrices = React.memo(StocksListWithLivePrices);
// MODERN THEME COLORS - Premium "Slate" Design System (Tailwind-inspired)
const DASHBOARD_COLORS = {
  // Dark theme (Slate/Obsidian optimized)
  dark: {
    background: "#0b0f19", // Obsidian Slate - Deep rich background
    surface: "#131c2e",    // Slate Panel - Surface
    surfaceHover: "#1e293b", // Slate 800
    text: "#f8fafc",       // Slate 50 - High contrast
    textSecondary: "#94a3b8", // Slate 400
    positive: "#10b981",   // Emerald 500
    negative: "#f43f5e",   // Rose 500
    neutral: "#f59e0b",    // Amber 500
    primary: "#3b82f6",    // Blue 500
    secondary: "#8b5cf6",  // Violet 500
    accent: "#06b6d4",     // Cyan 500
    border: "#1e293b",     // Slate border
    cardBackground: "#131c2e",
    gradient: "linear-gradient(135deg, #0b0f19 0%, #131c2e 100%)",
    header: "#60a5fa",
  },
  // Light theme
  light: {
    background: "#f8fafc",
    surface: "#ffffff",
    surfaceHover: "#f1f5f9",
    text: "#0f172a",
    textSecondary: "#64748b",
    positive: "#059669",
    negative: "#dc2626",
    neutral: "#d97706",
    primary: "#2563eb",
    secondary: "#7c3aed",
    accent: "#0891b2",
    border: "#e2e8f0",
    cardBackground: "#ffffff",
    gradient: "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)",
    header: "#2563eb",
  },
};
// Section navigation - moved outside component
const SECTIONS = [
  {
    id: "overview",
    label: "OVERVIEW",
    icon: <DashboardRounded fontSize="small" />,
  },
  { id: "search", label: "SEARCH", icon: <SearchIcon fontSize="small" /> },
  {
    id: "sectors",
    label: "SECTORS",
    icon: <CategoryRounded fontSize="small" />,
  },
  {
    id: "movers",
    label: "TOP MOVERS",
    icon: <TrendingUpRounded fontSize="small" />,
  },
  {
    id: "gaps",
    label: "GAP ANALYSIS",
    icon: <ShowChartRounded fontSize="small" />,
  },
  {
    id: "breakouts",
    label: "BREAKOUTS",
    icon: <BoltRounded fontSize="small" />,
  },
  {
    id: "indices",
    label: "INDICES",
    icon: <AccountBalanceRounded fontSize="small" />,
  },
  {
    id: "mcx",
    label: "MCX & F&O",
    icon: <CurrencyRupeeRounded fontSize="small" />,
  },
  {
    id: "fno",
    label: "FNO STOCKS",
    icon: <ReceiptLongRounded fontSize="small" />,
  },
  {
    id: "analytics",
    label: "ANALYTICS",
    icon: <AnalyticsRounded fontSize="small" />,
  },
  {
    id: "system",
    label: "SYSTEM",
    icon: <SettingsSuggestRounded fontSize="small" />,
  },
];
// FIXED: Helper function to safely extract numeric values
const safeNumber = (value, defaultValue = 0) => {
  if (value === null || value === undefined || value === "")
    return defaultValue;
  const num = Number(value);
  return isNaN(num) ? defaultValue : num;
};
// Component for Fixed/Sticky Section Navigation
const SectionNavigation = ({
  activeSection,
  handleSectionChange,
  colors,
  isMobile,
}) => {
  const [isScrolled, setIsScrolled] = React.useState(false);
  const scrollContainerRef = React.useRef(null);

  // Handle scroll effect for sticky header
  React.useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Auto-scroll to active tab
  React.useEffect(() => {
    if (scrollContainerRef.current) {
      const activeButton = scrollContainerRef.current.querySelector(
        `[data-section="${activeSection}"]`
      );
      if (activeButton) {
        activeButton.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
          inline: "center",
        });
      }
    }
  }, [activeSection]);

  return (
    <Box
      sx={{
        position: "sticky",
        top: 0,
        zIndex: 999, // Below header z-index (usually 1100+)
        bgcolor: colors.background + (isScrolled ? "dd" : "00"), // Transparent at top
        backdropFilter: isScrolled ? "blur(12px)" : "none",
        borderBottom: isScrolled ? `1px solid ${colors.border}` : "none",
        transition: "all 0.3s ease",
        pt: isScrolled ? 0 : 1,
      }}
    >
      <Container maxWidth="xl" sx={{ px: { xs: 0, sm: 2 } }}>
        <Box
          sx={{
            py: 1,
            px: { xs: 2, sm: 0 },
            overflowX: "auto",
            scrollbarWidth: "none", // Firefox
            "&::-webkit-scrollbar": { display: "none" }, // Chrome/Safari
            maskImage:
              "linear-gradient(to right, transparent, black 20px, black 90%, transparent)",
            WebkitMaskImage:
              "linear-gradient(to right, transparent, black 20px, black 90%, transparent)",
          }}
          ref={scrollContainerRef}
        >
          <Stack
            direction="row"
            spacing={1}
            sx={{
              width: "max-content",
              mx: "auto", // Center on desktop
              px: 2, // Padding for scroll mask
            }}
          >
            {SECTIONS.map((section) => {
              const isActive = activeSection === section.id;
              return (
                <Button
                  key={section.id}
                  onClick={() => handleSectionChange(section.id)}
                  data-section={section.id}
                  variant={isActive ? "contained" : "text"}
                  sx={{
                    borderRadius: "50px", // Pill shape
                    px: 2.5,
                    py: 0.75,
                    minWidth: "auto",
                    height: 36,
                    fontSize: "0.85rem",
                    fontWeight: isActive ? 600 : 500,
                    textTransform: "none",
                    whiteSpace: "nowrap",
                    color: isActive ? "white" : colors.textSecondary,
                    bgcolor: isActive ? colors.primary : "transparent",
                    boxShadow: isActive
                      ? `0 4px 12px ${colors.primary}40`
                      : "none",
                    border: isActive ? "none" : `1px solid ${colors.border}`,
                    transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                    "&:hover": {
                      bgcolor: isActive ? colors.primary : colors.surfaceHover,
                      color: isActive ? "white" : colors.text,
                      transform: "translateY(-1px)",
                    },
                  }}
                >
                  <span style={{ marginRight: "6px" }}>{section.icon}</span>
                  {section.label}
                </Button>
              );
            })}
          </Stack>
        </Box>
      </Container>
    </Box>
  );
};
const DashboardPage = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isTablet = useMediaQuery(theme.breakpoints.down("md")); // Used for heatmap responsive sizing
  // const isSmallScreen = useMediaQuery(theme.breakpoints.down("md")); // Not used anymore
  // Get current theme colors
  const colors = DASHBOARD_COLORS[theme.palette.mode] || DASHBOARD_COLORS.light;
  const {
    isConnected,
    marketData,
    marketStatus,
    totalStocks,
    sectors,
    topMovers,
    gapAnalysis,
    breakoutAnalysis,
    marketSentiment,
    heatmap,
    volumeAnalysis,
    intradayStocks,
    recordMovers,
    reconnect,
    getStocksBySector,
    searchStocks,
    getMarketSummary,
    indicesData,
    getIndicesByPerformance,
    getMarketSentimentFromIndices,
    getIndicesSummary,
  } = useMarket();

  // ⚡ CRITICAL FIX: Use interval-based refresh instead of subscribing to every update
  // Subscribing to updateCount causes re-renders 20 times/second = freezes UI
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Refresh dashboard data every 2 seconds (smooth, no freeze)
  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshTrigger((prev) => prev + 1);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Calculate derived data only every 2 seconds (not on every price update)
  const zustandTopGainers = useMemo(
    () => useMarketStore.getState().getTopGainers(20),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [refreshTrigger]
  );
  const zustandTopLosers = useMemo(
    () => useMarketStore.getState().getTopLosers(20),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [refreshTrigger]
  );
  const zustandStats = useMemo(
    () => useMarketStore.getState().getStats(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [refreshTrigger]
  );

  // 🔍 DEBUG: Check all data sources (throttled)
  useEffect(() => {
    console.log("📊 DASHBOARD RENDER:", {
      connected: isConnected,
      refreshTrigger,
      zustandStocks: zustandStats.totalSymbols,
      zustandGainers: zustandTopGainers.length,
      zustandLosers: zustandTopLosers.length,
      wsTopMoversGainers: topMovers?.gainers?.length || 0,
      wsTopMoversLosers: topMovers?.losers?.length || 0,
      indicesCount: indicesData?.indices?.length || 0,
      majorIndicesCount: indicesData?.major_indices?.length || 0,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  const [activeSection, setActiveSection] = useState("overview");
  const [expandedSection, setExpandedSection] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSector, setSelectedSector] = useState("ALL");
  const [fnoStockList, setFnoStockList] = useState({
    securities: [],
    total_count: 0,
  });
  const [fnoLoading, setFnoLoading] = useState(false);

  // Gap Analysis state
  const [gapAnalysisData, setGapAnalysisData] = useState({
    gap_up: [],
    gap_down: [],
    summary: null,
  });
  const [gapLoading, setGapLoading] = useState(false);
  const gapLoadingRef = React.useRef(false); // Ref to prevent race conditions/loops

  // REMOVED: Using Material-UI useMediaQuery for responsive detection

  // Fetch Gap Analysis data from API
  const fetchGapAnalysis = useCallback(async () => {
    if (gapLoadingRef.current) return;
    
    gapLoadingRef.current = true;
    setGapLoading(true);
    
    try {
      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/api/analytics/gap-analysis`
      );
      const data = await response.json();
      if (data.success && data.data) {
        setGapAnalysisData({
          gap_up: data.data.gap_up || [],
          gap_down: data.data.gap_down || [],
          summary: data.data.summary || null,
        });
        console.log(
          "Gap analysis loaded:",
          data.data.gap_up?.length || 0,
          "gap up,",
          data.data.gap_down?.length || 0,
          "gap down"
        );
      }
    } catch (error) {
      console.error("Failed to fetch gap analysis:", error);
    } finally {
      gapLoadingRef.current = false;
      setGapLoading(false);
    }
  }, []);

  // Fetch FNO stocks from API
  const fetchFnoStocks = useCallback(async () => {
    if (fnoLoading) return;
    setFnoLoading(true);
    try {
      // Use categorized=true for better data organization
      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/api/instruments/fno-stocks?categorized=true`
      );
      const data = await response.json();
      
      // Handle categorized data structure
      if (data.success && data.data) {
        const securities = [
          ...(data.data.indices || []),
          ...(data.data.stocks || [])
        ];
        
        setFnoStockList({
          securities: securities,
          total_count: data.data.metadata?.total_count || securities.length,
        });
      } else if (data.success && data.stocks) {
        // Fallback for flat structure
        setFnoStockList({
          securities: data.stocks,
          total_count: data.count || data.stocks.length,
        });
      }
    } catch (error) {
      console.error("Failed to fetch FNO stocks:", error);
    } finally {
      setFnoLoading(false);
    }
  }, [fnoLoading]);
  // Load Gap Analysis when gaps section is accessed
  useEffect(() => {
    if (activeSection === "gaps") {
        // Only fetch if we haven't loaded data yet (or if it's empty)
        // AND we aren't currently loading
        if (gapAnalysisData.gap_up.length === 0 && !gapLoadingRef.current) {
            fetchGapAnalysis();
        }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSection, fetchGapAnalysis]); // Removed data length dependencies to prevent loops

  // Load FNO stocks when component mounts or when FNO section is accessed
  useEffect(() => {
    if (activeSection === "fno" && fnoStockList.securities.length === 0) {
      fetchFnoStocks();
    }
  }, [activeSection, fetchFnoStocks, fnoStockList.securities.length]);
  // ⚡ FIX: Call functions directly without useMemo to avoid infinite dependency loops
  // These functions are already memoized inside useMarket hook
  const marketSummary = getMarketSummary();
  const searchResults = searchQuery.trim() ? searchStocks(searchQuery) : [];
  const sectorStocks =
    selectedSector === "ALL"
      ? Object.values(marketData || {})
      : getStocksBySector()[selectedSector] || [];
  const indicesSummary = getIndicesSummary();
  const indicesPerformance = getIndicesByPerformance();
  const indicesSentiment = getMarketSentimentFromIndices();

  // ⚡ PERFORMANCE FIX: Use Zustand store functions directly (no dependency on full state)
  const getRealTimeTopMovers = useCallback(() => {
    // Use Zustand store functions directly (already optimized)
    const gainers = useMarketStore.getState().getTopGainers(20);
    const losers = useMarketStore.getState().getTopLosers(20);

    console.log("🚀 getRealTimeTopMovers:", {
      gainers: gainers.length,
      losers: losers.length,
    });

    return {
      gainers: gainers.map((g) => g.symbol),
      losers: losers.map((l) => l.symbol),
    };
  }, []); // No dependencies - stable function

  // ⚡ CRITICAL FIX: Get live indices data with multiple key lookups
  const getEnhancedIndicesData = useCallback((indicesArray) => {
    return indicesArray.map((index) => {
      const symbol = index.symbol || index.name;
      const instrumentKey = index.instrument_key;

      // Try multiple keys to find live price
      const store = useMarketStore.getState();
      let livePrice = null;

      // Try: instrument_key, symbol, compact symbol, name
      if (instrumentKey) {
        livePrice = store.prices[instrumentKey];
      }
      if (!livePrice && symbol) {
        livePrice = store.prices[symbol];
      }
      if (!livePrice && symbol) {
        // Try compact symbol (BANKNIFTY, NIFTY, etc.)
        const compactSymbol = symbol.toUpperCase().replace(/[\s_-]+/g, "");
        livePrice = store.prices[compactSymbol];
      }

      if (livePrice) {
        console.log(`✅ Found live price for ${symbol}:`, livePrice.ltp);
        return {
          ...index,
          last_price: livePrice.ltp,
          ltp: livePrice.ltp,
          current_price: livePrice.ltp,
          change: livePrice.change,
          change_percent: livePrice.change_percent,
          volume: livePrice.volume,
          high: livePrice.high,
          low: livePrice.low,
          open: livePrice.open,
          _live_data_available: true,
          _source: "zustand_realtime",
        };
      }

      console.log(
        `⚠️ No live price found for ${symbol} (tried: ${instrumentKey}, ${symbol})`
      );
      // Return original data if no live data
      return {
        ...index,
        _live_data_available: false,
        _source: "analytics_static",
      };
    });
  }, []); // No dependencies - stable function

  // Helper function to identify indices
  const isIndexSymbol = useCallback((symbol, name) => {
    if (!symbol && !name) return false;
    const symbolLower = (symbol || "").toLowerCase();
    const nameLower = (name || "").toLowerCase();
    // Common index identifiers
    const indexKeywords = [
      "nifty",
      "sensex",
      "banknifty",
      "finnifty",
      "midcpnifty",
      "index",
    ];
    return (
      indexKeywords.some(
        (keyword) =>
          symbolLower.includes(keyword) || nameLower.includes(keyword)
      ) || symbolLower.match(/^(nifty|sensex|banknifty|finnifty|midcpnifty)/)
    );
  }, []);
  // ENHANCED: Memoized FNO stocks processing with proper sector mapping and live data integration
  const fnoStocksData = useMemo(() => {
    const processedStocks = fnoStockList.securities.map((stock, index) => {
      const symbol = stock.symbol;
      const instrumentKey = `${stock.exchange || "NSE"}|${symbol}`;

      // Get sector mapping from marketData or use a basic sector mapping
      let sector = "F&O"; // Default fallback

      // Try to get sector from live market data first
      const liveDataKey = Object.keys(marketData || {}).find(
        (key) =>
          key.includes(symbol) ||
          key.toLowerCase().includes(symbol.toLowerCase()) ||
          key.endsWith(`|${symbol}`) ||
          marketData[key]?.symbol === symbol ||
          marketData[key]?.trading_symbol === symbol
      );

      if (liveDataKey && marketData[liveDataKey]?.sector) {
        sector = marketData[liveDataKey].sector;
      } else {
        // Basic sector mapping for common FNO stocks
        const symbolUpper = symbol.toUpperCase();
        if (
          [
            "NIFTY",
            "BANKNIFTY",
            "FINNIFTY",
            "MIDCPNIFTY",
            "NIFTY-NEXT50",
          ].includes(symbolUpper)
        ) {
          sector = "INDEX";
        } else if (
          [
            "HDFCBANK",
            "SBIN",
            "ICICIBANK",
            "KOTAKBANK",
            "AXISBANK",
            "INDUSINDBK",
          ].includes(symbolUpper)
        ) {
          sector = "BANKING";
        } else if (
          ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM"].includes(
            symbolUpper
          )
        ) {
          sector = "IT";
        } else if (
          ["RELIANCE", "ONGC", "BPCL", "IOC", "POWERGRID", "NTPC"].includes(
            symbolUpper
          )
        ) {
          sector = "ENERGY";
        } else if (
          [
            "MARUTI",
            "TATAMOTORS",
            "M&M",
            "EICHERMOT",
            "BAJAJ-AUTO",
            "HEROMOTOCO",
          ].includes(symbolUpper)
        ) {
          sector = "AUTO";
        } else if (
          [
            "SUNPHARMA",
            "DRREDDY",
            "CIPLA",
            "DIVISLAB",
            "LUPIN",
            "BIOCON",
          ].includes(symbolUpper)
        ) {
          sector = "PHARMA";
        } else {
          sector = "F&O"; // Keep F&O as default for unknown stocks
        }
      }

      return {
        instrument_key: instrumentKey,
        symbol: symbol,
        name: stock.name,
        exchange: stock.exchange || "NSE",
        last_price: 0,
        change: 0,
        change_percent: 0,
        volume: 0,
        sector: sector,
        timestamp: Date.now(),
        is_index: isIndexSymbol(stock.symbol, stock.name),
      };
    });

    // Sort: indices first (alphabetically), then stocks (alphabetically)
    return processedStocks.sort((a, b) => {
      if (a.is_index && !b.is_index) return -1;
      if (!a.is_index && b.is_index) return 1;
      return (a.name || a.symbol).localeCompare(b.name || b.symbol);
    });
  }, [fnoStockList.securities, isIndexSymbol, marketData]);
  // Separate indices and stocks for categorized display
  const { fnoIndices, fnoStocks } = useMemo(() => {
    const indices = fnoStocksData.filter((stock) => stock.is_index);
    const stocks = fnoStocksData.filter((stock) => !stock.is_index);
    return {
      fnoIndices: indices,
      fnoStocks: stocks,
    };
  }, [fnoStocksData]);

  // ⚡ CRITICAL FIX: Helper to get live price from Zustand store (O(1) lookup)
  // Replaces marketDataLookup Map which was O(n) to build on every render
  const getLivePrice = useCallback((symbol) => {
    if (!symbol) return null;
    return useMarketStore.getState().getPrice(symbol);
  }, []);

  // ⚡ CRITICAL FIX: Use Zustand store for live data (O(1) instead of O(n))
  const {
    fnoIndicesWithLiveData,
    fnoStocksWithLiveData,
    livePriceCount,
    gainersCount,
    losersCount,
  } = useMemo(() => {
    // Fast live data integration using Zustand store (O(1) per stock)
    const addLiveDataFast = (stocksArray) => {
      return stocksArray.map((stock) => {
        // Get live price from Zustand store (O(1) lookup)
        const liveData = getLivePrice(stock.symbol);

        if (liveData) {
          return {
            ...stock,
            last_price: liveData.ltp || stock.last_price,
            change: liveData.change || stock.change,
            change_percent: liveData.change_percent || stock.change_percent,
            volume: liveData.volume || stock.volume,
            high: liveData.high || stock.high,
            low: liveData.low || stock.low,
            open: liveData.open || stock.open,
            timestamp: liveData.timestamp || Date.now(),
            _live: true,
          };
        }
        return { ...stock, _live: false };
      });
    };

    // Process arrays
    const indicesWithLive = addLiveDataFast(fnoIndices);
    const stocksWithLive = addLiveDataFast(fnoStocks);

    // Compute stats
    const allSecurities = [...indicesWithLive, ...stocksWithLive];
    let livePrices = 0,
      gainers = 0,
      losers = 0;

    allSecurities.forEach((s) => {
      if (s.last_price > 0) livePrices++;
      if (s.change_percent > 0) gainers++;
      else if (s.change_percent < 0) losers++;
    });

    return {
      fnoIndicesWithLiveData: indicesWithLive,
      fnoStocksWithLiveData: stocksWithLive,
      livePriceCount: livePrices,
      totalSecurities: allSecurities.length,
      gainersCount: gainers,
      losersCount: losers,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fnoIndices, fnoStocks, getLivePrice, refreshTrigger]);

  // ⚡ CRITICAL FIX: processedData now only depends on backend analytics (NOT marketData)
  // Removed marketData dependency to prevent re-processing on every price update
  const processedData = useMemo(() => {
    console.log("🔧 processedData recalculating:", {
      indicesData: !!indicesData,
      indicesCount: indicesData?.indices?.length || 0,
      majorIndicesCount: indicesData?.major_indices?.length || 0,
      topMoversGainers: topMovers?.gainers?.length || 0,
      topMoversLosers: topMovers?.losers?.length || 0,
      gapUp: gapAnalysis?.gap_up?.length || 0,
      gapDown: gapAnalysis?.gap_down?.length || 0,
    });

    // Use backend-provided indices directly (no marketData processing)
    const analyticsIndices = indicesData?.indices || [];
    const majorIndices = indicesData?.major_indices || [];
    const sectorIndices = indicesData?.sector_indices || [];
    const indices = analyticsIndices;
    // MCX stocks - empty for now (backend should send this)
    const mcxStocks = [];
    // FIXED: Better analytics data extraction with comprehensive error handling
    const extractAnalyticsData = (analyticsObject, arrayKey, limit = 50) => {
      try {
        if (!analyticsObject || typeof analyticsObject !== "object") {
          return [];
        }
        let data = analyticsObject[arrayKey];
        if (!data && analyticsObject.data) {
          data = analyticsObject.data[arrayKey];
        }
        if (!Array.isArray(data)) {
          return [];
        }

        const seenSymbols = new Set();
        const validData = data
          .filter((item) => {
            if (!item || typeof item !== "object" || !item.symbol) return false;
            if (seenSymbols.has(item.symbol)) return false;
            seenSymbols.add(item.symbol);
            return true;
          })
          .map((item) => ({
            symbol: item.symbol || item.trading_symbol || "N/A",
            name: item.name || item.symbol || item.trading_symbol || "N/A",
            last_price: safeNumber(item.last_price || item.ltp || item.price),
            change: safeNumber(item.change),
            change_percent: safeNumber(item.change_percent || item.pchange),
            volume: safeNumber(item.volume || item.daily_volume),
            sector: item.sector || "OTHER",
            exchange: item.exchange || "NSE",
            instrument_key:
              item.instrument_key && item.instrument_key.includes("|")
                ? item.instrument_key
                : null,
            ...item,
          }))
          .slice(0, limit);
        return validData;
      } catch (error) {
        return [];
      }
    };
    const topGainers = extractAnalyticsData(topMovers, "gainers", 20);
    const topLosers = extractAnalyticsData(topMovers, "losers", 20);

    console.log("📊 DEBUG: WebSocket analytics data:", {
      topGainers: topGainers.length,
      topLosers: topLosers.length,
      sampleGainers: topGainers.slice(0, 3).map((g) => g?.symbol),
      sampleLosers: topLosers.slice(0, 3).map((l) => l?.symbol),
    });

    console.log("📊 FULL topGainers data:", topGainers);
    console.log("📊 FULL topLosers data:", topLosers);
    // Enhanced gap data extraction with real-time updates and gap-specific info
    const extractGapData = (analyticsObject, arrayKey, limit = 25) => {
      try {
        if (!analyticsObject || typeof analyticsObject !== "object") {
          return [];
        }
        let data = analyticsObject[arrayKey];
        if (!data && analyticsObject.data) {
          data = analyticsObject.data[arrayKey];
        }
        if (!Array.isArray(data)) {
          return [];
        }

        const seenGapSymbols = new Set();
        const validData = data
          .filter((item) => {
            if (!item || typeof item !== "object" || !item.symbol) return false;
            if (seenGapSymbols.has(item.symbol)) return false;
            seenGapSymbols.add(item.symbol);
            return true;
          })
          .map((item) => {
            // Use backend data directly (no marketData lookup)
            const currentPrice =
              item.current_price ||
              item.ltp ||
              item.last_price ||
              item.open_price ||
              0;

            // Enhanced gap information
            const gapPercentage = item.gap_percentage || 0;
            const openPrice = item.open_price || currentPrice;
            const previousClose = item.previous_close || 0;

            // Gap detection time (should be at market opening)
            const gapTime = item.timestamp
              ? new Date(item.timestamp).toLocaleTimeString("en-US", {
                  hour12: false,
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })
              : "9:15:00"; // Default to market open time

            const gapDate = item.timestamp
              ? new Date(item.timestamp).toLocaleDateString("en-US", {
                  month: "short",
                  day: "2-digit",
                })
              : new Date().toLocaleDateString("en-US", {
                  month: "short",
                  day: "2-digit",
                });

            return {
              symbol: item.symbol || item.trading_symbol || "N/A",
              name: item.name || item.symbol || item.trading_symbol || "N/A",
              last_price: currentPrice,
              change: item.change || currentPrice - previousClose,
              change_percent: item.change_percent || gapPercentage,
              volume: item.volume || 0,
              sector: item.sector || "OTHER",
              exchange: item.exchange || "NSE",
              instrument_key:
                item.instrument_key && item.instrument_key.includes("|")
                  ? item.instrument_key
                  : null,
              // Gap-specific fields
              gap_type: item.gap_type || arrayKey,
              gap_percentage: gapPercentage,
              gap_strength: item.gap_strength || "moderate",
              confidence_score: item.confidence_score || 0,
              open_price: openPrice,
              previous_close: previousClose,
              volume_ratio: item.volume_ratio || 1,
              // Timestamp fields
              timestamp: item.timestamp || new Date().toISOString(),
              gap_time: gapTime,
              gap_date: gapDate,
              detected_at_opening: true, // Gaps are always detected at opening
              ...item,
            };
          })
          .slice(0, limit);
        return validData;
      } catch (error) {
        console.error("Error extracting gap data:", error);
        return [];
      }
    };

    // Use API-loaded gap analysis data if available, fallback to WebSocket data
    const gapUp =
      gapAnalysisData.gap_up.length > 0
        ? gapAnalysisData.gap_up.slice(0, 25)
        : extractGapData(gapAnalysis, "gap_up", 25);
    const gapDown =
      gapAnalysisData.gap_down.length > 0
        ? gapAnalysisData.gap_down.slice(0, 25)
        : extractGapData(gapAnalysis, "gap_down", 25);
    const intradayBoosters = extractAnalyticsData(
      intradayStocks,
      "all_candidates",
      30
    );
    const volumeLeaders = extractAnalyticsData(
      volumeAnalysis,
      "volume_leaders",
      25
    );
    const newHighs = extractAnalyticsData(recordMovers, "new_highs", 20);
    const newLows = extractAnalyticsData(recordMovers, "new_lows", 20);

    // Enhanced breakout data extraction with real-time updates and timestamps
    const extractBreakoutData = (analyticsObject, arrayKey, limit = 25) => {
      try {
        if (!analyticsObject || typeof analyticsObject !== "object") {
          return [];
        }
        let data = analyticsObject[arrayKey];
        if (!data && analyticsObject.data) {
          data = analyticsObject.data[arrayKey];
        }
        if (!Array.isArray(data)) {
          return [];
        }

        const validData = data
          .filter((item) => item && typeof item === "object" && item.symbol)
          .map((item) => {
            // Use backend data directly (no marketData lookup)
            const currentPrice =
              item.current_price || item.last_price || item.ltp || 0;

            // Enhanced timestamp handling
            const breakoutTime =
              item.breakout_time ||
              (item.timestamp
                ? new Date(item.timestamp).toLocaleTimeString("en-US", {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })
                : "N/A");

            const breakoutDate =
              item.breakout_date ||
              (item.timestamp
                ? new Date(item.timestamp).toLocaleDateString("en-US", {
                    month: "short",
                    day: "2-digit",
                  })
                : "N/A");

            // Calculate time ago
            const timeAgo = item.timestamp
              ? (() => {
                  const now = new Date();
                  const breakoutTimestamp = new Date(item.timestamp);
                  const diffInMinutes = Math.floor(
                    (now - breakoutTimestamp) / (1000 * 60)
                  );

                  if (diffInMinutes < 1) return "Just now";
                  if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
                  const hours = Math.floor(diffInMinutes / 60);
                  if (hours < 24) return `${hours}h ${diffInMinutes % 60}m ago`;
                  return breakoutTimestamp.toLocaleDateString();
                })()
              : "N/A";

            return {
              symbol: item.symbol || item.trading_symbol || "N/A",
              name: item.name || item.symbol || item.trading_symbol || "N/A",
              last_price: currentPrice,
              change: item.change || 0,
              change_percent: item.change_percent || 0,
              volume: item.volume || 0,
              sector: item.sector || "OTHER",
              exchange: item.exchange || "NSE",
              instrument_key:
                item.instrument_key && item.instrument_key.includes("|")
                  ? item.instrument_key
                  : null,
              // Breakout-specific fields
              breakout_type: item.breakout_type || "breakout",
              breakout_strength: item.breakout_strength || 0,
              breakout_quality: item.breakout_quality || "moderate",
              confidence_score: item.confidence_score || 0,
              resistance_level: item.resistance_level || 0,
              support_level: item.support_level || 0,
              volume_ratio: item.volume_ratio || 1,
              price_momentum: item.price_momentum || 0,
              time_since_level: item.time_since_level || 0,
              // Enhanced timestamp fields
              timestamp: item.timestamp || new Date().toISOString(),
              breakout_time: breakoutTime,
              breakout_date: breakoutDate,
              time_ago: timeAgo,
              // Real-time indicator
              is_fresh: item.timestamp
                ? new Date() - new Date(item.timestamp) < 900000
                : false, // Fresh if < 15 minutes
              ...item,
            };
          })
          .slice(0, limit);
        return validData;
      } catch (error) {
        console.error("Error extracting breakout data:", error);
        return [];
      }
    };

    const breakouts = extractBreakoutData(breakoutAnalysis, "breakouts", 25);
    const breakdowns = extractBreakoutData(breakoutAnalysis, "breakdowns", 25);
    return {
      indices,
      majorIndices,
      sectorIndices,
      // equityStocks, // Commented out since variable is commented
      mcxStocks,
      topGainers,
      topLosers,
      gapUp,
      gapDown,
      intradayBoosters,
      volumeLeaders,
      newHighs,
      newLows,
      breakouts,
      breakdowns,
    };
  }, [
    indicesData,
    topMovers,
    gapAnalysis,
    gapAnalysisData,
    intradayStocks,
    volumeAnalysis,
    recordMovers,
    breakoutAnalysis,
  ]); // ⚡ CRITICAL: Removed marketData dependency

  // Destructure processed data to make it available in component scope
  const {
    indices,
    majorIndices,
    sectorIndices,
    mcxStocks,
    topGainers,
    topLosers,
    gapUp,
    gapDown,
    intradayBoosters,
    volumeLeaders,
    newHighs,
    newLows,
    breakouts,
    breakdowns,
  } = processedData;

  // 🚀 MEMOIZED: Top movers data to prevent multiple calculations per render
  const topMoversData = useMemo(() => {
    const zustandData = getRealTimeTopMovers();

    // If Zustand has data, use it for live updates
    if (zustandData.gainers.length > 0 || zustandData.losers.length > 0) {
      return zustandData;
    }

    // Otherwise use WebSocket analytics data and populate Zustand store
    const webSocketData = {};
    [...(topGainers || []), ...(topLosers || [])].forEach((stock) => {
      if (stock && stock.symbol) {
        webSocketData[stock.symbol] = {
          symbol: stock.symbol,
          ltp: stock.last_price || stock.ltp || 0,
          change: stock.change || 0,
          change_percent: stock.change_percent || 0,
          volume: stock.volume || 0,
          high: stock.high || 0,
          low: stock.low || 0,
          open: stock.open || 0,
          sector: stock.sector || "OTHER",
          exchange: stock.exchange || "NSE",
          timestamp: new Date().toISOString(),
          last_updated: Date.now(),
        };
      }
    });

    // Update Zustand store so StocksListOptimized can find the data
    if (Object.keys(webSocketData).length > 0) {
      useMarketStore.getState().updatePrices(webSocketData);
    }

    return {
      gainers: [...new Set((topGainers || []).map((stock) => stock.symbol).filter(Boolean))],
      losers: [...new Set((topLosers || []).map((stock) => stock.symbol).filter(Boolean))],
    };
  }, [getRealTimeTopMovers, topGainers, topLosers]);

  // Simple getter function that returns memoized data
  const getTopMoversData = useCallback(() => topMoversData, [topMoversData]);

  // Get enhanced major indices for cards
  // ⚡ CRITICAL FIX: Always create from Zustand store for real-time data
  const enhancedMajorIndices = useMemo(() => {
    const store = useMarketStore.getState();

    // Get unique prices by instrument_key to avoid duplicates from multiple key mappings
    const pricesMap = new Map();
    Object.entries(store.prices).forEach(([key, price]) => {
      const uniqueKey = price.instrument_key || price.symbol || key;
      if (!pricesMap.has(uniqueKey)) {
        pricesMap.set(uniqueKey, price);
      }
    });
    const allPrices = Array.from(pricesMap.values());

    console.log(`🔍 Total unique prices in Zustand store: ${allPrices.length}`);
    console.log(`🔍 majorIndices from backend: ${majorIndices?.length || 0}`);
    console.log(
      `🔍 Sample prices:`,
      allPrices.slice(0, 3).map((p) => p.symbol)
    );

    // Filter for indices (NSE_INDEX, BSE_INDEX)
    const indicesFromStore = allPrices
      .filter((price) => {
        const isIndex =
          price.instrument_key?.includes("INDEX") ||
          [
            "NIFTY 50",
            "SENSEX",
            "BANKNIFTY",
            "FINNIFTY",
            "MIDCPNIFTY",
            "NIFTY AUTO",
            "NIFTY IT",
            "NIFTY FMCG",
            "NIFTY METAL",
            "NIFTY PHARMA",
            "NIFTY REALTY",
            "NIFTY MEDIA",
            "NIFTY PSUBANK",
            "NIFTY OIL AND GAS",
          ].includes(price.symbol?.toUpperCase());

        if (isIndex) {
          console.log(
            `✅ Found index: ${price.symbol} (${price.instrument_key}) ltp=${price.ltp}`
          );
        }
        return isIndex;
      })
      .map((price) => ({
        symbol: price.symbol,
        name: price.symbol,
        instrument_key: price.instrument_key,
        last_price: price.ltp,
        ltp: price.ltp,
        change: price.change,
        change_percent: price.change_percent,
        volume: price.volume,
        high: price.high,
        low: price.low,
        open: price.open,
        _live_data_available: true,
        _source: "zustand_realtime",
      }));

    console.log(`📊 Final indices count: ${indicesFromStore.length}`);
    console.log(
      `📊 Indices symbols:`,
      indicesFromStore.map((i) => i.symbol)
    );

    // If backend sent indices, merge/enhance them
    if (majorIndices && majorIndices.length > 0) {
      console.log(`🔄 Merging with backend indices: ${majorIndices.length}`);
      const enhanced = getEnhancedIndicesData(majorIndices);
      // Return backend indices enhanced with live prices
      return enhanced.length > 0 ? enhanced : indicesFromStore;
    }

    // Return Zustand-only indices
    return indicesFromStore;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [majorIndices, getEnhancedIndicesData, refreshTrigger]);

  // PERFORMANCE FIX: Memoized market status display
  const marketStatusDisplay = useMemo(() => {
    switch (marketStatus) {
      case "normal_open":
      case "open":
        return {
          text: "MARKET OPEN",
          color: colors.positive,
          icon: "🟢",
        };
      case "pre_market":
        return {
          text: "PRE-MARKET",
          color: colors.neutral,
          icon: "🟡",
        };
      case "after_market":
        return {
          text: "AFTER-MARKET",
          color: colors.accent,
          icon: "🔵",
        };
      case "closed":
      default:
        return {
          text: "MARKET CLOSED",
          color: colors.negative,
          icon: "🔴",
        };
    }
  }, [marketStatus, colors]);
  // PERFORMANCE FIX: Memoized callback functions
  const toggleExpanded = useCallback(
    (section) =>
      setExpandedSection(expandedSection === section ? null : section),
    [expandedSection]
  );
  const handleSectionChange = useCallback((sectionId) => {
    setActiveSection(sectionId);
    // Smooth scroll to top when changing sections
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);
  const handleSearchChange = useCallback(
    (e) => setSearchQuery(e.target.value),
    []
  );
  const handleSectorChange = useCallback(
    (e) => setSelectedSector(e.target.value),
    []
  );
  // Render function for the header (MODERN CLEAN HEADER)
  const renderHeader = () => (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        bgcolor: colors.background + "cc", // High transparency
        color: "text.primary",
        borderBottom: `1px solid ${colors.border}`,
        backdropFilter: "blur(12px)",
        transition: "all 0.3s ease",
      }}
    >
      <Container maxWidth="xl">
        <Toolbar
          disableGutters
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            py: 1,
            px: { xs: 2, sm: 3 },
            minHeight: { xs: 56, sm: 64 },
          }}
        >
          {/* Logo & Title */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Box
              sx={{
                width: 32,
                height: 32,
                borderRadius: "8px",
                background: `linear-gradient(135deg, ${colors.primary}, ${colors.secondary})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: `0 4px 12px ${colors.primary}40`,
              }}
            >
              <span style={{ fontSize: "1.2rem" }}>📈</span>
            </Box>
            <Box>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 700,
                  fontSize: { xs: "1rem", sm: "1.1rem" },
                  letterSpacing: "-0.5px",
                  color: colors.text,
                  lineHeight: 1.2,
                }}
              >
                TRADING<span style={{ color: colors.primary }}>BOT</span>
              </Typography>
              {isMobile ? null : (
                <Typography
                  variant="caption"
                  sx={{
                    color: colors.textSecondary,
                    fontSize: "0.7rem",
                    fontWeight: 500,
                    letterSpacing: "0.5px",
                  }}
                >
                  LIVE TERMINAL
                </Typography>
              )}
            </Box>
          </Box>

          {/* Right Side: Status & Actions */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: { xs: 1, sm: 2 },
            }}
          >
            {/* Market Status Pill */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 0.75,
                px: 1.5,
                py: 0.5,
                borderRadius: "20px",
                bgcolor: colors.surface,
                border: `1px solid ${colors.border}`,
              }}
            >
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  bgcolor: marketStatusDisplay.color,
                  boxShadow: `0 0 8px ${marketStatusDisplay.color}60`,
                }}
              />
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 600,
                  color: colors.text,
                  fontSize: "0.75rem",
                  display: { xs: "none", sm: "block" },
                }}
              >
                {marketStatusDisplay.text}
              </Typography>
            </Box>

            {/* Connection Status */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 0.5,
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  color: isConnected ? colors.positive : colors.negative,
                  fontWeight: 600,
                  fontSize: "0.75rem",
                  bgcolor: isConnected
                    ? colors.positive + "10"
                    : colors.negative + "10",
                  px: 1,
                  py: 0.25,
                  borderRadius: "6px",
                }}
              >
                {isConnected ? "CONNECTED" : "DISCONNECTED"}
              </Typography>
              {!isConnected && (
                <IconButton
                  size="small"
                  onClick={reconnect}
                  sx={{
                    color: colors.text,
                    bgcolor: colors.surfaceHover,
                    width: 24,
                    height: 24,
                  }}
                >
                  <RefreshIcon sx={{ fontSize: 14 }} />
                </IconButton>
              )}
            </Box>
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
  // Render function for the overview section (RESPONSIVE - SINGLE COLUMN FOR PAIRED LISTS)
  const renderOverviewSection = () => (
    <Stack spacing={2}>
      {marketSummary && (
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
          }}
        >
          <Typography
            variant="h6"
            sx={{ mb: 1.5, color: colors.primary, fontWeight: 700 }}
          >
            📊 ADVANCE DECLINE RATIO
          </Typography>
          <Grid container spacing={1}>
            {[
              {
                value: marketSummary.advancing,
                label: "ADV",
                color: colors.positive,
              },
              {
                value: marketSummary.declining,
                label: "DEC",
                color: colors.negative,
              },
              {
                value: marketSummary.unchanged,
                label: "UNCH",
                color: colors.neutral,
              },
              {
                value: marketSummary.advanceDeclineRatio,
                label: "A/D",
                color: colors.primary,
              },
              {
                value: `${marketSummary.marketBreadth}%`,
                label: "BRDTH",
                color: colors.text,
              },
              ...(indicesSentiment.sentiment !== "unknown"
                ? [
                    {
                      value: indicesSentiment.sentiment
                        .toUpperCase()
                        .substring(0, 4),
                      label: "INDX",
                      color: indicesSentiment.sentiment.includes("bullish")
                        ? colors.positive
                        : indicesSentiment.sentiment.includes("bearish")
                        ? colors.negative
                        : colors.neutral,
                    },
                  ]
                : []),
            ].map((item, index) => (
              <Grid item xs={4} sm={2} md={1} key={index}>
                <Paper
                  sx={{
                    p: 1,
                    textAlign: "center",
                    bgcolor: "background.default",
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{
                      color: item.color,
                      fontWeight: 700,
                      fontSize: { xs: "0.9rem", sm: "1rem" },
                    }}
                  >
                    {item.value}
                  </Typography>
                  <Typography variant="caption">{item.label}</Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}
      {/* Clean Major Indices Cards - Enhanced with Real-Time Data */}
      {/* ⚡ FIXED: Show if enhancedMajorIndices has data, not majorIndices */}
      {enhancedMajorIndices.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ p: { xs: 1.5, sm: 2 } }}>
            <Typography
              variant="h6"
              sx={{
                mb: { xs: 1, sm: 1.5 },
                color: colors.header,
                fontWeight: 700,
                fontSize: { xs: "1rem", sm: "1.1rem" },
                display: "flex",
                alignItems: "center",
                gap: 0.75,
              }}
            >
              🏛️ MAJOR INDICES ({enhancedMajorIndices.length})
              {/* Real-time indicator - check if any major index has live data */}
              {isConnected && (
                <Chip
                  size="small"
                  label="LIVE"
                  sx={{
                    backgroundColor: colors.positive,
                    color: "white",
                    fontSize: "0.6rem",
                    height: "18px",
                  }}
                />
              )}
            </Typography>
            {isMobile ? (
              // Mobile: Clean horizontal scroll cards
              <Box
                sx={{
                  display: "flex",
                  overflowX: "auto",
                  gap: 1,
                  pb: 1,
                  // Hide scrollbars
                  "&::-webkit-scrollbar": {
                    display: "none",
                  },
                  "&": {
                    msOverflowStyle: "none",
                    scrollbarWidth: "none",
                  },
                }}
              >
                {enhancedMajorIndices.slice(0, 8).map((index, i) => {
                  const isPositive = (index.change_percent || 0) >= 0;
                  const isLive = index._live_data_available;
                  return (
                    <Card
                      key={index.symbol || index.name || i}
                      sx={{
                        minWidth: 120,
                        flexShrink: 0,
                        bgcolor: colors.cardBackground,
                        borderRadius: 2,
                        border: `1px solid ${colors.border}30`,
                        borderLeft: `3px solid ${
                          isPositive ? colors.positive : colors.negative
                        }`,
                        "&:hover": {
                          transform: "translateY(-2px)",
                          boxShadow: theme.shadows[2],
                        },
                        transition: "all 0.2s ease",
                      }}
                    >
                      <CardContent
                        sx={{ p: 1.25, "&:last-child": { pb: 1.25 } }}
                      >
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 0.5,
                            mb: 0.5,
                          }}
                        >
                          <Typography
                            variant="body2"
                            sx={{
                              fontWeight: 700,
                              color: colors.header,
                              fontSize: "0.8rem",
                              lineHeight: 1.2,
                            }}
                            noWrap
                          >
                            {index.symbol}
                          </Typography>
                          {isLive && (
                            <Box
                              sx={{
                                width: 6,
                                height: 6,
                                borderRadius: "50%",
                                bgcolor: colors.positive,
                                animation: "pulse 1.5s infinite",
                              }}
                            />
                          )}
                        </Box>
                        <Typography
                          variant="body1"
                          sx={{
                            fontWeight: 700,
                            color: "text.primary",
                            mb: 0.5,
                            fontSize: "0.85rem",
                            textAlign: "center",
                            fontFamily: "monospace",
                          }}
                        >
                          ₹{(index.last_price || index.ltp || 0).toFixed(2)}
                        </Typography>
                        <Box
                          sx={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            gap: 0.25,
                          }}
                        >
                          <Typography
                            variant="body2"
                            sx={{
                              color: isPositive
                                ? colors.positive
                                : colors.negative,
                              fontWeight: 700,
                              fontSize: "0.75rem",
                              fontFamily: "monospace",
                            }}
                          >
                            {isPositive ? "+" : ""}
                            {(index.change_percent || 0).toFixed(2)}%
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{
                              color: "text.secondary",
                              fontSize: "0.65rem",
                              fontFamily: "monospace",
                            }}
                          >
                            {isPositive ? "+" : ""}
                            {(index.change || 0).toFixed(2)}
                          </Typography>
                        </Box>
                      </CardContent>
                    </Card>
                  );
                })}
              </Box>
            ) : (
              // Desktop: Grid layout
              <Grid container spacing={2}>
                {enhancedMajorIndices.slice(0, 6).map((index, i) => {
                  const isPositive = (index.change_percent || 0) >= 0;
                  const isLive = index._live_data_available;
                  return (
                    <Grid
                      item
                      xs={6}
                      sm={4}
                      md={2}
                      key={index.symbol || index.name || i}
                    >
                      <Card
                        sx={{
                          bgcolor: colors.cardBackground,
                          borderRadius: 2,
                          border: `1px solid ${colors.border}`,
                          borderLeft: `3px solid ${
                            isPositive ? colors.positive : colors.negative
                          }`,
                          "&:hover": {
                            transform: "translateY(-2px)",
                            boxShadow: theme.shadows[4],
                          },
                          transition: "all 0.2s ease",
                        }}
                      >
                        <CardContent
                          sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}
                        >
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              gap: 0.5,
                              mb: 0.75,
                            }}
                          >
                            <Typography
                              variant="body2"
                              sx={{
                                fontWeight: 700,
                                color: colors.header,
                                fontSize: "0.85rem",
                              }}
                              noWrap
                            >
                              {index.symbol}
                            </Typography>
                            {isLive && (
                              <Box
                                sx={{
                                  width: 6,
                                  height: 6,
                                  borderRadius: "50%",
                                  bgcolor: colors.positive,
                                  animation: "pulse 1.5s infinite",
                                }}
                              />
                            )}
                          </Box>
                          <Typography
                            variant="h6"
                            sx={{
                              fontWeight: 700,
                              color: "text.primary",
                              mb: 0.5,
                              fontSize: "1rem",
                              textAlign: "center",
                              fontFamily: "monospace",
                            }}
                          >
                            ₹{(index.last_price || index.ltp || 0).toFixed(2)}
                          </Typography>
                          <Box sx={{ textAlign: "center" }}>
                            <Typography
                              variant="body2"
                              sx={{
                                color: isPositive
                                  ? colors.positive
                                  : colors.negative,
                                fontWeight: 700,
                                fontSize: "0.8rem",
                                fontFamily: "monospace",
                              }}
                            >
                              {isPositive ? "+" : ""}
                              {(index.change_percent || 0).toFixed(2)}%
                            </Typography>
                            <Typography
                              variant="caption"
                              sx={{
                                color: "text.secondary",
                                display: "block",
                                fontSize: "0.7rem",
                                fontFamily: "monospace",
                              }}
                            >
                              {isPositive ? "+" : ""}
                              {(index.change || 0).toFixed(2)} pts
                            </Typography>
                          </Box>
                        </CardContent>
                      </Card>
                    </Grid>
                  );
                })}
              </Grid>
            )}
          </CardContent>
        </Card>
      )}
      {/* INDICES LIST */}
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
        }}
      >
        <MemoizedStocksListWithLivePrices
          title={`INDICES (${indices.length})`} titleIcon={<AccountBalanceRounded />}
          data={indices}
          layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
          showVolume={true} // Always show volume
          isLoading={!isConnected}
          maxItems={isMobile ? 8 : 12} // Show fewer items on mobile
          density="compact" // Use compact density
          compact={true}
          enhanceWithLivePrices={true}
          showLiveIndicator={true}
          // Remove fixed containerHeight to allow natural flow
          // containerHeight={isMobile ? "50vh" : "55vh"}
        />
      </Paper>

      {/* GAINERS/LOSERS - Stack vertically on ALL screens */}
      <Stack spacing={2}>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
            width: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <MemoizedStocksListOptimized
            title={`GAINERS (${getTopMoversData().gainers.length})`} titleIcon={<TrendingUpRounded />}
            symbols={getTopMoversData().gainers}
            showVolume={true} // Always show volume
            showSector={true} // Always show sector
            maxItems={isMobile ? 5 : 8} // Show fewer items on mobile
            isLoading={getTopMoversData().gainers.length === 0}
            compact={true}
            containerHeight="auto"
          />
        </Paper>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
            width: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <MemoizedStocksListOptimized
            title={`LOSERS (${getTopMoversData().losers.length})`} titleIcon={<TrendingDownRounded />}
            symbols={getTopMoversData().losers}
            showVolume={true} // Always show volume
            showSector={true} // Always show sector
            maxItems={isMobile ? 5 : 8} // Show fewer items on mobile
            isLoading={getTopMoversData().losers.length === 0}
            compact={true}
            containerHeight="auto"
          />
        </Paper>
      </Stack>

      {/* BOOSTERS/VOLUME - Stack vertically on ALL screens */}
      <Stack spacing={2}>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
            width: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <MemoizedStocksList
            title={`BOOSTERS (${intradayBoosters.length})`} titleIcon={<BoltRounded />}
            data={intradayBoosters}
            layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
            showVolume={true} // Always show volume
            showOptionChain={true} // Enable option chain for boosters
            showSector={false} // Generally hide sector for these lists
            maxItems={isMobile ? 5 : 10} // Show fewer items on mobile
            isLoading={!isConnected}
            density="compact" // Use compact density
            compact={true}
            // Remove fixed containerHeight to allow natural flow
            // containerHeight={isMobile ? "55vh" : "60vh"}
          />
        </Paper>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
            width: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <MemoizedStocksList
            title={`VOLUME (${volumeLeaders.length})`} titleIcon={<BarChartRounded />}
            data={volumeLeaders}
            layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
            showVolume={true} // Always show volume
            showOptionChain={true} // Enable option chain for volume leaders
            showSector={false} // Generally hide sector for these lists
            maxItems={isMobile ? 5 : 10} // Show fewer items on mobile
            isLoading={!isConnected}
            density="compact" // Use compact density
            compact={true}
            // Remove fixed containerHeight to allow natural flow
            // containerHeight={isMobile ? "55vh" : "60vh"}
          />
        </Paper>
      </Stack>
    </Stack>
  );
  // Render function for the search section (RESPONSIVE)
  const renderSearchSection = () => (
    <Stack spacing={2}>
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
        }}
      >
        <Typography
          variant="h6"
          sx={{ mb: 1.5, color: colors.primary, fontWeight: 700 }}
        >
          🔍 SEARCH STOCKS
        </Typography>
        <Box sx={{ display: "flex", alignItems: "center", width: "100%" }}>
          <InputBase
            placeholder="Symbol or company name..."
            value={searchQuery}
            onChange={handleSearchChange}
            sx={{
              flex: 1,
              p: "4px 8px",
              border: `1px solid ${colors.border}`,
              borderRadius: 2,
              bgcolor: "background.default",
              fontSize: "0.875rem",
            }}
            startAdornment={
              <SearchIcon sx={{ mr: 1, color: "text.secondary" }} />
            }
          />
        </Box>
      </Paper>
      {searchResults.length > 0 && (
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
          }}
        >
          <MemoizedStocksList
            title={`RESULTS (${searchResults.length})`} titleIcon={<SearchIcon />}
            data={searchResults}
            layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
            showVolume={true} // Always show volume
            showOptionChain={true} // Enable option chain for search results
            showName={true}
            showSector={true} // Always show sector
            maxItems={50} // Keep maxItems for search results
            isLoading={!isConnected}
            density="standard" // Use standard density for search results
            // Remove fixed containerHeight to allow natural flow
            // containerHeight="70vh"
          />
        </Paper>
      )}
    </Stack>
  );
  // Render function for the sectors section (RESPONSIVE)
  const renderSectorsSection = () => (
    <Stack spacing={2}>
      {/* Enhanced Financial Sector Heatmap - Full page responsive */}
      <FinancialHeatmap
        data={heatmap?.sectors || []}
        marketData={marketData}
        title="🔥 SECTOR HEATMAP"
        isLoading={!isConnected}
        maxItems={isMobile ? 25 : isTablet ? 35 : 40}
        fullPage={true}
      />
      {/* Enhanced TipRanks-style Stock Heatmap - Full page responsive with more stocks */}
      <TipRanksHeatmap
        data={[]} // This prop is not used by the component
        marketData={marketData}
        title="🔥 STOCK HEATMAP"
        isLoading={!isConnected}
        maxItems={isMobile ? 60 : isTablet ? 100 : 150}
        fullPage={true}
      />
      {/* Sector Selection and Stocks */}
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
        }}
      >
        <Box sx={{ mb: 2 }}>
          <Typography
            variant="h6"
            sx={{ mb: 1.5, color: colors.primary, fontWeight: 700 }}
          >
            🏢 SECTOR ANALYSIS
          </Typography>
          <Select
            value={selectedSector}
            onChange={handleSectorChange}
            fullWidth
            size="small"
            sx={{
              bgcolor: "background.default",
              borderRadius: 2,
              border: `1px solid ${colors.border}`,
              "& .MuiSelect-select": {
                py: 1,
                pl: 1.5,
                pr: 3,
              },
            }}
          >
            <MenuItem value="ALL">ALL SECTORS</MenuItem>
            {sectors.map((sector) => (
              <MenuItem key={sector} value={sector}>
                {sector}
              </MenuItem>
            ))}
          </Select>
        </Box>
        <MemoizedStocksList
          title={`📊 ${
            selectedSector === "ALL" ? "ALL STOCKS" : selectedSector
          } (${sectorStocks.length})`}
          data={sectorStocks}
          layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
          showVolume={true} // Always show volume
          showName={true}
          showSector={selectedSector === "ALL" && !isMobile} // Show sector on larger screens if table and showing all
          maxItems={50} // Keep maxItems for sector stocks
          isLoading={!isConnected}
          // Remove fixed containerHeight to allow natural flow
        />
      </Paper>
    </Stack>
  );
  // Render function for the indices section (RESPONSIVE - SINGLE COLUMN FOR PAIRED LISTS)
  const renderIndicesSection = () => (
    <Stack spacing={2}>
      {/* Indices Summary Stats */}
      {indicesSummary && Object.keys(indicesSummary).length > 0 && (
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
          }}
        >
          <Typography
            variant="h6"
            sx={{ mb: 1.5, color: colors.primary, fontWeight: 700 }}
          >
            📊 INDICES OVERVIEW
          </Typography>
          <Grid container spacing={1}>
            {[
              {
                value: indicesSummary.total_indices || 0,
                label: "TOTAL",
                color: colors.primary,
              },
              {
                value: indicesSummary.major_up || 0,
                label: "MAJ UP",
                color: colors.positive,
              },
              {
                value: indicesSummary.major_down || 0,
                label: "MAJ DN",
                color: colors.negative,
              },
              {
                value: indicesSummary.sector_up || 0,
                label: "SEC UP",
                color: colors.positive,
              },
              {
                value: indicesSummary.sector_down || 0,
                label: "SEC DN",
                color: colors.negative,
              },
              ...(indicesSentiment.sentiment !== "unknown"
                ? [
                    {
                      value: `${indicesSentiment.confidence}%`,
                      label: "CONF",
                      color: colors.accent,
                    },
                  ]
                : []),
            ].map((item, index) => (
              <Grid item xs={4} sm={2} md={1} key={index}>
                <Paper
                  sx={{
                    p: 1,
                    textAlign: "center",
                    bgcolor: "background.default",
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{
                      color: item.color,
                      fontWeight: 700,
                      fontSize: { xs: "0.9rem", sm: "1rem" },
                    }}
                  >
                    {item.value}
                  </Typography>
                  <Typography variant="caption">{item.label}</Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}
      {/* Major Market Indices */}
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
        }}
      >
        <MemoizedStocksListWithLivePrices
          title={`MAJOR INDICES (${enhancedMajorIndices.length})`} titleIcon={<AccountBalanceRounded />}
          data={enhancedMajorIndices}
          layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
          showVolume={false} // Hide volume for indices
          showName={true}
          showSector={false} // Hide sector for indices
          maxItems={isMobile ? 8 : 20} // Show fewer items on mobile
          isLoading={!isConnected}
          enhanceWithLivePrices={true}
          showLiveIndicator={true}
          // Remove fixed containerHeight to allow natural flow
        />
      </Paper>
      {/* Sector Indices */}
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
        }}
      >
        <MemoizedStocksListWithLivePrices
          title={`SECTOR INDICES (${sectorIndices.length})`} titleIcon={<CategoryRounded />}
          data={sectorIndices}
          layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
          showVolume={false} // Hide volume for indices
          showName={true}
          showSector={false} // Hide sector for indices
          maxItems={isMobile ? 8 : 30} // Show fewer items on mobile
          isLoading={!isConnected}
          enhanceWithLivePrices={true}
          showLiveIndicator={true}
          // Remove fixed containerHeight to allow natural flow
        />
      </Paper>
      {/* Top Performing Indices - Stack vertically on ALL screens */}
      <Stack spacing={2}>
        {indicesPerformance && indicesPerformance.gainers.length > 0 && (
          <Paper
            elevation={2}
            sx={{
              p: 2,
              borderRadius: 3,
              border: `1px solid ${colors.border}`,
              bgcolor: "background.paper",
              width: "100%",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <MemoizedStocksListWithLivePrices
              title={`TOP GAINING INDICES (${indicesPerformance.gainers.length})`} titleIcon={<TrendingUpRounded />}
              data={indicesPerformance.gainers.slice(0, isMobile ? 5 : 10)}
              layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
              showVolume={false} // Hide volume for indices
              showName={true}
              showSector={false} // Hide sector for indices
              maxItems={isMobile ? 5 : 10} // Show fewer items on mobile
              isLoading={!isConnected}
              enhanceWithLivePrices={true}
              showLiveIndicator={true}
              // Remove fixed containerHeight to allow natural flow
            />
          </Paper>
        )}
        {indicesPerformance && indicesPerformance.losers.length > 0 && (
          <Paper
            elevation={2}
            sx={{
              p: 2,
              borderRadius: 3,
              border: `1px solid ${colors.border}`,
              bgcolor: "background.paper",
              width: "100%",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <MemoizedStocksListWithLivePrices
              title={`TOP LOSING INDICES (${indicesPerformance.losers.length})`} titleIcon={<TrendingDownRounded />}
              data={indicesPerformance.losers.slice(0, isMobile ? 5 : 10)}
              layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
              showVolume={false} // Hide volume for indices
              showName={true}
              showSector={false} // Hide sector for indices
              maxItems={isMobile ? 5 : 10} // Show fewer items on mobile
              isLoading={!isConnected}
              enhanceWithLivePrices={true}
              showLiveIndicator={true}
              // Remove fixed containerHeight to allow natural flow
            />
          </Paper>
        )}
      </Stack>
      {/* All Indices Table */}
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
        }}
      >
        <MemoizedStocksListWithLivePrices
          title={`ALL INDICES (${indices.length})`} titleIcon={<AccountBalanceRounded />}
          data={indices}
          layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
          showVolume={true} // Always show volume
          showName={true}
          showSector={false} // Hide sector for indices
          maxItems={isMobile ? 8 : 100} // Show fewer items on mobile, more on desktop
          isLoading={!isConnected}
          enhanceWithLivePrices={true}
          showLiveIndicator={true}
          // Remove fixed containerHeight to allow natural flow
        />
      </Paper>
    </Stack>
  );
  // Render function for the movers section (RESPONSIVE - SINGLE COLUMN FOR PAIRED LISTS)
  const renderMoversSection = () => (
    <Stack spacing={2}>
      {/* GAINERS/LOSERS - Stack vertically on ALL screens (same logic as overview) */}
      <Stack spacing={2}>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
            position: "relative",
            width: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              mb: 1,
            }}
          >
            <Typography
              variant="h6"
              sx={{ color: colors.primary, fontWeight: 700 }}
            >
              🚀 TOP GAINERS ({getTopMoversData().gainers.length})
            </Typography>
            <Button
              size="small"
              onClick={() => toggleExpanded("gainers")}
              startIcon={
                expandedSection === "gainers" ? (
                  <ExpandLessIcon />
                ) : (
                  <ExpandMoreIcon />
                )
              }
              sx={{ minWidth: 0, px: 1 }}
            >
              {expandedSection === "gainers" ? "COMPACT" : "EXPAND"}
            </Button>
          </Box>
          <MemoizedStocksListOptimized
            title="" // Title already shown above
            symbols={getTopMoversData().gainers}
            showVolume={true} // Always show volume
            showSector={true} // Always show sector
            maxItems={
              expandedSection === "gainers"
                ? isMobile
                  ? 20
                  : 50
                : isMobile
                ? 10
                : 15
            }
            isLoading={getTopMoversData().gainers.length === 0}
            compact={true}
            containerHeight="auto"
          />
        </Paper>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
            position: "relative",
            width: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              mb: 1,
            }}
          >
            <Typography
              variant="h6"
              sx={{ color: colors.primary, fontWeight: 700 }}
            >
              📉 TOP LOSERS ({getTopMoversData().losers.length})
            </Typography>
            <Button
              size="small"
              onClick={() => toggleExpanded("losers")}
              startIcon={
                expandedSection === "losers" ? (
                  <ExpandLessIcon />
                ) : (
                  <ExpandMoreIcon />
                )
              }
              sx={{ minWidth: 0, px: 1 }}
            >
              {expandedSection === "losers" ? "COMPACT" : "EXPAND"}
            </Button>
          </Box>
          <MemoizedStocksListOptimized
            title="" // Title already shown above
            symbols={getTopMoversData().losers}
            showVolume={true} // Always show volume
            showSector={true} // Always show sector
            maxItems={
              expandedSection === "losers"
                ? isMobile
                  ? 20
                  : 50
                : isMobile
                ? 10
                : 15
            }
            isLoading={getTopMoversData().losers.length === 0}
            compact={true}
            containerHeight="auto"
          />
        </Paper>
      </Stack>
      {/* Volume Leaders - Single list */}
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
        }}
      >
        <MemoizedStocksList
          title={`VOLUME LEADERS (${volumeLeaders.length})`} titleIcon={<BarChartRounded />}
          data={volumeLeaders}
          layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
          showVolume={true} // Always show volume
          showSector={true} // Always show sector
          maxItems={isMobile ? 15 : 20} // Show fewer items on mobile
          isLoading={!isConnected}
          // Remove fixed containerHeight to allow natural flow
        />
      </Paper>
    </Stack>
  );
  // Render function for the gaps section (RESPONSIVE - SINGLE COLUMN FOR PAIRED LISTS)
  const renderGapsSection = () => (
    <Stack spacing={2}>
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
          width: "100%",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {gapLoading ? (
          <Box sx={{ textAlign: "center", py: 4 }}>
            <Typography variant="h6" sx={{ color: colors.primary, mb: 2 }}>
              Loading Gap Analysis...
            </Typography>
          </Box>
        ) : gapUp.length > 0 ? (
          <MemoizedStocksList
            title={`GAP UP (${gapUp.length})`} titleIcon={<TrendingUpRounded />}
            data={gapUp}
            layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
            showVolume={true} // Always show volume
            showSector={true} // Always show sector
            showTimestamp={true} // Show gap detection time (9:15 AM)
            maxItems={isMobile ? 15 : 25} // Show fewer items on mobile
            isLoading={gapLoading}
            // Remove fixed containerHeight to allow natural flow
          />
        ) : (
          <Box sx={{ textAlign: "center", py: 2 }}>
            <Typography variant="h6" sx={{ color: colors.primary, mb: 1 }}>
              📈 GAP UP (0)
            </Typography>
            <Typography
              variant="body2"
              sx={{ color: "text.secondary", fontStyle: "italic" }}
            >
              Stocks opening above previous close with significant gap
              <br />
              No gap up detected at market opening today
            </Typography>
          </Box>
        )}
      </Paper>
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
          width: "100%",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {gapLoading ? (
          <Box sx={{ textAlign: "center", py: 4 }}>
            <Typography variant="h6" sx={{ color: colors.primary, mb: 2 }}>
              Loading Gap Analysis...
            </Typography>
          </Box>
        ) : gapDown.length > 0 ? (
          <MemoizedStocksList
            title={`GAP DOWN (${gapDown.length})`} titleIcon={<TrendingDownRounded />}
            data={gapDown}
            layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
            showVolume={true} // Always show volume
            showSector={true} // Always show sector
            showTimestamp={true} // Show gap detection time (9:15 AM)
            maxItems={isMobile ? 15 : 25} // Show fewer items on mobile
            isLoading={gapLoading}
            // Remove fixed containerHeight to allow natural flow
          />
        ) : (
          <Box sx={{ textAlign: "center", py: 2 }}>
            <Typography variant="h6" sx={{ color: colors.primary, mb: 1 }}>
              📉 GAP DOWN (0)
            </Typography>
            <Typography
              variant="body2"
              sx={{ color: "text.secondary", fontStyle: "italic" }}
            >
              Stocks opening below previous close with significant gap
              <br />
              No gap down detected at market opening today
            </Typography>
          </Box>
        )}
      </Paper>
    </Stack>
  );
  // Render function for the breakouts section with REAL-TIME BREAKOUT WIDGETS
  const renderBreakoutsSection = () => (
    <Stack spacing={2}>
      {/* Enhanced Breakout Widget - Real-time detection */}
      <EnhancedBreakoutWidget
        data={breakoutAnalysis}
        isLoading={!breakoutAnalysis || !isConnected}
        compact={isMobile}
        realTimeEnabled={isConnected}
        onRefresh={() => {
          // Trigger refresh if needed
          console.log("Refreshing breakout data...");
        }}
      />

      {/* Breakout Analysis Widget - Detailed view */}
      <BreakoutAnalysisWidget
        data={breakoutAnalysis}
        isLoading={!breakoutAnalysis || !isConnected}
        compact={isMobile}
      />
    </Stack>
  );
  // Enhanced MCX trading symbol parser using proper data fields
  const parseMcxTradingSymbol = (stock) => {
    const tradingSymbol = stock.symbol || stock.name || "";
    const instrumentType = stock.instrument_type || "";
    const strikePrice = stock.strike_price || null;
    const expiry = stock.expiry || null;

    // Extract commodity from trading symbol (first part before space)
    const parts = tradingSymbol.split(" ");
    const commodity = parts[0]; // CRUDEOIL, GOLD, SILVER, etc.

    const isOption = instrumentType === "CE" || instrumentType === "PE";
    const isFuture = instrumentType === "FUT" || instrumentType === "FUTCOM";

    if (isOption && strikePrice) {
      // Use actual strike_price field and parse expiry from trading symbol
      const expiryText = parts.length >= 5 ? parts.slice(-3).join(" ") : "N/A";
      return {
        commodity,
        displayName: `${commodity} ${strikePrice} ${instrumentType}`,
        fullName: `${commodity} ${expiryText} ₹${strikePrice} ${
          instrumentType === "CE" ? "Call" : "Put"
        }`,
        type: instrumentType === "CE" ? "Call" : "Put",
        strike: strikePrice,
        strikeFormatted: `₹${strikePrice.toLocaleString()}`,
        expiry: expiryText,
        isOption: true,
        isFuture: false,
        sortKey: `${commodity}_OPT_${strikePrice}_${instrumentType}`,
      };
    } else if (isFuture) {
      // Future parsing from trading symbol
      const expiryText = parts.slice(2).join(" "); // Everything after "FUT"
      return {
        commodity,
        displayName: `${commodity} FUT`,
        fullName: `${commodity} ${expiryText} Futures`,
        type: "Future",
        expiry: expiryText,
        isOption: false,
        isFuture: true,
        sortKey: `${commodity}_FUT_${expiry || "0"}`,
      };
    }

    // Fallback for unrecognized formats
    return {
      commodity: commodity || tradingSymbol,
      displayName: tradingSymbol,
      fullName: tradingSymbol,
      type: instrumentType || "Unknown",
      isOption: instrumentType === "CE" || instrumentType === "PE",
      isFuture: instrumentType === "FUT" || instrumentType === "FUTCOM",
      sortKey: tradingSymbol,
    };
  };

  // Enhanced MCX processing with futures/options separation
  const processMcxStocks = () => {
    const processed = mcxStocks.map((stock) => ({
      ...stock,
      parsed: parseMcxTradingSymbol(stock),
    }));

    // Group by commodity type
    const crudeStocks = processed.filter(
      (stock) =>
        stock.parsed.commodity?.toUpperCase().includes("CRUDE") ||
        stock.name?.toUpperCase().includes("CRUDE")
    );

    const goldStocks = processed.filter(
      (stock) =>
        stock.parsed.commodity?.toUpperCase().includes("GOLD") ||
        stock.name?.toUpperCase().includes("GOLD")
    );

    const silverStocks = processed.filter(
      (stock) =>
        stock.parsed.commodity?.toUpperCase().includes("SILVER") ||
        stock.name?.toUpperCase().includes("SILVER")
    );

    const otherStocks = processed.filter(
      (stock) =>
        !crudeStocks.includes(stock) &&
        !goldStocks.includes(stock) &&
        !silverStocks.includes(stock)
    );

    return { crudeStocks, goldStocks, silverStocks, otherStocks };
  };

  // Enhanced commodity section renderer with futures/options separation
  const renderCommoditySection = (title, stocks, bgColor, textColor) => {
    if (!stocks || stocks.length === 0) return null;

    // Separate futures and options
    const futures = stocks.filter((stock) => stock.parsed.isFuture).slice(0, 5);
    const options = stocks
      .filter((stock) => stock.parsed.isOption)
      .slice(0, 15);

    return (
      <Paper
        elevation={1}
        sx={{
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
          overflow: "hidden",
        }}
      >
        {/* Section Header */}
        <Box
          sx={{
            p: 2,
            backgroundColor: bgColor + "10",
            borderBottom: `1px solid ${colors.border}`,
          }}
        >
          <Typography
            variant="h6"
            sx={{
              color: textColor,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 1,
            }}
          >
            {title} ({stocks.length})
          </Typography>
          <Typography variant="caption" sx={{ color: colors.textSecondary }}>
            {futures.length} Futures • {options.length} Options
          </Typography>
        </Box>

        <Stack spacing={1.5} sx={{ p: 2 }}>
          {/* Futures Section */}
          {futures.length > 0 && (
            <Box>
              <Typography
                variant="subtitle2"
                sx={{
                  color: colors.text,
                  fontWeight: 500,
                  mb: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                }}
              >
                📈 Futures ({futures.length})
              </Typography>
              <Stack spacing={0.5}>
                {futures.map((stock, index) => (
                  <Box
                    key={`future-${index}`}
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      p: 1,
                      borderRadius: 1,
                      bgcolor: colors.surface + "50",
                      border: `1px solid ${colors.border}50`,
                    }}
                  >
                    <Box>
                      <Typography
                        variant="body2"
                        sx={{
                          color: colors.text,
                          fontWeight: 500,
                        }}
                      >
                        {stock.parsed.displayName}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{ color: colors.textSecondary }}
                      >
                        Exp: {stock.parsed.expiry || "N/A"}
                      </Typography>
                    </Box>
                    <Box sx={{ textAlign: "right" }}>
                      <Typography
                        variant="body2"
                        sx={{
                          color: colors.text,
                          fontWeight: 500,
                        }}
                      >
                        ₹{stock.last_price?.toLocaleString() || "N/A"}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          color:
                            stock.change_percent >= 0
                              ? colors.positive
                              : colors.negative,
                          fontWeight: 500,
                        }}
                      >
                        {stock.change_percent >= 0 ? "+" : ""}
                        {stock.change_percent?.toFixed(2) || "0.00"}%
                      </Typography>
                    </Box>
                  </Box>
                ))}
              </Stack>
            </Box>
          )}

          {/* Options Section */}
          {options.length > 0 && (
            <Box>
              <Typography
                variant="subtitle2"
                sx={{
                  color: colors.text,
                  fontWeight: 500,
                  mb: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                }}
              >
                📊 Options Chain ({options.length})
              </Typography>

              {/* Option Chain Display */}
              <Box sx={{ maxHeight: isMobile ? 250 : 300, overflowY: "auto" }}>
                <Stack spacing={0.5}>
                  {options.map((stock, index) => (
                    <Box
                      key={`option-${index}`}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        p: 1,
                        borderRadius: 1,
                        bgcolor:
                          stock.parsed.type === "Call"
                            ? colors.positive + "10"
                            : colors.negative + "10",
                        border: `1px solid ${
                          stock.parsed.type === "Call"
                            ? colors.positive + "30"
                            : colors.negative + "30"
                        }`,
                      }}
                    >
                      <Box>
                        <Typography
                          variant="body2"
                          sx={{
                            color: colors.text,
                            fontWeight: 500,
                          }}
                        >
                          {stock.parsed.displayName}
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{ color: colors.textSecondary }}
                        >
                          Strike:{" "}
                          {stock.parsed.strikeFormatted ||
                            `₹${stock.parsed.strike || "N/A"}`}{" "}
                          • {stock.parsed.type}
                        </Typography>
                      </Box>
                      <Box sx={{ textAlign: "right" }}>
                        <Typography
                          variant="body2"
                          sx={{
                            color: colors.text,
                            fontWeight: 500,
                          }}
                        >
                          ₹{stock.last_price?.toLocaleString() || "N/A"}
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            color:
                              stock.change_percent >= 0
                                ? colors.positive
                                : colors.negative,
                            fontWeight: 500,
                          }}
                        >
                          {stock.change_percent >= 0 ? "+" : ""}
                          {stock.change_percent?.toFixed(2) || "0.00"}%
                        </Typography>
                      </Box>
                    </Box>
                  ))}
                </Stack>
              </Box>
            </Box>
          )}
        </Stack>
      </Paper>
    );
  };

  // Render function for the MCX section (RESPONSIVE) - Enhanced with Futures & Options Display
  const renderMcxSection = () => {
    const { crudeStocks, goldStocks, silverStocks, otherStocks } =
      processMcxStocks();

    if (!mcxStocks || mcxStocks.length === 0) {
      return (
        <Paper
          elevation={2}
          sx={{
            p: 3,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
            textAlign: "center",
          }}
        >
          <Typography variant="h6" sx={{ mb: 1, color: colors.text }}>
            🏭 MCX Commodities
          </Typography>
          <Typography sx={{ color: colors.textSecondary }}>
            No MCX data available
          </Typography>
          <Typography
            variant="caption"
            sx={{ mt: 1, display: "block", color: colors.textSecondary }}
          >
            Waiting for Gold, Crude Oil, Silver & Copper live data...
          </Typography>
        </Paper>
      );
    }

    return (
      <Stack spacing={2}>
        {/* Main MCX Header */}
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
          }}
        >
          <Typography
            variant="h6"
            sx={{
              color: colors.text,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 1,
              mb: 1,
            }}
          >
            🏭 MCX Commodities ({mcxStocks.length})
          </Typography>
          <Typography variant="caption" sx={{ color: colors.textSecondary }}>
            Live futures and options for precious metals and energy commodities
          </Typography>

          {/* Commodity Summary Chips */}
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 2 }}>
            {goldStocks.length > 0 && (
              <Chip
                label={`🥇 Gold: ${goldStocks.length}`}
                size="small"
                sx={{
                  backgroundColor: "#FFD70020",
                  color: "#B8860B",
                  fontWeight: 500,
                }}
              />
            )}
            {crudeStocks.length > 0 && (
              <Chip
                label={`🛢️ Crude: ${crudeStocks.length}`}
                size="small"
                sx={{
                  backgroundColor: "#2F4F4F40",
                  color: "#708090",
                  fontWeight: 500,
                }}
              />
            )}
            {silverStocks.length > 0 && (
              <Chip
                label={`🥈 Silver: ${silverStocks.length}`}
                size="small"
                sx={{
                  backgroundColor: "#C0C0C030",
                  color: "#778899",
                  fontWeight: 500,
                }}
              />
            )}
            {otherStocks.length > 0 && (
              <Chip
                label={`Other: ${otherStocks.length}`}
                size="small"
                sx={{
                  backgroundColor: colors.primary + "20",
                  color: colors.primary,
                  fontWeight: 500,
                }}
              />
            )}
          </Box>
        </Paper>

        {/* Enhanced Commodity Display with Futures & Options */}
        {renderCommoditySection("🥇 Gold", goldStocks, "#FFD700", "#B8860B")}
        {renderCommoditySection(
          "🛢️ Crude Oil",
          crudeStocks,
          "#2F4F4F",
          "#708090"
        )}
        {renderCommoditySection(
          "🥈 Silver",
          silverStocks,
          "#C0C0C0",
          "#778899"
        )}

        {/* Other MCX Commodities */}
        {otherStocks.length > 0 &&
          renderCommoditySection(
            "🏭 Other MCX",
            otherStocks,
            colors.primary,
            colors.primary
          )}
      </Stack>
    );
  };
  // Render function for the FNO stocks section (RESPONSIVE)
  const renderFnoSection = () => {
    return (
      <Stack spacing={2}>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
          }}
        >
          <Box sx={{ mb: 2 }}>
            <Typography
              variant="h6"
              sx={{ mb: 1, color: colors.primary, fontWeight: 700 }}
            >
              📋 F&O STOCKS REFERENCE LIST
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
              Complete F&O list: {fnoIndices.length} indices +{" "}
              {fnoStocks.length} stocks = {fnoStockList.total_count} total
              securities.
              {Object.keys(marketData || {}).length > 0
                ? ` Live prices available for ${livePriceCount} securities from market feed.`
                : " Connect to market feed to see live prices."}
              {isConnected && (
                <Box
                  component="span"
                  sx={{ color: colors.positive, fontWeight: 600 }}
                >
                  {" "}
                  📡 Live Feed Active
                </Box>
              )}
            </Typography>
            <Grid container spacing={1}>
              <Grid item xs={4} sm={2} md={1}>
                <Paper
                  sx={{
                    p: 1,
                    textAlign: "center",
                    bgcolor: "background.default",
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{ color: colors.primary, fontWeight: 700 }}
                  >
                    {fnoIndices.length}
                  </Typography>
                  <Typography variant="caption">INDICES</Typography>
                </Paper>
              </Grid>
              <Grid item xs={4} sm={2} md={1}>
                <Paper
                  sx={{
                    p: 1,
                    textAlign: "center",
                    bgcolor: "background.default",
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{ color: colors.primary, fontWeight: 700 }}
                  >
                    {fnoStocks.length}
                  </Typography>
                  <Typography variant="caption">STOCKS</Typography>
                </Paper>
              </Grid>
              <Grid item xs={4} sm={2} md={1}>
                <Paper
                  sx={{
                    p: 1,
                    textAlign: "center",
                    bgcolor: "background.default",
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{ color: colors.accent, fontWeight: 700 }}
                  >
                    {livePriceCount}
                  </Typography>
                  <Typography variant="caption">LIVE</Typography>
                </Paper>
              </Grid>
              <Grid item xs={4} sm={2} md={1}>
                <Paper
                  sx={{
                    p: 1,
                    textAlign: "center",
                    bgcolor: "background.default",
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{ color: colors.positive, fontWeight: 700 }}
                  >
                    {gainersCount}
                  </Typography>
                  <Typography variant="caption">UP</Typography>
                </Paper>
              </Grid>
              <Grid item xs={4} sm={2} md={1}>
                <Paper
                  sx={{
                    p: 1,
                    textAlign: "center",
                    bgcolor: "background.default",
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{ color: colors.negative, fontWeight: 700 }}
                  >
                    {losersCount}
                  </Typography>
                  <Typography variant="caption">DOWN</Typography>
                </Paper>
              </Grid>
            </Grid>
          </Box>
          {/* Indices Section */}
          {fnoIndices.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <MemoizedStocksListWithLivePrices
                title={`F&O INDICES (${fnoIndices.length})`} titleIcon={<AccountBalanceRounded />}
                data={fnoIndicesWithLiveData}
                layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
                showVolume={false} // Hide volume for indices
                showName={true}
                showSector={false} // Hide sector for indices
                maxItems={fnoIndices.length} // Show all indices
                isLoading={fnoLoading}
                emptyMessage="No F&O indices found"
                density="compact" // Use compact density
                compact={true}
                enhanceWithLivePrices={true}
                showLiveIndicator={true}
                // Remove fixed containerHeight to allow natural flow
              />
            </Box>
          )}
          {/* Stocks Section */}
          {fnoStocks.length > 0 && (
            <MemoizedStocksList
              title={`F&O STOCKS (${fnoStocks.length})`} titleIcon={<ReceiptLongRounded />}
              data={fnoStocksWithLiveData}
              layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
              showVolume={true} // Always show volume
              showName={true}
              showSector={true} // Always show sector
              maxItems={isMobile ? fnoStocks.length : fnoStocks.length} // Show all on mobile, limit on desktop if needed
              isLoading={fnoLoading}
              emptyMessage="No F&O stocks found"
              density="compact" // Use compact density
              compact={true}
              showOptionChain={true} // Enable option chain integration for F&O stocks
              // Remove fixed containerHeight to allow natural flow
              // containerHeight={isMobile ? "55vh" : "60vh"}
            />
          )}
        </Paper>
      </Stack>
    );
  };
  // FIXED: Analytics section renderer with comprehensive data display (RESPONSIVE - SINGLE COLUMN FOR PAIRED LISTS)
  const renderAnalyticsSection = () => (
    <Stack spacing={2}>
      {/* Market Sentiment */}
      {marketSentiment && Object.keys(marketSentiment).length > 0 && (
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
          }}
        >
          <Typography
            variant="h6"
            sx={{ mb: 1.5, color: colors.primary, fontWeight: 700 }}
          >
            📊 MARKET SENTIMENT
          </Typography>
          <Grid container spacing={1}>
            <Grid item xs={4} sm={2} md={1}>
              <Paper
                sx={{
                  p: 1,
                  textAlign: "center",
                  bgcolor: "background.default",
                }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    color:
                      marketSentiment.sentiment === "bullish"
                        ? colors.positive
                        : marketSentiment.sentiment === "bearish"
                        ? colors.negative
                        : colors.neutral,
                    fontWeight: 700,
                    textTransform: "uppercase",
                  }}
                >
                  {marketSentiment.sentiment
                    ? marketSentiment.sentiment.substring(0, 4)
                    : "NEUT"}
                </Typography>
                <Typography variant="caption">SENT</Typography>
              </Paper>
            </Grid>
            <Grid item xs={4} sm={2} md={1}>
              <Paper
                sx={{
                  p: 1,
                  textAlign: "center",
                  bgcolor: "background.default",
                }}
              >
                <Typography
                  variant="body2"
                  sx={{ color: colors.primary, fontWeight: 700 }}
                >
                  {marketSentiment.confidence || 0}%
                </Typography>
                <Typography variant="caption">CONF</Typography>
              </Paper>
            </Grid>
            {marketSentiment.market_breadth && (
              <>
                <Grid item xs={4} sm={2} md={1}>
                  <Paper
                    sx={{
                      p: 1,
                      textAlign: "center",
                      bgcolor: "background.default",
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{ color: colors.positive, fontWeight: 700 }}
                    >
                      {marketSentiment.market_breadth.advancing || 0}
                    </Typography>
                    <Typography variant="caption">ADV</Typography>
                  </Paper>
                </Grid>
                <Grid item xs={4} sm={2} md={1}>
                  <Paper
                    sx={{
                      p: 1,
                      textAlign: "center",
                      bgcolor: "background.default",
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{ color: colors.negative, fontWeight: 700 }}
                    >
                      {marketSentiment.market_breadth.declining || 0}
                    </Typography>
                    <Typography variant="caption">DEC</Typography>
                  </Paper>
                </Grid>
              </>
            )}
            {marketSentiment.sentiment_score !== undefined && (
              <Grid item xs={4} sm={2} md={1}>
                <Paper
                  sx={{
                    p: 1,
                    textAlign: "center",
                    bgcolor: "background.default",
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{
                      color:
                        marketSentiment.sentiment_score > 0
                          ? colors.positive
                          : marketSentiment.sentiment_score < 0
                          ? colors.negative
                          : colors.neutral,
                      fontWeight: 700,
                    }}
                  >
                    {marketSentiment.sentiment_score.toFixed(2)}
                  </Typography>
                  <Typography variant="caption">SCORE</Typography>
                </Paper>
              </Grid>
            )}
          </Grid>
        </Paper>
      )}
      {/* Record Movers - Stack vertically on ALL screens */}
      <Stack spacing={2}>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
            width: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {newHighs.length > 0 ? (
            <MemoizedStocksList
              title={`NEW HIGHS (${newHighs.length})`} titleIcon={<VerifiedRounded />}
              data={newHighs}
              layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
              showVolume={true} // Always show volume
              showSector={true} // Always show sector
              maxItems={isMobile ? 15 : 15} // Show fewer items on mobile
              isLoading={!isConnected}
              // Remove fixed containerHeight to allow natural flow
            />
          ) : (
            <Box sx={{ textAlign: "center", py: 2 }}>
              <Typography variant="h6" sx={{ color: colors.primary, mb: 1 }}>
                🎯 NEW HIGHS (0)
              </Typography>
              <Typography
                variant="body2"
                sx={{ color: "text.secondary", fontStyle: "italic" }}
              >
                Stocks hitting new 52-week highs
                <br />
                No data available
              </Typography>
            </Box>
          )}
        </Paper>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${colors.border}`,
            bgcolor: "background.paper",
            width: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {newLows.length > 0 ? (
            <MemoizedStocksList
              title={`NEW LOWS (${newLows.length})`} titleIcon={<VerticalAlignBottomRounded />}
              data={newLows}
              layoutType={isMobile ? "cards" : "table"} // Use cards on mobile
              showVolume={true} // Always show volume
              showSector={true} // Always show sector
              maxItems={isMobile ? 15 : 15} // Show fewer items on mobile
              isLoading={!isConnected}
              // Remove fixed containerHeight to allow natural flow
            />
          ) : (
            <Box sx={{ textAlign: "center", py: 2 }}>
              <Typography variant="h6" sx={{ color: colors.primary, mb: 1 }}>
                ⬇️ NEW LOWS (0)
              </Typography>
              <Typography
                variant="body2"
                sx={{ color: "text.secondary", fontStyle: "italic" }}
              >
                Stocks hitting new 52-week lows
                <br />
                No data available
              </Typography>
            </Box>
          )}
        </Paper>
      </Stack>
      {/* Additional Analytics Summary */}
      <Paper
        elevation={2}
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${colors.border}`,
          bgcolor: "background.paper",
        }}
      >
        <Typography
          variant="h6"
          sx={{ mb: 1.5, color: colors.primary, fontWeight: 700 }}
        >
          📈 ANALYTICS SUMMARY
        </Typography>
        <Grid container spacing={1}>
          <Grid item xs={4} sm={2} md={1}>
            <Paper
              sx={{ p: 1, textAlign: "center", bgcolor: "background.default" }}
            >
              <Typography
                variant="body2"
                sx={{
                  color: colors.positive,
                  fontWeight: 700,
                  fontSize: "1.1rem",
                }}
              >
                {getTopMoversData().gainers.length}
              </Typography>
              <Typography variant="caption">GAINERS</Typography>
            </Paper>
          </Grid>
          <Grid item xs={4} sm={2} md={1}>
            <Paper
              sx={{ p: 1, textAlign: "center", bgcolor: "background.default" }}
            >
              <Typography
                variant="body2"
                sx={{
                  color: colors.negative,
                  fontWeight: 700,
                  fontSize: "1.1rem",
                }}
              >
                {getTopMoversData().losers.length}
              </Typography>
              <Typography variant="caption">LOSERS</Typography>
            </Paper>
          </Grid>
          <Grid item xs={4} sm={2} md={1}>
            <Paper
              sx={{ p: 1, textAlign: "center", bgcolor: "background.default" }}
            >
              <Typography
                variant="body2"
                sx={{
                  color: colors.primary,
                  fontWeight: 700,
                  fontSize: "1.1rem",
                }}
              >
                {volumeLeaders.length}
              </Typography>
              <Typography variant="caption">VOLUME</Typography>
            </Paper>
          </Grid>
          <Grid item xs={4} sm={2} md={1}>
            <Paper
              sx={{ p: 1, textAlign: "center", bgcolor: "background.default" }}
            >
              <Typography
                variant="body2"
                sx={{
                  color: colors.neutral,
                  fontWeight: 700,
                  fontSize: "1.1rem",
                }}
              >
                {intradayBoosters.length}
              </Typography>
              <Typography variant="caption">BOOST</Typography>
            </Paper>
          </Grid>
          <Grid item xs={4} sm={2} md={1}>
            <Paper
              sx={{ p: 1, textAlign: "center", bgcolor: "background.default" }}
            >
              <Typography
                variant="body2"
                sx={{
                  color: colors.accent,
                  fontWeight: 700,
                  fontSize: "1.1rem",
                }}
              >
                {gapUp.length + gapDown.length}
              </Typography>
              <Typography variant="caption">GAPS</Typography>
            </Paper>
          </Grid>
          <Grid item xs={4} sm={2} md={1}>
            <Paper
              sx={{ p: 1, textAlign: "center", bgcolor: "background.default" }}
            >
              <Typography
                variant="body2"
                sx={{ color: colors.text, fontWeight: 700, fontSize: "1.1rem" }}
              >
                {breakouts.length + breakdowns.length}
              </Typography>
              <Typography variant="caption">BREAK</Typography>
            </Paper>
          </Grid>
        </Grid>
      </Paper>
    </Stack>
  );
  const renderSystemSection = () => (
    <Box sx={{ py: 2 }}>
      <SystemHealthDashboard />
    </Box>
  );
  // Render function for the footer (RESPONSIVE)
  const renderFooter = () => (
    <Paper
      elevation={3}
      sx={{
        position: "sticky",
        bottom: 0,
        left: 0,
        right: 0,
        py: 1,
        px: 2,
        bgcolor: "background.paper",
        borderTop: `1px solid ${colors.border}`,
        zIndex: 10,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 1,
        fontSize: "0.75rem",
      }}
    >
      <Typography variant="caption" sx={{ flexShrink: 0 }}>
        🔴 LIVE | {totalStocks} inst | {sectors.length} sec
      </Typography>
      <Typography variant="caption" sx={{ flexShrink: 0 }}>
        G: {getTopMoversData().gainers.length} | L:{" "}
        {getTopMoversData().losers.length}
      </Typography>
      <Typography variant="caption" sx={{ flexGrow: 1, textAlign: "right" }}>
        {new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}{" "}
        | {isConnected ? "LIVE" : "OFF"}
        {marketSummary && (
          <span style={{ marginLeft: 8 }}>
            | A/D: {marketSummary.advanceDeclineRatio} | B:{" "}
            {marketSummary.marketBreadth}%
          </span>
        )}
      </Typography>
    </Paper>
  );
  // Main render function
  return (
    <>
      {/* Global styles for animations */}
      <GlobalStyles
        styles={{
          "@keyframes pulse": {
            "0%": { opacity: 1 },
            "50%": { opacity: 0.5 },
            "100%": { opacity: 1 },
          },
        }}
      />
      <Box
        sx={{
          minHeight: "100vh",
          bgcolor: "background.default",
          color: "text.primary",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {renderHeader()}
        {/* Sticky Section Navigation */}
        <SectionNavigation
          activeSection={activeSection}
          handleSectionChange={handleSectionChange}
          colors={colors}
          isMobile={isMobile}
        />
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            py: 2,
            px: { xs: 1, sm: 2 },
            bgcolor: "background.default",
            overflowX: "hidden", // Prevent horizontal scroll on main container
          }}
        >
          <Container maxWidth="xl">
            {activeSection === "overview" && renderOverviewSection()}
            {activeSection === "search" && renderSearchSection()}
            {activeSection === "sectors" && renderSectorsSection()}
            {activeSection === "indices" && renderIndicesSection()}
            {activeSection === "movers" && renderMoversSection()}
            {activeSection === "gaps" && renderGapsSection()}
            {activeSection === "breakouts" && renderBreakoutsSection()}
            {activeSection === "mcx" && renderMcxSection()}
            {activeSection === "fno" && renderFnoSection()}
            {activeSection === "analytics" && renderAnalyticsSection()}
            {activeSection === "system" && renderSystemSection()}
          </Container>
        </Box>
        {renderFooter()}
      </Box>
    </>
  );
};
export default DashboardPage;
