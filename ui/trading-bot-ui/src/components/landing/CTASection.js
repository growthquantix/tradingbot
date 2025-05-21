import React from "react";
import {
  Box,
  Container,
  Typography,
  Button,
  Grid,
  Paper,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";

const features = [
  "AI-powered trading signals",
  "Multi-broker integration",
  "Real-time portfolio monitoring",
  "14-day free trial",
];

const CTASection = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isMedium = useMediaQuery(theme.breakpoints.down("md"));

  return (
    <Box
      id="cta"
      sx={{
        py: { xs: 8, md: 12 },
        position: "relative",
        overflow: "hidden",
        color: "white",
      }}
    >
      {/* Background with improved gradient and overlay */}
      <Box
        sx={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background:
            "linear-gradient(135deg, #00AEEF 0%, #0076a3 50%, #005072 100%)",
          zIndex: -2,
        }}
      />

      {/* Animated background elements */}
      <Box
        sx={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background:
            'url(\'data:image/svg+xml,%3Csvg width="60" height="60" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg"%3E%3Cg fill="none" fill-rule="evenodd"%3E%3Cg fill="%23ffffff" fill-opacity="0.05"%3E%3Cpath d="M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z"/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\')',
          backgroundSize: "60px 60px",
          zIndex: -1,
          opacity: 0.5,
          animation: "moveBackground 30s linear infinite",
          "@keyframes moveBackground": {
            "0%": { backgroundPosition: "0% 0%" },
            "100%": { backgroundPosition: "100% 100%" },
          },
        }}
      />

      <Container maxWidth="lg">
        <Grid container spacing={4} alignItems="center" justifyContent="center">
          {/* Left side content */}
          <Grid
            item
            xs={12}
            md={7}
            sx={{ textAlign: { xs: "center", md: "left" } }}
          >
            <Box
              sx={{
                display: "inline-flex",
                alignItems: "center",
                backgroundColor: "rgba(255, 255, 255, 0.2)",
                px: 2,
                py: 1,
                borderRadius: 4,
                mb: 3,
              }}
            >
              <TrendingUpIcon sx={{ mr: 1, fontSize: 18 }} />
              <Typography variant="subtitle2" fontWeight="medium">
                AI-Powered Trading Platform
              </Typography>
            </Box>

            <Typography
              variant="h3"
              fontWeight="bold"
              gutterBottom
              sx={{
                fontSize: { xs: "2rem", sm: "2.5rem", md: "3rem" },
                textShadow: "0 2px 10px rgba(0,0,0,0.2)",
              }}
            >
              Start your AI trading journey today
            </Typography>

            <Typography
              variant="h6"
              sx={{
                mb: 4,
                opacity: 0.9,
                maxWidth: { md: "80%" },
                fontSize: { xs: "1rem", md: "1.25rem" },
              }}
            >
              Join thousands of traders using Growth Quantix to automate their
              trades and maximize returns with AI-powered strategies.
            </Typography>

            <Grid container spacing={2} sx={{ mb: 4 }}>
              {features.map((feature, index) => (
                <Grid item xs={12} sm={6} key={index}>
                  <Box sx={{ display: "flex", alignItems: "center" }}>
                    <CheckCircleOutlineIcon sx={{ mr: 1, color: "#ffffff" }} />
                    <Typography>{feature}</Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>

            <Box
              sx={{
                display: "flex",
                flexDirection: { xs: "column", sm: "row" },
                gap: 2,
              }}
            >
              <Button
                variant="contained"
                size="large"
                endIcon={<ArrowForwardIcon />}
                sx={{
                  py: 1.5,
                  px: 4,
                  backgroundColor: "#fff",
                  color: "#005072",
                  fontWeight: "bold",
                  fontSize: "1rem",
                  boxShadow: "0 4px 14px rgba(0, 0, 0, 0.2)",
                  "&:hover": {
                    backgroundColor: "#f0f0f0",
                    transform: "translateY(-2px)",
                    boxShadow: "0 6px 20px rgba(0, 0, 0, 0.25)",
                  },
                  transition: "all 0.3s ease",
                }}
              >
                Get Started Free
              </Button>

              <Button
                variant="outlined"
                size="large"
                sx={{
                  py: 1.5,
                  px: 4,
                  borderColor: "#ffffff",
                  color: "#ffffff",
                  borderWidth: 2,
                  "&:hover": {
                    borderColor: "#ffffff",
                    backgroundColor: "rgba(255, 255, 255, 0.1)",
                    borderWidth: 2,
                  },
                }}
              >
                View Demo
              </Button>
            </Box>
          </Grid>

          {/* Right side stats or social proof */}
          {!isMedium && (
            <Grid item md={5}>
              <Paper
                elevation={15}
                sx={{
                  backgroundColor: "rgba(255, 255, 255, 0.94)",
                  backdropFilter: "blur(10px)",
                  borderRadius: 4,
                  py: 4,
                  px: 4,
                  color: "#333",
                  transform: "perspective(1000px) rotateY(-5deg)",
                  boxShadow: "0 15px 50px rgba(0, 0, 0, 0.3)",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                <Typography
                  variant="h5"
                  fontWeight="bold"
                  gutterBottom
                  sx={{ color: "#005072" }}
                >
                  Trading Performance
                </Typography>

                <Box mt={3}>
                  {[
                    {
                      label: "Average Monthly Return",
                      value: "12.4%",
                      change: "+2.1%",
                    },
                    { label: "Win Rate", value: "78%", change: "+5%" },
                    { label: "Drawdown", value: "4.8%", change: "-1.2%" },
                  ].map((stat, index) => (
                    <Box
                      key={index}
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        py: 1.5,
                        borderBottom:
                          index < 2 ? "1px solid rgba(0,0,0,0.1)" : "none",
                      }}
                    >
                      <Typography variant="body1" fontWeight="medium">
                        {stat.label}
                      </Typography>
                      <Box sx={{ textAlign: "right" }}>
                        <Typography variant="body1" fontWeight="bold">
                          {stat.value}
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            color: stat.change.startsWith("+")
                              ? "green"
                              : "red",
                            fontWeight: "bold",
                          }}
                        >
                          {stat.change} from last month
                        </Typography>
                      </Box>
                    </Box>
                  ))}
                </Box>

                <Box
                  mt={4}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{ color: "#666", fontStyle: "italic" }}
                  >
                    *Based on backtested performance. Past performance does not
                    guarantee future results.
                  </Typography>
                </Box>

                {/* Decorative element */}
                <Box
                  sx={{
                    position: "absolute",
                    width: "150px",
                    height: "150px",
                    borderRadius: "50%",
                    background:
                      "linear-gradient(45deg, rgba(0,174,239,0.1), rgba(0,80,114,0.05))",
                    top: "-50px",
                    right: "-50px",
                    zIndex: 0,
                  }}
                />
              </Paper>
            </Grid>
          )}
        </Grid>

        {/* Bottom trust indicators */}
        <Box
          sx={{
            mt: 8,
            pt: 4,
            borderTop: "1px solid rgba(255,255,255,0.2)",
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            alignItems: "center",
            justifyContent: "space-between",
            gap: 3,
          }}
        >
          <Typography variant="body2" sx={{ opacity: 0.8 }}>
            Trusted by 10,000+ traders worldwide
          </Typography>

          <Box sx={{ display: "flex", gap: 4, alignItems: "center" }}>
            {["Secure Payments", "Cancel Anytime", "24/7 Support"].map(
              (item, index) => (
                <Box key={index} sx={{ display: "flex", alignItems: "center" }}>
                  <CheckCircleOutlineIcon sx={{ fontSize: 18, mr: 0.5 }} />
                  <Typography variant="body2">{item}</Typography>
                </Box>
              )
            )}
          </Box>
        </Box>
      </Container>
    </Box>
  );
};

export default CTASection;
