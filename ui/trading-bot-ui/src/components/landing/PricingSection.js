import React from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Button,
  useTheme,
  Chip,
  Divider,
  Container,
  Stack,
} from "@mui/material";
import { KeyboardArrowRight, Star, CheckCircle } from "@mui/icons-material";

const plans = [
  {
    title: "Basic",
    price: "₹4999",
    period: "/mo",
    subtitle: "For Beginners",
    features: [
      "Live AI Signals",
      "1 Trading Strategy",
      "Basic Backtesting",
      "Email Alerts",
      "Basic Dashboard",
    ],
    color: "linear-gradient(135deg, #121a29, #1c2b39)",
    highlight: false,
  },
  {
    title: "Pro",
    price: "₹9999",
    period: "/mo",
    subtitle: "Most Popular",
    features: [
      "Everything in Basic",
      "Multi-Strategy AI",
      "Advanced Backtesting",
      "Priority Support",
      "Telegram Alerts",
      "Advanced Dashboard",
      "Strategy Customization",
    ],
    color: "linear-gradient(135deg, #00bfff, #005eff)",
    highlight: true,
  },
  {
    title: "Elite",
    price: "₹14999",
    period: "/mo",
    subtitle: "For Active Traders",
    features: [
      "Everything in Pro",
      "Full AI Automation",
      "Smart Entry & Exit",
      "Multiple Broker Integration",
      "Real-time Optimization",
      "Dedicated Account Manager",
      "Custom Strategy Development",
    ],
    color: "linear-gradient(135deg, #131b25, #1f2a38)",
    highlight: false,
  },
];

const PricingSection = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  return (
    <Box
      id="pricing"
      py={12}
      sx={{
        background: isDark
          ? "linear-gradient(to bottom, #030712, #0a1929)"
          : "linear-gradient(to bottom, #f4f6f8, #e0e7ff)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background decoration */}
      <Box
        sx={{
          position: "absolute",
          top: -100,
          right: -100,
          width: 400,
          height: 400,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(0,210,255,0.1), transparent 70%)",
          filter: "blur(80px)",
          zIndex: 0,
        }}
      />

      <Container maxWidth="lg" sx={{ position: "relative", zIndex: 1 }}>
        <Stack spacing={2} alignItems="center" sx={{ mb: 8 }}>
          <Typography
            variant="h4"
            fontWeight={800}
            align="center"
            sx={{
              background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              mb: 1,
            }}
          >
            Pricing Plans
          </Typography>
          <Typography
            variant="h6"
            align="center"
            color="text.secondary"
            sx={{ maxWidth: 600, mx: "auto" }}
          >
            Pick the plan that suits your trading journey and unlock AI-powered
            trading
          </Typography>
        </Stack>

        <Grid container spacing={4} justifyContent="center">
          {plans.map((plan, index) => {
            const isPro = plan.highlight;

            return (
              <Grid item xs={12} sm={6} md={4} key={index}>
                <Card
                  sx={{
                    background: plan.color,
                    color: isPro ? "#fff" : theme.palette.text.primary,
                    boxShadow: isPro
                      ? "0 8px 32px rgba(0, 186, 255, 0.4)"
                      : "0 4px 24px rgba(0, 0, 0, 0.15)",
                    transform: isPro ? "scale(1.05)" : "none",
                    transition: "all 0.3s ease-in-out",
                    borderRadius: 4,
                    position: "relative",
                    overflow: "hidden",
                    height: "100%",
                    "&:hover": {
                      transform: isPro ? "scale(1.08)" : "scale(1.03)",
                      boxShadow: isPro
                        ? "0 12px 40px rgba(0, 186, 255, 0.5)"
                        : "0 8px 30px rgba(0, 0, 0, 0.2)",
                    },
                    border: isPro
                      ? `2px solid ${theme.palette.primary.main}`
                      : `1px solid ${
                          isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"
                        }`,
                  }}
                >
                  <CardContent sx={{ p: 4 }}>
                    {isPro && (
                      <Chip
                        icon={<Star fontSize="small" />}
                        label="Most Popular"
                        color="secondary"
                        size="small"
                        sx={{
                          position: "absolute",
                          top: 16,
                          right: 16,
                          fontWeight: "bold",
                          backgroundColor: "#fff",
                          color: "#000",
                          px: 1,
                        }}
                      />
                    )}

                    <Typography variant="h5" fontWeight="bold" gutterBottom>
                      {plan.title}
                    </Typography>
                    <Typography
                      variant="subtitle2"
                      sx={{ mb: 3, opacity: 0.8 }}
                    >
                      {plan.subtitle}
                    </Typography>

                    <Box
                      sx={{ display: "flex", alignItems: "flex-end", mb: 0.5 }}
                    >
                      <Typography variant="h3" fontWeight="bold">
                        {plan.price}
                      </Typography>
                      <Typography
                        variant="body1"
                        sx={{ opacity: 0.8, ml: 0.5, mb: 0.8 }}
                      >
                        {plan.period}
                      </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ opacity: 0.7, mb: 3 }}>
                      Plus applicable GST
                    </Typography>

                    <Divider
                      sx={{
                        my: 2,
                        borderColor: isPro
                          ? "rgba(255,255,255,0.2)"
                          : isDark
                          ? "rgba(255,255,255,0.1)"
                          : "rgba(0,0,0,0.1)",
                      }}
                    />

                    <Box sx={{ mb: 4 }}>
                      {plan.features.map((feat, idx) => (
                        <Box
                          key={idx}
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            mb: 1.5,
                          }}
                        >
                          <CheckCircle
                            fontSize="small"
                            sx={{
                              mr: 1,
                              color: isPro
                                ? "#fff"
                                : theme.palette.primary.main,
                            }}
                          />
                          <Typography variant="body2" fontWeight={500}>
                            {feat}
                          </Typography>
                        </Box>
                      ))}
                    </Box>

                    <Button
                      variant={isPro ? "contained" : "outlined"}
                      fullWidth
                      endIcon={<KeyboardArrowRight />}
                      sx={{
                        borderRadius: "12px",
                        py: 1.2,
                        fontWeight: 600,
                        backgroundColor: isPro ? "#fff" : "transparent",
                        color: isPro ? "#000" : theme.palette.primary.main,
                        borderColor: isPro
                          ? "#fff"
                          : theme.palette.primary.main,
                        "&:hover": {
                          backgroundColor: isPro
                            ? "rgba(255, 255, 255, 0.9)"
                            : "rgba(0, 186, 255, 0.1)",
                          borderColor: isPro
                            ? "#fff"
                            : theme.palette.primary.main,
                        },
                        textTransform: "none",
                        fontSize: "1rem",
                      }}
                    >
                      Get Started
                    </Button>
                  </CardContent>
                </Card>
              </Grid>
            );
          })}
        </Grid>

        <Box sx={{ textAlign: "center", mt: 6 }}>
          <Typography variant="body2" color="text.secondary">
            Need a custom plan for your firm?{" "}
            <Button variant="text" sx={{ fontWeight: "bold", ml: 1 }}>
              Contact Sales
            </Button>
          </Typography>
        </Box>
      </Container>
    </Box>
  );
};

export default PricingSection;
