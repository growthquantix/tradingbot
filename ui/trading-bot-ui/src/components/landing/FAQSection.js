import React, { useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Container,
  Typography,
  Grid,
  Paper,
  Button,
  Fade,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import { ChevronDown, HelpCircle, MessageCircle } from "lucide-react";

const faqs = [
  {
    question: "Is Growth Quantix beginner-friendly?",
    answer:
      "Yes! We provide a plug-and-play system with smart defaults and clear documentation. Our platform is designed to make algorithmic trading accessible even if you have no prior experience with trading bots.",
    category: "Getting Started",
  },
  {
    question: "Can I run my own strategy?",
    answer:
      "No, as of now we do not support custom strategy. Our engine supports black box strategy logic and AI-enhanced decisions. We are working on a custom strategy builder for future releases.",
    category: "Features",
  },
  {
    question: "What brokers are supported?",
    answer:
      "Currently, we support Upstox, Dhan, and Fyers. More integrations are coming soon! We're actively working on adding Zerodha and Angel Broking to our platform.",
    category: "Integration",
  },
  {
    question: "How secure is the platform?",
    answer:
      "Security is our top priority. We use industry-standard encryption, secure API connections, and never store your broker passwords. All trading activities happen via official broker APIs with proper authentication.",
    category: "Security",
  },
  {
    question: "What are the subscription costs?",
    answer:
      "We offer flexible pricing plans starting at ₹999/month. Our subscription includes full access to our AI trading engine, real-time alerts, and broker integrations. Visit our pricing page for detailed information.",
    category: "Pricing",
  },
  {
    question: "Do you offer a trial period?",
    answer:
      "Yes, we offer a 14-day free trial so you can experience the power of our platform before committing. No credit card required to start your trial.",
    category: "Getting Started",
  },
];

// Group FAQs by category
const categorizedFaqs = faqs.reduce((acc, faq) => {
  if (!acc[faq.category]) {
    acc[faq.category] = [];
  }
  acc[faq.category].push(faq);
  return acc;
}, {});

const FAQSection = () => {
  const [expandedPanel, setExpandedPanel] = useState(false);
  const [activeCategory, setActiveCategory] = useState("All");
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

  const categories = ["All", ...Object.keys(categorizedFaqs)];

  const handleChange = (panel) => (event, isExpanded) => {
    setExpandedPanel(isExpanded ? panel : false);
  };

  const filteredFaqs =
    activeCategory === "All" ? faqs : categorizedFaqs[activeCategory] || [];

  return (
    <Box
      py={10}
      sx={{
        backgroundColor: "#071d36",
        color: "#fff",
        backgroundImage:
          "radial-gradient(circle at 10% 20%, rgba(6, 55, 123, 0.5) 0%, rgba(7, 29, 54, 0.5) 100%)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background accents */}
      <Box
        sx={{
          position: "absolute",
          width: "300px",
          height: "300px",
          borderRadius: "50%",
          background: "rgba(61, 225, 255, 0.08)",
          filter: "blur(60px)",
          top: "-100px",
          right: "-100px",
          zIndex: 0,
        }}
      />

      <Container maxWidth="md" sx={{ position: "relative", zIndex: 1 }}>
        <Fade in={true} timeout={800}>
          <Box>
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                mb: 2,
              }}
            >
              <HelpCircle size={32} color="#3DE1FF" />
              <Typography variant="h4" align="center" fontWeight="bold" ml={1}>
                Frequently Asked Questions
              </Typography>
            </Box>

            <Typography
              variant="subtitle1"
              align="center"
              sx={{ opacity: 0.7, mb: 5, maxWidth: "700px", mx: "auto" }}
            >
              Get quick answers to common questions about Growth Quantix's
              trading platform
            </Typography>
          </Box>
        </Fade>

        {/* Category selector */}
        <Grid container spacing={2} sx={{ mb: 4 }} justifyContent="center">
          {categories.map((category) => (
            <Grid item key={category}>
              <Button
                variant={activeCategory === category ? "contained" : "outlined"}
                color="primary"
                onClick={() => setActiveCategory(category)}
                sx={{
                  borderRadius: 4,
                  px: 2,
                  backgroundColor:
                    activeCategory === category
                      ? "rgba(61, 225, 255, 0.2)"
                      : "transparent",
                  borderColor: "rgba(61, 225, 255, 0.5)",
                  color: activeCategory === category ? "#3DE1FF" : "white",
                  "&:hover": {
                    backgroundColor: "rgba(61, 225, 255, 0.15)",
                  },
                }}
              >
                {category}
              </Button>
            </Grid>
          ))}
        </Grid>

        <Paper
          elevation={24}
          sx={{
            backgroundColor: "rgba(12, 27, 42, 0.7)",
            backdropFilter: "blur(10px)",
            borderRadius: 3,
            overflow: "hidden",
            border: "1px solid rgba(61, 225, 255, 0.1)",
          }}
        >
          {filteredFaqs.map((faq, index) => (
            <Accordion
              key={index}
              expanded={expandedPanel === `panel${index}`}
              onChange={handleChange(`panel${index}`)}
              sx={{
                backgroundColor: "transparent",
                color: "#fff",
                boxShadow: "none",
                "&:before": {
                  display: "none",
                },
                "&:not(:last-child)": {
                  borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                },
              }}
            >
              <AccordionSummary
                expandIcon={<ChevronDown color="#3DE1FF" />}
                sx={{
                  px: 3,
                  "&:hover": {
                    backgroundColor: "rgba(61, 225, 255, 0.05)",
                  },
                }}
              >
                <Box sx={{ display: "flex", alignItems: "center" }}>
                  {!isMobile && (
                    <Box
                      sx={{
                        bgcolor: "rgba(61, 225, 255, 0.1)",
                        borderRadius: "50%",
                        height: 32,
                        width: 32,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        mr: 2,
                      }}
                    >
                      <Typography fontWeight="bold" color="#3DE1FF">
                        {index + 1}
                      </Typography>
                    </Box>
                  )}
                  <Typography
                    fontWeight="bold"
                    fontSize={isMobile ? "0.95rem" : "1rem"}
                  >
                    {faq.question}
                  </Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails sx={{ px: 3, pb: 3 }}>
                <Typography
                  sx={{
                    color: "rgba(255, 255, 255, 0.7)",
                    lineHeight: 1.7,
                    borderLeft: "2px solid #3DE1FF",
                    pl: 2,
                  }}
                >
                  {faq.answer}
                </Typography>
              </AccordionDetails>
            </Accordion>
          ))}
        </Paper>

        <Box
          sx={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            mt: 6,
            p: 3,
            borderRadius: 3,
            backgroundColor: "rgba(61, 225, 255, 0.08)",
            border: "1px solid rgba(61, 225, 255, 0.2)",
          }}
        >
          <MessageCircle
            size={24}
            color="#3DE1FF"
            style={{ marginRight: 12 }}
          />
          <Typography variant="body1" sx={{ mr: 2 }}>
            Still have questions?
          </Typography>
          <Button
            variant="contained"
            color="primary"
            sx={{
              borderRadius: 4,
              backgroundColor: "#3DE1FF",
              color: "#071d36",
              fontWeight: "bold",
              "&:hover": {
                backgroundColor: "#2bc4e2",
              },
            }}
          >
            Contact Support
          </Button>
        </Box>
      </Container>
    </Box>
  );
};

export default FAQSection;
