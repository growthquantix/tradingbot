import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";

const StockContext = createContext();

export const useStockData = () => useContext(StockContext);

export const StockProvider = ({ children }) => {
  const [stocks, setStocks] = useState([]);

  const fetchStocks = async () => {
    try {
      const cached = sessionStorage.getItem("top_stocks");
      if (cached) {
        setStocks(JSON.parse(cached));
        return;
      }

      const res = await axios.get(
        `${process.env.REACT_APP_API_URL}/api/top-stocks`
      ); // Replace with actual API
      setStocks(res.data);
      sessionStorage.setItem("top_stocks", JSON.stringify(res.data));
    } catch (error) {
      console.error("Failed to fetch top stocks", error);
    }
  };

  useEffect(() => {
    fetchStocks();
  }, []);

  return (
    <StockContext.Provider value={{ stocks }}>{children}</StockContext.Provider>
  );
};
