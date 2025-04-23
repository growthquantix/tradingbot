import { Box, Typography, Container } from "@mui/material";

const TermsPage = () => {
  return (
    <Box sx={{ py: 10, px: 2 }}>
      <Container maxWidth="md">
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Terms & Conditions
        </Typography>

        <Typography variant="body1" sx={{ mb: 2 }}>
          By accessing or using <strong>Growth Quantix</strong>, you agree to
          the following terms and usage policies. These include but are not
          limited to:
        </Typography>

        <ul>
          <li>
            <Typography variant="body2">
              Users must not engage in manipulative, illegal, or prohibited
              trading activities.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              Growth Quantix does not guarantee profits. We are not liable for
              any trading losses, latency issues, or market fluctuations.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              Violations of policies may result in restricted access or
              termination of services.
            </Typography>
          </li>
        </ul>

        <Typography variant="h6" fontWeight="bold" sx={{ mt: 4 }}>
          Market Data Usage
        </Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          Market data is shown only to authorized users with a valid linked
          broker account. We do not redistribute or resell raw market data. All
          data is intended solely for personal use and real-time decision-making
          within the platform. External API access or scraping of data is
          prohibited without license.
        </Typography>

        <Typography variant="h6" fontWeight="bold" sx={{ mt: 4 }}>
          AI-Powered Strategy & Decision Support
        </Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          Growth Quantix uses AI models to assist in generating trade signals,
          analyzing stock performance, and improving decision-making. However,
          users must verify all signals independently. A human override is
          always available and required before live trade execution. AI
          strategies are continuously evolving and may not guarantee accurate or
          profitable outcomes.
        </Typography>

        <Typography variant="h6" fontWeight="bold" sx={{ mt: 4 }}>
          Regulatory Compliance
        </Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          This platform complies with SEBI guidelines for automated decision
          support systems. All automated models log predictions and
          recommendations. Final trade execution must be approved by the user.
          For any institutional use, regulatory approvals and licensing are the
          sole responsibility of the user.
        </Typography>

        <Typography variant="h6" fontWeight="bold" sx={{ mt: 4 }}>
          Contact
        </Typography>
        <Typography variant="body2">
          For full compliance documents, data licensing details, or legal
          concerns, please contact <strong>legal@growthquantix.com</strong>.
        </Typography>
      </Container>
    </Box>
  );
};

export default TermsPage;
