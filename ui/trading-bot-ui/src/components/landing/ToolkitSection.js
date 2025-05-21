import React from "react";
import {
  Box,
  Container,
  Typography,
  Grid,
  Paper,
  Button,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Card,
  CardContent,
  CardActions,
  Chip,
} from "@mui/material";
import {
  ShowChart as ShowChartIcon,
  FlashOn as FlashOnIcon,
  Timeline as TimelineIcon,
  BarChart as BarChartIcon,
  FiberManualRecord as DotIcon,
  ArrowForward as ArrowForwardIcon,
} from "@mui/icons-material";

const toolkits = [
  {
    title: "Price Action AI",
    desc: "Instantly detects breakouts, retests, and key support/resistance zones across multiple timeframes. Leverages neural network pattern recognition trained on 20+ years of market data.",
    icon: <ShowChartIcon sx={{ fontSize: 40, color: "#00aeef" }} />,
    features: [
      "Multi-timeframe analysis",
      "Pattern recognition",
      "Zone detection",
    ],
  },
  {
    title: "Signal Overlay Engine",
    desc: "Generates high-probability trend-following signals with customizable risk parameters. Combines multiple technical indicators with AI-optimized weighting for reduced false signals.",
    icon: <FlashOnIcon sx={{ fontSize: 40, color: "#00aeef" }} />,
    features: ["Trend strength analysis", "Dynamic stop-loss", "Entry timing"],
  },
  {
    title: "Oscillator Matrix",
    desc: "Advanced momentum, volume, and divergence analytics that identify early reversals and continuations. Combines traditional oscillators with proprietary AI-enhanced metrics.",
    icon: <TimelineIcon sx={{ fontSize: 40, color: "#00aeef" }} />,
    features: ["Hidden divergences", "Volume profile", "Momentum shifts"],
  },
  {
    title: "Volatility Predictor",
    desc: "Forecasts upcoming volatility shifts across markets and instruments. Ideal for options traders and risk management, with alerts for potential market turbulence.",
    icon: <BarChartIcon sx={{ fontSize: 40, color: "#00aeef" }} />,
    features: ["VIX correlation", "Volatility surface", "Range prediction"],
  },
];

const ToolkitSection = () => {
  return (
    <Box
      sx={{
        bgcolor: "#0a0f1a",
        color: "#fff",
        py: 10,
        backgroundImage: "linear-gradient(to right, #0a0f1a, #081525)",
      }}
    >
      <Container>
        <Box sx={{ textAlign: "center", mb: 6 }}>
          <Typography variant="h4" fontWeight="bold" align="center" mb={2}>
            Advanced AI Trading Toolkit
          </Typography>
          <Typography
            variant="subtitle1"
            align="center"
            sx={{
              color: "#00aeef",
              maxWidth: "700px",
              mx: "auto",
              mb: 2,
            }}
          >
            Quantix modules work together or independently to enhance your
            trading strategy
          </Typography>
        </Box>

        <Grid container spacing={4}>
          {toolkits.map((tool, i) => (
            <Grid item xs={12} md={6} lg={3} key={i}>
              <Card
                sx={{
                  bgcolor: "#061120",
                  border: "1px solid rgba(0, 174, 239, 0.3)",
                  borderRadius: 2,
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  transition: "all 0.3s ease",
                  "&:hover": {
                    border: "1px solid rgba(0, 174, 239, 0.7)",
                    boxShadow: "0 4px 20px rgba(0, 174, 239, 0.15)",
                  },
                }}
              >
                <CardContent sx={{ flexGrow: 1 }}>
                  <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                    {tool.icon}
                    <Box
                      sx={{
                        flexGrow: 1,
                        height: "1px",
                        ml: 2,
                        backgroundImage:
                          "linear-gradient(to right, rgba(0, 174, 239, 0.5), rgba(0, 174, 239, 0))",
                      }}
                    />
                  </Box>

                  <Typography
                    variant="h6"
                    fontWeight="bold"
                    color="#00aeef"
                    gutterBottom
                  >
                    {tool.title}
                  </Typography>

                  <Typography variant="body2" sx={{ opacity: 0.85, mb: 2 }}>
                    {tool.desc}
                  </Typography>

                  <List dense disablePadding>
                    {tool.features.map((feature, j) => (
                      <ListItem key={j} disableGutters sx={{ py: 0.5 }}>
                        <ListItemIcon sx={{ minWidth: 24 }}>
                          <DotIcon sx={{ color: "#00aeef", fontSize: 10 }} />
                        </ListItemIcon>
                        <ListItemText
                          primary={feature}
                          primaryTypographyProps={{
                            variant: "body2",
                            sx: { color: "rgba(255, 255, 255, 0.7)" },
                          }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>

                <CardActions sx={{ px: 2, pb: 2 }}>
                  <Button
                    size="small"
                    endIcon={<ArrowForwardIcon />}
                    sx={{
                      color: "#00aeef",
                      "&:hover": {
                        bgcolor: "rgba(0, 174, 239, 0.1)",
                      },
                    }}
                  >
                    Learn more
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>

        <Box sx={{ mt: 6, textAlign: "center" }}>
          <Paper
            sx={{
              display: "inline-block",
              bgcolor: "rgba(6, 17, 32, 0.7)",
              border: "1px solid rgba(0, 174, 239, 0.2)",
              p: 3,
              borderRadius: 2,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", mb: 1.5 }}>
              <Chip
                label="PRO TIP"
                size="small"
                sx={{
                  bgcolor: "rgba(0, 174, 239, 0.2)",
                  color: "#00aeef",
                  fontWeight: "bold",
                  mr: 1.5,
                }}
              />
              <Typography
                variant="body2"
                sx={{ color: "rgba(255, 255, 255, 0.85)" }}
              >
                Combine multiple modules for maximum trading edge
              </Typography>
            </Box>
            <Button
              variant="contained"
              sx={{
                bgcolor: "#00aeef",
                "&:hover": {
                  bgcolor: "#0099d4",
                },
              }}
            >
              View Module Compatibility
            </Button>
          </Paper>
        </Box>
      </Container>
    </Box>
  );
};

export default ToolkitSection;
