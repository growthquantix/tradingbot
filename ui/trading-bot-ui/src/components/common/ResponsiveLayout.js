import React from "react";
import { Box, Container, Grid, useTheme, useMediaQuery } from "@mui/material";

const ResponsiveLayout = ({
  children,
  sidebar = null,
  maxWidth = "lg",
  spacing = 3,
  sidebarWidth = 3,
  contentWidth = 9,
  sidebarPosition = "left", // or "right"
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  // On mobile, stack the sidebar and content vertically
  if (isMobile) {
    return (
      <Container maxWidth={maxWidth} sx={{ mt: 2, mb: 4 }}>
        <Grid container spacing={spacing} direction="column">
          {/* If sidebar exists and should be on top on mobile */}
          {sidebar && sidebarPosition === "left" && (
            <Grid item xs={12}>
              {sidebar}
            </Grid>
          )}

          {/* Main content */}
          <Grid item xs={12}>
            {children}
          </Grid>

          {/* If sidebar exists and should be on bottom on mobile */}
          {sidebar && sidebarPosition === "right" && (
            <Grid item xs={12}>
              {sidebar}
            </Grid>
          )}
        </Grid>
      </Container>
    );
  }

  // On desktop, use the specified layout
  return (
    <Container maxWidth={maxWidth} sx={{ mt: 2, mb: 4 }}>
      <Grid container spacing={spacing}>
        {/* Place sidebar on the left if that's the specified position */}
        {sidebar && sidebarPosition === "left" && (
          <Grid item xs={sidebarWidth}>
            {sidebar}
          </Grid>
        )}

        {/* Main content */}
        <Grid item xs={sidebar ? contentWidth : 12}>
          {children}
        </Grid>

        {/* Place sidebar on the right if that's the specified position */}
        {sidebar && sidebarPosition === "right" && (
          <Grid item xs={sidebarWidth}>
            {sidebar}
          </Grid>
        )}
      </Grid>
    </Container>
  );
};

export default ResponsiveLayout;
