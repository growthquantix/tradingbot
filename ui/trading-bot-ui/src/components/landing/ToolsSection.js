// src/components/landing/ToolsSection.jsx
import { Box, Container, Typography, Grid, Paper, alpha } from "@mui/material";
import { styled } from "@mui/material/styles";
import { motion } from "framer-motion";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import BoltIcon from "@mui/icons-material/Bolt";
import PsychologyIcon from "@mui/icons-material/Psychology";

// Custom styled components
const GradientPaper = styled(Paper)(({ theme, gradientColor }) => ({
  position: "relative",
  height: "100%",
  padding: theme.spacing(4),
  overflow: "hidden",
  borderRadius: theme.shape.borderRadius * 2,
  background: `linear-gradient(135deg, ${alpha(
    theme.palette.background.paper,
    0.8
  )} 0%, ${alpha(theme.palette.background.paper, 0.9)} 100%)`,
  backdropFilter: "blur(8px)",
  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
  transition: "transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out",
  "&:hover": {
    transform: "translateY(-5px)",
    boxShadow: `0 12px 24px -10px ${alpha(gradientColor, 0.3)}`,
    "& .MuiBox-root.icon-wrapper": {
      background: `linear-gradient(135deg, ${gradientColor} 0%, ${theme.palette.primary.main} 100%)`,
    },
    "& .MuiTypography-h6": {
      color: gradientColor,
    },
  },
  "&::before": {
    content: '""',
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: `linear-gradient(135deg, ${alpha(
      gradientColor,
      0.05
    )} 0%, ${alpha(theme.palette.background.paper, 0)} 100%)`,
    zIndex: 0,
  },
}));

const IconWrapper = styled(Box)(({ theme }) => ({
  width: 56,
  height: 56,
  borderRadius: theme.shape.borderRadius,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  marginBottom: theme.spacing(3),
  background: alpha(theme.palette.primary.main, 0.9),
  transition: "background 0.3s ease",
  boxShadow: `0 8px 16px -4px ${alpha(theme.palette.primary.main, 0.3)}`,
}));

const GlowingOrb = styled(Box)(({ theme, color }) => ({
  position: "absolute",
  width: 300,
  height: 300,
  borderRadius: "50%",
  background: alpha(color, 0.15),
  filter: "blur(80px)",
  zIndex: 0,
  opacity: 0.6,
}));

const ToolsSection = () => {
  const tools = [
    {
      title: "AI Trade Insights",
      description:
        "Neural networks analyze market patterns, identifying opportunities human traders might miss",
      icon: <ShowChartIcon sx={{ fontSize: 28 }} />,
      color: "#3f93f5", // blue
    },
    {
      title: "Automated Execution",
      description:
        "Millisecond-precision execution with no emotional bias, maximizing execution quality",
      icon: <BoltIcon sx={{ fontSize: 28 }} />,
      color: "#00c9ff", // cyan
    },
    {
      title: "Predictive Analytics",
      description:
        "Self-optimizing algorithms continuously improve based on market feedback loops",
      icon: <PsychologyIcon sx={{ fontSize: 28 }} />,
      color: "#7c4dff", // purple
    },
  ];

  return (
    <Box
      sx={{
        py: 10,
        background: (theme) =>
          theme.palette.mode === "dark"
            ? "linear-gradient(180deg, #0a1929 0%, #000000 100%)"
            : "linear-gradient(180deg, #f5f5f7 0%, #e0e7ff 100%)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background glowing orbs */}
      <GlowingOrb color="#00c9ff" sx={{ top: -100, right: -50 }} />
      <GlowingOrb color="#3f93f5" sx={{ bottom: -150, left: -100 }} />

      <Container maxWidth="lg" sx={{ position: "relative", zIndex: 1 }}>
        <Box
          component={motion.div}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          sx={{ textAlign: "center", mb: 8 }}
        >
          <Typography
            variant="overline"
            component="h4"
            sx={{
              color: "primary.main",
              fontWeight: 600,
              letterSpacing: 2,
              display: "block",
              mb: 2,
            }}
          >
            Algorithmic Advantage
          </Typography>

          <Typography
            variant="h3"
            component="h2"
            sx={{
              fontWeight: 700,
              mb: 2,
              background:
                "linear-gradient(90deg, #00c9ff 0%, #3f93f5 50%, #7c4dff 100%)",
              backgroundClip: "text",
              textFillColor: "transparent",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              display: { xs: "block", md: "block" },
            }}
          >
            AI-Powered Trading Infrastructure
          </Typography>

          <Typography
            variant="body1"
            color="text.secondary"
            sx={{
              maxWidth: 700,
              mx: "auto",
              mb: 2,
              fontSize: "1.1rem",
            }}
          >
            Our platform combines cutting-edge artificial intelligence with
            high-frequency trading technology
          </Typography>
        </Box>

        <Grid container spacing={4}>
          {tools.map((tool, index) => (
            <Grid item xs={12} md={4} key={index}>
              <Box
                component={motion.div}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.2 }}
                sx={{ height: "100%" }}
              >
                <GradientPaper gradientColor={tool.color} elevation={4}>
                  <Box sx={{ position: "relative", zIndex: 1 }}>
                    <IconWrapper className="icon-wrapper">
                      <Box sx={{ color: "white" }}>{tool.icon}</Box>
                    </IconWrapper>

                    <Typography
                      variant="h6"
                      sx={{
                        fontWeight: 600,
                        mb: 2,
                        transition: "color 0.3s ease",
                      }}
                    >
                      {tool.title}
                    </Typography>

                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ lineHeight: 1.6 }}
                    >
                      {tool.description}
                    </Typography>
                  </Box>
                </GradientPaper>
              </Box>
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  );
};

export default ToolsSection;
