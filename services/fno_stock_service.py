#!/usr/bin/env python3
"""
FnoStockListService + SimpleDhanScraper combined module.

- SimpleDhanScraper: proven, working scraper (returns pandas.DataFrame)
- FnoStockListService: enhanced service that uses SimpleDhanScraper as a reliable fallback/adapter
"""

import json
import logging
import re
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import List, Dict, Optional, Any

import pandas as pd
import pytz
import requests
from bs4 import BeautifulSoup

# Optional sector mapping import (fallback)
try:
    from services.sector_mapping import SYMBOL_TO_SECTOR, get_sector_for_stock
except Exception:
    SYMBOL_TO_SECTOR = {}

    def get_sector_for_stock(symbol):
        return None


# ---- Logging setup ----
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# -------------------------
# Working SimpleDhanScraper
# -------------------------
class SimpleDhanScraper:
    """
    Simple scraper for name and symbol only (proven working).
    Returns a pandas.DataFrame with columns ['name', 'symbol'].
    """

    def __init__(self):
        self.base_url = "https://dhan.co"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Connection": "keep-alive",
            }
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_fno_stocks(self) -> pd.DataFrame:
        self.logger.info("🎯 Getting F&O stocks (name and symbol only)...")
        all_stocks = []

        futures_stocks = self._get_futures_pagination()
        if futures_stocks:
            all_stocks.extend(futures_stocks)
            self.logger.info(f"✅ Futures: {len(futures_stocks)} stocks")

        lot_size_stocks = self._get_fno_lot_size()
        if lot_size_stocks:
            all_stocks.extend(lot_size_stocks)
            self.logger.info(f"✅ Lot size: {len(lot_size_stocks)} stocks")

        options_stocks = self._get_options_pagination()
        if options_stocks:
            all_stocks.extend(options_stocks)
            self.logger.info(f"✅ Options: {len(options_stocks)} stocks")

        unique_stocks = self._deduplicate_stocks(all_stocks)
        self.logger.info(f"📊 Total unique stocks: {len(unique_stocks)}")

        df = self._create_dataframe(unique_stocks)
        return df

    def _get_futures_pagination(self) -> list:
        all_stocks = []
        page = 1
        while page <= 10:
            try:
                url = f"{self.base_url}/futures-stocks-list/?page={page}"
                response = self.session.get(url, timeout=30)
                if response.status_code != 200:
                    break
                page_stocks = self._parse_html_page(response.text)
                if not page_stocks:
                    break
                all_stocks.extend(page_stocks)
                page += 1
                time.sleep(0.5)
            except Exception as e:
                self.logger.error(f"Futures page {page} failed: {e}")
                break
        return all_stocks

    def _get_fno_lot_size(self) -> list:
        try:
            url = f"{self.base_url}/nse-fno-lot-size/"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return self._parse_html_page(response.text)
        except Exception as e:
            self.logger.error(f"F&O lot size failed: {e}")
            return []

    def _get_options_pagination(self) -> list:
        all_stocks = []
        page = 1
        while page <= 10:
            try:
                url = f"{self.base_url}/options-stocks-list/?page={page}"
                response = self.session.get(url, timeout=30)
                if response.status_code != 200:
                    break
                page_stocks = self._parse_html_page(response.text)
                if not page_stocks:
                    break
                all_stocks.extend(page_stocks)
                page += 1
                time.sleep(0.5)
            except Exception as e:
                self.logger.error(f"Options page {page} failed: {e}")
                break
        return all_stocks

    def _parse_html_page(self, html_content: str) -> list:
        soup = BeautifulSoup(html_content, "html.parser")
        stocks = []
        rows = (
            soup.select("table tbody tr")
            or soup.select("tbody tr")
            or soup.select("tr")
        )
        for row in rows:
            try:
                if self._is_header_row(row):
                    continue
                stock = self._extract_name_symbol(row)
                if stock and self._is_valid_stock(stock):
                    stocks.append(stock)
            except Exception:
                continue
        return stocks

    def _extract_name_symbol(self, row) -> dict:
        try:
            cells = row.find_all(["td", "th"])
            if len(cells) < 1:
                return None
            name_text = cells[0].get_text(strip=True)
            name = self._clean_name(name_text)
            symbol = self._extract_symbol(row, cells[0])
            return {"name": name, "symbol": symbol if symbol else ""}
        except Exception:
            return None

    def _clean_name(self, name_text: str) -> str:
        if not name_text:
            return ""
        cleaned = name_text.strip()
        if len(cleaned) > 1 and cleaned[0] == cleaned[1] and cleaned[0].isupper():
            cleaned = cleaned[1:]
        cleaned = re.sub(
            r"\s*(Invest|Buy|Sell|Limited|Ltd\.?)\s*$", "", cleaned, flags=re.IGNORECASE
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _extract_symbol(self, row, name_cell) -> str:
        img = name_cell.find("img")
        if img:
            if img.get("alt"):
                match = re.search(r"\b([A-Z]{2,12})\b", img["alt"])
                if match:
                    return match.group(1)
            if img.get("src"):
                match = re.search(r"/symbol/([A-Z]+)\.png", img["src"], re.IGNORECASE)
                if match:
                    return match.group(1).upper()
        for attr in ["data-symbol", "data-stock"]:
            if name_cell.get(attr):
                symbol = name_cell[attr].strip().upper()
                if re.match(r"^[A-Z]{2,12}$", symbol):
                    return symbol
        text = name_cell.get_text()
        match = re.search(r"\(([A-Z]{2,12})\)", text)
        if match:
            return match.group(1)
        return ""

    def _is_header_row(self, row) -> bool:
        text = row.get_text().lower()
        return any(term in text for term in ["name", "symbol", "ltp", "lot size"])

    def _is_valid_stock(self, stock: dict) -> bool:
        name = stock.get("name", "").strip()
        if not name or len(name) < 3:
            return False
        invalid_terms = ["total", "showing", "results", "download"]
        if any(term in name.lower() for term in invalid_terms):
            return False
        return True

    def _deduplicate_stocks(self, all_stocks: list) -> list:
        if not all_stocks:
            return []
        seen = {}
        unique_stocks = []
        for stock in all_stocks:
            name = stock.get("name", "").strip()
            symbol = stock.get("symbol", "").strip().upper()
            if not self._is_valid_stock(stock):
                continue
            if symbol and len(symbol) >= 2:
                identifier = f"SYM:{symbol}"
            else:
                clean_name = re.sub(r"[^\w\s]", "", name.lower())
                clean_name = re.sub(r"\s+", "_", clean_name.strip())
                identifier = f"NAME:{clean_name}"
            if identifier not in seen:
                seen[identifier] = stock
                unique_stocks.append(stock)
            else:
                existing = seen[identifier]
                if not existing.get("symbol") and stock.get("symbol"):
                    existing["symbol"] = stock.get("symbol")
        return unique_stocks

    def _create_dataframe(self, stocks: list) -> pd.DataFrame:
        data = []
        for stock in stocks:
            data.append(
                {"name": stock.get("name", ""), "symbol": stock.get("symbol", "")}
            )
        df = pd.DataFrame(data)
        if "name" not in df.columns:
            df["name"] = ""
        if "symbol" not in df.columns:
            df["symbol"] = ""
        df = df[["name", "symbol"]]
        return df

    def save_csv(self, df: pd.DataFrame, filename: str = None) -> str:
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dhan_fno_name_symbol_{timestamp}.csv"
        df.to_csv(filename, index=False)
        self.logger.info(f"💾 Data saved to: {filename}")
        return filename


# --------------------------------
# FnoStockListService (enhanced)
# --------------------------------
class FnoStockListService:
    """
    Enhanced F&O stock list service that uses SimpleDhanScraper as reliable fallback.
    """

    def __init__(self):
        self.base_url = "https://dhan.co"
        self.ist = pytz.timezone("Asia/Kolkata")
        self.market_hours = {
            "early_start": dt_time(8, 0),
            "premarket": dt_time(9, 0),
            "market_open": dt_time(9, 15),
            "market_close": dt_time(15, 30),
        }
        self.json_file_path = Path("data/fno_stock_list.json")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Connection": "keep-alive",
            }
        )
        self.missing_symbols_map = {
            "Mahindra & Mahindra": "M&M",
            "Bajaj Auto": "BAJAJ-AUTO",
            "M&M Financial Services": "M&MFIN",
            "Nifty Bank": "BANKNIFTY",
            "Finnifty": "FINNIFTY",
            "Nifty Midcap Select": "MIDCPNIFTY",
            "Nifty 50": "NIFTY",
            "Nifty Next 50": "NIFTY-NEXT50",
            "360 One WAM": "360ONE",
            "3360 One WAM": "360ONE",
            "60 One WAM": "360ONE",
        }
        self.preferred_symbols = {
            "HDFC Bank": "HDFCBANK",
            "ICICI Bank": "ICICIBANK",
            "LIC of India": "LICI",
            "HCL Technologies": "HCLTECH",
            "Adani Ports & SEZ": "ADANIPORTS",
            "JSW Steel": "JSWSTEEL",
            "SBI Life Insurance": "SBILIFE",
        }
        self.actual_indices = {
            "NIFTY",
            "BANKNIFTY",
            "FINNIFTY",
            "MIDCPNIFTY",
            "NIFTY-NEXT50",
        }
        self.extracted_data_path = Path("dhan_nse_fno_extracted.json")
        self.last_update_time = None
        self.update_required_hours = [8, 9]

    def is_market_schedule_compliant(self) -> Dict[str, Any]:
        try:
            current_time = datetime.now(self.ist)
            current_dt_time = current_time.time()
            current_hour = current_time.hour
            current_day = current_time.day
            current_weekday = current_time.weekday()
            
            if current_time.weekday() >= 5:
                return {
                    "compliant": False,
                    "reason": "weekend",
                    "message": "Market closed - Weekend",
                    "next_update_time": "First Monday of next month 08:00 AM",
                }
            
            # Check if it's first Monday of the month for monthly refresh
            is_first_monday = current_weekday == 0 and 1 <= current_day <= 7
            
            if is_first_monday and current_hour in self.update_required_hours:
                return {
                    "compliant": True,
                    "reason": "monthly_update_window",
                    "message": f"First Monday monthly update window: {current_hour}:00",
                    "current_time": current_time.strftime("%H:%M:%S"),
                }
            
            if self.json_file_path.exists():
                file_mtime = datetime.fromtimestamp(
                    self.json_file_path.stat().st_mtime, tz=self.ist
                )
                days_old = (current_time - file_mtime).total_seconds() / 86400  # Convert to days
                
                # Only refresh if data is older than 30 days (monthly cycle)
                if days_old > 30:
                    return {
                        "compliant": True,
                        "reason": "monthly_stale_data",
                        "message": f"Data is {days_old:.1f} days old, monthly refresh needed",
                        "last_update": file_mtime.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                else:
                    return {
                        "compliant": False,
                        "reason": "data_fresh",
                        "message": f"Data is only {days_old:.1f} days old, monthly refresh not needed",
                        "next_update_time": "First Monday of next month",
                    }
            if (
                self.market_hours["market_open"]
                <= current_dt_time
                <= self.market_hours["market_close"]
            ):
                return {
                    "compliant": False,
                    "reason": "market_hours",
                    "message": "Market is open - avoiding updates during trading hours",
                    "next_update_time": "First Monday of next month 08:00 AM",
                }
            
            # Default: No refresh needed unless it's first Monday
            return {
                "compliant": False,
                "reason": "monthly_schedule",
                "message": "FNO data updates only on first Monday of each month",
                "next_update_time": "First Monday of next month 08:00 AM",
            }
        except Exception as e:
            logger.error(f"Market schedule compliance check failed: {e}")
            return {
                "compliant": True,
                "reason": "error_fallback",
                "message": f"Compliance check error: {e}",
            }

    # ----------------------------
    # Adapter: use SimpleDhanScraper
    # ----------------------------
    def _use_simple_dhan_scraper(self) -> List[Dict[str, str]]:
        """
        Run the proven SimpleDhanScraper and convert its DataFrame output
        to a list of dicts that match the service format.
        """
        try:
            scraper = SimpleDhanScraper()
            df = scraper.get_fno_stocks()  # returns pd.DataFrame
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                logger.info("SimpleDhanScraper returned no data")
                return []
            result = []
            for _, row in df.iterrows():
                name = (row.get("name") or "").strip()
                symbol = (row.get("symbol") or "").strip().upper()
                if name and symbol and self._is_valid_symbol(symbol):
                    result.append({"name": name, "symbol": symbol, "exchange": "NSE"})
                elif name:
                    result.append({"name": name, "symbol": "", "exchange": "NSE"})
            logger.info(f"✅ SimpleDhanScraper adapter returned {len(result)} records")
            return result
        except Exception as e:
            logger.exception(f"SimpleDhanScraper adapter failed: {e}")
            return []

    # ----------------------------
    # Main fetching pipeline
    # ----------------------------
    def get_fno_stocks(self) -> List[Dict[str, str]]:
        compliance_check = self.is_market_schedule_compliant()
        if not compliance_check["compliant"]:
            logger.info(f"⏰ Market schedule check: {compliance_check['message']}")
            existing_data = self.load_from_json()
            if existing_data:
                logger.info(f"📂 Using existing FNO data: {len(existing_data)} stocks")
                return existing_data
            else:
                logger.warning(
                    "No existing data available, proceeding with update despite schedule"
                )
        else:
            logger.info(f"✅ Market schedule compliant: {compliance_check['message']}")

        logger.info("🎯 Starting F&O stocks collection...")
        self.last_update_time = datetime.now(self.ist)
        all_stocks = []
        methods_used = []

        # Method 0: extracted data
        extracted_stocks = self._get_extracted_dhan_data()
        if extracted_stocks:
            all_stocks.extend(extracted_stocks)
            methods_used.append(f"ExtractedData({len(extracted_stocks)})")
            logger.info(
                f"✅ Using extracted data as primary source: {len(extracted_stocks)} stocks"
            )
        else:
            logger.info("⚠️ No extracted data found, will use other sources")

        # Method 0.5: proven SimpleDhanScraper (high priority)
        if len(all_stocks) < 200:
            simple_list = self._use_simple_dhan_scraper()
            if simple_list:
                all_stocks.extend(simple_list)
                methods_used.append(f"SimpleScraper({len(simple_list)})")

        # Method 1: CSV download
        if len(all_stocks) < 200:
            csv_stocks = self._get_fno_from_csv()
            if csv_stocks:
                all_stocks.extend(csv_stocks)
                methods_used.append(f"CSV({len(csv_stocks)})")
                logger.info(f"✅ CSV download: {len(csv_stocks)} stocks")

        # Method 2: futures pagination (basic)
        if len(all_stocks) < 200:
            futures_stocks = self._get_futures_pagination()
            if futures_stocks:
                all_stocks.extend(futures_stocks)
                methods_used.append(f"Futures({len(futures_stocks)})")
                logger.info(f"✅ Futures pagination: {len(futures_stocks)} stocks")

        # Method 3: options pagination
        if len(all_stocks) < 200:
            options_stocks = self._get_options_pagination()
            if options_stocks:
                all_stocks.extend(options_stocks)
                methods_used.append(f"Options({len(options_stocks)})")
                logger.info(f"✅ Options pagination: {len(options_stocks)} stocks")

        # Method 4: lot size page
        if len(all_stocks) < 200:
            lot_size_stocks = self._get_fno_lot_size()
            if lot_size_stocks:
                all_stocks.extend(lot_size_stocks)
                methods_used.append(f"LotSize({len(lot_size_stocks)})")
                logger.info(f"✅ Lot size page: {len(lot_size_stocks)} stocks")

        # Method 5: main futures list (more CSS scraping)
        if len(all_stocks) < 200:
            main_futures_stocks = self._get_main_futures_list()
            if main_futures_stocks:
                all_stocks.extend(main_futures_stocks)
                methods_used.append(f"MainFutures({len(main_futures_stocks)})")

        # Alternative sources
        if len(all_stocks) < 200:
            alt = self._get_alternative_sources()
            if alt:
                all_stocks.extend(alt)
                methods_used.append(f"Alt({len(alt)})")

        # Deduplicate & normalize
        unique_stocks = self._deduplicate_stocks(all_stocks)

        # Ensure indices present
        index_entries = [
            {"name": "Nifty 50", "symbol": "NIFTY", "exchange": "NSE"},
            {"name": "Nifty Bank", "symbol": "BANKNIFTY", "exchange": "NSE"},
            {"name": "Finnifty", "symbol": "FINNIFTY", "exchange": "NSE"},
            {"name": "Nifty Midcap Select", "symbol": "MIDCPNIFTY", "exchange": "NSE"},
            {"name": "Nifty Next 50", "symbol": "NIFTY-NEXT50", "exchange": "NSE"},
        ]
        for idx in index_entries:
            if not any(
                s.get("symbol", "").upper() == idx["symbol"] for s in unique_stocks
            ):
                unique_stocks.append(idx)
                logger.info(f"➕ Added index: {idx['name']} ({idx['symbol']})")

        # Convert, fix missing symbols, validate
        result = []
        fixed_symbols = 0
        for stock in unique_stocks:
            name = (stock.get("name") or "").strip()
            symbol = (stock.get("symbol") or "").strip()
            if not symbol and name in self.missing_symbols_map:
                symbol = self.missing_symbols_map[name]
                fixed_symbols += 1
            if not symbol:
                name_lower = name.lower()
                if "nifty 50" in name_lower or name_lower == "nifty":
                    symbol = "NIFTY"
                    fixed_symbols += 1
                elif "nifty bank" in name_lower or "bank nifty" in name_lower:
                    symbol = "BANKNIFTY"
                    fixed_symbols += 1
                elif "finnifty" in name_lower or "fin nifty" in name_lower:
                    symbol = "FINNIFTY"
                    fixed_symbols += 1
                elif "midcap" in name_lower and "nifty" in name_lower:
                    symbol = "MIDCPNIFTY"
                    fixed_symbols += 1
                elif "next 50" in name_lower and "nifty" in name_lower:
                    symbol = "NIFTY-NEXT50"
                    fixed_symbols += 1
            if name and len(name) >= 3:
                final_symbol = symbol or self._generate_symbol_from_name(name)
                if self._is_valid_symbol(final_symbol):
                    result.append(
                        {"name": name, "symbol": final_symbol, "exchange": "NSE"}
                    )

        indices = [r for r in result if r["symbol"] in self.actual_indices]
        stocks = [r for r in result if r["symbol"] not in self.actual_indices]
        total_count = len(result)
        logger.info(
            f"✅ F&O collection complete: {total_count} total ({len(indices)} indices, {len(stocks)} stocks) from {', '.join(methods_used)}; fixed {fixed_symbols} symbols"
        )

        expected_total = 211
        if total_count != expected_total:
            logger.warning(
                f"⚠️ Count mismatch: Got {total_count}, expected approx {expected_total} (difference: {expected_total - total_count})"
            )

        for i, stock in enumerate(result[:5]):
            logger.info(
                f"   {i+1}. {stock.get('name','N/A')} -> {stock.get('symbol','N/A')}"
            )

        return result

    # ----------------------------
    # Helpers (CSV, parsing, etc.)
    # ----------------------------
    def _get_extracted_dhan_data(self) -> list:
        try:
            if not self.extracted_data_path.exists():
                logger.debug(
                    f"Extracted data file not found: {self.extracted_data_path}"
                )
                return []
            logger.info(f"🔍 Loading extracted data from: {self.extracted_data_path}")
            with open(self.extracted_data_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            if not raw_data:
                logger.warning("Extracted data file is empty")
                return []
            processed_stocks = []
            for item in raw_data:
                try:
                    raw_name = item.get("All Companies", "").strip()
                    raw_symbol = item.get("Symbol", "").strip()
                    if not raw_name or not raw_symbol:
                        continue
                    cleaned_name = self._clean_extracted_name(raw_name)
                    cleaned_symbol = self._clean_extracted_symbol(raw_symbol)
                    if cleaned_name and cleaned_symbol and len(cleaned_name) >= 3:
                        processed_stocks.append(
                            {
                                "name": cleaned_name,
                                "symbol": cleaned_symbol,
                                "exchange": "NSE",
                            }
                        )
                except Exception as e:
                    logger.debug(f"Error processing extracted item {item}: {e}")
                    continue
            logger.info(
                f"✅ Processed extracted data: {len(processed_stocks)} valid stocks from {len(raw_data)} raw records"
            )
            return processed_stocks
        except Exception as e:
            logger.error(f"❌ Error loading extracted data: {e}")
            return []

    def _clean_extracted_name(self, raw_name: str) -> str:
        if not raw_name:
            return ""
        name = raw_name.strip()
        if name == "3360 One WAM":
            return "360 One WAM"
        if len(name) >= 2 and name[0] == name[1] and name[0].isalpha():
            name = name[1:]
        return self._clean_name(name)

    def _clean_extracted_symbol(self, raw_symbol: str) -> str:
        if not raw_symbol:
            return ""
        symbol = raw_symbol.strip().upper()
        suffixes_to_remove = ["BS", "FUT", "OPT", "CE", "PE"]
        for suffix in suffixes_to_remove:
            if symbol.endswith(suffix):
                symbol = symbol[: -len(suffix)]
                break
        symbol_mappings = {
            "BANKNIFTY": "BANKNIFTY",
            "FINNIFTY": "FINNIFTY",
            "MIDCPNIFTY": "MIDCPNIFTY",
            "NIFTY": "NIFTY",
            "NIFTY NEXT 50": "NIFTY-NEXT50",
            "360ONE": "360ONE",
        }
        if symbol in symbol_mappings:
            symbol = symbol_mappings[symbol]
        if self._is_valid_symbol(symbol):
            return symbol
        return ""

    def _get_main_futures_list(self) -> list:
        try:
            logger.info("🎯 Scraping main futures stocks list page...")
            url = f"{self.base_url}/futures-stocks-list/"
            headers = {
                "User-Agent": self.session.headers.get("User-Agent", ""),
                "Accept": "text/html",
            }
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            stocks = []
            data_elements = soup.find_all(attrs={"data-sym": True})
            for element in data_elements:
                try:
                    symbol = element.get("data-sym", "").strip()
                    name = ""
                    parent = element.parent
                    if parent:
                        name_element = parent.find(
                            string=lambda text: text and len(text.strip()) > 3
                        )
                        if name_element:
                            name = name_element.strip()
                    if symbol and len(symbol) > 1:
                        stocks.append({"name": name or symbol, "symbol": symbol})
                except Exception as e:
                    logger.debug(f"Error parsing data element: {e}")
                    continue
            if not stocks:
                stocks.extend(self._parse_html_page(response.text))
            if len(stocks) < 100:
                table_elements = soup.select(
                    ".css-p65e6u, [class*='table'], [class*='row']"
                )
                for table in table_elements:
                    try:
                        table_stocks = self._extract_from_table_element(table)
                        stocks.extend(table_stocks)
                    except Exception:
                        continue
            unique_stocks = []
            seen_symbols = set()
            for stock in stocks:
                symbol = (stock.get("symbol") or "").strip().upper()
                if symbol and symbol not in seen_symbols and len(symbol) > 1:
                    seen_symbols.add(symbol)
                    unique_stocks.append(stock)
            logger.info(f"🎯 Main futures list extracted: {len(unique_stocks)} stocks")
            return unique_stocks
        except Exception as e:
            logger.warning(f"Main futures list scraping failed: {e}")
            return []

    def _extract_from_table_element(self, table_element) -> list:
        stocks = []
        try:
            rows = table_element.find_all(
                ["tr", "div"],
                class_=lambda x: x and ("row" in x.lower() or "item" in x.lower()),
            )
            for row in rows:
                try:
                    text_content = row.get_text()
                    symbol_matches = re.findall(r"\b([A-Z]{2,12})\b", text_content)
                    for symbol in symbol_matches:
                        if symbol not in [
                            "THE",
                            "AND",
                            "FOR",
                            "LTD",
                            "LIMITED",
                            "INC",
                            "CORP",
                        ]:
                            name_text = text_content.replace(symbol, "").strip()
                            name = self._clean_name(name_text) if name_text else symbol
                            stocks.append({"name": name, "symbol": symbol})
                            break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Table element extraction failed: {e}")
        return stocks

    def _get_alternative_sources(self) -> list:
        all_alt_stocks = []
        alt_urls = [
            "/nse-equity-stocks/",
            "/stock-market/",
            "/equity-stocks-list/",
            "/nse-stocks-list/",
        ]
        for alt_url in alt_urls:
            try:
                url = f"{self.base_url}{alt_url}"
                logger.debug(f"Trying alternative URL: {url}")
                response = self.session.get(url, timeout=20)
                if response.status_code == 200:
                    if any(
                        keyword in response.text.lower()
                        for keyword in ["f&o", "fno", "futures", "derivatives"]
                    ):
                        alt_stocks = self._parse_html_page(response.text)
                        if alt_stocks:
                            all_alt_stocks.extend(alt_stocks)
                            logger.debug(
                                f"Alternative source {alt_url}: {len(alt_stocks)} stocks"
                            )
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Alternative URL {alt_url} failed: {e}")
                continue
        unique_alt_stocks = []
        seen_symbols = set()
        for stock in all_alt_stocks:
            symbol = (stock.get("symbol") or "").strip().upper()
            if symbol and symbol not in seen_symbols:
                seen_symbols.add(symbol)
                unique_alt_stocks.append(stock)
        if unique_alt_stocks:
            logger.info(
                f"🔍 Alternative sources found: {len(unique_alt_stocks)} additional stocks"
            )
        return unique_alt_stocks

    def _get_futures_pagination(self) -> list:
        all_stocks = []
        page = 1
        while page <= 10:
            try:
                url = f"{self.base_url}/futures-stocks-list/?page={page}"
                response = self.session.get(url, timeout=30)
                if response.status_code != 200:
                    break
                page_stocks = self._parse_html_page(response.text)
                if not page_stocks:
                    break
                all_stocks.extend(page_stocks)
                page += 1
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Futures page {page} failed: {e}")
                break
        return all_stocks

    def _get_fno_from_csv(self) -> list:
        try:
            logger.info("📥 Attempting to download complete F&O stock list via CSV...")
            all_csv_stocks = []
            csv_urls = [
                f"{self.base_url}/futures-stocks-list/download-csv/",
                f"{self.base_url}/options-stocks-list/download-csv/",
                f"{self.base_url}/nse-fno-lot-size/download-csv/",
                f"{self.base_url}/api/fno/stocks/csv",
                f"{self.base_url}/api/futures/stocks/csv",
                f"{self.base_url}/api/options/stocks/csv",
            ]
            headers = {
                "Accept": "text/csv, application/csv, application/octet-stream",
                "User-Agent": self.session.headers.get("User-Agent"),
            }
            for csv_url in csv_urls:
                try:
                    logger.debug(f"Trying CSV URL: {csv_url}")
                    response = self.session.get(csv_url, headers=headers, timeout=30)
                    if response.status_code == 200 and len(response.content) > 100:
                        content = response.text
                        if "," in content and (
                            "symbol" in content.lower() or "stock" in content.lower()
                        ):
                            csv_stocks = self._parse_csv_data(content)
                            if csv_stocks:
                                all_csv_stocks.extend(csv_stocks)
                                logger.info(
                                    f"✅ Downloaded {len(csv_stocks)} stocks from {csv_url}"
                                )
                                break
                        else:
                            logger.debug(
                                f"Response from {csv_url} doesn't appear to be CSV data"
                            )
                    else:
                        logger.debug(
                            f"CSV URL {csv_url}: Status {response.status_code}, Length {len(response.content) if response.content else 0}"
                        )
                except Exception as e:
                    logger.debug(f"CSV URL {csv_url} failed: {e}")
                    continue
            if all_csv_stocks:
                logger.info(
                    f"📥 CSV download successful: {len(all_csv_stocks)} total stocks"
                )
                return all_csv_stocks
            else:
                logger.info("📥 No CSV downloads successful, falling back to scraping")
                return []
        except Exception as e:
            logger.warning(f"CSV download failed: {e}")
            return []

    def _parse_csv_data(self, csv_content: str) -> list:
        try:
            import csv
            import io

            stocks = []
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            for row in csv_reader:
                name = ""
                symbol = ""
                name_columns = [
                    "company",
                    "name",
                    "stock",
                    "company_name",
                    "stock_name",
                ]
                for col in name_columns:
                    for key in row.keys():
                        if col in key.lower():
                            name = (row[key] or "").strip()
                            break
                    if name:
                        break
                symbol_columns = [
                    "symbol",
                    "ticker",
                    "code",
                    "stock_symbol",
                    "trading_symbol",
                ]
                for col in symbol_columns:
                    for key in row.keys():
                        if col in key.lower():
                            symbol = (row[key] or "").strip().upper()
                            break
                    if symbol:
                        break
                if not name or not symbol:
                    values = list(row.values())
                    if len(values) >= 2:
                        for i, val in enumerate(values[:2]):
                            if val is None:
                                continue
                            val_up = str(val).strip().upper()
                            if re.match(r"^[A-Z]{2,12}$", val_up):
                                symbol = val_up
                                name = values[1 - i].strip()
                                break
                if symbol and len(symbol) >= 2:
                    if not name:
                        name = symbol
                    stocks.append(
                        {
                            "name": self._clean_name(name),
                            "symbol": symbol,
                            "exchange": "NSE",
                        }
                    )
            logger.info(f"📊 Parsed CSV: {len(stocks)} stocks extracted")
            return stocks
        except Exception as e:
            logger.warning(f"CSV parsing failed: {e}")
            return []

    def _get_fno_lot_size(self) -> list:
        try:
            url = f"{self.base_url}/nse-fno-lot-size/"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return self._parse_html_page(response.text)
        except Exception as e:
            logger.error(f"F&O lot size failed: {e}")
            return []

    def _get_options_pagination(self) -> list:
        all_stocks = []
        page = 1
        while page <= 10:
            try:
                url = f"{self.base_url}/options-stocks-list/?page={page}"
                response = self.session.get(url, timeout=30)
                if response.status_code != 200:
                    break
                page_stocks = self._parse_html_page(response.text)
                if not page_stocks:
                    break
                all_stocks.extend(page_stocks)
                page += 1
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Options page {page} failed: {e}")
                break
        return all_stocks

    def _parse_html_page(self, html_content: str) -> list:
        soup = BeautifulSoup(html_content, "html.parser")
        stocks = []
        rows = (
            soup.select("table tbody tr")
            or soup.select("tbody tr")
            or soup.select("tr")
        )
        for row in rows:
            try:
                if self._is_header_row(row):
                    continue
                stock = self._extract_name_symbol(row)
                if stock and self._is_valid_stock(stock):
                    stocks.append(stock)
            except Exception:
                continue
        return stocks

    def _extract_name_symbol(self, row) -> dict:
        try:
            cells = row.find_all(["td", "th"])
            if len(cells) < 1:
                return None
            name_text = cells[0].get_text(strip=True)
            name = self._clean_name(name_text)
            symbol = self._extract_symbol(row, cells[0])
            return {"name": name, "symbol": symbol if symbol else ""}
        except Exception:
            return None

    def _clean_name(self, name_text: str) -> str:
        if not name_text:
            return ""
        cleaned = name_text.strip()
        if cleaned == "3360 One WAM":
            return "360 One WAM"
        if (
            len(cleaned) > 1
            and cleaned[0] == cleaned[1]
            and cleaned[0].isupper()
            and not cleaned[0].isdigit()
        ):
            cleaned = cleaned[1:]
        if len(cleaned) > 3 and cleaned.startswith("3360") and "One WAM" in cleaned:
            cleaned = "360 One WAM"
        cleaned = re.sub(
            r"\s*(Invest|Buy|Sell|Limited|Ltd\.?)\s*$", "", cleaned, flags=re.IGNORECASE
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _normalize_company_name(self, name: str) -> str:
        if not name:
            return ""
        if name == "3360 One WAM":
            name = "360 One WAM"
        normalized = name.strip().lower()
        remove_suffixes = [
            r"\s+limited\s*$",
            r"\s+ltd\.?\s*$",
            r"\s+ltd\s*$",
            r"\s+company\s*$",
            r"\s+co\.?\s*$",
            r"\s+corp\.?\s*$",
            r"\s+corporation\s*$",
            r"\s+enterprises\s*$",
            r"\s+industries\s*$",
            r"\s+inc\.?\s*$",
            r"\s+private\s*$",
            r"\s+pvt\.?\s*$",
            r"\s+group\s*$",
            r"\s+holding\s*$",
        ]
        for suffix in remove_suffixes:
            normalized = re.sub(suffix, "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+&\s+", " and ", normalized)
        normalized = re.sub(r"\s+technologies\s*$", " tech", normalized)
        normalized = re.sub(r"\s+financial\s+services\s*$", " fin", normalized)
        normalized = re.sub(r"\s+pharmaceuticals?\s*$", " pharma", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _extract_symbol(self, row, name_cell) -> str:
        try:
            img = name_cell.find("img")
            if img:
                if img.get("alt"):
                    match = re.search(r"\b([A-Z0-9\-]{2,12})\b", img["alt"])
                    if match:
                        return match.group(1).upper()
                if img.get("src"):
                    match = re.search(
                        r"/symbol/([A-Z0-9\-]+)\.png", img["src"], re.IGNORECASE
                    )
                    if match:
                        return match.group(1).upper()
            for attr in ["data-symbol", "data-stock", "data-sym"]:
                if name_cell.get(attr):
                    symbol = name_cell.get(attr).strip().upper()
                    if re.match(r"^[A-Z0-9\-]{2,12}$", symbol):
                        return symbol
            text = name_cell.get_text()
            match = re.search(r"\(([A-Z0-9\-]{2,12})\)", text)
            if match:
                return match.group(1).upper()
            # second cell heuristic
            cells = (
                name_cell.find_parent().find_all(["td", "th"])
                if name_cell.find_parent()
                else []
            )
            if len(cells) > 1:
                second_text = cells[1].get_text(strip=True)
                if re.match(r"^[A-Z0-9\-]{2,12}$", second_text.upper()):
                    return second_text.upper()
        except Exception:
            pass
        return ""

    def _is_header_row(self, row) -> bool:
        text = row.get_text().lower()
        return any(term in text for term in ["name", "symbol", "ltp", "lot size"])

    def _is_valid_stock(self, stock: dict) -> bool:
        name = (stock.get("name") or "").strip()
        if not name or len(name) < 3:
            return False
        invalid_patterns = [
            r"^total\s",
            r"\btotal\s+results",
            r"\bshowing\s",
            r"\bresults\b",
            r"\bdownload\b",
        ]
        name_lower = name.lower()
        for pattern in invalid_patterns:
            if re.search(pattern, name_lower):
                return False
        return True

    def _deduplicate_stocks(self, all_stocks: list) -> list:
        if not all_stocks:
            return []
        company_groups = {}
        for stock in all_stocks:
            name = (stock.get("name") or "").strip()
            symbol = (stock.get("symbol") or "").strip().upper()
            if not self._is_valid_stock(stock):
                continue
            if name == "3360 One WAM":
                name = "360 One WAM"
                stock["name"] = name
            normalized_name = self._normalize_company_name(name)
            company_groups.setdefault(normalized_name, []).append(
                {"original_name": name, "symbol": symbol, "stock": stock}
            )
        unique_stocks = []
        for normalized_name, entries in company_groups.items():
            if len(entries) == 1:
                unique_stocks.append(entries[0]["stock"])
            else:
                best_entry = self._select_best_entry(entries)
                if best_entry:
                    unique_stocks.append(best_entry["stock"])
        filtered_stocks = [s for s in unique_stocks if self._is_fno_eligible(s)]
        return filtered_stocks

    def _select_best_entry(self, entries: list) -> dict:
        if not entries:
            return None
        original_name = entries[0]["original_name"]
        if original_name in self.preferred_symbols:
            preferred_symbol = self.preferred_symbols[original_name]
            for entry in entries:
                if entry["symbol"] == preferred_symbol:
                    return entry
        scored_entries = []
        for entry in entries:
            score = 0
            symbol = entry.get("symbol") or ""
            if symbol:
                score += len(symbol) * 2
                name_words = original_name.upper().split()
                if any(word in symbol for word in name_words):
                    score += 10
                if not re.search(r"^(SBI|LIC|HCL|JSW)$", symbol):
                    score += 5
                if re.search(r"(BANK|TECH|STEEL|LIFE|PORTS)", symbol):
                    score += 3
            scored_entries.append((score, entry))
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        return scored_entries[0][1]

    def _is_fno_eligible(self, stock: dict) -> bool:
        name = (stock.get("name") or "").strip()
        symbol = (stock.get("symbol") or "").strip()
        if not name or not symbol:
            return False
        if symbol in self.actual_indices:
            return True
        skip_patterns = [
            r"^gold$",
            r"^silver$",
            r"^crude oil$",
            r"natural gas futures",
            r"^commodity",
            r"currency",
            r"forex",
            r"bond",
            r"treasury",
            r"etf$",
            r"index fund",
        ]
        name_lower = name.lower()
        for pattern in skip_patterns:
            if re.search(pattern, name_lower):
                return False
        index_name_patterns = [
            r"nifty\s+50",
            r"nifty\s+bank",
            r"finnifty",
            r"fin\s*nifty",
            r"nifty.*midcap",
            r"midcap.*nifty",
            r"nifty.*next.*50",
        ]
        for pattern in index_name_patterns:
            if re.search(pattern, name_lower):
                return True
        return True

    def _generate_symbol_from_name(self, name: str) -> str:
        if not name:
            return ""
        clean_name = name.strip().upper()
        remove_words = [
            "LIMITED",
            "LTD",
            "LTD.",
            "COMPANY",
            "CO",
            "CO.",
            "CORPORATION",
            "CORP",
            "CORP.",
            "ENTERPRISES",
            "GROUP",
            "INDUSTRIES",
            "INC",
            "INC.",
            "PVT",
            "PRIVATE",
            "&",
            "AND",
            "THE",
            "INDIA",
            "INDIAN",
        ]
        words = clean_name.split()
        filtered_words = []
        for word in words:
            word = re.sub(r"[^\w]", "", word)
            if word and word not in remove_words and len(word) > 1:
                filtered_words.append(word)
        if not filtered_words:
            return re.sub(r"[^\w]", "", name.upper())[:8]
        if len(filtered_words) == 1:
            return filtered_words[0][:8]
        elif len(filtered_words) <= 3:
            return "".join(filtered_words)[:8]
        else:
            return "".join(word[0] for word in filtered_words[:8])

    def _is_valid_symbol(self, symbol: str) -> bool:
        if not symbol:
            return False
        symbol = symbol.strip().upper()
        if not re.match(r"^[A-Z0-9\-&]+$", symbol):
            return False
        if len(symbol) < 2 or len(symbol) > 12:
            return False
        invalid_patterns = [r"^\d+$", r"[_]{2,}"]
        for pattern in invalid_patterns:
            if re.search(pattern, symbol):
                return False
        if re.match(r"^\d+[A-Z]+", symbol):
            return True
        if not re.match(r"^[A-Z]", symbol) and symbol not in ["360ONE"]:
            return False
        return True

    def save_to_json(self, stocks: List[Dict[str, str]]) -> bool:
        try:
            data = {
                "securities": stocks,
                "last_updated": datetime.now().isoformat(),
                "total_count": len(stocks),
                "data_source": "dhan_scraper",
            }
            self.json_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.json_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Saved {len(stocks)} F&O stocks to {self.json_file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving to JSON: {e}")
            return False

    def load_from_json(self) -> List[Dict[str, str]]:
        try:
            if not self.json_file_path.exists():
                logger.warning(f"JSON file {self.json_file_path} does not exist")
                return []
            with open(self.json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            stocks = data.get("securities", [])
            logger.info(
                f"📂 Loaded {len(stocks)} F&O stocks from {self.json_file_path}"
            )
            return stocks
        except Exception as e:
            logger.error(f"❌ Error loading from JSON: {e}")
            return []

    def update_fno_list(self) -> Dict[str, any]:
        start_time = datetime.now()
        logger.info("🚀 Starting F&O stock list update...")
        try:
            stocks = self.get_fno_stocks()
            if not stocks:
                logger.warning("No stocks fetched, keeping existing data")
                return {
                    "status": "failed",
                    "error": "No stocks fetched",
                    "timestamp": datetime.now().isoformat(),
                }
            saved = self.save_to_json(stocks)
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            result = {
                "status": "success" if saved else "partial_success",
                "total_stocks": len(stocks),
                "file_saved": saved,
                "file_path": str(self.json_file_path),
                "processing_time_seconds": processing_time,
                "last_updated": datetime.now().isoformat(),
            }
            logger.info(f"✅ F&O stock list update completed in {processing_time:.2f}s")
            return result
        except Exception as e:
            logger.error(f"❌ F&O stock list update failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }


# -----------------
# Standalone usage
# -----------------
def update_fno_stock_list() -> Dict[str, any]:
    service = FnoStockListService()
    return service.update_fno_list()


def get_fno_stocks_from_file() -> List[Dict[str, str]]:
    service = FnoStockListService()
    stocks = service.load_from_json()
    enhanced_stocks = []
    for stock in stocks:
        enhanced_stock = stock.copy()
        symbol = stock.get("symbol")
        if symbol:
            sector = get_sector_for_stock(symbol)
            if sector:
                enhanced_stock["sector"] = sector
            else:
                enhanced_stock["sector"] = (
                    "INDEX"
                    if symbol
                    in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTY-NEXT50"]
                    else "F&O"
                )
        else:
            enhanced_stock["sector"] = "UNKNOWN"
        enhanced_stocks.append(enhanced_stock)
    return enhanced_stocks


def get_categorized_fno_data() -> Dict[str, any]:
    service = FnoStockListService()
    return service.get_categorized_fno_data()


def fix_missing_symbols_in_json(input_file: str = None) -> Dict[str, any]:
    service = FnoStockListService()
    return service.fix_existing_json_symbols(input_file)


# -----------------
# Quick test runner
# -----------------
def main():
    svc = FnoStockListService()
    res = svc.update_fno_list()
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
