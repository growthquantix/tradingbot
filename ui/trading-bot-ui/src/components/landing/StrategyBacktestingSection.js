import { useState } from "react";
import {
  Box,
  Container,
  Typography,
  Grid,
  Paper,
  Button,
  Chip,
  LinearProgress,
  Avatar,
  IconButton,
  Tab,
  Tabs,
} from "@mui/material";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import BarChartIcon from "@mui/icons-material/BarChart";
import PieChartIcon from "@mui/icons-material/PieChart";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import AutoGraphIcon from "@mui/icons-material/AutoGraph";
import CodeIcon from "@mui/icons-material/Code";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";

const strategies = [
  {
    title: "Index Breakout AI",
    desc: "Scans NIFTY/BANKNIFTY for high-volume breakout patterns with real-time entry/exit signals.",
    icon: ShowChartIcon,
    metrics: { winRate: 76, profitFactor: 2.1, drawdown: 8.5 },
    tags: ["NIFTY", "BANKNIFTY", "Momentum"],
    color: "#4CAF50",
  },
  {
    title: "Options Scalper",
    desc: "Uses IV, Delta, Gamma models for fast intraday scalping setups with dynamic stop management.",
    icon: BarChartIcon,
    metrics: { winRate: 68, profitFactor: 1.8, drawdown: 5.2 },
    tags: ["Options", "Scalping", "Intraday"],
    color: "#FF9800",
  },
  {
    title: "Sector Rotation Engine",
    desc: "Monitors FII/DII flows and shifts capital between sectors based on institutional positioning.",
    icon: PieChartIcon,
    metrics: { winRate: 82, profitFactor: 2.4, drawdown: 12.3 },
    tags: ["Sectors", "Swing", "Multi-day"],
    color: "#2196F3",
  },
];

const perftabs = [
  { label: "1 Month", data: [14.2, 9.8, 22.4] },
  { label: "3 Months", data: [28.7, 21.5, 41.2] },
  { label: "6 Months", data: [42.1, 31.6, 65.8] },
  { label: "1 Year", data: [78.5, 52.3, 112.4] },
];

