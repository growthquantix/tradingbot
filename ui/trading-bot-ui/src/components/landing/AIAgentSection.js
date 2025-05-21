import React from "react";
import {
  Box,
  Container,
  Typography,
  Button,
  Grid,
  Paper,
  Avatar,
  Chip,
} from "@mui/material";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import PsychologyIcon from "@mui/icons-material/Psychology";
import SpeedIcon from "@mui/icons-material/Speed";
import CodeIcon from "@mui/icons-material/Code";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import AutorenewIcon from "@mui/icons-material/Autorenew";
import TuneIcon from "@mui/icons-material/Tune";

const AIAgentSection = () => {
  // const theme = useTheme();
  // const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

  // Mock conversation with AI agent
  const conversation = [
    {
      role: "user",
      message:
        "Create a momentum strategy for NIFTY with 14-day RSI and 20-day EMA",
    },
    {
      role: "ai",
      message:
        "Building momentum strategy with RSI(14) and EMA(20) for NIFTY...\n\nStrategy parameters:\n- Entry: RSI crosses above 55 and price > EMA(20)\n- Exit: RSI crosses below 45 or 8% profit target reached\n- Stop loss: 3% from entry price",
    },
    {
      role: "user",
      message: "Backtest this strategy for the last 6 months",
    },
    {
      role: "ai",
      message:
        "Running backtest from Nov 2023 to May 2024...\n\nResults:\n✅ Win rate: 72%\n✅ Profit factor: 2.3\n✅ Max drawdown: 5.2%\n✅ Total trades: 28\n✅ Net profit: ₹92,450 (9.24%)",
    },
    {
      role: "user",
      message: "Can you optimize the RSI parameters?",
    },
    {
      role: "ai",
      message:
        "Optimizing RSI parameters...\n\nTested RSI periods (7-21) and thresholds (40-70).\n\nOptimal parameters:\n- RSI period: 12 days\n- Entry threshold: 58\n- Exit threshold: 42\n\nImproved results:\n✅ Win rate: 78% (+6%)\n✅ Profit factor: 2.8 (+0.5)\n✅ Max drawdown: 4.3% (-0.9%)",
    },
  ];

  const features = [
    {
      icon: <PsychologyIcon sx={{ color: "#00BFFF" }} />,
      title: "Natural Language Strategy Building",
      description:
        "Simply describe your strategy idea, and our AI will build and code it",
    },
    {
      icon: <SpeedIcon sx={{ color: "#00BFFF" }} />,
      title: "Automated Backtesting",
      description:
        "Test strategies against historical data with comprehensive metrics",
    },
    {
      icon: <TuneIcon sx={{ color: "#00BFFF" }} />,
      title: "Parameter Optimization",
      description:
        "Let AI find the optimal parameters for your trading strategies",
    },
    {
      icon: <AutorenewIcon sx={{ color: "#00BFFF" }} />,
      title: "Continuous Learning",
      description:
        "AI improves strategies based on market conditions and performance",
    },
  ];

  return (
    <Box
      sx={{
        py: { xs: 8, md: 12 },
        bgcolor: "#14161f",
        color: "#fff",
        backgroundImage:
          "radial-gradient(circle at 50% 50%, #1c1f2e 0%, #14161f 50%)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Decorative elements */}
      <Box
        sx={{
          position: "absolute",
          width: "400px",
          height: "400px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(0,191,255,0.08) 0%, rgba(0,61,81,0.03) 70%, rgba(20,22,31,0) 100%)",
          top: "-200px",
          left: "-100px",
          zIndex: 0,
        }}
      />

      <Box
        sx={{
          position: "absolute",
          width: "300px",
          height: "300px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(0,191,255,0.05) 0%, rgba(0,61,81,0.02) 70%, rgba(20,22,31,0) 100%)",
          bottom: "-150px",
          right: "-50px",
          zIndex: 0,
        }}
      />

      <Container maxWidth="lg" sx={{ position: "relative", zIndex: 1 }}>
        <Grid container spacing={6} alignItems="center">
          <Grid item xs={12} md={6}>
            <Box sx={{ mb: { xs: 4, md: 0 } }}>
              <Chip
                icon={<SmartToyIcon />}
                label="AI AGENT"
                sx={{
                  bgcolor: "rgba(0, 191, 255, 0.1)",
                  color: "#00BFFF",
                  fontWeight: "bold",
                  mb: 3,
                  borderRadius: "4px",
                }}
              />

              <Typography
                variant="h3"
                fontWeight="bold"
                gutterBottom
                sx={{
                  fontSize: { xs: "2rem", sm: "2.5rem", md: "3rem" },
                  lineHeight: 1.2,
                  background:
                    "linear-gradient(90deg, #FFFFFF 0%, #00BFFF 100%)",
                  backgroundClip: "text",
                  textFillColor: "transparent",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  mb: 2,
                }}
              >
                An AI Agent to build winning strategies
              </Typography>

              <Typography
                variant="h6"
                sx={{
                  mb: 4,
                  color: "rgba(255, 255, 255, 0.8)",
                  fontWeight: "normal",
                  lineHeight: 1.6,
                }}
              >
                Ask GrowthQuantix's AI Agent to build, test, and optimize
                strategies using backtesting on historical data. Unlock smarter,
                automated decision-making and significantly improve your win
                rate with AI-powered insights.
              </Typography>

              <Grid container spacing={3} sx={{ mb: 4 }}>
                {features.map((feature, i) => (
                  <Grid item xs={12} sm={6} key={i}>
                    <Box sx={{ display: "flex", mb: 1 }}>
                      <Avatar
                        sx={{
                          mr: 1.5,
                          bgcolor: "rgba(0, 191, 255, 0.1)",
                          width: 42,
                          height: 42,
                        }}
                      >
                        {feature.icon}
                      </Avatar>
                      <Box>
                        <Typography
                          variant="subtitle1"
                          sx={{
                            fontWeight: "bold",
                            color: "#00BFFF",
                          }}
                        >
                          {feature.title}
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{
                            color: "rgba(255, 255, 255, 0.7)",
                          }}
                        >
                          {feature.description}
                        </Typography>
                      </Box>
                    </Box>
                  </Grid>
                ))}
              </Grid>

              <Button
                variant="contained"
                size="large"
                endIcon={<ArrowForwardIcon />}
                sx={{
                  bgcolor: "#00BFFF",
                  color: "#14161f",
                  py: 1.5,
                  px: 4,
                  fontWeight: "bold",
                  borderRadius: "4px",
                  "&:hover": {
                    bgcolor: "#00a6dd",
                  },
                  boxShadow: "0 4px 14px rgba(0, 191, 255, 0.3)",
                }}
              >
                Get Access Now
              </Button>

              <Button
                variant="outlined"
                size="large"
                startIcon={<CodeIcon />}
                sx={{
                  ml: 2,
                  color: "#00BFFF",
                  borderColor: "rgba(0, 191, 255, 0.5)",
                  py: 1.5,
                  "&:hover": {
                    borderColor: "#00BFFF",
                    bgcolor: "rgba(0, 191, 255, 0.05)",
                  },
                }}
              >
                View Demo
              </Button>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper
              elevation={20}
              sx={{
                bgcolor: "rgba(24, 27, 41, 0.7)",
                backdropFilter: "blur(10px)",
                p: 0,
                borderRadius: 3,
                overflow: "hidden",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {/* Chat header */}
              <Box
                sx={{
                  bgcolor: "rgba(0, 0, 0, 0.2)",
                  p: 2,
                  display: "flex",
                  alignItems: "center",
                  borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
                }}
              >
                <Avatar sx={{ bgcolor: "#00BFFF", mr: 2 }}>
                  <SmartToyIcon />
                </Avatar>
                <Box>
                  <Typography variant="subtitle1" fontWeight="bold">
                    QuantixAI Agent
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ color: "rgba(255, 255, 255, 0.6)" }}
                  >
                    Online • Ready to help
                  </Typography>
                </Box>
              </Box>

              {/* Chat messages */}
              <Box
                sx={{
                  p: 2,
                  flexGrow: 1,
                  overflowY: "auto",
                  maxHeight: 450,
                }}
              >
                {conversation.map((msg, i) => (
                  <Box
                    key={i}
                    sx={{
                      display: "flex",
                      flexDirection:
                        msg.role === "user" ? "row-reverse" : "row",
                      mb: 2,
                    }}
                  >
                    <Paper
                      sx={{
                        p: 2,
                        maxWidth: "80%",
                        borderRadius: 2,
                        bgcolor:
                          msg.role === "user"
                            ? "rgba(0, 191, 255, 0.15)"
                            : "rgba(255, 255, 255, 0.05)",
                        border:
                          msg.role === "user"
                            ? "1px solid rgba(0, 191, 255, 0.3)"
                            : "1px solid rgba(255, 255, 255, 0.1)",
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          whiteSpace: "pre-wrap",
                          color:
                            msg.role === "user"
                              ? "#fff"
                              : "rgba(255, 255, 255, 0.9)",
                        }}
                      >
                        {msg.message}
                      </Typography>
                    </Paper>
                  </Box>
                ))}
              </Box>

              {/* Input area */}
              <Box
                sx={{
                  p: 2,
                  borderTop: "1px solid rgba(255, 255, 255, 0.05)",
                  bgcolor: "rgba(0, 0, 0, 0.2)",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    color: "rgba(255, 255, 255, 0.6)",
                    fontStyle: "italic",
                  }}
                >
                  Ask the AI agent to build, test, or optimize trading
                  strategies...
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default AIAgentSection;
