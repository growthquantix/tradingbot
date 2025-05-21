import React, { useState } from "react";
import {
  TextField,
  Button,
  Container,
  Typography,
  Box,
  Paper,
  InputAdornment,
  IconButton,
  Link,
  Divider,
  CircularProgress,
  Alert,
  useMediaQuery,
  useTheme,
  Avatar,
} from "@mui/material";
import EmailIcon from "@mui/icons-material/Email";
import LockIcon from "@mui/icons-material/Lock";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import GoogleIcon from "@mui/icons-material/Google";
import { loginUser } from "../../services/authService";

const LoginForm = ({ onLogin }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

  const [credentials, setCredentials] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formValid, setFormValid] = useState(false);
  const [userInitials, setUserInitials] = useState("TB");

  // Validate form
  React.useEffect(() => {
    setFormValid(
      credentials.email.includes("@") && credentials.password.length >= 6
    );
  }, [credentials]);

  const handleLogin = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await loginUser(credentials);
      if (response.success || response.access_token) {
        if (response.access_token) {
          localStorage.setItem("token", response.access_token);
        }
        // If user data is included, update avatar
        if (response.user && response.user.fullName) {
          const initials = getInitials(response.user.fullName);
          setUserInitials(initials);
        }
        onLogin(response.user);
      } else {
        setError(response.message || response.detail || "Login failed");
      }
    } catch (err) {
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Function to generate initials
  const getInitials = (name) => {
    if (!name || name.trim() === "") return "TB";

    const nameParts = name.trim().split(" ");
    if (nameParts.length === 1) return nameParts[0].charAt(0).toUpperCase();
    return (
      nameParts[0].charAt(0) + nameParts[nameParts.length - 1].charAt(0)
    ).toUpperCase();
  };

  return (
    <Container maxWidth="sm">
      <Paper
        elevation={3}
        sx={{
          p: 4,
          mt: isMobile ? 4 : 8,
          borderRadius: "16px",
          background:
            theme.palette.mode === "dark"
              ? "linear-gradient(145deg, #111827, #1f2937)"
              : "linear-gradient(145deg, #f9fafb, #f3f4f6)",
        }}
      >
        {/* Avatar */}
        <Box sx={{ display: "flex", justifyContent: "center", mb: 3 }}>
          <Avatar
            sx={{
              width: 64,
              height: 64,
              bgcolor: "#4186ff",
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
              fontSize: "1.6rem",
              fontWeight: 600,
            }}
          >
            {userInitials}
          </Avatar>
        </Box>

        <Box sx={{ textAlign: "center", mb: 4 }}>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              backgroundImage: "linear-gradient(90deg, #3f8fff, #75b8ff)",
              backgroundClip: "text",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              mb: 1,
            }}
          >
            Welcome Back
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Sign in to access your trading dashboard
          </Typography>
        </Box>

        {error && (
          <Alert
            severity="error"
            sx={{ mb: 3, borderRadius: "8px" }}
            onClose={() => setError("")}
          >
            {error}
          </Alert>
        )}

        <Box display="flex" flexDirection="column" gap={3}>
          <TextField
            label="Email Address"
            variant="outlined"
            fullWidth
            value={credentials.email}
            onChange={(e) => {
              setCredentials({ ...credentials, email: e.target.value });
              if (error) setError("");
            }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <EmailIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ "& .MuiOutlinedInput-root": { borderRadius: "10px" } }}
          />

          <TextField
            label="Password"
            type={showPassword ? "text" : "password"}
            variant="outlined"
            fullWidth
            value={credentials.password}
            onChange={(e) => {
              setCredentials({ ...credentials, password: e.target.value });
              if (error) setError("");
            }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <LockIcon fontSize="small" />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowPassword(!showPassword)}
                    edge="end"
                  >
                    {showPassword ? (
                      <VisibilityOffIcon fontSize="small" />
                    ) : (
                      <VisibilityIcon fontSize="small" />
                    )}
                  </IconButton>
                </InputAdornment>
              ),
            }}
            sx={{ "& .MuiOutlinedInput-root": { borderRadius: "10px" } }}
          />

          <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
            <Link
              component="button"
              variant="body2"
              onClick={() => console.log("Forgot password clicked")}
              sx={{
                color: "primary.main",
                textDecoration: "none",
                "&:hover": { textDecoration: "underline" },
              }}
            >
              Forgot password?
            </Link>
          </Box>

          <Button
            variant="contained"
            color="primary"
            onClick={handleLogin}
            disabled={loading || !formValid}
            sx={{
              py: 1.5,
              borderRadius: "10px",
              textTransform: "none",
              fontWeight: 600,
              fontSize: "1rem",
              background: formValid
                ? "linear-gradient(90deg, #3f8fff, #75b8ff)"
                : undefined,
              boxShadow: formValid
                ? "0 4px 12px rgba(63, 143, 255, 0.25)"
                : "none",
              "&:hover": {
                background: formValid
                  ? "linear-gradient(90deg, #3080f0, #6aadff)"
                  : undefined,
                boxShadow: formValid
                  ? "0 6px 16px rgba(63, 143, 255, 0.3)"
                  : "none",
                transform: formValid ? "translateY(-2px)" : "none",
              },
              transition: "all 0.3s ease",
            }}
          >
            {loading ? (
              <CircularProgress size={24} sx={{ color: "white" }} />
            ) : (
              "Login"
            )}
          </Button>
        </Box>

        <Box sx={{ mt: 4, mb: 2 }}>
          <Divider>
            <Typography variant="body2" sx={{ color: "text.secondary", px: 1 }}>
              or continue with
            </Typography>
          </Divider>

          <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
            <Button
              startIcon={<GoogleIcon />}
              variant="outlined"
              sx={{
                px: 3,
                py: 1,
                borderRadius: "8px",
                borderColor: "#ddd",
                color: "#444",
                textTransform: "none",
                fontWeight: 500,
                backgroundColor: "white",
                "&:hover": {
                  backgroundColor: "#f5f5f5",
                  borderColor: "#ccc",
                  boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
                },
              }}
            >
              Google
            </Button>
          </Box>
        </Box>

        <Typography
          variant="body2"
          sx={{ textAlign: "center", mt: 3, color: "text.secondary" }}
        >
          Don't have an account?{" "}
          <Link
            href="/signup"
            sx={{
              fontWeight: 600,
              color: "primary.main",
              textDecoration: "none",
              "&:hover": { textDecoration: "underline" },
            }}
          >
            Sign up
          </Link>
        </Typography>
      </Paper>
    </Container>
  );
};

export default LoginForm;
