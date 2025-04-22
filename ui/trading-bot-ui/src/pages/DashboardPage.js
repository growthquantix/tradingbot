import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Modal,
  Button,
  Alert,
  TextField,
  useTheme,
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { useMarket } from "../context/MarketProvider";

const DashboardPage = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const navigate = useNavigate();
  const { groupedStocks, ltps, marketStatus, tokenExpired } = useMarket();
  const [processedRows, setProcessedRows] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");

  const spotStocks = useMemo(() => {
    return Object.entries(groupedStocks)
      .map(([symbol, stock]) => {
        const spot = stock?.spot;
        if (!spot?.instrument_key) return null;

        const key = spot.instrument_key.toUpperCase();
        const feed = ltps[key] || {};
        const ltp = feed.ltp ?? null;
        const cp = feed.cp ?? null;
        const ltq = feed.ltq ?? null;

        const change =
          ltp != null && cp != null && cp !== 0
            ? ((ltp - cp) / cp) * 100
            : null;

        return {
          id: key,
          symbol: spot.symbol,
          name: spot.display_name || spot.name,
          exchange: spot.exchange,
          instrument_key: key,
          ltp,
          cp,
          change,
          volume: ltq,
        };
      })
      .filter(Boolean);
  }, [groupedStocks, ltps]);

  const filteredRows = useMemo(() => {
    return spotStocks.filter(
      (s) =>
        s.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [spotStocks, searchQuery]);

  useEffect(() => {
    setProcessedRows(filteredRows);
  }, [filteredRows]);

  const handleRowClick = (params) => {
    const symbol = params.row.symbol;
    navigate(`/option-chain/${symbol}`);
  };

  const formatCell =
    (decimals = 2, suffix = "") =>
    (params) =>
      params.value != null && !isNaN(params.value)
        ? `${Number(params.value).toFixed(decimals)}${suffix}`
        : "–";

  const handleNameClick = (symbol) => {
    navigate(`/option-chain/${symbol}`);
  };

  const columns = [
    { field: "symbol", headerName: "Symbol", flex: 1 },
    {
      field: "name",
      headerName: "Name",
      flex: 1.5,
      renderCell: (params) => (
        <span
          onClick={() => handleNameClick(params.row.symbol)}
          style={{
            color: "#1976d2",
            cursor: "pointer",
            textDecoration: "underline",
          }}
        >
          {params.row.name}
        </span>
      ),
    },
    { field: "exchange", headerName: "Exchange", flex: 1 },
    {
      field: "ltp",
      headerName: "LTP",
      flex: 1,
      type: "number",
      renderCell: formatCell(2),
    },
    {
      field: "cp",
      headerName: "Close Price",
      flex: 1,
      type: "number",
      renderCell: formatCell(2),
    },
    {
      field: "change",
      headerName: "% Change",
      flex: 1,
      type: "number",
      renderCell: (params) =>
        params.value != null && !isNaN(params.value)
          ? `${params.value.toFixed(2)}%`
          : "–",
      cellClassName: (params) =>
        params?.value > 0
          ? "positive-change"
          : params?.value < 0
          ? "negative-change"
          : "",
    },
    {
      field: "volume",
      headerName: "Volume",
      flex: 1,
      type: "number",
      renderCell: (params) =>
        params.value != null && !isNaN(params.value)
          ? Number(params.value).toLocaleString("en-IN")
          : "–",
    },
  ];

  return (
    <Box sx={{ padding: 3 }}>
      <Typography
        variant="h4"
        gutterBottom
        sx={{ color: theme.palette.text.primary }}
      >
        Market Status:{" "}
        <strong
          style={{ color: marketStatus === "normal_open" ? "green" : "red" }}
        >
          {marketStatus === "normal_open"
            ? "Open"
            : marketStatus === "loading"
            ? "Loading..."
            : "Closed"}
        </strong>
      </Typography>

      {marketStatus === "closed" && (
        <Alert
          severity="info"
          sx={{
            mb: 2,
            bgcolor: isDark ? "#263238" : undefined,
            color: isDark ? "#fff" : undefined,
          }}
        >
          Market is currently closed. Live feed has been paused. You can still
          view stock data based on your last fetched snapshot.
        </Alert>
      )}

      <TextField
        fullWidth
        variant="outlined"
        size="small"
        placeholder="🔍 Search by symbol or name"
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        sx={{
          mb: 2,
          input: { color: theme.palette.text.primary },
          "& .MuiOutlinedInput-root": {
            backgroundColor: isDark ? "#1e1e1e" : "#fff",
            "& fieldset": {
              borderColor: isDark ? "#444" : "#ccc",
            },
          },
        }}
      />

      <Box
        sx={{
          height: 620,
          backgroundColor: isDark ? "#121212" : "#fff",
          color: isDark ? "#fff" : "#000",
          borderRadius: 2,
          "& .MuiDataGrid-root": {
            border: "none",
          },
          "& .MuiDataGrid-cell": {
            color: isDark ? "#fff" : "#000",
          },
          "& .MuiDataGrid-columnHeaders": {
            backgroundColor: isDark ? "#1e1e1e" : "#f5f5f5",
            color: isDark ? "#fff" : "#000",
            fontWeight: "bold",
          },
          "& .positive-change": { color: "#00C853", fontWeight: 600 },
          "& .negative-change": { color: "#EF5350", fontWeight: 600 },
        }}
      >
        <DataGrid
          rows={processedRows}
          columns={columns}
          pageSize={15}
          rowsPerPageOptions={[10, 15, 25, 50]}
          getRowId={(row) => row.id}
          onRowClick={handleRowClick}
          disableSelectionOnClick
        />
      </Box>

      <Modal open={tokenExpired} onClose={() => {}}>
        <Box
          sx={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: 400,
            p: 4,
            bgcolor: "background.paper",
            boxShadow: 24,
            borderRadius: 2,
            textAlign: "center",
          }}
        >
          <Typography variant="h6" gutterBottom>
            Token Expired
          </Typography>
          <Typography variant="body2" gutterBottom>
            Your token has expired. Please go to the <strong>Config</strong> tab
            to reauthorize and resume live data.
          </Typography>
          <Button
            variant="contained"
            fullWidth
            sx={{ mt: 2 }}
            onClick={() => (window.location.href = "/config")}
          >
            Go to Config
          </Button>
        </Box>
      </Modal>
    </Box>
  );
};

export default DashboardPage;
