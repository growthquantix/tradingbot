import React, { useState, useEffect } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import Layout from "./components/common/Layout";
import LandingPage from "./pages/LandingPage";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import TradeControlPage from "./pages/TradeControlPage";
import ConfigPage from "./pages/BrokerConfigPage";
import { isAuthenticated } from "./services/authService";
import { CustomThemeProvider } from "./context/ThemeContext";
import { CssBaseline } from "@mui/material";
import PrivateRoute from "./routes/PrivateRoute";
import StockAnalysisPage from "./pages/StockAnalysisPage";
import ProfilePage from "./pages/ProfilePage";
import BacktestingPage from "./pages/BacktestingPage";
import PaperTradingPage from "./pages/PaperTradingPage";
import { MarketProvider } from "./context/MarketProvider"; // ✅ NEW
import OptionChainPage from "./pages/OptionChainPage";
import AboutPage from "./pages/AboutPage";
import ContactPage from "./pages/ContactPage";
import PrivacyPolicyPage from "./pages/PrivacyPolicyPage";
import TermsPage from "./pages/TermsPage";
import SecurityPage from "./pages/SecurityPage";
import TermsModal from "./components/TermsModal";

const App = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(isAuthenticated());

  useEffect(() => {
    const checkAuth = () => setIsLoggedIn(isAuthenticated());
    window.addEventListener("storage", checkAuth);
    return () => window.removeEventListener("storage", checkAuth);
  }, []);

  return (
    <CustomThemeProvider>
      <CssBaseline />
      <Router>
        <TermsModal />
        <Routes>
          <Route
            path="/"
            element={
              isLoggedIn ? <Navigate to="/dashboard" /> : <LandingPage />
            }
          />

          {/* ✅ Wrap private routes with MarketProvider */}
          <Route
            element={
              <PrivateRoute>
                <MarketProvider>
                  <Layout />
                </MarketProvider>
              </PrivateRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/option-chain/:symbol" element={<OptionChainPage />} />

            <Route path="/trade-control" element={<TradeControlPage />} />
            <Route path="/config" element={<ConfigPage />} />
            <Route path="/backtesting" element={<BacktestingPage />} />
            <Route path="/papertrading" element={<PaperTradingPage />} />
            <Route path="/analysis" element={<StockAnalysisPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>

          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/privacy" element={<PrivacyPolicyPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/security" element={<SecurityPage />} />
        </Routes>
      </Router>
    </CustomThemeProvider>
  );
};

export default App;
