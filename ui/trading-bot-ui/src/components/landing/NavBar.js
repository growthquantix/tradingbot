import React, { useState } from "react";
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Button,
  Container,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemText,
  useMediaQuery,
  useTheme,
  Slide,
} from "@mui/material";
import { Menu as MenuIcon, Close as CloseIcon } from "@mui/icons-material";
import { Link as RouterLink } from "react-router-dom";

const NavBar = ({ onSignIn, onSignUp, isScrolled }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const navLinks = [
    { label: "Features", href: "#features" },
    { label: "How AI Works", href: "#how-ai-works" },
    { label: "Strategy", href: "#strategy" },
    { label: "Pricing", href: "#pricing" },
  ];

  const drawer = (
    <Box
      onClick={handleDrawerToggle}
      sx={{ textAlign: "center", p: 2, height: "100%", bgcolor: "#0A0B0E" }}
    >
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
        }}
      >
        <Typography
          variant="h6"
          component="div"
          sx={{ fontWeight: "bold", color: theme.palette.primary.main }}
        >
          GrowthQuantix
        </Typography>
        <IconButton color="inherit" onClick={handleDrawerToggle}>
          <CloseIcon />
        </IconButton>
      </Box>
      <List>
        {navLinks.map((item) => (
          <ListItem
            button
            key={item.label}
            component="a"
            href={item.href}
            sx={{
              textAlign: "center",
              py: 1.5,
              color: "white",
              "&:hover": {
                color: theme.palette.primary.main,
              },
            }}
          >
            <ListItemText primary={item.label} />
          </ListItem>
        ))}
        <ListItem button onClick={onSignIn} sx={{ mt: 2 }}>
          <Button
            fullWidth
            variant="outlined"
            color="primary"
            sx={{ borderRadius: "8px" }}
          >
            Login
          </Button>
        </ListItem>
        <ListItem button onClick={onSignUp}>
          <Button
            fullWidth
            variant="contained"
            color="primary"
            sx={{
              borderRadius: "8px",
              background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
              fontWeight: "bold",
              boxShadow: "0 4px 14px 0 rgba(0, 186, 255, 0.4)",
            }}
          >
            Sign Up Free
          </Button>
        </ListItem>
      </List>
    </Box>
  );

  return (
    <>
      <Slide appear={false} direction="down" in={!isScrolled}>
        <AppBar
          position="fixed"
          sx={{
            bgcolor: isScrolled ? "rgba(10, 11, 14, 0.85)" : "transparent",
            backdropFilter: isScrolled ? "blur(10px)" : "none",
            boxShadow: isScrolled ? "0 4px 20px rgba(0,0,0,0.1)" : "none",
            transition: "all 0.3s ease",
            borderBottom: isScrolled
              ? `1px solid rgba(0, 186, 255, 0.2)`
              : "none",
          }}
        >
          <Container maxWidth="xl">
            <Toolbar
              sx={{
                display: "flex",
                justifyContent: "space-between",
                py: isScrolled ? 1 : 1.5,
                transition: "all 0.3s ease",
              }}
            >
              <Typography
                variant="h5"
                component={RouterLink}
                to="/"
                sx={{
                  fontWeight: "bold",
                  color: theme.palette.primary.main,
                  textDecoration: "none",
                  backgroundImage: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  transition: "transform 0.3s ease",
                  "&:hover": {
                    transform: "scale(1.05)",
                  },
                }}
              >
                GrowthQuantix
              </Typography>

              {/* Desktop Navigation */}
              {!isMobile && (
                <Box sx={{ display: "flex", alignItems: "center", gap: 4 }}>
                  {navLinks.map((link) => (
                    <Button
                      key={link.label}
                      color="inherit"
                      component="a"
                      href={link.href}
                      sx={{
                        fontWeight: "medium",
                        position: "relative",
                        "&:hover": {
                          color: theme.palette.primary.main,
                          background: "transparent",
                        },
                        "&::after": {
                          content: '""',
                          position: "absolute",
                          bottom: 0,
                          left: "50%",
                          width: "0%",
                          height: "2px",
                          backgroundColor: theme.palette.primary.main,
                          transition: "all 0.3s ease",
                          transform: "translateX(-50%)",
                        },
                        "&:hover::after": {
                          width: "80%",
                        },
                      }}
                    >
                      {link.label}
                    </Button>
                  ))}

                  <Button
                    onClick={onSignIn}
                    sx={{
                      borderRadius: "8px",
                      px: 3,
                      border: `1px solid rgba(0, 186, 255, 0.3)`,
                      color: "white",
                      "&:hover": {
                        borderColor: theme.palette.primary.main,
                        backgroundColor: "rgba(0, 186, 255, 0.1)",
                      },
                    }}
                  >
                    Login
                  </Button>

                  <Button
                    onClick={onSignUp}
                    variant="contained"
                    color="primary"
                    sx={{
                      borderRadius: "8px",
                      px: 3,
                      fontWeight: "bold",
                      background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                      boxShadow: "0 4px 14px 0 rgba(0, 186, 255, 0.4)",
                      "&:hover": {
                        background: `linear-gradient(90deg, ${theme.palette.primary.dark}, ${theme.palette.secondary.dark})`,
                        boxShadow: "0 6px 20px 0 rgba(0, 186, 255, 0.6)",
                      },
                    }}
                  >
                    Sign Up Free
                  </Button>
                </Box>
              )}

              {/* Mobile Menu Button */}
              {isMobile && (
                <IconButton
                  color="inherit"
                  aria-label="open drawer"
                  edge="start"
                  onClick={handleDrawerToggle}
                >
                  <MenuIcon />
                </IconButton>
              )}
            </Toolbar>
          </Container>
        </AppBar>
      </Slide>

      {/* Mobile Navigation Drawer */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={handleDrawerToggle}
        ModalProps={{
          keepMounted: true,
        }}
        sx={{
          display: { xs: "block", md: "none" },
          "& .MuiDrawer-paper": { width: "100%" },
        }}
      >
        {drawer}
      </Drawer>
    </>
  );
};

export default NavBar;
