import React from "react";
import {
  Box,
  Container,
  Typography,
  Button,
  Grid,
  useTheme,
  useMediaQuery,
  Paper,
} from "@mui/material";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";

const HeroSection = ({ onGetStarted }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  return (
    <Box
      id="hero"
      sx={{
        pt: { xs: 12, md: 20 },
        pb: { xs: 10, md: 15 },
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background elements */}
      <Box
        sx={{
          position: "absolute",
          top: "10%",
          right: "-5%",
          width: "500px",
          height: "500px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(0, 210, 255, 0.1), transparent 70%)",
          filter: "blur(60px)",
          zIndex: 0,
        }}
      />

      <Container maxWidth="lg">
        <Grid
          container
          spacing={6}
          alignItems="center"
          justifyContent="space-between"
          sx={{ position: "relative", zIndex: 2 }}
        >
          <Grid item xs={12} md={6}>
            <Box
              sx={{
                maxWidth: "600px",
                mx: isMobile ? "auto" : "0",
                textAlign: isMobile ? "center" : "left",
              }}
            >
              <Typography
                variant="h1"
                sx={{
                  fontSize: { xs: "2.5rem", sm: "3.5rem", md: "4rem" },
                  fontWeight: 800,
                  lineHeight: 1.2,
                  mb: 3,
                  background: `linear-gradient(90deg, #fff, ${theme.palette.primary.main})`,
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                The Future of <br />
                <Box
                  component="span"
                  sx={{
                    background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  AI Trading
                </Box>
              </Typography>

              <Typography
                variant="h6"
                sx={{
                  fontSize: "1.25rem",
                  fontWeight: 400,
                  color: "rgba(255, 255, 255, 0.8)",
                  mb: 5,
                  maxWidth: "540px",
                  mx: isMobile ? "auto" : "0",
                }}
              >
                Optimize your strategy using AI models trained on decades of
                market data to make smarter trading decisions.
              </Typography>

              <Box
                sx={{
                  display: "flex",
                  gap: 2,
                  flexDirection: isMobile ? "column" : "row",
                  justifyContent: isMobile ? "center" : "flex-start",
                }}
              >
                <Button
                  variant="contained"
                  color="primary"
                  size="large"
                  onClick={onGetStarted}
                  sx={{
                    py: 1.5,
                    px: 4,
                    fontWeight: "bold",
                    borderRadius: "12px",
                    background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                    boxShadow: "0 4px 14px 0 rgba(0, 186, 255, 0.4)",
                    "&:hover": {
                      background: `linear-gradient(90deg, ${theme.palette.primary.dark}, ${theme.palette.secondary.dark})`,
                      boxShadow: "0 6px 20px 0 rgba(0, 186, 255, 0.6)",
                    },
                  }}
                  endIcon={<ArrowForwardIcon />}
                >
                  Get Started Free
                </Button>

                <Button
                  variant="outlined"
                  size="large"
                  sx={{
                    py: 1.5,
                    px: 4,
                    borderRadius: "12px",
                    borderColor: "rgba(255, 255, 255, 0.2)",
                    color: "white",
                    "&:hover": {
                      borderColor: theme.palette.primary.main,
                      backgroundColor: "rgba(0, 186, 255, 0.1)",
                    },
                  }}
                  startIcon={<PlayArrowIcon />}
                >
                  Watch Demo
                </Button>
              </Box>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper
              elevation={8}
              sx={{
                p: 2,
                borderRadius: "16px",
                background: "rgba(16, 24, 40, 0.6)",
                backdropFilter: "blur(10px)",
                border: "1px solid rgba(0, 186, 255, 0.2)",
                overflow: "hidden",
                position: "relative",
                maxWidth: "600px",
                mx: "auto",
                boxShadow: "0 20px 40px rgba(0, 0, 0, 0.3)",
              }}
            >
              <Box
                component="img"
                src="/assets/neural-network.png" // Replace with your actual image path
                alt="AI Trading Platform"
                sx={{
                  width: "100%",
                  borderRadius: "12px",
                  transition: "transform 0.5s ease",
                  "&:hover": {
                    transform: "scale(1.02)",
                  },
                }}
              />

              {/* Trading signals overlay */}
              <Box
                sx={{
                  position: "absolute",
                  bottom: "20px",
                  left: "20px",
                  right: "20px",
                  p: 2,
                  borderRadius: "12px",
                  backdropFilter: "blur(5px)",
                  backgroundColor: "rgba(0, 0, 0, 0.7)",
                  border: "1px solid rgba(0, 186, 255, 0.3)",
                }}
              >
                <Typography
                  variant="subtitle2"
                  color={theme.palette.primary.main}
                  fontWeight="bold"
                >
                  AI Signal: Strong Buy
                </Typography>
                <Typography variant="body2" color="white">
                  Confidence Score: 87% • Pattern Detected: Breakout
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default HeroSection;
