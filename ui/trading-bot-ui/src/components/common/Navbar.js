import React, { useState, useEffect } from "react";
import {
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Box,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Badge,
  Avatar,
  Menu,
  MenuItem,
  useTheme,
  useMediaQuery,
  Divider,
  Tooltip,
  styled,
  Button,
  Container,
} from "@mui/material";
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Settings as ConfigIcon,
  BarChart as AnalyticsIcon,
  Logout as LogoutIcon,
  Person as ProfileIcon,
  Notifications as NotificationsIcon,
  Assignment as PaperTradingIcon,
  History as BacktestingIcon,
  ShowChart as TradeControlIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
} from "@mui/icons-material";
import { useNavigate, useLocation } from "react-router-dom"; // Removed unused NavLink
import ThemeToggle from "../settings/ThemeToggle";
import { isAuthenticated, logout } from "../../services/authService";
import { getUserProfile } from "../../services/userService";

// Clean, modern styled components
const ModernAppBar = styled(AppBar)(({ theme }) => ({
  backgroundColor: "rgba(13, 17, 27, 0.95)",
  backdropFilter: "blur(10px)",
  boxShadow: "none",
  borderBottom: "1px solid rgba(49, 60, 78, 0.5)",
  zIndex: theme.zIndex.drawer + 1,
}));

const Logo = styled(Typography)({
  fontWeight: 700,
  fontSize: "1.5rem",
  color: "#00E5FF",
  display: "flex",
  alignItems: "center",
  gap: "8px",
  cursor: "pointer",
});

const NavButtonContainer = styled(Box)({
  display: "flex",
  alignItems: "center",
  height: "40px",
});

const NavButton = styled(Button)(({ active }) => ({
  color: active ? "#00E5FF" : "#ffffff",
  textTransform: "none",
  fontWeight: active ? 600 : 400,
  fontSize: "0.95rem",
  padding: "6px 14px",
  borderRadius: "4px",
  marginRight: "8px",
  minWidth: "auto",
  backgroundColor: active ? "rgba(0, 229, 255, 0.1)" : "transparent",
  "&:hover": {
    backgroundColor: active
      ? "rgba(0, 229, 255, 0.15)"
      : "rgba(255, 255, 255, 0.05)",
  },
}));

const StatusBadge = styled(Box)(({ status }) => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "4px 12px",
  borderRadius: "40px",
  fontSize: "0.75rem",
  fontWeight: 600,
  letterSpacing: "0.5px",
  color: "#ffffff",
  backgroundColor: status === "open" ? "#10B981" : "#EF4444",
  "&::before": {
    content: '""',
    display: "inline-block",
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    backgroundColor: "#ffffff",
    marginRight: "6px",
    animation: status === "open" ? "pulse 2s infinite" : "none",
  },
  "@keyframes pulse": {
    "0%": {
      opacity: 0.5,
    },
    "50%": {
      opacity: 1,
    },
    "100%": {
      opacity: 0.5,
    },
  },
}));

const IconButtonClean = styled(IconButton)({
  color: "#ffffff",
  borderRadius: "4px",
  padding: "8px",
  "&:hover": {
    backgroundColor: "rgba(255, 255, 255, 0.05)",
  },
});

