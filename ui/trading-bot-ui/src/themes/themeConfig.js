import { createTheme } from "@mui/material/styles";

// Create responsive theme with breakpoints
const createResponsiveTheme = (mode) => {
  return createTheme({
    palette: {
      mode,
      primary: { main: mode === "dark" ? "#3DE1FF" : "#1E3A8A" },
      secondary: { main: "#22D3EE" },
      background: {
        default: mode === "dark" ? "#0d1117" : "#F3F4F6",
        paper: mode === "dark" ? "#161b22" : "#ffffff",
      },
      text: {
        primary: mode === "dark" ? "#E5E7EB" : "#111827",
        secondary: mode === "dark" ? "#9CA3AF" : "#6B7280",
      },
    },
    typography: {
      // Responsive typography
      h1: {
        fontSize: "2.5rem", // Default size
        "@media (min-width:600px)": {
          fontSize: "3rem", // Tablet size
        },
        "@media (min-width:900px)": {
          fontSize: "3.5rem", // Desktop size
        },
      },
      h2: {
        fontSize: "2rem",
        "@media (min-width:600px)": {
          fontSize: "2.5rem",
        },
        "@media (min-width:900px)": {
          fontSize: "3rem",
        },
      },
      h4: {
        fontSize: "1.5rem",
        "@media (min-width:600px)": {
          fontSize: "1.75rem",
        },
        "@media (min-width:900px)": {
          fontSize: "2rem",
        },
      },
      h6: {
        fontSize: "1rem",
        "@media (min-width:600px)": {
          fontSize: "1.1rem",
        },
        "@media (min-width:900px)": {
          fontSize: "1.25rem",
        },
      },
      body1: {
        fontSize: "0.875rem",
        "@media (min-width:600px)": {
          fontSize: "1rem",
        },
      },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: "none",
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            width: {
              xs: "100%",
              sm: 350,
            },
          },
        },
      },
    },
  });
};

export const lightTheme = createResponsiveTheme("light");
export const darkTheme = createResponsiveTheme("dark");
