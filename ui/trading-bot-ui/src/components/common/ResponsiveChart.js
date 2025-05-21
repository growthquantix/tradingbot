import React, { useEffect, useRef, useState } from "react";
import { Box, Typography, useTheme, useMediaQuery, Paper } from "@mui/material";
import { createChart } from "lightweight-charts";

const ResponsiveChart = ({ data, title, type = "candlestick" }) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isTablet = useMediaQuery(theme.breakpoints.between("sm", "md"));

  // We use state to trigger re-render on window resize
  const [containerWidth, setContainerWidth] = useState(0);

  // Handle initial chart creation
  useEffect(() => {
    if (!chartContainerRef.current || !data?.length) return;

    // Clean up previous chart if it exists
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    // Set width based on container
    const width = chartContainerRef.current.clientWidth;
    setContainerWidth(width);

    // Adjust height based on screen size
    const height = isMobile ? 250 : isTablet ? 300 : 400;

    // Create chart with responsive dimensions
    const chart = createChart(chartContainerRef.current, {
      width,
      height,
      layout: {
        background: { color: theme.palette.background.paper },
        textColor: theme.palette.text.primary,
      },
      grid: {
        vertLines: { color: theme.palette.divider },
        horzLines: { color: theme.palette.divider },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // Add series based on type
    let series;
    if (type === "candlestick") {
      series = chart.addCandlestickSeries({
        upColor: "#26a69a",
        downColor: "#ef5350",
        borderVisible: false,
        wickUpColor: "#26a69a",
        wickDownColor: "#ef5350",
      });
    } else if (type === "area") {
      series = chart.addAreaSeries({
        topColor: "rgba(33, 150, 243, 0.56)",
        bottomColor: "rgba(33, 150, 243, 0.04)",
        lineColor: "rgba(33, 150, 243, 1)",
        lineWidth: 2,
      });
    } else if (type === "line") {
      series = chart.addLineSeries({
        color: "#2196F3",
        lineWidth: 2,
      });
    }

    // Set data
    series.setData(data);

    // Make chart fit content
    chart.timeScale().fitContent();

    // Handle resize event for responsiveness
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        const newWidth = chartContainerRef.current.clientWidth;
        const newHeight = isMobile ? 250 : isTablet ? 300 : 400;
        chartRef.current.resize(newWidth, newHeight);
        setContainerWidth(newWidth);
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [data, isMobile, isTablet, theme.palette, type]);

  return (
    <Paper elevation={2} sx={{ p: isMobile ? 1 : 2, mb: 3 }}>
      <Typography
        variant="h6"
        gutterBottom
        sx={{ fontSize: isMobile ? "1rem" : "1.25rem" }}
      >
        {title || "Chart"}
      </Typography>

      <Box
        ref={chartContainerRef}
        sx={{
          width: "100%",
          height: isMobile ? 250 : isTablet ? 300 : 400,
        }}
      />

      {isMobile && (
        <Typography
          variant="caption"
          sx={{ display: "block", textAlign: "center", mt: 1 }}
        >
          Rotate your device for a better view
        </Typography>
      )}
    </Paper>
  );
};

export default ResponsiveChart;
