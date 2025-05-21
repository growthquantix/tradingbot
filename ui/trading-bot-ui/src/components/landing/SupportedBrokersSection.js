import {
  Box,
  Typography,
  Container,
  Grid,
  Paper,
  Divider,
  Button,
  LinearProgress,
  Avatar,
  Chip,
} from "@mui/material";
import { motion } from "framer-motion";
import HistoryIcon from "@mui/icons-material/History";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import FlashOnIcon from "@mui/icons-material/FlashOn";
// import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import AutoGraphIcon from "@mui/icons-material/AutoGraph";
import BarChartIcon from "@mui/icons-material/BarChart";
// import PsychologyIcon from "@mui/icons-material/Psychology";
import SecurityIcon from "@mui/icons-material/Security";

const StrategySection = () => {
  const strategyItems = [
    {
      title: "Backtested Over 5 Years",
      desc: "Using real historical market data with comprehensive statistical validation across multiple market conditions",
      icon: HistoryIcon,
      metric: "2,500+",
      metricLabel: "Testing Hours",
      color: "#2196F3",
    },
    {
      title: "85% Win Ratio",
      desc: "Optimized with smart entry/exit signals based on machine learning algorithms that adapt to changing markets",
      icon: CheckCircleIcon,
      metric: "3.2:1",
      metricLabel: "Risk-Reward Ratio",
      color: "#4CAF50",
    },
    {
      title: "Real-Time AI Execution",
      desc: "No emotions, just logic & automation with microsecond execution to capitalize on fleeting opportunities",
      icon: FlashOnIcon,
      metric: "<5ms",
      metricLabel: "Execution Speed",
      color: "#FF9800",
    },
  ];

  return (
    <Box
      sx={{
        py: { xs: 8, md: 12 },
        bgcolor: "#111",
        position: "relative",
        overflow: "hidden",
        backgroundImage: `
          radial-gradient(circle at 20% 150%, rgba(0, 229, 255, 0.15) 0%, rgba(17, 17, 17, 0) 50%),
          radial-gradient(circle at 80% 30%, rgba(0, 229, 255, 0.1) 0%, rgba(17, 17, 17, 0) 50%)
        `,
      }}
    >
      {/* Background accent */}
      <Box
        sx={{
          position: "absolute",
          width: "600px",
          height: "600px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(0, 229, 255, 0.05) 0%, rgba(17, 17, 17, 0) 70%)",
          top: "-300px",
          right: "-200px",
          zIndex: 0,
        }}
      />

      <Container maxWidth="lg" sx={{ position: "relative", zIndex: 1 }}>
        <Grid container spacing={6} alignItems="center">
          <Grid item xs={12} md={6}>
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              viewport={{ once: true }}
            >
              <Chip
                icon={<AutoGraphIcon />}
                label="AI POWERED"
                sx={{
                  mb: 2,
                  bgcolor: "rgba(0, 229, 255, 0.15)",
                  color: "#00E5FF",
                  fontWeight: "bold",
                  "& .MuiChip-icon": {
                    color: "#00E5FF",
                  },
                }}
              />

              <Typography
                variant="h3"
                sx={{
                  color: "#00E5FF",
                  fontWeight: 600,
                  mb: 3,
                  fontSize: { xs: "2rem", sm: "2.5rem", md: "3rem" },
                  lineHeight: 1.2,
                }}
              >
                Proven AI Strategy
              </Typography>

              <Typography
                variant="h6"
                sx={{
                  color: "#ccc",
                  maxWidth: 700,
                  mb: 4,
                  lineHeight: 1.6,
                  fontSize: { xs: "1rem", md: "1.25rem" },
                }}
              >
                Our trading AI is trained with years of historical data,
                adaptive logic, and smart risk management. It continuously scans
                for opportunities, executes trades with precision, and evolves
                with the market — so you stay ahead in any market condition.
              </Typography>

              <Box sx={{ mb: 6 }}>
                {[
                  "Neural network decision algorithms",
                  "Adaptive position sizing based on volatility",
                  "Multi-timeframe analysis for signal confirmation",
                  "Smart risk management with dynamic stop-loss",
                ].map((item, idx) => (
                  <Box
                    key={idx}
                    sx={{ display: "flex", alignItems: "center", mb: 1.5 }}
                  >
                    <Box
                      component={motion.div}
                      initial={{ scale: 0 }}
                      whileInView={{ scale: 1 }}
                      transition={{ delay: idx * 0.1, type: "spring" }}
                      viewport={{ once: true }}
                      sx={{
                        width: 24,
                        height: 24,
                        borderRadius: "50%",
                        bgcolor: "rgba(0, 229, 255, 0.15)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        mr: 2,
                      }}
                    >
                      <CheckCircleIcon
                        sx={{ color: "#00E5FF", fontSize: 16 }}
                      />
                    </Box>
                    <Typography
                      component={motion.p}
                      initial={{ opacity: 0, x: -20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.1 + 0.2 }}
                      viewport={{ once: true }}
                      variant="body1"
                      sx={{ color: "#fff" }}
                    >
                      {item}
                    </Typography>
                  </Box>
                ))}
              </Box>

              <Button
                variant="contained"
                startIcon={<BarChartIcon />}
                sx={{
                  bgcolor: "#00E5FF",
                  color: "#0a0a0a",
                  fontWeight: "bold",
                  px: 4,
                  py: 1.5,
                  "&:hover": {
                    bgcolor: "#00c2d6",
                  },
                }}
                component={motion.button}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.98 }}
              >
                View Performance Report
              </Button>
            </motion.div>
          </Grid>

          <Grid item xs={12} md={6}>
            <Box
              component={motion.div}
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              viewport={{ once: true }}
              sx={{
                p: 3,
                bgcolor: "rgba(35, 35, 35, 0.7)",
                backdropFilter: "blur(10px)",
                borderRadius: 3,
                border: "1px solid rgba(255, 255, 255, 0.1)",
                boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
              }}
            >
              <Typography
                variant="h6"
                fontWeight="bold"
                sx={{ color: "#fff", mb: 3 }}
              >
                Strategy Performance
              </Typography>

              <Box sx={{ mb: 3 }}>
                <Grid container spacing={2} alignItems="center">
                  <Grid item xs={4}>
                    <Box
                      sx={{
                        textAlign: "center",
                        p: 2,
                        bgcolor: "rgba(0, 229, 255, 0.1)",
                        borderRadius: 2,
                      }}
                    >
                      <Typography
                        variant="h4"
                        fontWeight="bold"
                        sx={{ color: "#00E5FF" }}
                      >
                        85%
                      </Typography>
                      <Typography variant="caption" sx={{ color: "#ccc" }}>
                        Win Rate
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={4}>
                    <Box
                      sx={{
                        textAlign: "center",
                        p: 2,
                        bgcolor: "rgba(0, 229, 255, 0.1)",
                        borderRadius: 2,
                      }}
                    >
                      <Typography
                        variant="h4"
                        fontWeight="bold"
                        sx={{ color: "#00E5FF" }}
                      >
                        2.8
                      </Typography>
                      <Typography variant="caption" sx={{ color: "#ccc" }}>
                        Profit Factor
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={4}>
                    <Box
                      sx={{
                        textAlign: "center",
                        p: 2,
                        bgcolor: "rgba(0, 229, 255, 0.1)",
                        borderRadius: 2,
                      }}
                    >
                      <Typography
                        variant="h4"
                        fontWeight="bold"
                        sx={{ color: "#00E5FF" }}
                      >
                        11.2%
                      </Typography>
                      <Typography variant="caption" sx={{ color: "#ccc" }}>
                        Max Drawdown
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </Box>

              <Typography
                variant="subtitle2"
                gutterBottom
                sx={{ color: "#ccc", mt: 4, mb: 2 }}
              >
                Monthly Returns (Last 6 Months)
              </Typography>

              <Box sx={{ mb: 4 }}>
                {[
                  "Apr 2024",
                  "Mar 2024",
                  "Feb 2024",
                  "Jan 2024",
                  "Dec 2023",
                  "Nov 2023",
                ].map((month, idx) => {
                  const returns = [8.2, 7.5, 12.6, 6.8, 9.3, 7.9][idx];
                  return (
                    <Box key={idx} sx={{ mb: 1.5 }}>
                      <Box
                        sx={{
                          display: "flex",
                          justifyContent: "space-between",
                          mb: 0.5,
                        }}
                      >
                        <Typography variant="body2" sx={{ color: "#ccc" }}>
                          {month}
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{ color: "#00E5FF", fontWeight: "bold" }}
                        >
                          {returns}%
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={returns * 5}
                        sx={{
                          height: 8,
                          borderRadius: 4,
                          bgcolor: "rgba(255, 255, 255, 0.1)",
                          "& .MuiLinearProgress-bar": {
                            bgcolor: "#00E5FF",
                          },
                        }}
                      />
                    </Box>
                  );
                })}
              </Box>

              <Box
                sx={{
                  p: 2,
                  bgcolor: "rgba(0, 0, 0, 0.3)",
                  borderRadius: 2,
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <SecurityIcon sx={{ color: "#00E5FF", mr: 1.5 }} />
                <Typography
                  variant="caption"
                  sx={{ color: "#ccc", fontStyle: "italic" }}
                >
                  Past performance is not indicative of future results. All
                  statistics based on backtested data with real market
                  conditions.
                </Typography>
              </Box>
            </Box>
          </Grid>
        </Grid>

        <Grid container spacing={4} mt={6}>
          {strategyItems.map((item, i) => (
            <Grid item xs={12} md={4} key={i}>
              <motion.div
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.2 }}
                viewport={{ once: true }}
              >
                <Paper
                  elevation={4}
                  sx={{
                    p: 4,
                    borderRadius: 2,
                    bgcolor: "rgba(35, 35, 35, 0.7)",
                    backdropFilter: "blur(10px)",
                    color: "#fff",
                    border: "1px solid #222",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    transition: "transform 0.3s ease",
                    "&:hover": {
                      transform: "translateY(-10px)",
                    },
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "flex-start" }}>
                    <Avatar
                      sx={{
                        bgcolor: `${item.color}20`,
                        color: item.color,
                        mr: 2,
                      }}
                    >
                      <item.icon />
                    </Avatar>
                    <Box>
                      <Typography
                        variant="h6"
                        sx={{ color: "#00E5FF", fontWeight: "bold" }}
                      >
                        {item.title}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{ color: "#ccc", mt: 1, lineHeight: 1.6 }}
                      >
                        {item.desc}
                      </Typography>
                    </Box>
                  </Box>

                  <Divider
                    sx={{ my: 3, borderColor: "rgba(255, 255, 255, 0.1)" }}
                  />

                  <Box
                    sx={{ mt: "auto", display: "flex", alignItems: "baseline" }}
                  >
                    <Typography
                      variant="h4"
                      sx={{
                        color: item.color,
                        fontWeight: "bold",
                        mr: 1.5,
                      }}
                    >
                      {item.metric}
                    </Typography>
                    <Typography variant="caption" sx={{ color: "#ccc" }}>
                      {item.metricLabel}
                    </Typography>
                  </Box>
                </Paper>
              </motion.div>
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  );
};

export default StrategySection;
