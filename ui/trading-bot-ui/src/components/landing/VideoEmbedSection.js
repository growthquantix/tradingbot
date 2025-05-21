import React from "react";
import { Box, Typography, Grid, Paper, Container } from "@mui/material";
import { motion } from "framer-motion";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import BoltIcon from "@mui/icons-material/Bolt";
import PsychologyIcon from "@mui/icons-material/Psychology";

const ToolsSection = () => {
  const tools = [
    {
      title: "AI Trade Insights",
      description:
        "Neural networks analyze market patterns, identifying opportunities human traders might miss",
      icon: <ShowChartIcon sx={{ fontSize: 36, color: "#20B3FF" }} />,
    },
    {
      title: "Automated Execution",
      description:
        "Millisecond-precision execution with no emotional bias, maximizing execution quality",
      icon: <BoltIcon sx={{ fontSize: 36, color: "#20B3FF" }} />,
    },
    {
      title: "Predictive Analytics",
      description:
        "Self-optimizing algorithms continuously improve based on market feedback loops",
      icon: <PsychologyIcon sx={{ fontSize: 36, color: "#20B3FF" }} />,
    },
  ];

  return (
    <Box
      sx={{
        bgcolor: "#0B1120",
        py: 10,
        px: 2,
        color: "#fff",
      }}
    >
      <Container maxWidth="lg">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          style={{ textAlign: "center", marginBottom: 48 }}
        >
          <Typography
            variant="h4"
            sx={{ fontWeight: 700, mb: 2, color: "#F8FAFC" }}
          >
            Everything You Need to{" "}
            <Box component="span" sx={{ color: "#20B3FF" }}>
              Win
            </Box>
          </Typography>

          <Typography
            sx={{ mb: 3, color: "#94A3B8", maxWidth: 700, mx: "auto" }}
          >
            Our platform combines cutting-edge artificial intelligence with
            high-frequency trading technology to give you the edge in today's
            markets.
          </Typography>
        </motion.div>

        <Grid container spacing={4} justifyContent="center">
          {tools.map((tool, index) => (
            <Grid item xs={12} md={4} key={index}>
              <motion.div
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.2 }}
                whileHover={{ y: -8 }}
              >
                <Paper
                  elevation={4}
                  sx={{
                    p: 4,
                    height: "100%",
                    borderRadius: "12px",
                    background:
                      "linear-gradient(135deg, rgba(32, 179, 255, 0.08) 0%, rgba(13, 18, 36, 0.8) 100%)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    transition:
                      "transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out",
                    "&:hover": {
                      boxShadow:
                        "0 12px 24px rgba(0,0,0,0.4), 0 0 20px rgba(32, 179, 255, 0.15)",
                    },
                  }}
                >
                  <Box sx={{ mb: 2 }}>{tool.icon}</Box>

                  <Typography
                    variant="h6"
                    sx={{
                      fontWeight: 600,
                      mb: 2,
                      color: "#F8FAFC",
                    }}
                  >
                    {tool.title}
                  </Typography>

                  <Typography
                    variant="body2"
                    sx={{
                      color: "#94A3B8",
                      lineHeight: 1.6,
                    }}
                  >
                    {tool.description}
                  </Typography>
                </Paper>
              </motion.div>
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  );
};

export default ToolsSection;
