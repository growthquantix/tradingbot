// src/pages/PrivacyPolicyPage.jsx
import { Box, Typography, Container } from "@mui/material";

const PrivacyPolicyPage = () => {
  return (
    <Box sx={{ py: 10, px: 2 }}>
      <Container maxWidth="md">
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Privacy Policy
        </Typography>

        <Typography variant="body1" sx={{ mb: 2 }}>
          Growth Quantix is committed to protecting your personal information.
          This policy explains how we collect, use, and safeguard your data.
        </Typography>

        <ul>
          <li>
            <Typography variant="body2">
              We collect only essential user data such as email, broker
              credentials, and usage patterns.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              Your broker credentials are stored securely and used only to fetch
              market data or place trades on your behalf.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              We do not share or sell your personal data with third parties.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              All data is encrypted in transit and at rest.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              You can request account deletion by emailing:{" "}
              <a href="mailto:support@growthquantix.com">
                support@growthquantix.com
              </a>
              .
            </Typography>
          </li>
        </ul>

        <Typography variant="body1" sx={{ mt: 2 }}>
          For questions or concerns, contact{" "}
          <a href="mailto:privacy@growthquantix.com">
            privacy@growthquantix.com
          </a>
          .
        </Typography>
      </Container>
    </Box>
  );
};

export default PrivacyPolicyPage;
