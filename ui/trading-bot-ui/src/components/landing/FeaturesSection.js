import React from "react";
import {
  Box,
  Grid,
  Typography,
  Container,
  Paper,
  Card,
  CardContent,
  Divider,
  Avatar,
  Button,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import {
  Bolt,
  QueryStats,
  Timeline,
  ShowChart,
  TrendingUp,
  AutoGraph,
  Speed,
  Insights,
  Psychology,
} from "@mui/icons-material";

// Expanded features list
const features = [
  {
    icon: <Bolt fontSize="large" />,
    title: "AI Execution",
    desc: "Lightning-fast order execution with AI precision and signal-driven automation.",
    benefits: [
      "Microsecond order placement",
      "Smart slippage prevention",
      "Multi-broker support",
    ],
    color: "#3DE1FF",
  },
  {
    icon: <QueryStats fontSize="large" />,
    title: "Smart Analysis",
    desc: "Advanced market analysis powered by machine learning and trend detection.",
    benefits: [
      "Pattern recognition",
      "Market sentiment analysis",
      "Volume profile interpretation",
    ],
    color: "#FF5C8D",
  },
  {
    icon: <Timeline fontSize="large" />,
    title: "Performance Tracking",
    desc: "Monitor strategy performance, PnL, and improve continuously in real-time.",
    benefits: [
      "Real-time P&L tracking",
      "Advanced metrics dashboard",
      "Auto-generated reports",
    ],
    color: "#5EBF4D",
  },
  {
    icon: <Psychology fontSize="large" />,
    title: "AI Strategy Building",
    desc: "Let AI create and optimize trading strategies based on your preferences and risk profile.",
    benefits: [
      "Custom strategy generation",
      "Continuous optimization",
      "Multi-asset compatibility",
    ],
    color: "#F5A623",
  },
  {
    icon: <AutoGraph fontSize="large" />,
    title: "Risk Management",
    desc: "Sophisticated risk controls to protect your portfolio and maximize returns.",
    benefits: [
      "Dynamic stop-loss",
      "Position sizing algorithms",
      "Drawdown protection",
    ],
    color: "#A665FF",
  },
  {
    icon: <Insights fontSize="large" />,
    title: "Market Insights",
    desc: "Get actionable insights and predictions for market movements before they happen.",
    benefits: [
      "Institutional flow analysis",
      "Volatility forecasting",
      "Sector rotation signals",
    ],
    color: "#4DDFBF",
  },
];

const FeaturesSection = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isMedium = useMediaQuery(theme.breakpoints.down("md"));

  // Filter to show only the original 3 on mobile, all on larger screens
  const displayedFeatures = isMedium ? features.slice(0, 3) : features;

  return (
    <Box
      py={10}
      sx={{
        backgroundColor: "#010d1a",
        color: "#fff",
        position: "relative",
        backgroundImage: `
          linear-gradient(to bottom, rgba(1, 13, 26, 0.8), rgba(1, 13, 26, 1)), 
          url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%232C3E50' fill-opacity='0.15'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")
        `,
        overflow: "hidden",
      }}
    >
      {/* Background elements */}
      <Box
        sx={{
          position: "absolute",
          width: "300px",
          height: "300px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(61, 225, 255, 0.1) 0%, rgba(61, 225, 255, 0.05) 40%, rgba(1, 13, 26, 0) 70%)",
          top: "-100px",
          right: "5%",
          zIndex: 0,
        }}
      />

      <Box
        sx={{
          position: "absolute",
          width: "400px",
          height: "400px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(61, 225, 255, 0.08) 0%, rgba(61, 225, 255, 0.03) 40%, rgba(1, 13, 26, 0) 70%)",
          bottom: "-200px",
          left: "10%",
          zIndex: 0,
        }}
      />

      <Container maxWidth="lg" sx={{ position: "relative", zIndex: 1 }}>
        <Box sx={{ textAlign: "center", mb: 8 }}>
          <Typography
            variant="overline"
            sx={{
              color: "#3DE1FF",
              letterSpacing: 2,
              fontSize: "1rem",
              fontWeight: "bold",
              display: "block",
              mb: 1,
            }}
          >
            CUTTING-EDGE FEATURES
          </Typography>

          <Typography
            variant="h3"
            align="center"
            fontWeight="bold"
            mb={2}
            sx={{
              fontSize: { xs: "2rem", sm: "2.5rem", md: "3rem" },
              background: "linear-gradient(45deg, #3DE1FF, #5EBF4D)",
              backgroundClip: "text",
              textFillColor: "transparent",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Why Traders Choose Growth Quantix
          </Typography>

          <Typography
            variant="h6"
            align="center"
            sx={{
              maxWidth: "700px",
              mx: "auto",
              color: "rgba(255,255,255,0.7)",
              mb: 3,
            }}
          >
            Our platform combines cutting-edge AI technology with
            institutional-grade execution to give you an edge in any market
            condition.
          </Typography>

          <Divider
            sx={{
              width: "80px",
              mx: "auto",
              borderColor: "rgba(61, 225, 255, 0.5)",
              borderBottomWidth: 3,
              mb: 6,
            }}
          />
        </Box>

        <Grid container spacing={4}>
          {displayedFeatures.map((item, index) => (
            <Grid key={index} item xs={12} sm={6} md={4}>
              <Paper
                elevation={4}
                sx={{
                  height: "100%",
                  backgroundColor: "rgba(5, 25, 45, 0.7)",
                  backdropFilter: "blur(10px)",
                  transition:
                    "transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out",
                  borderRadius: 3,
                  overflow: "hidden",
                  border: "1px solid rgba(61, 225, 255, 0.1)",
                  "&:hover": {
                    transform: "translateY(-8px)",
                    boxShadow: `0 12px 20px -10px rgba(${
                      item.color === "#3DE1FF"
                        ? "61, 225, 255"
                        : item.color === "#FF5C8D"
                        ? "255, 92, 141"
                        : item.color === "#5EBF4D"
                        ? "94, 191, 77"
                        : item.color === "#F5A623"
                        ? "245, 166, 35"
                        : item.color === "#A665FF"
                        ? "166, 101, 255"
                        : "77, 223, 191"
                    }, 0.3)`,
                  },
                }}
              >
                <Box
                  sx={{
                    height: "8px",
                    width: "100%",
                    backgroundColor: item.color,
                  }}
                />

                <CardContent sx={{ p: 4 }}>
                  <Avatar
                    sx={{
                      width: 64,
                      height: 64,
                      backgroundColor: `${item.color}20`,
                      color: item.color,
                      mb: 2,
                      boxShadow: `0 8px 16px -8px ${item.color}40`,
                    }}
                  >
                    {item.icon}
                  </Avatar>

                  <Typography
                    variant="h5"
                    fontWeight="bold"
                    gutterBottom
                    sx={{
                      color: "#fff",
                    }}
                  >
                    {item.title}
                  </Typography>

                  <Typography
                    variant="body1"
                    sx={{
                      color: "rgba(255,255,255,0.7)",
                      mb: 3,
                      height: "60px",
                    }}
                  >
                    {item.desc}
                  </Typography>

                  <Divider
                    sx={{ my: 2, borderColor: "rgba(255,255,255,0.1)" }}
                  />

                  <Box>
                    {item.benefits.map((benefit, i) => (
                      <Box
                        key={i}
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          mb: 1,
                        }}
                      >
                        <Box
                          component="span"
                          sx={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            backgroundColor: item.color,
                            mr: 1.5,
                          }}
                        />
                        <Typography
                          variant="body2"
                          sx={{
                            color: "rgba(255,255,255,0.9)",
                          }}
                        >
                          {benefit}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </CardContent>
              </Paper>
            </Grid>
          ))}
        </Grid>

        {isMedium && (
          <Box sx={{ textAlign: "center", mt: 4 }}>
            <Button
              variant="outlined"
              size="large"
              endIcon={<ShowChart />}
              sx={{
                color: "#3DE1FF",
                borderColor: "rgba(61, 225, 255, 0.5)",
                "&:hover": {
                  backgroundColor: "rgba(61, 225, 255, 0.08)",
                  borderColor: "#3DE1FF",
                },
                py: 1,
                px: 3,
              }}
            >
              View All Features
            </Button>
          </Box>
        )}

        <Box
          sx={{
            mt: 10,
            py: 4,
            px: 4,
            borderRadius: 3,
            backgroundColor: "rgba(61, 225, 255, 0.08)",
            border: "1px solid rgba(61, 225, 255, 0.2)",
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Box sx={{ mb: { xs: 3, md: 0 } }}>
            <Typography variant="h5" fontWeight="bold" gutterBottom>
              Ready to elevate your trading?
            </Typography>
            <Typography variant="body1" sx={{ color: "rgba(255,255,255,0.7)" }}>
              Join thousands of traders using Growth Quantix to gain an edge in
              the markets.
            </Typography>
          </Box>

          <Button
            variant="contained"
            size="large"
            startIcon={<TrendingUp />}
            sx={{
              bgcolor: "#3DE1FF",
              color: "#010d1a",
              fontWeight: "bold",
              px: 4,
              py: 1.5,
              "&:hover": {
                bgcolor: "#2bc4e2",
              },
            }}
          >
            Start Trading Now
          </Button>
        </Box>
      </Container>
    </Box>
  );
};

export default FeaturesSection;
