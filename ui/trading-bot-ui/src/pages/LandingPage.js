import React, { useState, lazy, Suspense, useEffect, useRef } from "react";
import {
  Box,
  Container,
  useMediaQuery,
  useTheme,
  CssBaseline,
  ThemeProvider,
  createTheme,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { isAuthenticated } from "../services/authService";
import NavBar from "../components/landing/NavBar";
import HeroSection from "../components/landing/HeroSection";
import StrategySection from "../components/landing/StrategySection";
import ToolsSection from "../components/landing/ToolsSection";
import BacktestSection from "../components/landing/BacktestSection";
import FAQSection from "../components/landing/FAQSection";
import VideoEmbedSection from "../components/landing/VideoEmbedSection";
import PricingPlansSection from "../components/landing/PricingSection";
import TrustBadgesSection from "../components/landing/TrustBadgesSection";
import ScreenerAlertsSection from "../components/landing/ScreenerAlertsSection";
import AIAgentSection from "../components/landing/AIAgentSection";
import Footer from "../components/common/Footer";
import HowAIWorksSection from "../components/landing/HowAIWorksSection";
import StrategyBacktestingSection from "../components/landing/StrategyBacktestingSection";
import ToolkitSection from "../components/landing/ToolkitSection";
import VisionSection from "../components/landing/VisionSection";
import TestimonialsSection from "../components/landing/TestimonialsSection";
import SupportedBrokersSection from "../components/landing/SupportedBrokersSection";

// Lazy load the Auth modal for better performance
const LazyAuthModal = lazy(() => import("../components/auth/AuthModal"));

// Create a custom theme with responsive breakpoints
const darkTheme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#3f8fff",
      light: "#75b8ff",
      dark: "#0062cc",
    },
    secondary: {
      main: "#19de9b",
      light: "#6effce",
      dark: "#00ac6c",
    },
    background: {
      default: "#030712",
      paper: "#111827",
    },
    text: {
      primary: "#ffffff",
      secondary: "rgba(255, 255, 255, 0.7)",
    },
  },
  typography: {
    fontFamily: "'Inter', 'Roboto', 'Helvetica', 'Arial', sans-serif",
    h1: {
      fontSize: "3.5rem",
      "@media (max-width:900px)": {
        fontSize: "2.5rem",
      },
      "@media (max-width:600px)": {
        fontSize: "2rem",
      },
    },
    h2: {
      fontSize: "2.8rem",
      "@media (max-width:900px)": {
        fontSize: "2.2rem",
      },
      "@media (max-width:600px)": {
        fontSize: "1.8rem",
      },
    },
    h3: {
      fontSize: "2.2rem",
      "@media (max-width:900px)": {
        fontSize: "1.8rem",
      },
      "@media (max-width:600px)": {
        fontSize: "1.5rem",
      },
    },
    button: {
      textTransform: "none",
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: "8px",
          padding: "10px 20px",
          fontSize: "1rem",
          transition: "all 0.3s ease",
          "&:hover": {
            transform: "translateY(-2px)",
            boxShadow: "0 7px 14px rgba(0, 0, 0, 0.25)",
          },
        },
        containedPrimary: {
          background: "linear-gradient(45deg, #3f8fff 30%, #75b8ff 90%)",
        },
        containedSecondary: {
          background: "linear-gradient(45deg, #19de9b 30%, #6effce 90%)",
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backdropFilter: "blur(10px)",
          backgroundColor: "rgba(17, 24, 39, 0.7)",
          borderRadius: "16px",
          boxShadow: "0 10px 20px rgba(0, 0, 0, 0.2)",
          transition: "transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out",
          "&:hover": {
            transform: "translateY(-5px)",
            boxShadow: "0 15px 30px rgba(0, 0, 0, 0.3)",
          },
        },
      },
    },
    MuiContainer: {
      styleOverrides: {
        root: {
          paddingLeft: "24px",
          paddingRight: "24px",
          "@media (min-width:600px)": {
            paddingLeft: "32px",
            paddingRight: "32px",
          },
        },
      },
    },
  },
});

