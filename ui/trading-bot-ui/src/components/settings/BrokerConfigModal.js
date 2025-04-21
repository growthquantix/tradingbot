import React, { useState, useEffect } from "react";
import {
  Modal,
  Box,
  Typography,
  TextField,
  Button,
  Select,
  MenuItem,
  CircularProgress,
  IconButton,
  useTheme,
} from "@mui/material";
import { Close } from "@mui/icons-material";
import brokerAPI from "../../services/brokerAPI"; // ✅ Use API service
const BASE_URL = process.env.REACT_APP_API_URL;
const brokers = ["Zerodha", "Upstox", "Dhan", "Angel One", "Fyers"];
const fields = {
  Dhan: ["client_id", "access_token"],
  Zerodha: ["api_key", "api_secret", "request_token"],
  Upstox: ["api_key", "api_secret"],
  "Angel One": ["api_key", "api_secret", "client_code", "password"],
  Fyers: ["client_id", "secret_key"],
};

const BrokerConfigModal = ({
  open,
  onClose,
  refreshBrokers,
  existingBrokers,
}) => {
  const theme = useTheme(); // ✅ ADD THIS
  const isDark = theme.palette.mode === "dark"; // ✅ ADD THIS
  const [broker, setBroker] = useState({ broker_name: "", credentials: {} });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setError(""); // Clear errors when modal opens
  }, [open]);

  const handleChange = (field, value) => {
    setBroker((prev) => ({
      ...prev,
      credentials: { ...prev.credentials, [field]: value.trim() },
    }));
  };

  // ✅ Log existing brokers to check structure
  console.log("Existing Brokers:", existingBrokers);

  // ✅ Improved duplicate check function
  const isDuplicate = () => {
    return existingBrokers.some((existing) => {
      if (existing.broker_name !== broker.broker_name) return false;

      const requiredFields = fields[broker.broker_name] || [];

      // ✅ Extract credentials correctly from the existing broker
      const existingCredentials = existing.config || existing.credentials || {};

      return requiredFields.every(
        (field) =>
          existingCredentials[field]?.trim() ===
          broker.credentials[field]?.trim()
      );
    });
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError("");

    if (!broker.broker_name) {
      setError("Please select a broker.");
      setLoading(false);
      return;
    }

    const requiredFields = fields[broker.broker_name] || [];
    const missingFields = requiredFields.filter(
      (field) => !broker.credentials[field]
    );

    if (missingFields.length > 0) {
      setError(`Missing required fields: ${missingFields.join(", ")}`);
      setLoading(false);
      return;
    }

    if (isDuplicate()) {
      setError("This broker account already exists.");
      setLoading(false);
      return;
    }

    // ✅ Special handling for Upstox
    if (broker.broker_name === "Upstox") {
      try {
        const response = await brokerAPI.initUpstoxAuth({
          api_key: broker.credentials.api_key,
          api_secret: broker.credentials.api_secret,
          redirect_uri: `${BASE_URL}/api/broker/upstox/callback`, // Match with registered URI
        });

        const authUrl = response?.auth_url;
        if (authUrl) {
          window.open(authUrl, "_blank");
          onClose();
          return;
        }

        setError("Failed to retrieve auth URL.");
      } catch (error) {
        console.error(error);
        setError(error.response?.data?.detail || "Upstox auth failed");
      } finally {
        setLoading(false);
      }
      return;
    }

    if (broker.broker_name === "Fyers") {
      try {
        const response = await brokerAPI.initFyersAuth({
          broker: "Fyers",
          config: {
            client_id: broker.credentials.client_id,
            secret_key: broker.credentials.secret_key,
            redirect_uri: "http://127.0.0.1:8000/api/broker/fyers/callback", // ✅ Correct the redirect URI too
          },
        });

        const authUrl = response?.auth_url;
        if (authUrl) {
          window.open(authUrl, "_blank");
          onClose();
          return;
        }

        setError("Failed to retrieve Fyers auth URL.");
      } catch (error) {
        console.error(error);
        const err = error.response?.data;
        setError(
          Array.isArray(err?.detail)
            ? err.detail
            : err?.detail || "Fyers auth failed"
        );
      } finally {
        setLoading(false);
      }
      return;
    }

    try {
      await brokerAPI.addBroker(broker);
      refreshBrokers();
      onClose();
    } catch (error) {
      setError(error.response?.data?.detail || "Failed to add broker");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose}>
      <Box
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          bgcolor: isDark ? "#1e1e1e" : "#fff",
          color: isDark ? "#fff" : "#000",
          p: 4,
          borderRadius: 2,
          width: 400,
          boxShadow: 24,
        }}
      >
        <IconButton
          onClick={onClose}
          sx={{
            position: "absolute",
            top: 8,
            right: 8,
            color: isDark ? "#fff" : "#000",
          }}
        >
          <Close />
        </IconButton>

        <Typography variant="h6" gutterBottom>
          Add Broker
        </Typography>

        <Select
          fullWidth
          value={broker.broker_name}
          onChange={(e) =>
            setBroker({ broker_name: e.target.value, credentials: {} })
          }
          sx={{
            mt: 2,
            backgroundColor: isDark ? "#2c2c2c" : "#fff",
            color: isDark ? "#fff" : "#000",
          }}
        >
          {brokers.map((name) => (
            <MenuItem key={name} value={name}>
              {name}
            </MenuItem>
          ))}
        </Select>

        {fields[broker.broker_name]?.map((field) => (
          <TextField
            key={field}
            label={field}
            fullWidth
            onChange={(e) => handleChange(field, e.target.value)}
            sx={{ mt: 2 }}
            InputLabelProps={{
              style: { color: isDark ? "#ccc" : "#000" },
            }}
            InputProps={{
              sx: {
                backgroundColor: isDark ? "#2c2c2c" : "#fff",
                color: isDark ? "#fff" : "#000",
              },
            }}
          />
        ))}

        {error && (
          <Typography color="error" sx={{ mt: 1 }}>
            {error}
          </Typography>
        )}

        <Button
          variant="contained"
          fullWidth
          onClick={handleSubmit}
          disabled={loading}
          sx={{ mt: 3 }}
        >
          {loading ? (
            <CircularProgress size={20} color="inherit" />
          ) : (
            "Add Broker"
          )}
        </Button>
      </Box>
    </Modal>
  );
};

export default BrokerConfigModal;
