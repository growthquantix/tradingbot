import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Card,
  CardContent,
  Typography,
  useTheme,
  useMediaQuery,
} from "@mui/material";

const ResponsiveTable = ({ columns, data, onRowClick }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

  // For mobile: Convert table to cards
  if (isMobile) {
    return (
      <Box sx={{ mt: 2 }}>
        {data.map((row, index) => (
          <Card
            key={index}
            sx={{
              mb: 2,
              cursor: onRowClick ? "pointer" : "default",
            }}
            onClick={() => onRowClick && onRowClick(row)}
          >
            <CardContent>
              {/* Display the first column as the card title */}
              <Typography variant="h6" gutterBottom>
                {row[columns[0].field]}
              </Typography>

              {/* Display the remaining columns as key-value pairs */}
              {columns.slice(1).map((column) => (
                <Box
                  key={column.field}
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    mb: 1,
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    {column.headerName}:
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      color: column.getValueColor
                        ? column.getValueColor(row)
                        : "inherit",
                      fontWeight: column.bold ? "bold" : "normal",
                    }}
                  >
                    {column.renderCell
                      ? column.renderCell({ row, value: row[column.field] })
                      : row[column.field]}
                  </Typography>
                </Box>
              ))}
            </CardContent>
          </Card>
        ))}
      </Box>
    );
  }

  // For tablet/desktop: Use standard table
  return (
    <TableContainer component={Paper} sx={{ mt: 2 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell key={column.field}>{column.headerName}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((row, index) => (
            <TableRow
              key={index}
              hover={!!onRowClick}
              onClick={() => onRowClick && onRowClick(row)}
              sx={{
                cursor: onRowClick ? "pointer" : "default",
              }}
            >
              {columns.map((column) => (
                <TableCell
                  key={column.field}
                  sx={{
                    color: column.getValueColor
                      ? column.getValueColor(row)
                      : "inherit",
                    fontWeight: column.bold ? "bold" : "normal",
                  }}
                >
                  {column.renderCell
                    ? column.renderCell({ row, value: row[column.field] })
                    : row[column.field]}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default ResponsiveTable;
