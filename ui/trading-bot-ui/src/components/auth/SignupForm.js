import React, { useState, useEffect } from "react";
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
  Alert,
  CircularProgress,
  LinearProgress,
  Tooltip,
  useTheme,
  useMediaQuery,
  Avatar,
  Divider,
} from "@mui/material";
import PersonIcon from "@mui/icons-material/Person";
import EmailIcon from "@mui/icons-material/Email";
import LockIcon from "@mui/icons-material/Lock";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import GoogleIcon from "@mui/icons-material/Google";
import { signup } from "../../services/authService";
import { useNavigate } from "react-router-dom";

const SignupForm = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const navigate = useNavigate();

  const [form, setForm] = useState({
    fullname: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState(0);
  const [formValid, setFormValid] = useState(false);
  const [userInitials, setUserInitials] = useState("TB");

  // Generate initials from name
  const getInitials = (name) => {
    if (!name || name.trim() === "") return "TB";

    const nameParts = name.trim().split(" ");
    if (nameParts.length === 1) return nameParts[0].charAt(0).toUpperCase();
    return (
      nameParts[0].charAt(0) + nameParts[nameParts.length - 1].charAt(0)
    ).toUpperCase();
  };

  // Update initials when name changes
  useEffect(() => {
    if (form.fullname) {
      setUserInitials(getInitials(form.fullname));
    } else {
      setUserInitials("TB");
    }
  }, [form.fullname]);

  // Password strength calculation
  useEffect(() => {
    if (!form.password) {
      setPasswordStrength(0);
      return;
    }

    let strength = 0;

    // Length check
    if (form.password.length >= 8) strength += 25;

    // Contains number
    if (/\d/.test(form.password)) strength += 25;

    // Contains lowercase
    if (/[a-z]/.test(form.password)) strength += 25;

    // Contains uppercase or special char
    if (/[A-Z]/.test(form.password) || /[^A-Za-z0-9]/.test(form.password))
      strength += 25;

    setPasswordStrength(strength);
  }, [form.password]);

  // Form validation
  useEffect(() => {
    setFormValid(
      form.fullname.length >= 2 &&
        form.email.includes("@") &&
        form.password.length >= 8 &&
        form.password === form.confirmPassword
    );
  }, [form]);

  const getPasswordStrengthColor = () => {
    if (passwordStrength < 50) return theme.palette.error.main;
    if (passwordStrength < 75) return theme.palette.warning.main;
    return theme.palette.success.main;
  };

  const getPasswordStrengthLabel = () => {
    if (passwordStrength < 50) return "Weak";
    if (passwordStrength < 75) return "Medium";
    return "Strong";
  };

  const handleSignup = async () => {
    setError("");
    setLoading(true);

    // Basic validation
    if (
      !form.fullname ||
      !form.email.includes("@") ||
      form.password.length < 8
    ) {
      setError("Please enter valid details.");
      setLoading(false);
      return;
    }

    // Password confirmation check
    if (form.password !== form.confirmPassword) {
      setError("Passwords don't match.");
      setLoading(false);
      return;
    }

    try {
      const response = await signup({
        full_name: form.fullname,
        email: form.email,
        password: form.password,
      });

      if (response.access_token) {
        localStorage.setItem("token", response.access_token);
        navigate("/dashboard");
      } else {
        setError(response.detail || "Signup failed. Try again.");
      }
    } catch (err) {
      console.error("Signup error:", err);
      setError("An error occurred during signup. Please try again.");
    } finally {
      setLoading(false);
    }
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
        {/* Dynamic Avatar */}
        <Box sx={{ display: "flex", justifyContent: "center", mb: 3 }}>
          <Avatar
            sx={{
              width: 64,
              height: 64,
              bgcolor: "#4186ff",
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
              fontSize: "1.6rem",
              fontWeight: 600,
              transition: "all 0.3s ease",
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
            Create Account
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Join our algorithmic trading platform
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
            label="Full Name"
            variant="outlined"
            fullWidth
            value={form.fullname}
            onChange={(e) => {
              setForm({ ...form, fullname: e.target.value });
              if (error) setError("");
            }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <PersonIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ "& .MuiOutlinedInput-root": { borderRadius: "10px" } }}
          />

          <TextField
            label="Email Address"
            variant="outlined"
            fullWidth
            type="email"
            value={form.email}
            onChange={(e) => {
              setForm({ ...form, email: e.target.value });
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

          <Box>
            <TextField
              label="Password"
              type={showPassword ? "text" : "password"}
              variant="outlined"
              fullWidth
              value={form.password}
              onChange={(e) => {
                setForm({ ...form, password: e.target.value });
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

            {form.password && (
              <Box sx={{ mt: 1 }}>
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    mb: 0.5,
                  }}
                >
                  <Typography variant="caption" color="text.secondary">
                    Password Strength
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      color: getPasswordStrengthColor(),
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      gap: 0.5,
                    }}
                  >
                    {getPasswordStrengthLabel()}
                    {passwordStrength >= 75 && (
                      <CheckCircleIcon fontSize="inherit" />
                    )}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={passwordStrength}
                  sx={{
                    height: 6,
                    borderRadius: 3,
                    backgroundColor:
                      theme.palette.mode === "dark"
                        ? "rgba(255,255,255,0.1)"
                        : "rgba(0,0,0,0.05)",
                    "& .MuiLinearProgress-bar": {
                      backgroundColor: getPasswordStrengthColor(),
                    },
                  }}
                />

                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1 }}>
                  <PasswordRequirement
                    label="8+ characters"
                    met={form.password.length >= 8}
                  />
                  <PasswordRequirement
                    label="Numbers"
                    met={/\d/.test(form.password)}
                  />
                  <PasswordRequirement
                    label="Letters"
                    met={/[a-zA-Z]/.test(form.password)}
                  />
                </Box>
              </Box>
            )}
          </Box>

          <TextField
            label="Confirm Password"
            type={showConfirmPassword ? "text" : "password"}
            variant="outlined"
            fullWidth
            value={form.confirmPassword}
            onChange={(e) => {
              setForm({ ...form, confirmPassword: e.target.value });
              if (error) setError("");
            }}
            error={
              form.confirmPassword !== "" &&
              form.password !== form.confirmPassword
            }
            helperText={
              form.confirmPassword !== "" &&
              form.password !== form.confirmPassword
                ? "Passwords don't match"
                : ""
            }
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <LockIcon fontSize="small" />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    edge="end"
                  >
                    {showConfirmPassword ? (
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

          <Button
            variant="contained"
            color="primary"
            onClick={handleSignup}
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
              "Create Account"
            )}
          </Button>
        </Box>

        {/* Google Sign Up Button */}
        <Box sx={{ mt: 4, mb: 2 }}>
          <Divider>
            <Typography variant="body2" sx={{ color: "text.secondary", px: 1 }}>
              or sign up with
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

        {/* Terms and Conditions */}
        <Typography
          variant="caption"
          sx={{
            display: "block",
            textAlign: "center",
            mt: 3,
            color: "text.secondary",
          }}
        >
          By signing up, you agree to our{" "}
          <Link href="#" sx={{ fontWeight: 500 }}>
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link href="#" sx={{ fontWeight: 500 }}>
            Privacy Policy
          </Link>
        </Typography>

        <Typography
          variant="body2"
          sx={{ textAlign: "center", mt: 3, color: "text.secondary" }}
        >
          Already have an account?{" "}
          <Link
            href="/login"
            sx={{
              fontWeight: 600,
              color: "primary.main",
              textDecoration: "none",
              "&:hover": { textDecoration: "underline" },
            }}
          >
            Log in
          </Link>
        </Typography>
      </Paper>
    </Container>
  );
};

// Helper component for password requirements
const PasswordRequirement = ({ label, met }) => {
  return (
    <Tooltip title={met ? "Requirement met" : "Requirement not met"}>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 0.5,
          fontSize: "0.75rem",
          color: met ? "success.main" : "text.secondary",
          backgroundColor: met
            ? "rgba(46, 125, 50, 0.1)"
            : "rgba(0, 0, 0, 0.05)",
          borderRadius: "4px",
          px: 1,
          py: 0.5,
        }}
      >
        {met ? (
          <CheckCircleIcon fontSize="inherit" />
        ) : (
          <ErrorIcon fontSize="inherit" />
        )}
        {label}
      </Box>
    </Tooltip>
  );
};

export default SignupForm;
