import { useEffect, useState } from "react";
import { Modal, Box, Typography, Button } from "@mui/material";

const TermsModal = () => {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const accepted = localStorage.getItem("termsAccepted");
    if (!accepted) {
      setOpen(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem("termsAccepted", "true");
    setOpen(false);
  };

  return (
    <Modal open={open}>
      <Box
        sx={{
          width: 500,
          mx: "auto",
          my: "20%",
          p: 4,
          bgcolor: "background.paper",
          boxShadow: 24,
          borderRadius: 2,
        }}
      >
        <Typography variant="h6" gutterBottom>
          Accept Terms & Privacy
        </Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          By using Growth Quantix, you agree to our{" "}
          <a href="/terms" target="_blank" rel="noopener noreferrer">
            Terms & Conditions
          </a>{" "}
          and{" "}
          <a href="/privacy-policy" target="_blank" rel="noopener noreferrer">
            Privacy Policy
          </a>
          .
        </Typography>
        <Button variant="contained" fullWidth onClick={handleAccept}>
          I Accept
        </Button>
      </Box>
    </Modal>
  );
};

export default TermsModal;
