import React from "react";
import {
  Box,
  Typography,
  Grid,
  Paper,
  Container,
  useTheme,
  alpha,
} from "@mui/material";
import { motion } from "framer-motion";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import FlashOnIcon from "@mui/icons-material/FlashOn";
import AutoGraphIcon from "@mui/icons-material/AutoGraph";

const ToolsSection = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const tools = [
    {
      title: "AI Trade Insights",
      description: "Smart insights based on technical & volume patterns",
      icon: <ShowChartIcon sx={{ fontSize: 28 }} />,
      color: "#3a86ff",
      gradient: "linear-gradient(135deg, #3a86ff 0%, #00c6ff 100%)",
    },
    {
      title: "Automated Execution",
      description: "Speed matters. AI executes trades with zero latency",
      icon: <FlashOnIcon sx={{ fontSize: 28 }} />,
      color: "#8338ec",
      gradient: "linear-gradient(135deg, #8338ec 0%, #3a86ff 100%)",
    },
    {
      title: "Adaptive Accuracy",
      description: "Self-learning algorithms that evolve with market shifts",
      icon: <AutoGraphIcon sx={{ fontSize: 28 }} />,
      color: "#ff006e",
      gradient: "linear-gradient(135deg, #ff006e 0%, #8338ec 100%)",
    },
  ];

  // Animations
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.2 },
    },
  };

  const cardVariants = {
    hidden: { y: 50, opacity: 0 },
    visible: {
      y: 0,
      opacity: 1,
      transition: { type: "spring", stiffness: 100, damping: 12 },
    },
    hover: {
      y: -12,
      transition: { type: "spring", stiffness: 300, damping: 15 },
    },
  };

  const iconVariants = {
    hidden: { scale: 0 },
    visible: {
      scale: 1,
      transition: { type: "spring", stiffness: 200, delay: 0.2 },
    },
    hover: {
      rotate: [0, -10, 10, -10, 0],
      transition: { duration: 0.5 },
    },
  };

  return (
    <Box
      sx={{
        position: "relative",
        py: 12,
        background: isDark
          ? "linear-gradient(180deg, #050816 0%, #0c0f20 100%)"
          : "linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%)",
        overflow: "hidden",
      }}
    >
      {/* Background decorative elements */}
      <Box
        sx={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 0,
          opacity: 0.3,
          backgroundImage:
            "radial-gradient(circle at 20% 25%, rgba(58, 134, 255, 0.15) 0%, transparent 50%), radial-gradient(circle at 80% 75%, rgba(131, 56, 236, 0.15) 0%, transparent 50%)",
        }}
      />

      {/* Main content */}
      <Container maxWidth="lg" sx={{ position: "relative", zIndex: 1 }}>
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
        >
          <Box textAlign="center" mb={8}>
            <Typography
              variant="overline"
              component="div"
              sx={{
                display: "inline-block",
                color: "#3a86ff",
                fontWeight: 600,
                letterSpacing: 1.5,
                mb: 2,
                background: isDark
                  ? "linear-gradient(to right, #3a86ff, #00c6ff)"
                  : "none",
                backgroundClip: isDark ? "text" : "none",
                WebkitBackgroundClip: isDark ? "text" : "none",
                WebkitTextFillColor: isDark ? "transparent" : "inherit",
              }}
            >
              TRADING TOOLS
            </Typography>

            <Typography
              variant="h3"
              component="h2"
              fontWeight="800"
              sx={{
                mb: 3,
                background:
                  "linear-gradient(to right, #3a86ff, #8338ec, #ff006e)",
                backgroundClip: "text",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                textAlign: "center",
              }}
            >
              Everything You Need To Win
            </Typography>

            <Typography
              variant="body1"
              sx={{
                color: isDark ? "grey.400" : "grey.700",
                maxWidth: 700,
                mx: "auto",
                fontSize: "1.1rem",
              }}
            >
              Our AI-powered platform provides advanced tools that give you the
              edge in today's competitive markets
            </Typography>
          </Box>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          <Grid container spacing={4}>
            {tools.map((tool, index) => (
              <Grid item xs={12} md={4} key={index}>
                <motion.div variants={cardVariants} whileHover="hover">
                  <Paper
                    elevation={isDark ? 16 : 4}
                    sx={{
                      position: "relative",
                      p: 4,
                      pt: 6,
                      pb: 5,
                      height: "100%",
                      overflow: "hidden",
                      borderRadius: 4,
                      background: isDark ? alpha("#0c0f20", 0.7) : "#ffffff",
                      backdropFilter: "blur(10px)",
                      border: `1px solid ${
                        isDark ? alpha(tool.color, 0.2) : alpha(tool.color, 0.1)
                      }`,
                      transition: "all 0.3s ease-in-out",
                      "&:hover": {
                        boxShadow: `0 20px 30px -10px ${alpha(
                          tool.color,
                          0.2
                        )}`,
                        border: `1px solid ${alpha(tool.color, 0.4)}`,
                      },
                    }}
                  >
                    {/* Decorative background gradient */}
                    <Box
                      sx={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        height: "100%",
                        width: "5px",
                        background: tool.gradient,
                      }}
                    />

                    {/* Icon with circular background */}
                    <motion.div
                      variants={iconVariants}
                      style={{
                        marginBottom: 24,
                        display: "inline-block",
                      }}
                    >
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 56,
                          height: 56,
                          borderRadius: "50%",
                          background: tool.gradient,
                          color: "white",
                          boxShadow: `0 10px 20px ${alpha(tool.color, 0.3)}`,
                        }}
                      >
                        {tool.icon}
                      </Box>
                    </motion.div>

                    <Typography
                      variant="h5"
                      fontWeight="700"
                      sx={{
                        mb: 2,
                        color: isDark ? "white" : "grey.800",
                        transition: "color 0.3s ease",
                      }}
                    >
                      {tool.title}
                    </Typography>

                    <Typography
                      variant="body1"
                      sx={{
                        color: isDark ? "grey.400" : "grey.600",
                        fontSize: "1rem",
                        lineHeight: 1.6,
                      }}
                    >
                      {tool.description}
                    </Typography>

                    {/* Decorative corner element */}
                    <Box
                      sx={{
                        position: "absolute",
                        bottom: 0,
                        right: 0,
                        width: 80,
                        height: 80,
                        background: `radial-gradient(circle at bottom right, ${alpha(
                          tool.color,
                          0.15
                        )}, transparent 70%)`,
                      }}
                    />
                  </Paper>
                </motion.div>
              </Grid>
            ))}
          </Grid>
        </motion.div>
      </Container>
    </Box>
  );
};

export default ToolsSection;
