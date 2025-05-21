import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  useTheme,
} from "@mui/material";
import { motion } from "framer-motion";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import FlashOnIcon from "@mui/icons-material/FlashOn";
import PsychologyIcon from "@mui/icons-material/Psychology";

const tools = [
  {
    title: "AI Trade Insights",
    description: "Smart insights based on technical & volume patterns",
    icon: <TrendingUpIcon sx={{ fontSize: 36 }} />,
    color: "#3a86ff",
  },
  {
    title: "Automated Execution",
    description: "Speed matters. AI executes trades with zero latency",
    icon: <FlashOnIcon sx={{ fontSize: 36 }} />,
    color: "#00c6ff",
  },
  {
    title: "Adaptive Accuracy",
    description: "Self-learning algorithms that evolve with market shifts",
    icon: <PsychologyIcon sx={{ fontSize: 36 }} />,
    color: "#8338ec",
  },
];

const ToolsSection = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  return (
    <Box
      id="tools"
      sx={{ py: 10, px: 4, bgcolor: isDark ? "#0a1929" : "#f8fafc" }}
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Typography variant="h4" textAlign="center" fontWeight="bold" mb={1}>
          Everything You Need to Win
        </Typography>

        <Typography
          variant="body1"
          textAlign="center"
          color="text.secondary"
          sx={{ maxWidth: 700, mx: "auto", mb: 6 }}
        >
          Our platform combines cutting-edge AI with high-frequency trading
          technology
        </Typography>
      </motion.div>

      <Grid container spacing={4} justifyContent="center">
        {tools.map((tool, idx) => (
          <Grid item xs={12} sm={6} md={4} key={idx}>
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              whileHover={{ y: -10, transition: { duration: 0.2 } }}
            >
              <Card
                elevation={isDark ? 8 : 2}
                sx={{
                  height: "100%",
                  borderRadius: 3,
                  position: "relative",
                  overflow: "hidden",
                  transition: "transform 0.3s, box-shadow 0.3s",
                  "&:hover": {
                    boxShadow: `0 10px 30px rgba(0,0,0,0.15), 0 0 0 1px ${tool.color}20`,
                  },
                  bgcolor: isDark ? "#082440" : "#fff",
                }}
              >
                {/* Colorful top border */}
                <Box
                  sx={{
                    height: 5,
                    width: "100%",
                    background: `linear-gradient(90deg, ${tool.color}, ${tool.color}80)`,
                    position: "absolute",
                    top: 0,
                    left: 0,
                  }}
                />

                <CardContent sx={{ p: 4 }}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      mb: 2.5,
                      color: tool.color,
                    }}
                  >
                    {tool.icon}
                    <Typography variant="h6" fontWeight="bold" sx={{ ml: 1.5 }}>
                      {tool.title}
                    </Typography>
                  </Box>

                  <Typography
                    variant="body1"
                    color="text.secondary"
                    sx={{
                      fontSize: "1rem",
                      lineHeight: 1.6,
                    }}
                  >
                    {tool.description}
                  </Typography>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default ToolsSection;
