import React, { useState, useEffect } from "react";
import {
  Fab,
  Tooltip,
  Zoom,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  TextField,
  InputAdornment,
  IconButton,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import RocketLaunchIcon from "@mui/icons-material/RocketLaunch";
import ChevronUpIcon from "@mui/icons-material/KeyboardArrowUp";
import CloseIcon from "@mui/icons-material/Close";
import EmailIcon from "@mui/icons-material/Email";
import SendIcon from "@mui/icons-material/Send";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";

const FloatingCTA = () => {
  const [visible, setVisible] = useState(false);
  const [showDialog, setShowDialog] = useState(false);
  const [email, setEmail] = useState("");
  const [emailSent, setEmailSent] = useState(false);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

  // Show button when user scrolls down
  useEffect(() => {
    const toggleVisibility = () => {
      if (window.pageYOffset > 300) {
        setVisible(true);
      } else {
        setVisible(false);
      }
    };

    window.addEventListener("scroll", toggleVisibility);
    return () => window.removeEventListener("scroll", toggleVisibility);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleOpen = () => {
    setShowDialog(true);
  };

  const handleClose = () => {
    setShowDialog(false);
    // Reset state when dialog closes
    if (emailSent) {
      setTimeout(() => {
        setEmailSent(false);
        setEmail("");
      }, 300);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Simulate sending email
    setEmailSent(true);
    // In a real app, you would send this to your API
    console.log("Email submitted:", email);
  };

  return (
    <>
      {/* Scroll to top button */}
      <Zoom in={visible}>
        <Tooltip title="Back to top" placement="left">
          <Fab
            size="small"
            aria-label="scroll back to top"
            sx={{
              position: "fixed",
              bottom: isMobile ? 80 : 90,
              right: 20,
              background: "#ffffff",
              color: "#00AEEF",
              boxShadow: "0px 4px 16px rgba(0, 0, 0, 0.1)",
              zIndex: 1000,
              ":hover": {
                background: "#f8f8f8",
              },
            }}
            onClick={scrollToTop}
          >
            <ChevronUpIcon />
          </Fab>
        </Tooltip>
      </Zoom>

      {/* Main CTA button */}
      <Zoom in>
        <Tooltip title="Launch your trading journey" placement="left">
          <Fab
            color="primary"
            size={isMobile ? "medium" : "large"}
            sx={{
              position: "fixed",
              bottom: 20,
              right: 20,
              background: "linear-gradient(145deg, #00f2fe, #4facfe)",
              color: "#fff",
              boxShadow: "0px 4px 24px rgba(0, 175, 239, 0.5)",
              zIndex: 1000,
              ":hover": {
                background: "linear-gradient(145deg, #00c6fb, #005bea)",
                transform: "scale(1.05)",
                boxShadow: "0px 6px 30px rgba(0, 175, 239, 0.7)",
              },
              transition: "all 0.3s ease-in-out",
            }}
            onClick={handleOpen}
          >
            <RocketLaunchIcon />
          </Fab>
        </Tooltip>
      </Zoom>

      {/* Get started dialog */}
      <Dialog
        open={showDialog}
        onClose={handleClose}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          elevation: 24,
          sx: {
            borderRadius: 3,
            overflow: "hidden",
          },
        }}
      >
        {!emailSent ? (
          <>
            <DialogTitle
              sx={{
                p: 3,
                background: "linear-gradient(to right, #00AEEF, #4facfe)",
                color: "white",
                position: "relative",
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <RocketLaunchIcon sx={{ mr: 1 }} />
                <Typography variant="h5" component="div" fontWeight="bold">
                  Start Your Trading Journey
                </Typography>
              </Box>
              <IconButton
                aria-label="close"
                onClick={handleClose}
                sx={{
                  position: "absolute",
                  right: 16,
                  top: 16,
                  color: "white",
                }}
              >
                <CloseIcon />
              </IconButton>
            </DialogTitle>

            <DialogContent sx={{ p: 3, pt: 4 }}>
              <Typography variant="body1" paragraph>
                Ready to transform your trading with AI-powered automation? Get
                started today and receive:
              </Typography>

              <Box sx={{ pl: 2, mb: 3 }}>
                {[
                  "14-day free trial with full platform access",
                  "Personalized onboarding session with a trading specialist",
                  "Access to our library of pre-built strategies",
                  "Real-time market insights directly to your inbox",
                ].map((item, index) => (
                  <Box
                    key={index}
                    sx={{ display: "flex", alignItems: "center", mb: 1 }}
                  >
                    <Box
                      component="span"
                      sx={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        backgroundColor: "#00AEEF",
                        mr: 1.5,
                      }}
                    />
                    <Typography variant="body1">{item}</Typography>
                  </Box>
                ))}
              </Box>

              <Typography variant="body1" sx={{ mb: 3 }}>
                Enter your email to get started or to receive more information:
              </Typography>

              <form onSubmit={handleSubmit}>
                <TextField
                  fullWidth
                  variant="outlined"
                  placeholder="Your email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  type="email"
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <EmailIcon color="primary" />
                      </InputAdornment>
                    ),
                  }}
                  sx={{ mb: 2 }}
                />

                <Button
                  type="submit"
                  variant="contained"
                  size="large"
                  fullWidth
                  startIcon={<TrendingUpIcon />}
                  endIcon={<SendIcon />}
                  sx={{
                    py: 1.5,
                    backgroundColor: "#00AEEF",
                    background: "linear-gradient(145deg, #00f2fe, #4facfe)",
                    fontWeight: "bold",
                    "&:hover": {
                      background: "linear-gradient(145deg, #00c6fb, #005bea)",
                    },
                  }}
                >
                  Get Started Now
                </Button>
              </form>
            </DialogContent>

            <DialogActions sx={{ px: 3, pb: 3, justifyContent: "center" }}>
              <Typography
                variant="caption"
                align="center"
                color="textSecondary"
              >
                By submitting, you agree to our Terms of Service and Privacy
                Policy. We'll never share your information with third parties.
              </Typography>
            </DialogActions>
          </>
        ) : (
          <>
            <DialogTitle sx={{ p: 0 }}>
              <Box
                sx={{
                  background: "linear-gradient(to right, #00AEEF, #4facfe)",
                  p: 10,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  position: "relative",
                }}
              >
                <IconButton
                  aria-label="close"
                  onClick={handleClose}
                  sx={{
                    position: "absolute",
                    right: 16,
                    top: 16,
                    color: "white",
                  }}
                >
                  <CloseIcon />
                </IconButton>

                <Box
                  sx={{
                    width: 80,
                    height: 80,
                    borderRadius: "50%",
                    bgcolor: "white",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    mb: 3,
                  }}
                >
                  <SendIcon sx={{ fontSize: 40, color: "#00AEEF" }} />
                </Box>

                <Typography
                  variant="h4"
                  fontWeight="bold"
                  color="white"
                  align="center"
                >
                  Thank You!
                </Typography>

                <Typography
                  variant="body1"
                  color="white"
                  align="center"
                  sx={{ mt: 1, opacity: 0.9 }}
                >
                  We've sent your welcome email to {email}
                </Typography>
              </Box>
            </DialogTitle>

            <DialogContent sx={{ p: 4, textAlign: "center" }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                What's Next?
              </Typography>

              <Typography variant="body1" paragraph>
                Check your inbox for login details and next steps to set up your
                account. Our team will reach out shortly to schedule your
                onboarding session.
              </Typography>

              <Button
                variant="outlined"
                color="primary"
                onClick={handleClose}
                sx={{ mt: 2 }}
              >
                Close
              </Button>
            </DialogContent>
          </>
        )}
      </Dialog>
    </>
  );
};

export default FloatingCTA;