const StrategyBacktestingSection = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [expandedStrategy, setExpandedStrategy] = useState(null);

  // const theme = useTheme();
  // const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  // const isMedium = useMediaQuery(theme.breakpoints.down("md"));

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const toggleExpand = (index) => {
    if (expandedStrategy === index) {
      setExpandedStrategy(null);
    } else {
      setExpandedStrategy(index);
    }
  };

  return (
    <Box
      sx={{
        bgcolor: "#001427",
        color: "#fff",
        py: { xs: 8, md: 12 },
        position: "relative",
        overflow: "hidden",
        backgroundImage: `
          linear-gradient(to bottom, rgba(0, 20, 39, 0.9), rgba(0, 20, 39, 1)), 
          url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23003366' fill-opacity='0.1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")
        `,
      }}
    >
      {/* Background accents */}
      <Box
        sx={{
          position: "absolute",
          width: "400px",
          height: "400px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(0, 174, 239, 0.1) 0%, rgba(0, 20, 39, 0) 70%)",
          top: "-150px",
          right: "-100px",
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
            "radial-gradient(circle, rgba(0, 174, 239, 0.08) 0%, rgba(0, 20, 39, 0) 70%)",
          bottom: "-100px",
          left: "-50px",
          zIndex: 0,
        }}
      />

      <Container sx={{ position: "relative", zIndex: 1 }}>
        <Box sx={{ textAlign: "center", mb: 6 }}>
          <Chip
            icon={<AutoGraphIcon />}
            label="AI STRATEGIES"
            sx={{
              bgcolor: "rgba(0, 174, 239, 0.1)",
              color: "#00AEEF",
              fontWeight: "bold",
              mb: 2,
            }}
          />

          <Typography
            variant="h3"
            fontWeight="bold"
            align="center"
            sx={{
              mb: 2,
              fontSize: { xs: "2rem", sm: "2.5rem", md: "3rem" },
            }}
          >
            Strategy & Backtesting Engine
          </Typography>

          <Typography
            variant="h6"
            align="center"
            color="rgba(255,255,255,0.7)"
            sx={{
              maxWidth: "800px",
              mx: "auto",
              mb: 3,
              fontSize: { xs: "1rem", md: "1.25rem" },
            }}
          >
            Our proprietary algorithms deliver consistent results across various
            market conditions. Each strategy is rigorously backtested and
            continuously optimized by our AI systems.
          </Typography>
        </Box>

        <Grid container spacing={4}>
          {strategies.map((s, i) => (
            <Grid item xs={12} md={4} key={i}>
              <Paper
                elevation={6}
                sx={{
                  p: 0,
                  bgcolor: "#061120",
                  border: "1px solid rgba(0, 174, 239, 0.2)",
                  borderRadius: 2,
                  overflow: "hidden",
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  transition: "transform 0.3s ease, box-shadow 0.3s ease",
                  "&:hover": {
                    transform: "translateY(-8px)",
                    boxShadow: `0 16px 40px -12px rgba(0, 174, 239, 0.2)`,
                  },
                }}
              >
                <Box
                  sx={{
                    height: "6px",
                    width: "100%",
                    bgcolor: s.color,
                    mb: 0,
                  }}
                />

                <Box sx={{ p: 3 }}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      mb: 2,
                    }}
                  >
                    <Avatar sx={{ bgcolor: `${s.color}20`, color: s.color }}>
                      <s.icon />
                    </Avatar>

                    <IconButton
                      size="small"
                      sx={{ color: "rgba(255, 255, 255, 0.5)" }}
                      onClick={() => toggleExpand(i)}
                    >
                      <InfoOutlinedIcon />
                    </IconButton>
                  </Box>

                  <Typography variant="h5" fontWeight="bold" gutterBottom>
                    {s.title}
                  </Typography>

                  <Typography sx={{ opacity: 0.85, mb: 3 }}>
                    {s.desc}
                  </Typography>

                  <Box
                    sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 3 }}
                  >
                    {s.tags.map((tag, index) => (
                      <Chip
                        key={index}
                        label={tag}
                        size="small"
                        sx={{
                          bgcolor: "rgba(255, 255, 255, 0.08)",
                          color: "rgba(255, 255, 255, 0.9)",
                        }}
                      />
                    ))}
                  </Box>
                </Box>

                <Box
                  sx={{
                    mt: "auto",
                    bgcolor: "rgba(0, 0, 0, 0.2)",
                    p: 3,
                    borderTop: "1px solid rgba(255, 255, 255, 0.05)",
                  }}
                >
                  <Grid container spacing={2}>
                    <Grid item xs={4}>
                      <Typography
                        variant="caption"
                        color="rgba(255, 255, 255, 0.7)"
                      >
                        Win Rate
                      </Typography>
                      <Typography variant="h6" fontWeight="bold" gutterBottom>
                        {s.metrics.winRate}%
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={s.metrics.winRate}
                        sx={{
                          height: 4,
                          borderRadius: 2,
                          bgcolor: "rgba(255, 255, 255, 0.1)",
                          "& .MuiLinearProgress-bar": {
                            bgcolor: s.color,
                          },
                        }}
                      />
                    </Grid>
                    <Grid item xs={4}>
                      <Typography
                        variant="caption"
                        color="rgba(255, 255, 255, 0.7)"
                      >
                        Profit Factor
                      </Typography>
                      <Typography variant="h6" fontWeight="bold" gutterBottom>
                        {s.metrics.profitFactor}
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={s.metrics.profitFactor * 20}
                        sx={{
                          height: 4,
                          borderRadius: 2,
                          bgcolor: "rgba(255, 255, 255, 0.1)",
                          "& .MuiLinearProgress-bar": {
                            bgcolor: s.color,
                          },
                        }}
                      />
                    </Grid>
                    <Grid item xs={4}>
                      <Typography
                        variant="caption"
                        color="rgba(255, 255, 255, 0.7)"
                      >
                        Max DD
                      </Typography>
                      <Typography variant="h6" fontWeight="bold" gutterBottom>
                        {s.metrics.drawdown}%
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={s.metrics.drawdown * 3}
                        sx={{
                          height: 4,
                          borderRadius: 2,
                          bgcolor: "rgba(255, 255, 255, 0.1)",
                          "& .MuiLinearProgress-bar": {
                            bgcolor: "rgba(255, 153, 0, 0.7)",
                          },
                        }}
                      />
                    </Grid>
                  </Grid>
                </Box>

                {expandedStrategy === i && (
                  <Box
                    sx={{
                      p: 3,
                      bgcolor: "rgba(0, 0, 0, 0.3)",
                      borderTop: "1px solid rgba(255, 255, 255, 0.05)",
                    }}
                  >
                    <Typography
                      variant="subtitle2"
                      fontWeight="bold"
                      gutterBottom
                    >
                      Strategy Details
                    </Typography>

                    <Box sx={{ mb: 2 }}>
                      {[
                        "Fully automated execution",
                        "AI-powered entry/exit signals",
                        "Dynamic position sizing",
                      ].map((feature, idx) => (
                        <Box
                          key={idx}
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            mb: 0.5,
                          }}
                        >
                          <CheckCircleOutlineIcon
                            sx={{ fontSize: 16, mr: 1, color: s.color }}
                          />
                          <Typography
                            variant="body2"
                            color="rgba(255, 255, 255, 0.8)"
                          >
                            {feature}
                          </Typography>
                        </Box>
                      ))}
                    </Box>

                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<CodeIcon />}
                      sx={{
                        borderColor: s.color,
                        color: s.color,
                        "&:hover": {
                          borderColor: s.color,
                          bgcolor: `${s.color}20`,
                        },
                      }}
                    >
                      View Backtest
                    </Button>
                  </Box>
                )}
              </Paper>
            </Grid>
          ))}
        </Grid>

        <Box sx={{ mt: 8, mb: 2 }}>
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            variant="fullWidth"
            sx={{
              "& .MuiTabs-indicator": {
                backgroundColor: "#00AEEF",
              },
              "& .Mui-selected": {
                color: "#00AEEF !important",
              },
              "& .MuiTab-root": {
                color: "rgba(255, 255, 255, 0.7)",
              },
              mb: 4,
            }}
          >
            {perftabs.map((tab, index) => (
              <Tab key={index} label={tab.label} />
            ))}
          </Tabs>

          <Paper
            elevation={6}
            sx={{
              p: 3,
              bgcolor: "#061120",
              border: "1px solid rgba(0, 174, 239, 0.2)",
              borderRadius: 2,
            }}
          >
            <Typography variant="h6" fontWeight="bold" gutterBottom>
              Strategy Performance ({perftabs[activeTab].label})
            </Typography>

            <Grid container spacing={3} sx={{ mt: 1 }}>
              {strategies.map((strategy, index) => (
                <Grid item xs={12} key={index}>
                  <Box sx={{ mb: 1 }}>
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        mb: 1,
                      }}
                    >
                      <Box sx={{ display: "flex", alignItems: "center" }}>
                        <Box
                          sx={{
                            width: 12,
                            height: 12,
                            borderRadius: "50%",
                            bgcolor: strategy.color,
                            mr: 1,
                          }}
                        />
                        <Typography variant="body1" fontWeight="medium">
                          {strategy.title}
                        </Typography>
                      </Box>
                      <Typography variant="body1" fontWeight="bold">
                        {perftabs[activeTab].data[index]}%
                      </Typography>
                    </Box>

                    <LinearProgress
                      variant="determinate"
                      value={perftabs[activeTab].data[index] * 1.5}
                      sx={{
                        height: 8,
                        borderRadius: 4,
                        bgcolor: "rgba(255, 255, 255, 0.1)",
                        "& .MuiLinearProgress-bar": {
                          bgcolor: strategy.color,
                        },
                      }}
                    />
                  </Box>
                </Grid>
              ))}
            </Grid>

            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                mt: 4,
              }}
            >
              <Typography variant="caption" color="rgba(255, 255, 255, 0.6)">
                * Past performance does not guarantee future results. All
                strategies backtested on historical data.
              </Typography>

              <Button
                endIcon={<ArrowForwardIcon />}
                sx={{
                  color: "#00AEEF",
                  "&:hover": {
                    bgcolor: "rgba(0, 174, 239, 0.1)",
                  },
                }}
              >
                View detailed report
              </Button>
            </Box>
          </Paper>
        </Box>

        <Box
          sx={{
            display: "flex",
            justifyContent: "center",
            mt: 6,
          }}
        >
          <Button
            variant="contained"
            size="large"
            sx={{
              px: 4,
              py: 1.5,
              bgcolor: "#00AEEF",
              fontWeight: "bold",
              "&:hover": {
                bgcolor: "#0096cc",
              },
            }}
          >
            Explore All Strategies
          </Button>
        </Box>
      </Container>
    </Box>
  );
};

export default StrategyBacktestingSection;
