import React from "react";
import {
  Box,
  Typography,
  Grid,
  Paper,
  Container,
  Avatar,
  Chip,
  Button,
} from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import SearchIcon from "@mui/icons-material/Search";
import PsychologyIcon from "@mui/icons-material/Psychology";
import TimelineIcon from "@mui/icons-material/Timeline";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";

const features = [
  {
    title: "State-of-the-Art Trading Tools",
    desc: "Automated price action detection, reversal signals, and professional workflows to simplify your trading decisions across multiple markets and timeframes.",
    icon: TimelineIcon,
    highlight: "Pro-grade tools",
  },
  {
    title: "AI Screeners & Alerts",
    desc: "Find high-probability trades using intelligent screeners that analyze patterns, volume, and institutional activity to deliver actionable alerts in real-time.",
    icon: SearchIcon,
    highlight: "Smart filtering",
  },
  {
    title: "AI Backtesting Assistant",
    desc: "Build, test, and refine profitable strategies with our proprietary AI agent that optimizes parameters and identifies edge-giving opportunities.",
    icon: PsychologyIcon,
    highlight: "Strategy builder",
  },
];

const Features = () => {
  return (
    <Box
      sx={{
        py: { xs: 8, md: 12 },
        backgroundColor: "#020617",
        color: "#fff",
        position: "relative",
        overflow: "hidden",
        backgroundImage: `
          radial-gradient(circle at 20% 150%, rgba(67, 56, 202, 0.15) 0%, rgba(2, 6, 23, 0) 50%),
          radial-gradient(circle at 80% 70%, rgba(14, 165, 233, 0.1) 0%, rgba(2, 6, 23, 0) 50%)
        `,
      }}
    >
      {/* Decorative elements */}
      <Box
        sx={{
          position: "absolute",
          width: "800px",
          height: "800px",
          top: "-400px",
          left: "-400px",
          background:
            "radial-gradient(circle, rgba(14, 165, 233, 0.03) 0%, rgba(2, 6, 23, 0) 70%)",
          borderRadius: "50%",
          zIndex: 0,
        }}
      />

      <Container sx={{ position: "relative", zIndex: 1 }}>
        <Box sx={{ textAlign: "center", mb: { xs: 6, md: 8 } }}>
          <Chip
            icon={<AutoAwesomeIcon />}
            label="POWERED BY AI"
            sx={{
              mb: 2,
              bgcolor: "rgba(14, 165, 233, 0.2)",
              color: "#38bdf8",
              fontWeight: "bold",
              "& .MuiChip-icon": {
                color: "#38bdf8",
              },
            }}
          />

          <Typography
            variant="h3"
            textAlign="center"
            fontWeight="bold"
            sx={{
              mb: 2,
              fontSize: { xs: "2rem", sm: "2.5rem", md: "3rem" },
              background: "linear-gradient(to right, #38bdf8, #818cf8)",
              backgroundClip: "text",
              textFillColor: "transparent",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Built-in Intelligence with AI
          </Typography>

          <Typography
            variant="h6"
            textAlign="center"
            sx={{
              maxWidth: "800px",
              mx: "auto",
              color: "rgba(255, 255, 255, 0.7)",
              mb: 2,
            }}
          >
            Our platform leverages advanced artificial intelligence to enhance
            every aspect of your trading experience, from analysis to execution.
          </Typography>
        </Box>

        <Grid container spacing={4} justifyContent="center">
          {features.map((item, i) => (
            <Grid item xs={12} sm={6} md={4} key={i}>
              <Paper
                elevation={6}
                sx={{
                  p: 4,
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  background: "rgba(30, 41, 59, 0.7)",
                  backdropFilter: "blur(10px)",
                  borderRadius: 3,
                  border: "1px solid rgba(67, 56, 202, 0.1)",
                  transition: "transform 0.3s ease, box-shadow 0.3s ease",
                  "&:hover": {
                    transform: "translateY(-8px)",
                    boxShadow: "0 16px 40px -12px rgba(14, 165, 233, 0.2)",
                  },
                }}
              >
                <Box
                  sx={{
                    mb: 3,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                  }}
                >
                  <Avatar
                    sx={{
                      bgcolor: "rgba(14, 165, 233, 0.15)",
                      color: "#38bdf8",
                      width: 56,
                      height: 56,
                    }}
                  >
                    <item.icon fontSize="large" />
                  </Avatar>

                  <Chip
                    label={item.highlight}
                    size="small"
                    sx={{
                      bgcolor: "rgba(14, 165, 233, 0.1)",
                      color: "#38bdf8",
                      fontWeight: "medium",
                      fontSize: "0.75rem",
                    }}
                  />
                </Box>

                <Typography
                  variant="h5"
                  fontWeight="bold"
                  sx={{ mb: 2, color: "#fff" }}
                >
                  {item.title}
                </Typography>

                <Typography
                  variant="body1"
                  sx={{
                    color: "rgba(255, 255, 255, 0.7)",
                    mb: 3,
                    flexGrow: 1,
                  }}
                >
                  {item.desc}
                </Typography>

                <Button
                  variant="text"
                  endIcon={<ArrowForwardIcon />}
                  sx={{
                    alignSelf: "flex-start",
                    color: "#38bdf8",
                    p: 0,
                    "&:hover": {
                      backgroundColor: "transparent",
                      transform: "translateX(4px)",
                      transition: "transform 0.2s ease",
                    },
                  }}
                >
                  Learn more
                </Button>
              </Paper>
            </Grid>
          ))}
        </Grid>

        <Box
          sx={{
            mt: 8,
            display: "flex",
            flexDirection: { xs: "column", sm: "row" },
            alignItems: "center",
            justifyContent: "center",
            gap: 3,
          }}
        >
          <Button
            variant="contained"
            size="large"
            sx={{
              py: 1.5,
              px: 4,
              fontWeight: "bold",
              borderRadius: 2,
              bgcolor: "#38bdf8",
              "&:hover": {
                bgcolor: "#0ea5e9",
              },
            }}
          >
            Try Our AI Tools
          </Button>

          <Button
            variant="outlined"
            size="large"
            sx={{
              py: 1.5,
              px: 4,
              fontWeight: "medium",
              borderRadius: 2,
              borderColor: "rgba(255, 255, 255, 0.3)",
              color: "#fff",
              "&:hover": {
                borderColor: "#fff",
                bgcolor: "rgba(255, 255, 255, 0.05)",
              },
            }}
          >
            Watch Demo
          </Button>
        </Box>
      </Container>
    </Box>
  );
};

export default Features;
