import React from "react";
import {
  Box,
  Container,
  Typography,
  LinearProgress,
  Grid,
  Paper,
  Fade,
} from "@mui/material";
import { ChartLine, Target, TrendingDown, Gauge } from "lucide-react";

const metrics = [
  { label: "Backtest Win Rate", value: 82, icon: Target, color: "#4CAF50" },
  {
    label: "Risk Control (Drawdown)",
    value: 91,
    icon: TrendingDown,
    color: "#2196F3",
  },
  { label: "Expected ROI", value: 76, icon: ChartLine, color: "#FF9800" },
  { label: "Latency Optimization", value: 95, icon: Gauge, color: "#9C27B0" },
];

const PerformanceMetricsSection = () => {
  return (
    <Box sx={{ bgcolor: "#010920", color: "#ffffff", py: 10 }}>
      <Container maxWidth="lg">
        <Typography variant="h4" fontWeight="bold" align="center" mb={2}>
          Performance Metrics
        </Typography>
        <Typography
          variant="subtitle1"
          align="center"
          color="rgba(255,255,255,0.7)"
          mb={6}
        >
          Our AI trading algorithms have been extensively tested and optimized
        </Typography>

        <Grid container spacing={4}>
          {metrics.map((metric, i) => (
            <Grid item xs={12} md={6} key={i}>
              <Fade in={true} timeout={500 + i * 200}>
                <Paper
                  elevation={4}
                  sx={{
                    p: 3,
                    bgcolor: "rgba(30,40,70,0.6)",
                    backdropFilter: "blur(10px)",
                    borderRadius: 2,
                    transition: "transform 0.3s",
                    "&:hover": {
                      transform: "translateY(-5px)",
                    },
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                    <Box
                      sx={{
                        mr: 2,
                        bgcolor: "rgba(255,255,255,0.1)",
                        p: 1,
                        borderRadius: 1,
                      }}
                    >
                      <metric.icon size={24} color={metric.color} />
                    </Box>
                    <Typography variant="h6" fontWeight="bold">
                      {metric.label}
                    </Typography>
                  </Box>

                  <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
                    <Typography variant="h4" fontWeight="bold" mr={2}>
                      {metric.value}%
                    </Typography>
                    <Box sx={{ flexGrow: 1 }}>
                      <LinearProgress
                        variant="determinate"
                        value={metric.value}
                        sx={{
                          height: 12,
                          borderRadius: 6,
                          backgroundColor: "rgba(255,255,255,0.1)",
                          "& .MuiLinearProgress-bar": {
                            backgroundColor: metric.color,
                            transition: "transform 1.5s ease-in-out",
                          },
                        }}
                      />
                    </Box>
                  </Box>
                </Paper>
              </Fade>
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  );
};

export default PerformanceMetricsSection;