// Intersection Observer component for animations
const FadeInSection = ({ children }) => {
  const [isVisible, setVisible] = useState(false);
  const domRef = useRef();

  useEffect(() => {
    const currentRef = domRef.current;
    if (!currentRef) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisible(true);
          observer.unobserve(currentRef);
        }
      },
      { threshold: 0.15 }
    );

    observer.observe(currentRef);
    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
    };
  }, []);

  return (
    <div
      ref={domRef}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "translateY(0)" : "translateY(20px)",
        transition: "opacity 0.6s ease-out, transform 0.6s ease-out",
      }}
    >
      {children}
    </div>
  );
};

const LandingPage = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const isUserAuthenticated = isAuthenticated();
  const [authOpen, setAuthOpen] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  const [isScrolled, setIsScrolled] = useState(false);
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isTablet = useMediaQuery(theme.breakpoints.down("md"));

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Smooth scroll to sections
  useEffect(() => {
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
      anchor.addEventListener("click", function (e) {
        e.preventDefault();

        const targetId = this.getAttribute("href").substring(1);
        const targetElement = document.getElementById(targetId);

        if (targetElement) {
          window.scrollTo({
            top: targetElement.offsetTop - 80, // Adjust for navbar height
            behavior: "smooth",
          });
        }
      });
    });
  }, []);

  const handleGetStarted = () => {
    if (isUserAuthenticated) {
      navigate("/dashboard");
    } else {
      setIsLogin(true);
      setAuthOpen(true);
    }
  };

  // Custom scroll indicator
  const [scrollPercentage, setScrollPercentage] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const windowHeight =
        document.documentElement.scrollHeight -
        document.documentElement.clientHeight;
      const scrolled = (window.scrollY / windowHeight) * 100;
      setScrollPercentage(scrolled);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />

      {/* Scroll Progress Indicator */}
      <Box
        sx={{
          position: "fixed",
          top: 0,
          left: 0,
          height: "4px",
          width: `${scrollPercentage}%`,
          backgroundColor: theme.palette.primary.main,
          backgroundImage: `linear-gradient(to right, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
          zIndex: 2000,
          transition: "width 0.1s",
        }}
      />

      {/* Enhanced NavBar with scroll effect */}
      <NavBar
        isScrolled={isScrolled}
        isMobile={isMobile}
        onSignIn={() => {
          setIsLogin(true);
          setAuthOpen(true);
        }}
        onSignUp={() => {
          setIsLogin(false);
          setAuthOpen(true);
        }}
      />

      {/* All Sections with enhanced styling */}
      <Box
        sx={{
          background: `linear-gradient(to bottom, #030712, #111827)`,
          color: theme.palette.text.primary,
          overflow: "hidden",
          position: "relative",
        }}
      >
        {/* Dynamic background elements */}
        <Box
          sx={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            opacity: 0.1,
            zIndex: 0,
            background:
              "radial-gradient(circle at 50% 50%, rgba(63, 143, 255, 0.15), transparent 70%)",
            pointerEvents: "none",
          }}
        />

        {/* Animated grid background */}
        <Box
          sx={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            opacity: 0.05,
            zIndex: 0,
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
            backgroundSize: isMobile ? "30px 30px" : "60px 60px",
            pointerEvents: "none",
          }}
        />

        {/* Floating gradient orbs for visual interest */}
        <Box
          sx={{
            position: "absolute",
            top: "20%",
            left: "5%",
            width: isMobile ? "150px" : "300px",
            height: isMobile ? "150px" : "300px",
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(63, 143, 255, 0.1) 0%, rgba(25, 222, 155, 0.05) 70%, transparent 100%)",
            filter: "blur(40px)",
            animation: "float 15s ease-in-out infinite alternate",
            zIndex: 0,
            "@keyframes float": {
              "0%": { transform: "translateY(0) translateX(0)" },
              "50%": { transform: "translateY(-30px) translateX(20px)" },
              "100%": { transform: "translateY(20px) translateX(-20px)" },
            },
          }}
        />

        <Box
          sx={{
            position: "absolute",
            bottom: "30%",
            right: "10%",
            width: isMobile ? "100px" : "200px",
            height: isMobile ? "100px" : "200px",
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(25, 222, 155, 0.1) 0%, rgba(63, 143, 255, 0.05) 70%, transparent 100%)",
            filter: "blur(30px)",
            animation: "float2 18s ease-in-out infinite alternate",
            zIndex: 0,
            "@keyframes float2": {
              "0%": { transform: "translateY(0) translateX(0)" },
              "50%": { transform: "translateY(40px) translateX(-30px)" },
              "100%": { transform: "translateY(-30px) translateX(40px)" },
            },
          }}
        />

        {/* Main content with fade-in animations */}
        <Container maxWidth="xl" sx={{ position: "relative", zIndex: 1 }}>
          <FadeInSection>
            <HeroSection
              onGetStarted={handleGetStarted}
              isMobile={isMobile}
              isTablet={isTablet}
            />
          </FadeInSection>

          <FadeInSection>
            <VideoEmbedSection isMobile={isMobile} />
          </FadeInSection>

          <FadeInSection>
            <StrategySection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <ToolsSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <ScreenerAlertsSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <HowAIWorksSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <StrategyBacktestingSection
              isMobile={isMobile}
              isTablet={isTablet}
            />
          </FadeInSection>

          <FadeInSection>
            <AIAgentSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <PricingPlansSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <TrustBadgesSection isMobile={isMobile} />
          </FadeInSection>

          <FadeInSection>
            <BacktestSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <SupportedBrokersSection isMobile={isMobile} />
          </FadeInSection>

          <FadeInSection>
            <ToolkitSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <VisionSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <TestimonialsSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>

          <FadeInSection>
            <FAQSection isMobile={isMobile} isTablet={isTablet} />
          </FadeInSection>
        </Container>

        <Footer isMobile={isMobile} />
      </Box>

      {/* Auth Modal (Sign In/Up) with loading state */}
      <Suspense
        fallback={
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              height: "100vh",
              width: "100vw",
              position: "fixed",
              top: 0,
              left: 0,
              background: "rgba(3, 7, 18, 0.8)",
              backdropFilter: "blur(8px)",
              zIndex: 9999,
            }}
          >
            <Box
              sx={{
                width: "40px",
                height: "40px",
                borderRadius: "50%",
                border: "3px solid rgba(63, 143, 255, 0.3)",
                borderTop: "3px solid #3f8fff",
                animation: "spin 1s linear infinite",
                "@keyframes spin": {
                  "0%": { transform: "rotate(0deg)" },
                  "100%": { transform: "rotate(360deg)" },
                },
              }}
            />
          </Box>
        }
      >
        {authOpen && (
          <LazyAuthModal
            open={authOpen}
            handleClose={() => setAuthOpen(false)}
            onLoginSuccess={() => {
              setAuthOpen(false);
              navigate("/dashboard");
            }}
            isLogin={isLogin}
            setIsLogin={setIsLogin}
            isMobile={isMobile}
          />
        )}
      </Suspense>

      {/* Back to top button */}
      <Box
        onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        sx={{
          position: "fixed",
          bottom: "20px",
          right: "20px",
          width: "50px",
          height: "50px",
          borderRadius: "50%",
          backgroundColor: "rgba(63, 143, 255, 0.8)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          cursor: "pointer",
          zIndex: 999,
          boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
          opacity: isScrolled ? 1 : 0,
          transition: "opacity 0.3s ease",
          "&:hover": {
            backgroundColor: theme.palette.primary.main,
            transform: "translateY(-5px)",
          },
          "&::before": {
            content: '""',
            width: "10px",
            height: "10px",
            borderTop: "2px solid #fff",
            borderLeft: "2px solid #fff",
            transform: "rotate(45deg) translateY(2px)",
          },
        }}
      />
    </ThemeProvider>
  );
};

export default LandingPage;
