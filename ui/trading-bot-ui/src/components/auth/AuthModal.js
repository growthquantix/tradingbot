import React, { useState, useEffect } from "react";
import {
  Drawer,
  TextField,
  Button,
  Typography,
  Box,
  IconButton,
  Link,
  Alert,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  CircularProgress,
  useTheme,
  useMediaQuery,
  InputAdornment,
  Tabs,
  Tab,
  Collapse,
  Divider,
  Avatar,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import EmailIcon from "@mui/icons-material/Email";
import LockIcon from "@mui/icons-material/Lock";
import PersonIcon from "@mui/icons-material/Person";
import PhoneIcon from "@mui/icons-material/Phone";
import GoogleIcon from "@mui/icons-material/Google";
import { login, signup, verifyOtp } from "../../services/authService";

const countryCodes = [
  { code: "+1", country: "United States" },
  { code: "+91", country: "India" },
  { code: "+44", country: "United Kingdom" },
  { code: "+61", country: "Australia" },
  { code: "+49", country: "Germany" },
  { code: "+33", country: "France" },
];

const AuthModal = ({
  open,
  handleClose,
  onLoginSuccess,
  isLogin,
  setIsLogin,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isMedium = useMediaQuery(theme.breakpoints.down("md"));

  const [credentials, setCredentials] = useState({
    fullname: "",
    identifier: "",
    phone: "",
    countryCode: "+1",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [showOtpField, setShowOtpField] = useState(false);
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [activeTab, setActiveTab] = useState(isLogin ? 0 : 1);
  const [formValid, setFormValid] = useState(false);

  // Avatar state
  const [userInitials, setUserInitials] = useState("TB");
  const [avatarColor, setAvatarColor] = useState("#4186ff");

  // Function to generate initials from name
  const getInitials = (name) => {
    if (!name || name.trim() === "") return "TB";

    const nameParts = name.trim().split(" ");
    if (nameParts.length === 1) return nameParts[0].charAt(0).toUpperCase();
    return (
      nameParts[0].charAt(0) + nameParts[nameParts.length - 1].charAt(0)
    ).toUpperCase();
  };

  // Update initials when name changes in signup
  // Update initials and avatar color when name changes
  useEffect(() => {
    if (!isLogin && credentials.fullname) {
      const initials = getInitials(credentials.fullname);
      setUserInitials(initials);
      setAvatarColor(stringToColor(credentials.fullname)); // this is now doing something
    } else {
      setUserInitials("TB");
      setAvatarColor("#4186ff"); // fallback color
    }
  }, [isLogin, credentials.fullname]);

  const stringToColor = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    let color = "#";
    for (let i = 0; i < 3; i++) {
      const value = (hash >> (i * 8)) & 0xff;
      color += `00${value.toString(16)}`.substr(-2);
    }
    return color;
  };

  // Form validation
  useEffect(() => {
    if (isLogin) {
      setFormValid(
        credentials.identifier.includes("@") && credentials.password.length >= 6
      );
    } else {
      setFormValid(
        credentials.fullname.length >= 2 &&
          credentials.identifier.includes("@") &&
          credentials.password.length >= 6 &&
          (showOtpField || credentials.phone.length >= 5)
      );
    }
  }, [credentials, isLogin, showOtpField]);

  // Update tab when isLogin changes
  useEffect(() => {
    setActiveTab(isLogin ? 0 : 1);
  }, [isLogin]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setCredentials((prev) => ({
      ...prev,
      [name]: value,
    }));
    // Clear error when typing
    if (error) setError("");
  };

  // Handle tab changes
  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
    setIsLogin(newValue === 0);
    setError("");
  };

  const handleAuth = async () => {
    setError("");
    setLoading(true);

    try {
      let response;

      if (isLogin) {
        response = await login({
          email: credentials.identifier,
          password: credentials.password,
        });

        if (response.success || response.access_token) {
          // Store token if available
          if (response.access_token) {
            localStorage.setItem("token", response.access_token);
          }
          // If user data is available, update initials
          if (response.user && response.user.fullName) {
            setUserInitials(getInitials(response.user.fullName));
          }
          handleSuccess();
        } else {
          handleError(response.message || "Login failed");
        }
      } else {
        response = await signup({
          full_name: credentials.fullname,
          email: credentials.identifier,
          phone_number: credentials.phone,
          country_code: credentials.countryCode,
          password: credentials.password,
        });

        if (response.success || response.access_token) {
          if (response.access_token) {
            localStorage.setItem("token", response.access_token);
            handleSuccess();
          } else {
            setShowOtpField(true);
          }
        } else {
          handleError(response.message || "Signup failed");
        }
      }
    } catch (err) {
      console.error("Auth error:", err);
      handleError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleOtpVerification = async () => {
    setLoading(true);
    try {
      const response = await verifyOtp(
        credentials.phone,
        credentials.countryCode,
        otp
      );
      if (response.success) {
        handleSuccess();
      } else {
        handleError(response.message);
      }
    } catch (err) {
      handleError("Invalid OTP. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSuccess = () => {
    setShowOtpField(false);
    handleClose();
    // Reset form
    setCredentials({
      fullname: "",
      identifier: "",
      phone: "",
      countryCode: "+1",
      password: "",
      confirmPassword: "",
    });
    setOtp("");
    window.dispatchEvent(new Event("storage"));
    onLoginSuccess();
  };

  const handleError = (message) => {
    let errorMessage = "Something went wrong.";

    if (typeof message === "string") {
      errorMessage = message;
    } else if (Array.isArray(message)) {
      errorMessage = message.map((err) => err.msg).join(", ");
    } else if (typeof message === "object" && message !== null) {
      errorMessage = JSON.stringify(message);
    }

    setError(errorMessage);
  };

  return (
    <Drawer
      anchor={isMobile ? "bottom" : "right"}
      open={open}
      onClose={handleClose}
      PaperProps={{
        sx: {
          background:
            theme.palette.mode === "dark"
              ? "linear-gradient(145deg, #111827, #1f2937)"
              : "linear-gradient(145deg, #f9fafb, #f3f4f6)",
          borderRadius: isMobile ? "16px 16px 0 0" : "0",
          boxShadow: "0 10px 30px rgba(0,0,0,0.15)",
        },
      }}
    >
      <Box
        sx={{
          width: isMobile ? "100%" : isMedium ? 400 : 450,
          maxHeight: isMobile ? "92vh" : "100%",
          overflowY: "auto",
          p: isMobile ? 3 : 4,
          position: "relative",
        }}
      >
        {/* Close button */}
        <IconButton
          onClick={handleClose}
          sx={{
            position: "absolute",
            top: 16,
            right: 16,
            backgroundColor: "rgba(0, 0, 0, 0.03)",
            "&:hover": {
              backgroundColor: "rgba(0, 0, 0, 0.07)",
            },
            zIndex: 1,
          }}
        >
          <CloseIcon />
        </IconButton>

        {/* Dynamic Avatar - Shows TB or user initials */}
        <Box sx={{ display: "flex", justifyContent: "center", mb: 3 }}>
          <Avatar
            sx={{
              width: 64,
              height: 64,
              bgcolor: avatarColor,
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
              fontSize: "1.6rem",
              fontWeight: 600,
              transition: "all 0.3s ease",
            }}
          >
            {userInitials}
          </Avatar>
        </Box>

        {/* Title */}
        <Typography
          variant="h5"
          sx={{
            fontWeight: 700,
            mb: 0.5,
            textAlign: "center",
            backgroundImage: "linear-gradient(90deg, #3f8fff, #75b8ff)",
            backgroundClip: "text",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          {isLogin ? "Welcome Back" : "Create Account"}
        </Typography>

        <Typography
          variant="body2"
          sx={{ color: "text.secondary", mb: 3, textAlign: "center" }}
        >
          {isLogin
            ? "Access your trading account"
            : "Join the algorithmic trading community"}
        </Typography>

        {/* Tab Navigation */}
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          centered
          sx={{
            mb: 3,
            "& .MuiTabs-indicator": {
              height: 3,
              borderRadius: "2px",
            },
          }}
        >
          <Tab
            label="Login"
            sx={{
              fontWeight: activeTab === 0 ? 700 : 500,
              textTransform: "none",
              fontSize: "1rem",
              opacity: activeTab === 0 ? 1 : 0.7,
            }}
          />
          <Tab
            label="Sign Up"
            sx={{
              fontWeight: activeTab === 1 ? 700 : 500,
              textTransform: "none",
              fontSize: "1rem",
              opacity: activeTab === 1 ? 1 : 0.7,
            }}
          />
        </Tabs>

        {/* Error Message */}
        <Collapse in={!!error}>
          <Alert
            severity="error"
            sx={{ mb: 2, borderRadius: "8px" }}
            onClose={() => setError("")}
          >
            {error}
          </Alert>
        </Collapse>

        {!showOtpField ? (
          <>
            {/* Login Form */}
            {isLogin && (
              <Box>
                <TextField
                  fullWidth
                  label="Email Address"
                  name="identifier"
                  variant="outlined"
                  margin="normal"
                  value={credentials.identifier}
                  onChange={handleChange}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <EmailIcon fontSize="small" />
                      </InputAdornment>
                    ),
                  }}
                  sx={{
                    mb: 2,
                    "& .MuiOutlinedInput-root": { borderRadius: "10px" },
                  }}
                />

                <TextField
                  fullWidth
                  label="Password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  variant="outlined"
                  margin="normal"
                  value={credentials.password}
                  onChange={handleChange}
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
                  sx={{
                    mb: 1,
                    "& .MuiOutlinedInput-root": { borderRadius: "10px" },
                  }}
                />

                <Box
                  sx={{ display: "flex", justifyContent: "flex-end", mb: 2 }}
                >
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
                  fullWidth
                  variant="contained"
                  disabled={loading || !formValid}
                  onClick={handleAuth}
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

                {/* Google Login Button (Colorful) */}
                <Box sx={{ mt: 3, mb: 2 }}>
                  <Divider>
                    <Typography
                      variant="body2"
                      sx={{ color: "text.secondary", px: 1 }}
                    >
                      or continue with
                    </Typography>
                  </Divider>

                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "center",
                      mt: 2,
                    }}
                  >
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
              </Box>
            )}

            {/* Sign Up Form */}
            {!isLogin && (
              <Box>
                <TextField
                  fullWidth
                  label="Full Name"
                  name="fullname"
                  variant="outlined"
                  margin="normal"
                  value={credentials.fullname}
                  onChange={handleChange}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <PersonIcon fontSize="small" />
                      </InputAdornment>
                    ),
                  }}
                  sx={{
                    mb: 2,
                    "& .MuiOutlinedInput-root": { borderRadius: "10px" },
                  }}
                />

                <TextField
                  fullWidth
                  label="Email Address"
                  name="identifier"
                  variant="outlined"
                  margin="normal"
                  value={credentials.identifier}
                  onChange={handleChange}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <EmailIcon fontSize="small" />
                      </InputAdornment>
                    ),
                  }}
                  sx={{
                    mb: 2,
                    "& .MuiOutlinedInput-root": { borderRadius: "10px" },
                  }}
                />

                <Box
                  sx={{
                    display: "flex",
                    flexDirection: isMobile ? "column" : "row",
                    gap: 2,
                    mb: 2,
                  }}
                >
                  <FormControl
                    sx={{
                      minWidth: isMobile ? "100%" : 110,
                      "& .MuiOutlinedInput-root": { borderRadius: "10px" },
                    }}
                  >
                    <InputLabel>Country Code</InputLabel>
                    <Select
                      name="countryCode"
                      value={credentials.countryCode}
                      onChange={handleChange}
                      label="Country Code"
                    >
                      {countryCodes.map((country) => (
                        <MenuItem key={country.code} value={country.code}>
                          {isMobile
                            ? country.code
                            : `${country.country} (${country.code})`}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  <TextField
                    fullWidth
                    label="Phone Number"
                    name="phone"
                    variant="outlined"
                    value={credentials.phone}
                    onChange={handleChange}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <PhoneIcon fontSize="small" />
                        </InputAdornment>
                      ),
                    }}
                    sx={{
                      "& .MuiOutlinedInput-root": { borderRadius: "10px" },
                    }}
                  />
                </Box>

                <TextField
                  fullWidth
                  label="Password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  variant="outlined"
                  margin="normal"
                  value={credentials.password}
                  onChange={handleChange}
                  helperText="At least 6 characters"
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
                  sx={{
                    mb: 2,
                    "& .MuiOutlinedInput-root": { borderRadius: "10px" },
                  }}
                />

                <Button
                  fullWidth
                  variant="contained"
                  disabled={loading || !formValid}
                  onClick={handleAuth}
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

                {/* Terms and Conditions */}
                <Typography
                  variant="caption"
                  sx={{
                    display: "block",
                    textAlign: "center",
                    mt: 2,
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
              </Box>
            )}
          </>
        ) : (
          /* OTP Verification Form */
          <Box>
            <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
              Verify Phone Number
            </Typography>

            <Typography variant="body2" sx={{ mb: 3, color: "text.secondary" }}>
              We've sent a verification code to {credentials.countryCode}{" "}
              {credentials.phone}
            </Typography>

            <TextField
              fullWidth
              label="Enter Verification Code"
              name="otp"
              variant="outlined"
              value={otp}
              onChange={(e) => {
                setOtp(e.target.value);
                setError("");
              }}
              sx={{
                mb: 3,
                "& .MuiOutlinedInput-root": { borderRadius: "10px" },
              }}
            />

            <Button
              fullWidth
              variant="contained"
              disabled={loading || otp.length < 4}
              onClick={handleOtpVerification}
              sx={{
                py: 1.5,
                borderRadius: "10px",
                textTransform: "none",
                fontWeight: 600,
                fontSize: "1rem",
                background:
                  otp.length >= 4
                    ? "linear-gradient(90deg, #3f8fff, #75b8ff)"
                    : undefined,
                "&:hover": {
                  transform: otp.length >= 4 ? "translateY(-2px)" : "none",
                },
                transition: "all 0.3s ease",
              }}
            >
              {loading ? (
                <CircularProgress size={24} sx={{ color: "white" }} />
              ) : (
                "Verify & Continue"
              )}
            </Button>

            <Box sx={{ display: "flex", justifyContent: "center", mt: 3 }}>
              <Button
                variant="text"
                sx={{ textTransform: "none" }}
                disabled={loading}
              >
                Didn't receive code? Resend
              </Button>
            </Box>

            <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
              <Button
                variant="text"
                sx={{ textTransform: "none" }}
                onClick={() => {
                  setShowOtpField(false);
                  setOtp("");
                  setError("");
                }}
              >
                Go Back
              </Button>
            </Box>
          </Box>
        )}
      </Box>
    </Drawer>
  );
};

export default AuthModal;
