import {
  Box,
  Typography,
  Container,
  Grid,
  Paper,
  Card,
  CardContent,
  Divider,
  LinearProgress,
  Chip,
  Button,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from "@mui/material";
import TimelineIcon from "@mui/icons-material/Timeline";
import SpeedIcon from "@mui/icons-material/Speed";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import BarChartIcon from "@mui/icons-material/BarChart";
import HistoryIcon from "@mui/icons-material/History";
import SettingsIcon from "@mui/icons-material/Settings";
import CodeIcon from "@mui/icons-material/Code";

const BacktestSection = () => {
  // const theme = useTheme();
  // const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  // const isMedium = useMediaQuery(theme.breakpoints.down("md"));

  const backtestResults = [
    { strategy: "Momentum", winRate: 78, profitFactor: 2.4, drawdown: 12 },
    { strategy: "Mean Reversion", winRate: 65, profitFactor: 1.8, drawdown: 8 },
    { strategy: "Breakout", winRate: 72, profitFactor: 2.1, drawdown: 15 },
  ];

  const features = [
    {
      title: "Historical Analysis",
      description:
        "Analyze strategy performance across multiple market conditions and timeframes",
      icon: HistoryIcon,
    },
    {
      title: "Performance Metrics",
      description:
        "Comprehensive metrics including win rate, profit factor, Sharpe ratio, and max drawdown",
      icon: SpeedIcon,
    },
    {
      title: "Parameter Optimization",
      description:
        "Automatically find optimal parameters for your trading strategies",
      icon: SettingsIcon,
    },
    {
      title: "Visual Reports",
      description:
        "Visualize equity curves, drawdowns, and trade distributions",
      icon: BarChartIcon,
    },
  ];

  return (
    <Box
      id="backtest"
      sx={{
        py: { xs: 8, md: 12 },
        backgroundColor: "#f8fafc",
        backgroundImage: `
        radial-gradient(#00AEEF10 1px, transparent 1px), 
        radial-gradient(#00AEEF10 1px, transparent 1px)
      `,
        backgroundSize: "20px 20px",
        backgroundPosition: "0 0, 10px 10px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Decorative element */}
      <Box
        sx={{
          position: "absolute",
          width: "500px",
          height: "500px",
          borderRadius: "50%",
          background:
            "linear-gradient(135deg, rgba(0,174,239,0.05) 0%, rgba(0,80,114,0.02) 100%)",
          top: "-250px",
          right: "-100px",
          zIndex: 0,
        }}
      />

      <Container sx={{ position: "relative", zIndex: 1 }}>
        <Grid container spacing={5} alignItems="center">
          <Grid item xs={12} md={6}>
            {/* Content section */}
            <Box sx={{ mb: 2 }}>
              <Chip
                icon={<TimelineIcon />}
                label="Advanced Backtesting"
                color="primary"
                sx={{
                  mb: 2,
                  fontWeight: "medium",
                  backgroundColor: "#00AEEF20",
                  color: "#005072",
                  "& .MuiChip-icon": {
                    color: "#00AEEF",
                  },
                }}
              />

              <Typography
                variant="h3"
                fontWeight={800}
                gutterBottom
                sx={{
                  fontSize: { xs: "2rem", sm: "2.5rem", md: "3rem" },
                  color: "#0a2540",
                  lineHeight: 1.2,
                }}
              >
                Smart Backtesting Engine
              </Typography>

              <Typography
                variant="h6"
                sx={{
                  mb: 4,
                  color: "#4a5568",
                  maxWidth: "500px",
                  lineHeight: 1.6,
                }}
              >
                Test and optimize strategies on historical data with powerful
                analytics for risk control, profit/loss tracking, and drawdown
                management.
              </Typography>

              <List sx={{ mb: 4 }}>
                {features.map((feature, index) => (
                  <ListItem key={index} sx={{ px: 0 }}>
                    <ListItemIcon>
                      <Paper
                        elevation={0}
                        sx={{
                          width: 36,
                          height: 36,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          borderRadius: "50%",
                          bgcolor: "#00AEEF15",
                          color: "#00AEEF",
                        }}
                      >
                        <feature.icon fontSize="small" />
                      </Paper>
                    </ListItemIcon>
                    <ListItemText
                      primary={feature.title}
                      secondary={feature.description}
                      primaryTypographyProps={{
                        fontWeight: "bold",
                        color: "#0a2540",
                        gutterBottom: true,
                      }}
                      secondaryTypographyProps={{
                        color: "#4a5568",
                      }}
                    />
                  </ListItem>
                ))}
              </List>

              <Button
                variant="contained"
                color="primary"
                size="large"
                startIcon={<CodeIcon />}
                sx={{
                  px: 3,
                  py: 1.5,
                  borderRadius: 2,
                  backgroundColor: "#00AEEF",
                  "&:hover": {
                    backgroundColor: "#0094d4",
                  },
                }}
              >
                Try Backtesting Demo
              </Button>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            {/* Visualization section */}
            <Paper
              elevation={10}
              sx={{
                borderRadius: 4,
                overflow: "hidden",
                bgcolor: "white",
                boxShadow: "0 10px 50px rgba(0,0,0,0.1)",
              }}
            >
              <Box sx={{ p: 3, bgcolor: "#0a2540", color: "white" }}>
                <Typography variant="h6" fontWeight="bold">
                  Backtest Results
                </Typography>
                <Typography variant="caption">
                  Performance metrics across different strategies
                </Typography>
              </Box>

              <Box sx={{ p: 3 }}>
                {backtestResults.map((result, index) => (
                  <Card
                    key={index}
                    variant="outlined"
                    sx={{
                      mb: 2,
                      border: "1px solid #e0e7ff",
                      "&:last-child": { mb: 0 },
                    }}
                  >
                    <CardContent>
                      <Box
                        sx={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          mb: 2,
                        }}
                      >
                        <Box sx={{ display: "flex", alignItems: "center" }}>
                          <TrendingUpIcon sx={{ color: "#00AEEF", mr: 1 }} />
                          <Typography variant="h6" fontWeight="bold">
                            {result.strategy}
                          </Typography>
                        </Box>
                        <Chip
                          label={
                            result.winRate >= 70
                              ? "High Performance"
                              : "Moderate Performance"
                          }
                          size="small"
                          sx={{
                            bgcolor:
                              result.winRate >= 70 ? "#d0f5e0" : "#fff8e0",
                            color: result.winRate >= 70 ? "#1e7e4b" : "#b7953f",
                            fontWeight: "medium",
                          }}
                        />
                      </Box>

                      <Grid container spacing={2}>
                        <Grid item xs={4}>
                          <Typography variant="caption" color="textSecondary">
                            Win Rate
                          </Typography>
                          <Typography variant="h6" fontWeight="bold">
                            {result.winRate}%
                          </Typography>
                          <LinearProgress
                            variant="determinate"
                            value={result.winRate}
                            sx={{
                              height: 6,
                              borderRadius: 3,
                              mt: 0.5,
                              bgcolor: "#edf2f7",
                              "& .MuiLinearProgress-bar": {
                                bgcolor: "#00AEEF",
                              },
                            }}
                          />
                        </Grid>

                        <Grid item xs={4}>
                          <Typography variant="caption" color="textSecondary">
                            Profit Factor
                          </Typography>
                          <Typography variant="h6" fontWeight="bold">
                            {result.profitFactor}
                          </Typography>
                          <LinearProgress
                            variant="determinate"
                            value={result.profitFactor * 20}
                            sx={{
                              height: 6,
                              borderRadius: 3,
                              mt: 0.5,
                              bgcolor: "#edf2f7",
                              "& .MuiLinearProgress-bar": {
                                bgcolor: "#38b2ac",
                              },
                            }}
                          />
                        </Grid>

                        <Grid item xs={4}>
                          <Typography variant="caption" color="textSecondary">
                            Drawdown
                          </Typography>
                          <Typography variant="h6" fontWeight="bold">
                            {result.drawdown}%
                          </Typography>
                          <LinearProgress
                            variant="determinate"
                            value={result.drawdown * 3}
                            sx={{
                              height: 6,
                              borderRadius: 3,
                              mt: 0.5,
                              bgcolor: "#edf2f7",
                              "& .MuiLinearProgress-bar": {
                                bgcolor: "#f6ad55",
                              },
                            }}
                          />
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                ))}
              </Box>

              <Divider />

              <Box
                sx={{
                  p: 3,
                  bgcolor: "#f9fafb",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <Typography variant="body2" color="textSecondary">
                  Backtest period: Jan 2023 - May 2024
                </Typography>
                <Button
                  size="small"
                  sx={{
                    color: "#00AEEF",
                    "&:hover": {
                      backgroundColor: "rgba(0, 174, 239, 0.08)",
                    },
                  }}
                >
                  View Full Report
                </Button>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default BacktestSection;