const Navbar = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const isTablet = useMediaQuery(theme.breakpoints.between("sm", "md"));

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const [notificationAnchorEl, setNotificationAnchorEl] = useState(null);
  const [user, setUser] = useState(null);
  const [marketStatus] = useState("closed"); // Removed unused setMarketStatus

  // Navigation items with clear labels and icons
  const navItems = [
    { name: "Dashboard", path: "/dashboard", icon: <DashboardIcon /> },
    {
      name: "Trade Control",
      path: "/trade-control",
      icon: <TradeControlIcon />,
    },
    { name: "Analysis", path: "/analysis", icon: <AnalyticsIcon /> },
    { name: "Backtesting", path: "/backtesting", icon: <BacktestingIcon /> },
    {
      name: "Paper Trading",
      path: "/papertrading",
      icon: <PaperTradingIcon />,
    },
    { name: "Config", path: "/config", icon: <ConfigIcon /> },
  ];

  // Fetch user profile
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const data = await getUserProfile();
        setUser(data);
      } catch (error) {
        console.error("Error fetching user profile:", error);
      }
    };

    if (isAuthenticated()) {
      fetchProfile();
    }

    // In a real app, you would fetch market status here
  }, []);

  const handleMenuOpen = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleNotificationOpen = (event) => {
    setNotificationAnchorEl(event.currentTarget);
  };

  const handleNotificationClose = () => {
    setNotificationAnchorEl(null);
  };

  const handleProfileClick = () => {
    navigate("/profile");
    handleMenuClose();
    setDrawerOpen(false);
  };

  const handleLogout = () => {
    logout();
    handleMenuClose();
    setDrawerOpen(false);
  };

  const handleNavigate = (path) => {
    navigate(path);
    setDrawerOpen(false);
  };

  const refreshData = () => {
    // Add data refresh logic here
    console.log("Refreshing data...");
  };

  const isActive = (path) => location.pathname === path;

  return (
    <>
      <ModernAppBar position="fixed">
        <Container maxWidth="xl" sx={{ px: { xs: 1, sm: 2 } }}>
          <Toolbar disableGutters sx={{ height: 64, px: 0 }}>
            {/* Logo with spacing */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                flexGrow: isMobile ? 1 : 0,
              }}
            >
              <Logo onClick={() => navigate("/")}>
                <TrendingUpIcon fontSize="small" />
                Growth Quantix
              </Logo>
            </Box>

            {/* Desktop Navigation - Clean and spaced */}
            {!isMobile && (
              <NavButtonContainer sx={{ mx: 4 }}>
                {navItems.map((item) => (
                  <NavButton
                    key={item.path}
                    active={isActive(item.path)}
                    onClick={() => navigate(item.path)}
                    startIcon={!isTablet && item.icon}
                  >
                    {isTablet ? null : item.name}
                    {isTablet && item.icon}
                  </NavButton>
                ))}
              </NavButtonContainer>
            )}

            {/* Action Items - Right aligned, clean */}
            <Box sx={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {/* Market Status */}
              <StatusBadge status={marketStatus}>
                {marketStatus.toUpperCase()}
              </StatusBadge>

              {/* Refresh Data */}
              <Tooltip title="Refresh Data" arrow>
                <IconButtonClean onClick={refreshData} size="small">
                  <RefreshIcon fontSize="small" />
                </IconButtonClean>
              </Tooltip>

              {/* Notifications */}
              <Tooltip title="Notifications" arrow>
                <IconButtonClean onClick={handleNotificationOpen} size="small">
                  <Badge
                    badgeContent={3}
                    color="error"
                    sx={{ "& .MuiBadge-badge": { fontWeight: "bold" } }}
                  >
                    <NotificationsIcon fontSize="small" />
                  </Badge>
                </IconButtonClean>
              </Tooltip>

              {/* Theme Toggle */}
              <ThemeToggle />

              {/* Profile */}
              <Tooltip title="Profile" arrow>
                <IconButtonClean onClick={handleMenuOpen} size="small">
                  <Avatar
                    sx={{
                      width: 32,
                      height: 32,
                      bgcolor: "#334155",
                      fontSize: "0.9rem",
                      fontWeight: "bold",
                      border: "2px solid #00E5FF",
                    }}
                  >
                    P
                  </Avatar>
                </IconButtonClean>
              </Tooltip>

              {/* Mobile menu button */}
              {isMobile && (
                <IconButtonClean onClick={() => setDrawerOpen(true)} edge="end">
                  <MenuIcon />
                </IconButtonClean>
              )}
            </Box>
          </Toolbar>
        </Container>
      </ModernAppBar>

      {/* Profile Menu - Clean design */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        PaperProps={{
          elevation: 0,
          sx: {
            mt: 1.5,
            overflow: "visible",
            filter: "drop-shadow(0px 2px 8px rgba(0,0,0,0.32))",
            backgroundColor: "#1A2233",
            border: "1px solid rgba(49, 60, 78, 0.5)",
            color: "#fff",
            "&:before": {
              content: '""',
              display: "block",
              position: "absolute",
              top: 0,
              right: 14,
              width: 10,
              height: 10,
              bgcolor: "#1A2233",
              transform: "translateY(-50%) rotate(45deg)",
              zIndex: 0,
              borderLeft: "1px solid rgba(49, 60, 78, 0.5)",
              borderTop: "1px solid rgba(49, 60, 78, 0.5)",
            },
          },
        }}
      >
        <MenuItem onClick={handleProfileClick} sx={{ py: 1.5 }}>
          <ListItemIcon>
            <ProfileIcon fontSize="small" sx={{ color: "#94A3B8" }} />
          </ListItemIcon>
          <Typography>Profile</Typography>
        </MenuItem>
        <Divider sx={{ my: 0.5, borderColor: "rgba(49, 60, 78, 0.5)" }} />
        <MenuItem onClick={handleLogout} sx={{ py: 1.5 }}>
          <ListItemIcon>
            <LogoutIcon fontSize="small" sx={{ color: "#94A3B8" }} />
          </ListItemIcon>
          <Typography>Logout</Typography>
        </MenuItem>
      </Menu>

      {/* Notifications Menu - Clean design with clear information hierarchy */}
      <Menu
        anchorEl={notificationAnchorEl}
        open={Boolean(notificationAnchorEl)}
        onClose={handleNotificationClose}
        PaperProps={{
          elevation: 0,
          sx: {
            mt: 1.5,
            width: 320,
            maxHeight: 360,
            overflowY: "auto",
            backgroundColor: "#1A2233",
            border: "1px solid rgba(49, 60, 78, 0.5)",
            color: "#fff",
            filter: "drop-shadow(0px 2px 8px rgba(0,0,0,0.32))",
          },
        }}
      >
        <Box
          sx={{
            px: 2,
            py: 1.5,
            borderBottom: "1px solid rgba(49, 60, 78, 0.5)",
          }}
        >
          <Typography variant="subtitle1" fontWeight="600">
            Notifications
          </Typography>
        </Box>

        <MenuItem sx={{ py: 1.5 }}>
          <Box>
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{ color: "#10B981", fontWeight: 600 }}
              >
                NIFTY Buy Signal
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: "rgba(255,255,255,0.5)" }}
              >
                2m ago
              </Typography>
            </Box>
            <Typography
              variant="body2"
              sx={{ color: "rgba(255,255,255,0.7)", mt: 0.5 }}
            >
              AI detected strong buy signal for NIFTY 50
            </Typography>
          </Box>
        </MenuItem>

        <MenuItem sx={{ py: 1.5 }}>
          <Box>
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{ color: "#EF4444", fontWeight: 600 }}
              >
                Stop Loss Triggered
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: "rgba(255,255,255,0.5)" }}
              >
                15m ago
              </Typography>
            </Box>
            <Typography
              variant="body2"
              sx={{ color: "rgba(255,255,255,0.7)", mt: 0.5 }}
            >
              Stop loss triggered for HDFC Bank position
            </Typography>
          </Box>
        </MenuItem>

        <Divider sx={{ my: 0.5, borderColor: "rgba(49, 60, 78, 0.5)" }} />
        <MenuItem sx={{ justifyContent: "center", py: 1.5 }}>
          <Typography sx={{ color: "#00E5FF", fontWeight: 500 }}>
            View All Notifications
          </Typography>
        </MenuItem>
      </Menu>

      {/* Mobile Navigation Drawer - Clean, modern design */}
      <Drawer
        anchor="right"
        open={drawerOpen && isMobile}
        onClose={() => setDrawerOpen(false)}
        PaperProps={{
          sx: {
            width: 280,
            backgroundColor: "#0D1627",
            backgroundImage:
              "linear-gradient(rgba(0, 229, 255, 0.03), transparent)",
          },
        }}
      >
        <Box sx={{ p: 3 }}>
          {/* Header with close button */}
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              mb: 2,
            }}
          >
            <Typography variant="subtitle1" fontWeight="600">
              Navigation
            </Typography>
            <IconButtonClean onClick={() => setDrawerOpen(false)}>
              <MenuIcon fontSize="small" />
            </IconButtonClean>
          </Box>

          {/* User profile section */}
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              py: 2,
              mb: 2,
              borderRadius: 1,
              bgcolor: "rgba(255, 255, 255, 0.03)",
            }}
          >
            <Avatar
              sx={{
                width: 60,
                height: 60,
                mb: 1,
                bgcolor: "#334155",
                fontSize: "1.2rem",
                fontWeight: "bold",
                border: "2px solid #00E5FF",
              }}
            >
              {user?.name?.charAt(0) || "P"}
            </Avatar>
            <Typography variant="subtitle1" fontWeight="bold">
              {user?.name || "User"}
            </Typography>
            <Box sx={{ mt: 1 }}>
              <StatusBadge status={marketStatus}>
                {marketStatus.toUpperCase()}
              </StatusBadge>
            </Box>
          </Box>

          <Divider sx={{ borderColor: "rgba(49, 60, 78, 0.5)", mb: 2 }} />

          {/* Navigation list */}
          <List sx={{ p: 0 }}>
            {navItems.map((item) => (
              <ListItem
                button
                key={item.path}
                onClick={() => handleNavigate(item.path)}
                selected={isActive(item.path)}
                sx={{
                  borderRadius: "4px",
                  mb: 0.5,
                  pl: 2,
                  height: "44px",
                  backgroundColor: isActive(item.path)
                    ? "rgba(0, 229, 255, 0.1)"
                    : "transparent",
                  "&:hover": {
                    backgroundColor: isActive(item.path)
                      ? "rgba(0, 229, 255, 0.15)"
                      : "rgba(255, 255, 255, 0.05)",
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    minWidth: 36,
                    color: isActive(item.path)
                      ? "#00E5FF"
                      : "rgba(255, 255, 255, 0.7)",
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.name}
                  primaryTypographyProps={{
                    fontSize: "0.95rem",
                    fontWeight: isActive(item.path) ? 600 : 400,
                    color: isActive(item.path)
                      ? "#00E5FF"
                      : "rgba(255, 255, 255, 0.9)",
                  }}
                />
              </ListItem>
            ))}
          </List>

          <Divider
            sx={{
              borderColor: "rgba(49, 60, 78, 0.5)",
              my: 2,
            }}
          />

          {/* Footer actions */}
          <List sx={{ p: 0 }}>
            <ListItem
              button
              onClick={handleProfileClick}
              sx={{
                borderRadius: "4px",
                mb: 0.5,
                pl: 2,
                height: "44px",
              }}
            >
              <ListItemIcon
                sx={{ minWidth: 36, color: "rgba(255, 255, 255, 0.7)" }}
              >
                <ProfileIcon />
              </ListItemIcon>
              <ListItemText
                primary="Profile"
                primaryTypographyProps={{
                  fontSize: "0.95rem",
                }}
              />
            </ListItem>

            <ListItem
              button
              onClick={handleLogout}
              sx={{
                borderRadius: "4px",
                mb: 0.5,
                pl: 2,
                height: "44px",
              }}
            >
              <ListItemIcon
                sx={{ minWidth: 36, color: "rgba(255, 255, 255, 0.7)" }}
              >
                <LogoutIcon />
              </ListItemIcon>
              <ListItemText
                primary="Logout"
                primaryTypographyProps={{
                  fontSize: "0.95rem",
                }}
              />
            </ListItem>
          </List>

          {/* Refresh button */}
          <Button
            fullWidth
            startIcon={<RefreshIcon />}
            onClick={refreshData}
            sx={{
              mt: 2,
              py: 1,
              backgroundColor: "rgba(0, 229, 255, 0.1)",
              color: "#00E5FF",
              textTransform: "none",
              fontWeight: 600,
              borderRadius: "4px",
              border: "1px solid rgba(0, 229, 255, 0.2)",
              "&:hover": {
                backgroundColor: "rgba(0, 229, 255, 0.2)",
              },
            }}
          >
            Refresh Market Data
          </Button>
        </Box>
      </Drawer>

      {/* Extra space to prevent content overlap */}
      <Toolbar sx={{ minHeight: "64px !important" }} />
    </>
  );
};

export default Navbar;
