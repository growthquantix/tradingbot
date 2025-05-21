import React from "react";
import {
  Box,
  Container,
  Typography,
  Grid,
  Paper,
  useTheme,
  alpha,
} from "@mui/material";
import { TrendingUp, Code, DataObject, Bolt } from "@mui/icons-material";

const steps = [
  {
    title: "Data Ingestion",
    desc: "Real-time prices, options data, sentiment analysis, and news feeds processed instantly.",
    icon: <TrendingUp fontSize="large" />,
    color: "#00bfff",
  },
  {
    title: "Feature Engineering",
    desc: "Transform market behavior into AI-understandable features using proprietary algorithms.",
    icon: <Code fontSize="large" />,
    color: "#9c27b0",
  },
  {
    title: "AI Model Prediction",
    desc: "Advanced neural networks analyze patterns and predict high-probability trade setups.",
    icon: <DataObject fontSize="large" />,
    color: "#2e7d32",
  },
  {
    title: "Smart Execution",
    desc: "Automated trading signals with precise entry, exit and risk management parameters.",
    icon: <Bolt fontSize="large" />,
    color: "#ed6c02",
  },
];

const HowAIWorksSection = () => {
  const theme = useTheme();

  return (
    <Box
      id="how-ai-works"
      sx={{
        background: `linear-gradient(to bottom, #03071c, #051230)`,
        color: "#fff",
        py: 12,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Neural network background pattern */}
      <Box
        sx={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          opacity: 0.05,
          zIndex: 0,
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M11 18c3.866 0 7-3.134 7-7s-3.134-7-7-7-7 3.134-7 7 3.134 7 7 7zm48 25c3.866 0 7-3.134 7-7s-3.134-7-7-7-7 3.134-7 7 3.134 7 7 7zm-43-7c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zm63 31c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zM34 90c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zm56-76c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zM12 86c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm28-65c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm23-11c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm-6 60c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm29 22c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zM32 63c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm57-13c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm-9-21c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM60 91c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM35 41c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM12 60c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2z' fill='%23ffffff' fill-opacity='0.1' fill-rule='evenodd'/%3E%3C/svg%3E")`,
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
            How Our AI Works
          </Typography>
          <Typography
            variant="h6"
            color="rgba(255,255,255,0.7)"
            sx={{ maxWidth: 600, mx: "auto" }}
          >
            Powered by advanced machine learning models trained on decades of
            market data
          </Typography>
        </Box>

        <Grid container spacing={4}>
          {steps.map((step, i) => (
            <Grid item xs={12} md={3} key={i}>
              <Paper
                sx={{
                  p: 4,
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  background: alpha(theme.palette.background.paper, 0.05),
                  backdropFilter: "blur(10px)",
                  border: `1px solid ${alpha(step.color, 0.3)}`,
                  borderRadius: 4,
                  transition: "transform 0.3s ease, box-shadow 0.3s ease",
                  "&:hover": {
                    transform: "translateY(-8px)",
                    boxShadow: `0 10px 25px -5px ${alpha(step.color, 0.3)}`,
                  },
                }}
              >
                <Box
                  sx={{
                    bgcolor: alpha(step.color, 0.15),
                    color: step.color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    p: 1.5,
                    borderRadius: 2,
                    mb: 2,
                  }}
                >
                  {step.icon}
                </Box>

                <Typography variant="h6" fontWeight="bold" gutterBottom>
                  {i + 1}. {step.title}
                </Typography>

                <Typography sx={{ color: "rgba(255,255,255,0.7)" }}>
                  {step.desc}
                </Typography>

                {/* Connector line - only for non-last items */}
                {i < steps.length - 1 && (
                  <Box
                    sx={{
                      display: { xs: "none", md: "block" },
                      position: "absolute",
                      top: "30%",
                      right: "-30px",
                      width: "60px",
                      height: "2px",
                      background: `linear-gradient(to right, ${step.color}, ${
                        steps[i + 1].color
                      })`,
                      zIndex: 2,
                    }}
                  />
                )}
              </Paper>
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  );
};

export default HowAIWorksSection;
