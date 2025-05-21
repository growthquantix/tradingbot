import React from "react";
import {
  Box,
  Container,
  Typography,
  Grid,
  Paper,
  Avatar,
  Button,
  Divider,
  Rating,
} from "@mui/material";
import { Star as StarIcon } from "@mui/icons-material";

const testimonials = [
  {
    name: "Ravi M.",
    position: "Day Trader",
    comment:
      "Quantix's breakout AI replaced hours of manual charting! The predictive algorithms spotted patterns I would have missed, increasing my daily profits by 22%.",
    rating: 5,
    image: "/api/placeholder/80/80",
  },
  {
    name: "Neha S.",
    position: "Options Specialist",
    comment:
      "My options win rate jumped by 30% using the scalping bot. The real-time market data analysis gives me an edge I never had with traditional platforms.",
    rating: 5,
    image: "/api/placeholder/80/80",
  },
  {
    name: "Arjun D.",
    position: "Portfolio Manager",
    comment:
      "The sector rotation AI outperformed my ETF strategy easily. I've been able to capture alpha in changing market conditions that would have been impossible to track manually.",
    rating: 5,
    image: "/api/placeholder/80/80",
  },
  {
    name: "Maya P.",
    position: "Crypto Trader",
    comment:
      "Quantix's volatility prediction tools have completely transformed my crypto trading strategy. The AI anticipates market movements with impressive accuracy.",
    rating: 5,
    image: "/api/placeholder/80/80",
  },
];

const TestimonialsSection = () => {
  return (
    <Box
      sx={{
        bgcolor: "#0a0f1a",
        color: "#ffffff",
        py: 10,
        backgroundImage: "linear-gradient(to bottom, #0a0f1a, #081525)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Decorative elements */}
      <Box
        sx={{
          position: "absolute",
          left: -20,
          top: "33%",
          width: 120,
          height: 120,
          borderRadius: "50%",
          bgcolor: "rgba(0, 130, 255, 0.1)",
          filter: "blur(30px)",
        }}
      />
      <Box
        sx={{
          position: "absolute",
          right: -20,
          bottom: "33%",
          width: 160,
          height: 160,
          borderRadius: "50%",
          bgcolor: "rgba(0, 174, 239, 0.1)",
          filter: "blur(30px)",
        }}
      />

      <Container maxWidth="lg">
        <Box sx={{ textAlign: "center", mb: 6 }}>
          <Typography variant="h4" fontWeight="bold" gutterBottom>
            Trusted by Profitable Traders
          </Typography>
          <Typography
            variant="subtitle1"
            sx={{
              color: "#00aeef",
              maxWidth: 600,
              mx: "auto",
            }}
          >
            See why thousands of traders rely on Quantix AI for their daily
            market edge
          </Typography>
        </Box>

        <Grid container spacing={3}>
          {testimonials.map((testimonial, index) => (
            <Grid item xs={12} md={6} lg={3} key={index}>
              <Paper
                sx={{
                  p: 3,
                  bgcolor: "rgba(6, 17, 32, 0.7)",
                  backdropFilter: "blur(8px)",
                  border: "1px solid rgba(0, 174, 239, 0.2)",
                  borderRadius: 2,
                  height: "100%",
                  transition: "all 0.3s ease",
                  "&:hover": {
                    transform: "translateY(-4px)",
                    boxShadow: "0 10px 20px rgba(0, 174, 239, 0.1)",
                    border: "1px solid rgba(0, 174, 239, 0.5)",
                  },
                }}
              >
                <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                  <Avatar
                    src={testimonial.image}
                    alt={testimonial.name}
                    sx={{
                      width: 48,
                      height: 48,
                      border: "2px solid rgba(0, 174, 239, 0.3)",
                    }}
                  />
                  <Box sx={{ ml: 2 }}>
                    <Typography variant="body1" fontWeight="bold">
                      {testimonial.name}
                    </Typography>
                    <Typography variant="caption" sx={{ color: "#00aeef" }}>
                      {testimonial.position}
                    </Typography>
                  </Box>
                </Box>

                <Rating
                  value={testimonial.rating}
                  readOnly
                  size="small"
                  icon={
                    <StarIcon fontSize="inherit" sx={{ color: "#f9d100" }} />
                  }
                  emptyIcon={
                    <StarIcon fontSize="inherit" sx={{ opacity: 0.3 }} />
                  }
                  sx={{ mb: 1.5 }}
                />

                <Typography
                  variant="body2"
                  sx={{
                    fontStyle: "italic",
                    color: "rgba(255, 255, 255, 0.8)",
                    mb: 2,
                  }}
                >
                  "{testimonial.comment}"
                </Typography>

                <Divider
                  sx={{ borderColor: "rgba(255, 255, 255, 0.1)", my: 1.5 }}
                />

                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      color: "#00aeef",
                      fontWeight: "medium",
                    }}
                  >
                    Verified Trader
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ color: "rgba(255, 255, 255, 0.5)" }}
                  >
                    Quantix User
                  </Typography>
                </Box>
              </Paper>
            </Grid>
          ))}
        </Grid>

        <Box sx={{ mt: 6, textAlign: "center" }}>
          <Typography
            variant="body1"
            sx={{ color: "#00aeef", fontWeight: "medium", mb: 2 }}
          >
            Join 10,000+ traders using Quantix
          </Typography>
          <Button
            variant="contained"
            sx={{
              backgroundImage: "linear-gradient(to right, #00aeef, #0080cc)",
              px: 4,
              py: 1.5,
              fontWeight: "bold",
              borderRadius: 2,
              "&:hover": {
                boxShadow: "0 4px 12px rgba(0, 174, 239, 0.3)",
              },
            }}
          >
            Start Free Trial
          </Button>
        </Box>
      </Container>
    </Box>
  );
};

export default TestimonialsSection;
