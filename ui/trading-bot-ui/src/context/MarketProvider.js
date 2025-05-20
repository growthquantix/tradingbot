import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
} from "react";
import axios from "axios";
import { getSocket } from "../utils/socket";

const MarketContext = createContext();
export const useMarket = () => useContext(MarketContext);

// 🔄 Global single WebSocket instance
let globalWs = null;
let globalPingInterval = null;

export const MarketProvider = ({ children }) => {
  const [groupedStocks, setGroupedStocks] = useState({});
  const [ltps, setLtps] = useState({});
  const [marketStatus, setMarketStatus] = useState("loading");
  const [tokenExpired, setTokenExpired] = useState(false);

  const connectingRef = useRef(false);
  const hasReceivedFeed = useRef(false);
  const reconnectTimeoutRef = useRef(null);

  // Function to reset token expired state
  const resetTokenExpired = () => {
    setTokenExpired(false);
  };

  const disconnectWebSocket = () => {
    if (globalWs) globalWs.close();
    if (globalPingInterval) clearInterval(globalPingInterval);
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    globalWs = null;
    globalPingInterval = null;
    reconnectTimeoutRef.current = null;
    connectingRef.current = false;
    hasReceivedFeed.current = false;
  };

  useEffect(() => {
    const fetchGrouped = async () => {
      try {
        const res = await axios.get(
          `${process.env.REACT_APP_API_URL}/api/stocks/top`
        );
        const stocks = res.data?.data || {};
        setGroupedStocks(stocks);
      } catch (err) {
        console.error("❌ Failed to fetch stock groups:", err);
      }
    };

    fetchGrouped();
  }, []);

  useEffect(() => {
    if (
      Object.keys(groupedStocks).length === 0 ||
      globalWs ||
      connectingRef.current
    )
      return;

    const token = localStorage.getItem("access_token");
    if (!token) return;

    const wsUrl = `${process.env.REACT_APP_API_URL.replace(
      /^http/,
      "ws"
    )}/ws/market?token=${token}`;
    const ws = getSocket(wsUrl);
    globalWs = ws;
    connectingRef.current = true;

    ws.onopen = () => {
      connectingRef.current = false;
      globalPingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 30000);

      console.info("✅ WebSocket connected. Backend handles subscriptions.");
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === "error" && msg.reason === "token_expired") {
          // Always set tokenExpired to true when we get this message
          setTokenExpired(true);
          console.log("❌ Token expired notification received");
          disconnectWebSocket();
          return;
        }

        if (msg.type === "market_info") {
          const status = msg.marketStatus?.toLowerCase() || "closed";
          setMarketStatus(status);
        }

        if (msg.type === "live_feed" && msg.data) {
          hasReceivedFeed.current = true;
          const feeds = msg.data;

          console.log("📡 Received live data for:", Object.keys(feeds));

          setLtps((prev) => {
            const updates = { ...prev };
            Object.entries(feeds).forEach(([key, parsed]) => {
              if (parsed?.ltp !== undefined) {
                const isIndexKey =
                  key.startsWith("NSE_INDEX|") || key.startsWith("BSE_INDEX|");
                const finalKey = isIndexKey ? key : key.toUpperCase();
                updates[finalKey] = {
                  ltp: parsed.ltp ?? null,
                  cp: parsed.cp ?? null,
                  ohlc: parsed.ohlc ?? [],
                  iv: parsed.iv ?? null,
                  oi: parsed.oi ?? null,
                  atp: parsed.atp ?? null,
                  bid_ask: parsed.bid_ask ?? [],
                  greeks: parsed.greeks ?? {},
                  ltq: parsed.ltq ?? null,
                  last_trade_time: parsed.last_trade_time ?? null,
                };
              }
            });
            return updates;
          });
        }
      } catch (e) {
        console.error("⚠️ WebSocket parse error:", e);
      }
    };

    ws.onclose = () => {
      console.warn("❌ WebSocket closed");
      disconnectWebSocket();
    };

    ws.onerror = (err) => {
      console.error("💥 WebSocket error:", err);
      disconnectWebSocket();
    };
  }, [groupedStocks]);

  return (
    <MarketContext.Provider
      value={{
        groupedStocks,
        ltps,
        marketStatus,
        tokenExpired,
        resetTokenExpired,
      }}
    >
      {children}
    </MarketContext.Provider>
  );
};

export default MarketProvider;
