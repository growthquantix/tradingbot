import {
  Box,
  Typography,
  Container,
  Grid,
  Paper,
  useTheme,
  alpha,
} from "@mui/material";
import {
  Visibility,
  Notifications,
  Search,
  TrendingUp,
  ShowChart,
  PriceCheck,
} from "@mui/icons-material";

const ScreenerAlertsSection = () => {
  const theme = useTheme();

  // Mock data for screener
  const screenerData = [
    { symbol: "HDFC Bank", change: "+2.5%", signal: "BUY", confidence: "87%" },
    { symbol: "TCS", change: "+1.8%", signal: "HOLD", confidence: "65%" },
    { symbol: "Reliance", change: "-0.7%", signal: "SELL", confidence: "82%" },
  ];

  // Mock data for alerts
  const alertData = [
    {
      type: "Breakout",
      symbol: "TCS",
      message: "Crossed resistance at ₹3540",
      time: "2 min ago",
    },
    {
      type: "Pattern",
      symbol: "INFY",
      message: "Bullish engulfing pattern",
      time: "15 min ago",
    },
    {
      type: "AI Signal",
      symbol: "HDFCBANK",
      message: "Strong buy signal detected",
      time: "32 min ago",
    },
  ];

  return (
    <Box
      id="screener-alerts"
      sx={{
        py: 12,
        background: `linear-gradient(to bottom, #05071a, #0a0c10)`,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Decorative elements */}
      <Box
        sx={{
          position: "absolute",
          top: "10%",
          left: "-10%",
          width: "300px",
          height: "300px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(0,100,255,0.05), transparent 70%)",
          filter: "blur(50px)",
          zIndex: 0,
        }}
      />

      <Container maxWidth="lg" sx={{ position: "relative", zIndex: 1 }}>
        <Box sx={{ textAlign: "center", mb: 8 }}>
          <Typography
            variant="h4"
            fontWeight={800}
            gutterBottom
            sx={{
              background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Live Screener + Alerts
          </Typography>
          <Typography
            variant="h6"
            color="rgba(255,255,255,0.7)"
            sx={{ maxWidth: 700, mx: "auto" }}
          >
            Never miss a trading opportunity with our intelligent screeners and
            real-time alerts
          </Typography>
        </Box>

        <Grid container spacing={5}>
          {/* Screener Panel */}
          <Grid item xs={12} md={6}>
            <Paper
              elevation={0}
              sx={{
                p: 3,
                height: "100%",
                background: alpha(theme.palette.background.paper, 0.05),
                backdropFilter: "blur(10px)",
                border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
                borderRadius: 4,
                overflow: "hidden",
                position: "relative",
              }}
            >
              {/* Visual elements */}
              <Box
                sx={{
                  position: "absolute",
                  top: -20,
                  right: -20,
                  width: 100,
                  height: 100,
                  borderRadius: "50%",
                  background: alpha(theme.palette.primary.main, 0.1),
                  filter: "blur(30px)",
                }}
              />

              <Box sx={{ display: "flex", alignItems: "center", mb: 3 }}>
                <Search sx={{ color: theme.palette.primary.main, mr: 2 }} />
                <Typography variant="h6" fontWeight={600} color="white">
                  AI-Powered Stock Screener
                </Typography>
              </Box>

              <Box
                sx={{
                  mb: 3,
                  pb: 1,
                  borderBottom: `1px solid ${alpha("#fff", 0.1)}`,
                }}
              >
                <Grid
                  container
                  sx={{
                    px: 1,
                    color: alpha("#fff", 0.6),
                    fontSize: "0.85rem",
                    fontWeight: 500,
                  }}
                >
                  <Grid item xs={4}>
                    Symbol
                  </Grid>
                  <Grid item xs={2} sx={{ textAlign: "center" }}>
                    Change
                  </Grid>
                  <Grid item xs={3} sx={{ textAlign: "center" }}>
                    Signal
                  </Grid>
                  <Grid item xs={3} sx={{ textAlign: "right" }}>
                    Confidence
                  </Grid>
                </Grid>
              </Box>

              <Box sx={{ mb: 2 }}>
                {screenerData.map((item, idx) => (
                  <Paper
                    key={idx}
                    sx={{
                      p: 2,
                      mb: 1.5,
                      background: alpha(theme.palette.background.paper, 0.1),
                      border: `1px solid ${alpha("#fff", 0.05)}`,
                      borderRadius: 2,
                      "&:hover": {
                        background: alpha(theme.palette.background.paper, 0.15),
                        borderColor: alpha(theme.palette.primary.main, 0.3),
                      },
                      transition: "all 0.2s ease",
                    }}
                  >
                    <Grid container alignItems="center">
                      <Grid item xs={4}>
                        <Box sx={{ display: "flex", alignItems: "center" }}>
                          <ShowChart
                            sx={{
                              fontSize: 20,
                              mr: 1,
                              color: theme.palette.primary.main,
                            }}
                          />
                          <Typography fontWeight={500} color="white">
                            {item.symbol}
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={2} sx={{ textAlign: "center" }}>
                        <Typography
                          sx={{
                            color: item.change.startsWith("+")
                              ? theme.palette.success.main
                              : theme.palette.error.main,
                            fontWeight: 500,
                          }}
                        >
                          {item.change}
                        </Typography>
                      </Grid>
                      <Grid item xs={3} sx={{ textAlign: "center" }}>
                        <Box
                          sx={{
                            display: "inline-block",
                            py: 0.5,
                            px: 1.5,
                            borderRadius: 1,
                            backgroundColor:
                              item.signal === "BUY"
                                ? alpha(theme.palette.success.main, 0.2)
                                : item.signal === "SELL"
                                ? alpha(theme.palette.error.main, 0.2)
                                : alpha(theme.palette.warning.main, 0.2),
                            color:
                              item.signal === "BUY"
                                ? theme.palette.success.main
                                : item.signal === "SELL"
                                ? theme.palette.error.main
                                : theme.palette.warning.main,
                            fontSize: "0.75rem",
                            fontWeight: 700,
                          }}
                        >
                          {item.signal}
                        </Box>
                      </Grid>
                      <Grid item xs={3} sx={{ textAlign: "right" }}>
                        <Typography
                          fontWeight={600}
                          color={theme.palette.primary.main}
                        >
                          {item.confidence}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Paper>
                ))}
              </Box>

              <Box
                sx={{
                  textAlign: "center",
                  mt: 2,
                  color: alpha("#fff", 0.5),
                  fontSize: "0.85rem",
                }}
              >
                <Visibility sx={{ fontSize: 16, mr: 0.5, mb: -0.3 }} />
                Real-time data refreshes every 5 seconds
              </Box>
            </Paper>
          </Grid>

          {/* Alerts Panel */}
          <Grid item xs={12} md={6}>
            <Paper
              elevation={0}
              sx={{
                p: 3,
                height: "100%",
                background: alpha(theme.palette.background.paper, 0.05),
                backdropFilter: "blur(10px)",
                border: `1px solid ${alpha(theme.palette.secondary.main, 0.2)}`,
                borderRadius: 4,
                overflow: "hidden",
                position: "relative",
              }}
            >
              {/* Visual elements */}
              <Box
                sx={{
                  position: "absolute",
                  bottom: -20,
                  left: -20,
                  width: 100,
                  height: 100,
                  borderRadius: "50%",
                  background: alpha(theme.palette.secondary.main, 0.1),
                  filter: "blur(30px)",
                }}
              />

              <Box sx={{ display: "flex", alignItems: "center", mb: 3 }}>
                <Notifications
                  sx={{ color: theme.palette.secondary.main, mr: 2 }}
                />
                <Typography variant="h6" fontWeight={600} color="white">
                  Smart Alerts
                </Typography>
              </Box>

              <Box sx={{ mb: 3 }}>
                {alertData.map((alert, idx) => {
                  // Determine styling based on alert type
                  const getAlertStyle = (type) => {
                    switch (type) {
                      case "Breakout":
                        return {
                          bg: alpha(theme.palette.success.main, 0.2),
                          border: alpha(theme.palette.success.main, 0.3),
                          color: theme.palette.success.main,
                          icon: <TrendingUp />,
                        };
                      case "Pattern":
                        return {
                          bg: alpha(theme.palette.info.main, 0.2),
                          border: alpha(theme.palette.info.main, 0.3),
                          color: theme.palette.info.main,
                          icon: <ShowChart />,
                        };
                      case "AI Signal":
                        return {
                          bg: alpha(theme.palette.secondary.main, 0.2),
                          border: alpha(theme.palette.secondary.main, 0.3),
                          color: theme.palette.secondary.main,
                          icon: <PriceCheck />,
                        };
                      default:
                        return {
                          bg: alpha(theme.palette.primary.main, 0.2),
                          border: alpha(theme.palette.primary.main, 0.3),
                          color: theme.palette.primary.main,
                          icon: <Notifications />,
                        };
                    }
                  };

                  const style = getAlertStyle(alert.type);

                  return (
                    <Paper
                      key={idx}
                      sx={{
                        p: 2,
                        mb: 2,
                        backgroundColor: style.bg,
                        border: `1px solid ${style.border}`,
                        borderRadius: 2,
                      }}
                    >
                      <Box sx={{ display: "flex", alignItems: "flex-start" }}>
                        <Box
                          sx={{
                            mr: 2,
                            mt: 0.5,
                            p: 0.8,
                            borderRadius: 1.5,
                            backgroundColor: alpha(style.color, 0.1),
                            color: style.color,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          {style.icon}
                        </Box>

                        <Box sx={{ flexGrow: 1 }}>
                          <Box
                            sx={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              mb: 0.5,
                            }}
                          >
                            <Typography fontWeight={600} color={style.color}>
                              {alert.type} Alert: {alert.symbol}
                            </Typography>
                            <Typography
                              variant="caption"
                              color={alpha("#fff", 0.6)}
                            >
                              {alert.time}
                            </Typography>
                          </Box>

                          <Typography variant="body2" color="white">
                            {alert.message}
                          </Typography>
                        </Box>
                      </Box>
                    </Paper>
                  );
                })}
              </Box>

              <Box
                sx={{
                  textAlign: "center",
                  mt: 2,
                  p: 1.5,
                  borderRadius: 2,
                  border: `1px dashed ${alpha("#fff", 0.2)}`,
                  color: alpha("#fff", 0.7),
                  fontSize: "0.85rem",
                }}
              >
                Configure custom alerts based on your strategy preferences
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default ScreenerAlertsSection;
