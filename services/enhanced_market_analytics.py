from datetime import datetime
import logging
from typing import Any, Dict, List


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Import the ENHANCED breakout detection engine (NEW - Primary)
try:
    from services.enhanced_breakout_engine import enhanced_breakout_engine

    ENHANCED_BREAKOUT_SERVICE_AVAILABLE = True
except ImportError:
    ENHANCED_BREAKOUT_SERVICE_AVAILABLE = False


class EnhancedMarketAnalyticsService:
    def __init__(self):
        self.cache = {}
        self.last_calculated = {}
        self.cache_ttl = 2  # TRADING SAFETY: Reduced to 2 seconds for better accuracy
        self.max_cache_size = 1000  # Maximum cached items
        self.cache_access_times = {}  # Track access times for LRU cleanup

        # 🚀 NEW: Single enriched data cache to avoid multiple fetches
        self._enriched_data_cache = None
        self._enriched_data_cache_time = 0
        self._enriched_data_cache_ttl = 1  # 1 second cache for enriched data

    def _cleanup_cache(self):
        """Clean up old cache entries using LRU strategy"""
        if len(self.cache) <= self.max_cache_size:
            return

        # Remove oldest 20% of entries
        now = datetime.now()
        entries_to_remove = []

        # Find expired entries first
        for key, timestamp in self.last_calculated.items():
            if (now - timestamp).total_seconds() > self.cache_ttl:
                entries_to_remove.append(key)

        # If still over limit, use LRU
        if len(self.cache) - len(entries_to_remove) > self.max_cache_size:
            # Sort by access time and remove oldest
            sorted_by_access = sorted(
                self.cache_access_times.items(), key=lambda x: x[1]
            )
            remaining_to_remove = (
                len(self.cache) - len(entries_to_remove) - self.max_cache_size + 200
            )
            entries_to_remove.extend(
                [key for key, _ in sorted_by_access[:remaining_to_remove]]
            )

        # Remove selected entries
        for key in entries_to_remove:
            self.cache.pop(key, None)
            self.last_calculated.pop(key, None)
            self.cache_access_times.pop(key, None)

        if entries_to_remove:
            logger.debug(f"Cleaned up {len(entries_to_remove)} cache entries")

    def _get_cached_or_compute(
        self, cache_key: str, compute_func: callable, ttl: int = None
    ) -> Any:
        """Get cached result or compute new one with automatic cleanup"""
        now = datetime.now()
        effective_ttl = ttl or self.cache_ttl

        # Check if cached result exists and is valid
        if (
            cache_key in self.cache
            and cache_key in self.last_calculated
            and (now - self.last_calculated[cache_key]).total_seconds() < effective_ttl
        ):

            # Update access time for LRU
            self.cache_access_times[cache_key] = now
            return self.cache[cache_key]

        # Compute new result
        try:
            result = compute_func()

            # Store in cache with cleanup
            self.cache[cache_key] = result
            self.last_calculated[cache_key] = now
            self.cache_access_times[cache_key] = now

            # Trigger cleanup if needed
            if len(self.cache) > self.max_cache_size:
                self._cleanup_cache()

            return result

        except Exception as e:
            logger.error(f"Error computing {cache_key}: {e}")
            return None

    def _get_cached_enriched_data(self) -> Dict[str, Any]:
        """🚀 OPTIMIZED: Get enriched data with caching to avoid multiple fetches"""
        import time

        current_time = time.time()

        # Check if cached data is still valid
        if (
            self._enriched_data_cache
            and current_time - self._enriched_data_cache_time
            < self._enriched_data_cache_ttl
        ):
            return self._enriched_data_cache

        # Fetch fresh data
        try:
            from services.instrument_registry import instrument_registry

            enriched_data = instrument_registry.get_enriched_prices()

            # Update cache
            self._enriched_data_cache = enriched_data or {}
            self._enriched_data_cache_time = current_time

            return self._enriched_data_cache

        except Exception as e:
            logger.error(f"❌ Error fetching enriched data: {e}")
            return self._enriched_data_cache or {}

    def _invalidate_enriched_data_cache(self):
        """Invalidate enriched data cache to force refresh"""
        self._enriched_data_cache = None
        self._enriched_data_cache_time = 0

    def get_complete_analytics(self) -> Dict[str, Any]:
        """COMPLETE: Get all analytics with enriched data - optimized for real-time"""
        try:
            start_time = datetime.now()

            # Prioritized order - most critical features first for faster UI updates
            analytics = {
                "top_movers": self.get_top_gainers_losers(),
                "intraday_stocks": self.get_intraday_stocks(),  # High priority for trading
                "market_sentiment": self.get_market_sentiment(),
                "indices_data": self.get_indices_data(),
                "volume_analysis": self.get_volume_analysis(),
                "sector_heatmap": self.get_sector_heatmap(),
                "gap_analysis": self.get_gap_analysis(),
                "breakout_analysis": self.get_breakout_analysis(),
                "market_breadth": self.get_market_breadth(),
                "intraday_highlights": self.get_intraday_highlights(),
                "performance_summary": self.get_performance_summary(),
                "record_movers": self.get_record_movers(),
                "generated_at": datetime.now().isoformat(),
                "processing_time_ms": (datetime.now() - start_time).total_seconds()
                * 1000,
                "cache_status": self._get_cache_status(),
            }

            logger.info(
                f"📊 Complete analytics generated in {analytics['processing_time_ms']:.2f}ms"
            )
            return analytics

        except Exception as e:
            logger.error(f"Error generating complete analytics: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    def get_priority_analytics(self) -> Dict[str, Any]:
        """Get high-priority analytics for real-time updates - bypasses cache"""
        try:
            start_time = datetime.now()

            # Force refresh for real-time critical features
            analytics = {
                "top_movers": self.get_top_gainers_losers(force_refresh=True),
                "intraday_stocks": self.get_intraday_stocks(force_refresh=True),
                "volume_analysis": self.get_volume_analysis(
                    force_refresh=True
                ),  # Added for real-time volume updates
                "market_sentiment": self.get_market_sentiment(),
                "indices_data": self.get_indices_data(),
                "generated_at": datetime.now().isoformat(),
                "processing_time_ms": (datetime.now() - start_time).total_seconds()
                * 1000,
                "is_priority_update": True,
            }

            logger.info(
                f"📊 Priority analytics generated in {analytics['processing_time_ms']:.2f}ms"
            )
            return analytics

        except Exception as e:
            logger.error(f"Error generating priority analytics: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "is_priority_update": True,
            }

    def get_all_live_stocks(self) -> List[Dict[str, Any]]:
        """COMPLETE: Get enriched stock data"""
        try:
            # 🚀 OPTIMIZED: Use cached enriched data to avoid multiple fetches
            enriched_data = self._get_cached_enriched_data()

            stocks = []
            for instrument_key, data in enriched_data.items():
                # Check for either ltp or last_price for compatibility
                if (data.get("ltp") or data.get("last_price")) and data.get("symbol"):
                    # Data is already enriched with all metadata
                    stock_entry = {
                        "symbol": data["symbol"],
                        "name": data.get("name", data["symbol"]),
                        "sector": data.get("sector", "OTHER"),
                        "instrument_key": instrument_key,
                        "trading_symbol": data.get("trading_symbol", data["symbol"]),
                        "exchange": data.get("exchange", "NSE"),
                        "instrument_type": data.get("instrument_type", "EQ"),
                        # ✅ FIX: Handle both ltp and last_price fields
                        "last_price": data.get("ltp") or data.get("last_price", 0),
                        "change": data.get("change", 0),
                        "change_percent": data.get("change_percent", 0),
                        "previous_close": data.get("cp", 0),
                        # OHLC
                        "open": data.get("open", 0),
                        "high": data.get("high", 0),
                        "low": data.get("low", 0),
                        "close": data.get("close", 0),
                        # Volume
                        "volume": data.get("volume", 0),
                        "avg_trade_price": data.get("avg_trade_price"),
                        # Advanced metrics
                        "trend": data.get("trend", "neutral"),
                        "volatility": data.get("volatility", "normal"),
                        "has_derivatives": data.get("has_derivatives", False),
                        # Computed fields
                        "market_cap_category": self._categorize_by_price(
                            data.get("ltp") or data.get("last_price", 0)
                        ),
                        "volume_category": self._categorize_volume(
                            data.get("volume", 0)
                        ),
                        "performance_category": self._categorize_performance(
                            data.get("change_percent", 0)
                        ),
                        # Metadata
                        "last_updated": data.get("last_updated"),
                        "update_count": data.get("update_count", 0),
                    }

                    # Calculate additional metrics
                    if stock_entry["open"] > 0 and stock_entry["close"] > 0:
                        stock_entry["gap_percent"] = (
                            (stock_entry["open"] - stock_entry["close"])
                            / stock_entry["close"]
                            * 100
                        )

                    stocks.append(stock_entry)

            logger.info(
                f"📊 Retrieved {len(stocks)} enriched stocks with complete metadata"
            )

            # ✅ CRITICAL FIX: If no stocks retrieved, try to get data from fallback sources
            if len(stocks) == 0:
                logger.warning(
                    "⚠️ No enriched stocks found - checking fallback data sources"
                )
                # Try to get any available live prices data
                try:
                    from services.instrument_registry import instrument_registry

                    live_data = instrument_registry._live_prices
                    if live_data:
                        logger.info(
                            f"📊 Found {len(live_data)} live prices as fallback"
                        )
                        # Convert live data to basic stock format
                        for key, data in list(live_data.items())[
                            :50
                        ]:  # Limit to prevent overload
                            if isinstance(data, dict) and data.get("ltp"):
                                symbol = key.split("|")[-1] if "|" in key else key
                                fallback_stock = {
                                    "symbol": symbol,
                                    "name": symbol,
                                    "sector": "UNKNOWN",
                                    "last_price": data.get("ltp", 0),
                                    "change": data.get("change", 0),
                                    "change_percent": data.get("change_percent", 0),
                                    "volume": data.get("volume", 0),
                                    "market_cap_category": "unknown",
                                    "volume_category": "unknown",
                                    "performance_category": "unknown",
                                    "has_derivatives": False,
                                    "last_updated": datetime.now().isoformat(),
                                }
                                stocks.append(fallback_stock)
                        logger.info(f"📊 Created {len(stocks)} fallback stock entries")
                except Exception as fallback_error:
                    logger.warning(
                        f"⚠️ Fallback data retrieval failed: {fallback_error}"
                    )

            return stocks

        except Exception as e:
            logger.error(f"Error getting live stocks: {e}")
            return []

    def get_top_gainers_losers(
        self, limit: int = 20, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """COMPLETE: Top movers with enriched data - real-time capable"""
        if not force_refresh and not self._should_recalculate("top_movers"):
            return self.cache.get("top_movers", {"gainers": [], "losers": []})

        try:
            from services.instrument_registry import instrument_registry

            # Use optimized registry method if available, otherwise calculate manually
            try:
                movers_data = instrument_registry.get_top_movers(limit)
            except AttributeError:
                # Fallback: calculate manually
                movers_data = self._calculate_top_movers_manually(limit)

            # Add additional analysis
            gainers = movers_data.get("gainers", [])
            losers = movers_data.get("losers", [])

            # Analyze sectors in top movers
            gainer_sectors = {}
            loser_sectors = {}

            for stock in gainers:
                sector = stock.get("sector", "OTHER")
                gainer_sectors[sector] = gainer_sectors.get(sector, 0) + 1

            for stock in losers:
                sector = stock.get("sector", "OTHER")
                loser_sectors[sector] = loser_sectors.get(sector, 0) + 1

            result = {
                "gainers": gainers,
                "losers": losers,
                "analysis": {
                    "avg_gainer_change": (
                        sum(s.get("change_percent", 0) for s in gainers) / len(gainers)
                        if gainers
                        else 0
                    ),
                    "avg_loser_change": (
                        sum(s.get("change_percent", 0) for s in losers) / len(losers)
                        if losers
                        else 0
                    ),
                    "gainer_sectors": gainer_sectors,
                    "loser_sectors": loser_sectors,
                    "total_analyzed": movers_data.get("total_stocks_analyzed", 0),
                },
                "timestamp": datetime.now().isoformat(),
            }

            self.cache["top_movers"] = result
            self._mark_calculated("top_movers")
            return result

        except Exception as e:
            logger.error(f"Error calculating top movers: {e}")
            return {"gainers": [], "losers": [], "error": str(e)}

    def get_sector_heatmap(self) -> Dict[str, Any]:
        """COMPLETE: Sector heatmap with detailed analysis - FIXED VERSION"""
        if not self._should_recalculate("sector_heatmap"):
            return self.cache.get("sector_heatmap", {"sectors": []})

        try:
            from services.instrument_registry import instrument_registry

            # FIXED: Use direct enriched prices instead of registry method
            logger.info("📊 Starting sector heatmap calculation")

            # 🚀 OPTIMIZED: Use cached enriched data
            enriched_data = self._get_cached_enriched_data()

            if not enriched_data:
                logger.warning("⚠️ No enriched data available for sector heatmap")
                return {
                    "sectors": [],
                    "summary": {
                        "total_sectors": 0,
                        "bullish_sectors": 0,
                        "bearish_sectors": 0,
                        "neutral_sectors": 0,
                    },
                    "error": "No enriched data available",
                    "timestamp": datetime.now().isoformat(),
                }

            # Group stocks by sector
            sectors_data = {}
            total_stocks_processed = 0

            for instrument_key, stock_data in enriched_data.items():
                try:
                    sector = stock_data.get("sector", "OTHER")
                    if sector not in sectors_data:
                        sectors_data[sector] = {
                            "stocks": [],
                            "total_stocks": 0,
                            "advancing": 0,
                            "declining": 0,
                            "unchanged": 0,
                            "total_volume": 0,
                            "changes": [],
                        }

                    # Add stock to sector
                    sectors_data[sector]["stocks"].append(stock_data)
                    sectors_data[sector]["total_stocks"] += 1
                    sectors_data[sector]["total_volume"] += stock_data.get("volume", 0)

                    # Track change percentage
                    change_pct = stock_data.get("change_percent", 0)
                    if change_pct is not None:
                        sectors_data[sector]["changes"].append(change_pct)

                        if change_pct > 0:
                            sectors_data[sector]["advancing"] += 1
                        elif change_pct < 0:
                            sectors_data[sector]["declining"] += 1
                        else:
                            sectors_data[sector]["unchanged"] += 1

                    total_stocks_processed += 1

                except Exception as e:
                    logger.warning(f"⚠️ Error processing stock for sector heatmap: {e}")
                    continue

            logger.info(
                f"📊 Processed {total_stocks_processed} stocks across {len(sectors_data)} sectors"
            )

            # Build sector analysis
            sectors = []
            for sector_name, data in sectors_data.items():
                if data["total_stocks"] == 0:
                    continue

                # Calculate average change
                changes = data["changes"]
                avg_change = sum(changes) / len(changes) if changes else 0

                # Find top and worst performers
                top_performer = max(
                    data["stocks"], key=lambda x: x.get("change_percent", 0)
                )
                worst_performer = min(
                    data["stocks"], key=lambda x: x.get("change_percent", 0)
                )

                sector_entry = {
                    "sector": sector_name,
                    "stocks_count": data["total_stocks"],
                    "avg_change_percent": round(avg_change, 2),
                    "advancing": data["advancing"],
                    "declining": data["declining"],
                    "unchanged": data["unchanged"],
                    "strength_score": (
                        round(
                            (data["advancing"] - data["declining"])
                            / data["total_stocks"]
                            * 100,
                            2,
                        )
                        if data["total_stocks"] > 0
                        else 0
                    ),
                    "total_volume": data["total_volume"],
                    # Performance categorization
                    "performance_category": self._categorize_sector_performance(
                        avg_change
                    ),
                    "momentum": self._calculate_sector_momentum(
                        {
                            "strength_score": (
                                (data["advancing"] - data["declining"])
                                / data["total_stocks"]
                                * 100
                                if data["total_stocks"] > 0
                                else 0
                            )
                        }
                    ),
                    # Top/worst performers
                    "top_performer": {
                        "symbol": top_performer.get("symbol", "N/A"),
                        "name": top_performer.get("name", "N/A"),
                        "change_percent": top_performer.get("change_percent", 0),
                    },
                    "worst_performer": {
                        "symbol": worst_performer.get("symbol", "N/A"),
                        "name": worst_performer.get("name", "N/A"),
                        "change_percent": worst_performer.get("change_percent", 0),
                    },
                    # Advanced metrics
                    "breadth_ratio": self._calculate_breadth_ratio(data),
                    "participation_rate": self._calculate_participation_rate(data),
                }

                sectors.append(sector_entry)

            # Sort by performance
            sectors.sort(key=lambda x: x["avg_change_percent"], reverse=True)

            # Build summary
            best_performing = sectors[0]["sector"] if sectors else None
            worst_performing = sectors[-1]["sector"] if sectors else None

            result = {
                "sectors": sectors,
                "summary": {
                    "best_performing": best_performing,
                    "worst_performing": worst_performing,
                    "total_sectors": len(sectors),
                    "bullish_sectors": len(
                        [s for s in sectors if s["avg_change_percent"] > 0.5]
                    ),
                    "bearish_sectors": len(
                        [s for s in sectors if s["avg_change_percent"] < -0.5]
                    ),
                    "neutral_sectors": len(
                        [s for s in sectors if -0.5 <= s["avg_change_percent"] <= 0.5]
                    ),
                },
                "timestamp": datetime.now().isoformat(),
                "debug_info": {
                    "total_stocks_processed": total_stocks_processed,
                    "enriched_data_count": len(enriched_data),
                    "sectors_found": list(sectors_data.keys()),
                },
            }

            self.cache["sector_heatmap"] = result
            self._mark_calculated("sector_heatmap")

            logger.info(
                f"✅ Sector heatmap calculated successfully with {len(sectors)} sectors"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Error calculating sector heatmap: {e}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                "sectors": [],
                "summary": {
                    "total_sectors": 0,
                    "bullish_sectors": 0,
                    "bearish_sectors": 0,
                    "neutral_sectors": 0,
                },
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _calculate_participation_rate(self, sector_data: dict) -> float:
        """Calculate participation rate for a sector"""
        advancing = sector_data.get("advancing", 0)
        declining = sector_data.get("declining", 0)
        total_stocks = sector_data.get("total_stocks", 1)

        if total_stocks == 0:
            return 0.0

        return round((advancing + declining) / total_stocks, 3)

    # Add this method to your EnhancedMarketAnalyticsService class in enhanced_market_analytics_service.py

    def get_indices_data(self) -> Dict[str, Any]:
        """COMPLETE: Get comprehensive indices data with analytics"""
        if not self._should_recalculate("indices_data"):
            return self.cache.get("indices_data", {"indices": [], "summary": {}})

        try:
            from services.instrument_registry import instrument_registry

            # Define major indices with their possible keys
            major_indices = {
                "NIFTY": ["NSE_INDEX|Nifty 50", "NSE_INDEX|NIFTY 50"],
                "BANKNIFTY": ["NSE_INDEX|Nifty Bank", "NSE_INDEX|BANK NIFTY"],
                "FINNIFTY": [
                    "NSE_INDEX|Nifty Fin Service",
                    "NSE_INDEX|Nifty Financial Services",
                ],
                "SENSEX": ["BSE_INDEX|SENSEX"],
                "MIDCPNIFTY": [
                    "NSE_INDEX|Nifty Midcap 50",
                    "NSE_INDEX|NIFTY MID SELECT",
                ],
                # "SMALLCAPNIFTY": ["NSE_INDEX|Nifty Smallcap 50"],
                # "CNXAUTO": ["NSE_INDEX|Nifty Auto"],
                # "CNXBANK": ["NSE_INDEX|Nifty Bank"],
                # "CNXIT": ["NSE_INDEX|Nifty IT"],
                # "CNXPHARMA": ["NSE_INDEX|Nifty Pharma"],
                # "CNXFMCG": ["NSE_INDEX|Nifty FMCG"],
                # "CNXMETAL": ["NSE_INDEX|Nifty Metal"],
                # "CNXREALTY": ["NSE_INDEX|Nifty Realty"],
                # "CNXENERGY": ["NSE_INDEX|Nifty Energy"],
                # "CNXPSE": ["NSE_INDEX|Nifty PSE"],
            }

            indices_data = []
            sector_indices = []
            major_market_indices = []

            # 🚀 OPTIMIZED: Use cached enriched data
            enriched_data = self._get_cached_enriched_data()

            if not enriched_data:
                logger.warning("⚠️ No enriched data available for indices")
                return {
                    "indices": [],
                    "major_indices": [],
                    "sector_indices": [],
                    "summary": {"total_indices": 0, "major_up": 0, "major_down": 0},
                    "error": "No enriched data available",
                    "timestamp": datetime.now().isoformat(),
                }

            logger.info(
                f"📊 Processing indices from {len(enriched_data)} enriched instruments"
            )

            # Process each major index
            for symbol, possible_keys in major_indices.items():
                index_data = None

                # Try to find the index using spot price method first
                try:
                    spot_data = instrument_registry.get_spot_price(symbol)
                    if spot_data and spot_data.get("last_price") is not None:
                        index_data = {
                            "symbol": symbol,
                            "name": spot_data.get("trading_symbol", symbol),
                            "instrument_key": spot_data.get("instrument_key"),
                            "exchange": spot_data.get(
                                "exchange",
                                (
                                    "NSE"
                                    if "NSE" in spot_data.get("instrument_key", "")
                                    else "BSE"
                                ),
                            ),
                            "last_price": spot_data.get("last_price"),
                            "change": spot_data.get("change"),
                            "change_percent": spot_data.get("change_percent"),
                            "high": spot_data.get("high"),
                            "low": spot_data.get("low"),
                            "open": spot_data.get("open"),
                            "close": spot_data.get("close"),
                            "volume": spot_data.get("volume", 0),
                            "last_updated": spot_data.get("last_updated"),
                            "data_source": "registry_spot_price",
                        }
                        logger.info(
                            f"✅ Found {symbol} via spot price: {index_data['last_price']}"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Error getting spot price for {symbol}: {e}")

                # If spot price didn't work, try direct lookup in enriched data
                if not index_data:
                    for possible_key in possible_keys:
                        if possible_key in enriched_data:
                            data = enriched_data[possible_key]
                            if data.get("ltp") is not None:
                                index_data = {
                                    "symbol": symbol,
                                    "name": data.get("name", symbol),
                                    "instrument_key": possible_key,
                                    "exchange": data.get(
                                        "exchange",
                                        "NSE" if "NSE" in possible_key else "BSE",
                                    ),
                                    "last_price": data.get("ltp"),
                                    "change": data.get("change"),
                                    "change_percent": data.get("change_percent"),
                                    "high": data.get("high"),
                                    "low": data.get("low"),
                                    "open": data.get("open"),
                                    "close": data.get("close") or data.get("cp"),
                                    "volume": data.get("volume", 0),
                                    "last_updated": data.get("last_updated")
                                    or data.get("timestamp"),
                                    "data_source": "enriched_direct",
                                }
                                logger.info(
                                    f"✅ Found {symbol} via enriched data: {index_data['last_price']}"
                                )
                                break

                # If still no data, try fallback search
                if not index_data:
                    for instrument_key, data in enriched_data.items():
                        if "INDEX" in instrument_key and data.get("ltp") is not None:
                            # Check if this might be our target index
                            key_upper = instrument_key.upper()
                            symbol_variations = [
                                symbol,
                                symbol.replace("NIFTY", "Nifty"),
                                symbol.replace("CNX", "Nifty"),
                            ]

                            for variation in symbol_variations:
                                if variation.upper() in key_upper or any(
                                    word in key_upper
                                    for word in variation.upper().split()
                                ):
                                    index_data = {
                                        "symbol": symbol,
                                        "name": data.get("name", symbol),
                                        "instrument_key": instrument_key,
                                        "exchange": data.get(
                                            "exchange",
                                            "NSE" if "NSE" in instrument_key else "BSE",
                                        ),
                                        "last_price": data.get("ltp"),
                                        "change": data.get("change"),
                                        "change_percent": data.get("change_percent"),
                                        "high": data.get("high"),
                                        "low": data.get("low"),
                                        "open": data.get("open"),
                                        "close": data.get("close") or data.get("cp"),
                                        "volume": data.get("volume", 0),
                                        "last_updated": data.get("last_updated")
                                        or data.get("timestamp"),
                                        "data_source": "fallback_search",
                                    }
                                    logger.info(
                                        f"✅ Found {symbol} via fallback search: {index_data['last_price']}"
                                    )
                                    break
                            if index_data:
                                break

                # Add to appropriate category
                if index_data:
                    # Calculate additional metrics
                    if index_data["last_price"] and index_data["close"]:
                        if not index_data["change"]:
                            index_data["change"] = (
                                index_data["last_price"] - index_data["close"]
                            )
                        if (
                            not index_data["change_percent"]
                            and index_data["close"] != 0
                        ):
                            index_data["change_percent"] = (
                                index_data["change"] / index_data["close"]
                            ) * 100

                    # Add trend and performance indicators
                    change_pct = index_data.get("change_percent", 0)
                    index_data["trend"] = (
                        "strong_bullish"
                        if change_pct > 2
                        else (
                            "bullish"
                            if change_pct > 0.5
                            else (
                                "strong_bearish"
                                if change_pct < -2
                                else "bearish" if change_pct < -0.5 else "neutral"
                            )
                        )
                    )

                    index_data["performance_category"] = (
                        "strong_gainer"
                        if change_pct > 2
                        else (
                            "gainer"
                            if change_pct > 0
                            else (
                                "strong_loser"
                                if change_pct < -2
                                else "loser" if change_pct < 0 else "unchanged"
                            )
                        )
                    )

                    # Categorize indices
                    if symbol in [
                        "NIFTY",
                        "BANKNIFTY",
                        "SENSEX",
                        "MIDCPNIFTY",
                        "FINNIFTY",
                        "SMALLCAPNIFTY",
                    ]:
                        major_market_indices.append(index_data)
                    else:
                        sector_indices.append(index_data)

                    indices_data.append(index_data)
                else:
                    logger.warning(f"⚠️ Could not find data for index: {symbol}")

            # Find any additional INDEX instruments that we might have missed
            additional_indices = []
            processed_keys = set()

            for index in indices_data:
                processed_keys.add(index["instrument_key"])

            for instrument_key, data in enriched_data.items():
                if (
                    "INDEX" in instrument_key
                    and instrument_key not in processed_keys
                    and data.get("ltp") is not None
                ):

                    # Extract symbol from key
                    symbol = (
                        instrument_key.split("|")[-1]
                        if "|" in instrument_key
                        else instrument_key
                    )
                    symbol = symbol.replace(" ", "").upper()

                    additional_index = {
                        "symbol": symbol,
                        "name": data.get("name", symbol),
                        "instrument_key": instrument_key,
                        "exchange": data.get(
                            "exchange", "NSE" if "NSE" in instrument_key else "BSE"
                        ),
                        "last_price": data.get("ltp"),
                        "change": data.get("change"),
                        "change_percent": data.get("change_percent"),
                        "high": data.get("high"),
                        "low": data.get("low"),
                        "open": data.get("open"),
                        "close": data.get("close") or data.get("cp"),
                        "volume": data.get("volume", 0),
                        "last_updated": data.get("last_updated")
                        or data.get("timestamp"),
                        "data_source": "additional_discovery",
                        "trend": "neutral",
                        "performance_category": "unknown",
                    }

                    additional_indices.append(additional_index)
                    indices_data.append(additional_index)

            # Sort indices by change percentage
            indices_data.sort(key=lambda x: x.get("change_percent", 0), reverse=True)
            major_market_indices.sort(
                key=lambda x: x.get("change_percent", 0), reverse=True
            )
            sector_indices.sort(key=lambda x: x.get("change_percent", 0), reverse=True)

            # Calculate summary statistics
            major_up = len(
                [
                    idx
                    for idx in major_market_indices
                    if idx.get("change_percent", 0) > 0
                ]
            )
            major_down = len(
                [
                    idx
                    for idx in major_market_indices
                    if idx.get("change_percent", 0) < 0
                ]
            )
            sector_up = len(
                [idx for idx in sector_indices if idx.get("change_percent", 0) > 0]
            )
            sector_down = len(
                [idx for idx in sector_indices if idx.get("change_percent", 0) < 0]
            )

            # Find best and worst performers
            best_performer = indices_data[0] if indices_data else None
            worst_performer = indices_data[-1] if indices_data else None

            # Calculate market sentiment from indices
            if major_market_indices:
                avg_major_change = sum(
                    idx.get("change_percent", 0) for idx in major_market_indices
                ) / len(major_market_indices)
                market_sentiment_from_indices = (
                    "very_bullish"
                    if avg_major_change > 2
                    else (
                        "bullish"
                        if avg_major_change > 0.5
                        else (
                            "very_bearish"
                            if avg_major_change < -2
                            else "bearish" if avg_major_change < -0.5 else "neutral"
                        )
                    )
                )
            else:
                avg_major_change = 0
                market_sentiment_from_indices = "unknown"

            result = {
                "indices": indices_data,
                "major_indices": major_market_indices,
                "sector_indices": sector_indices,
                "additional_indices": additional_indices,
                "summary": {
                    "total_indices": len(indices_data),
                    "major_indices_count": len(major_market_indices),
                    "sector_indices_count": len(sector_indices),
                    "additional_indices_count": len(additional_indices),
                    "major_up": major_up,
                    "major_down": major_down,
                    "major_unchanged": len(major_market_indices)
                    - major_up
                    - major_down,
                    "sector_up": sector_up,
                    "sector_down": sector_down,
                    "sector_unchanged": len(sector_indices) - sector_up - sector_down,
                    "avg_major_change": round(avg_major_change, 2),
                    "market_sentiment_from_indices": market_sentiment_from_indices,
                    "best_performer": {
                        "symbol": (
                            best_performer.get("symbol") if best_performer else None
                        ),
                        "change_percent": (
                            best_performer.get("change_percent")
                            if best_performer
                            else None
                        ),
                    },
                    "worst_performer": {
                        "symbol": (
                            worst_performer.get("symbol") if worst_performer else None
                        ),
                        "change_percent": (
                            worst_performer.get("change_percent")
                            if worst_performer
                            else None
                        ),
                    },
                },
                "timestamp": datetime.now().isoformat(),
                "debug_info": {
                    "enriched_data_available": len(enriched_data),
                    "indices_found_by_method": {
                        "spot_price": len(
                            [
                                idx
                                for idx in indices_data
                                if idx.get("data_source") == "registry_spot_price"
                            ]
                        ),
                        "enriched_direct": len(
                            [
                                idx
                                for idx in indices_data
                                if idx.get("data_source") == "enriched_direct"
                            ]
                        ),
                        "fallback_search": len(
                            [
                                idx
                                for idx in indices_data
                                if idx.get("data_source") == "fallback_search"
                            ]
                        ),
                        "additional_discovery": len(
                            [
                                idx
                                for idx in indices_data
                                if idx.get("data_source") == "additional_discovery"
                            ]
                        ),
                    },
                },
            }

            # Cache the result
            self.cache["indices_data"] = result
            self._mark_calculated("indices_data")

            logger.info(
                f"✅ Indices data calculated: {len(indices_data)} total indices, {len(major_market_indices)} major, {len(sector_indices)} sectoral"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Error calculating indices data: {e}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                "indices": [],
                "major_indices": [],
                "sector_indices": [],
                "summary": {"total_indices": 0, "major_up": 0, "major_down": 0},
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_market_sentiment(self) -> Dict[str, Any]:
        """COMPLETE: Market sentiment analysis"""
        if not self._should_recalculate("market_sentiment"):
            return self.cache.get("market_sentiment", {"sentiment": "neutral"})

        try:
            from services.instrument_registry import instrument_registry

            # Get comprehensive market summary
            try:
                market_summary = instrument_registry.get_market_summary()
            except AttributeError:
                # Fallback: calculate manually
                market_summary = self._calculate_market_summary_manually()

            if "error" in market_summary:
                return {"sentiment": "unknown", "error": market_summary["error"]}

            # Calculate sentiment metrics
            breadth_pct = market_summary.get("market_breadth_percent", 0)
            adv_dec_ratio = market_summary.get("advance_decline_ratio", 1)

            # Determine sentiment
            if breadth_pct >= 30:
                sentiment = "very_bullish"
                confidence = min(100, breadth_pct + 30)
            elif breadth_pct >= 10:
                sentiment = "bullish"
                confidence = min(100, breadth_pct + 40)
            elif breadth_pct >= -10:
                sentiment = "neutral"
                confidence = 100 - abs(breadth_pct) * 3
            elif breadth_pct >= -30:
                sentiment = "bearish"
                confidence = min(100, abs(breadth_pct) + 40)
            else:
                sentiment = "very_bearish"
                confidence = min(100, abs(breadth_pct) + 30)

            # Volume analysis
            volume_stats = market_summary.get("volume_stats", {})
            high_volume_participation = volume_stats.get("high_volume_stocks", 0)

            # Sector analysis
            sector_performance = market_summary.get("sector_performance", {})
            bullish_sectors = len(
                [
                    s
                    for s in sector_performance.values()
                    if s.get("avg_change_percent", 0) > 1
                ]
            )
            bearish_sectors = len(
                [
                    s
                    for s in sector_performance.values()
                    if s.get("avg_change_percent", 0) < -1
                ]
            )

            result = {
                "sentiment": sentiment,
                "confidence": round(confidence, 1),
                "sentiment_score": breadth_pct,
                "market_breadth": {
                    "total_stocks": market_summary.get("total_stocks", 0),
                    "advancing": market_summary.get("advancing", 0),
                    "declining": market_summary.get("declining", 0),
                    "unchanged": market_summary.get("unchanged", 0),
                    "advance_decline_ratio": adv_dec_ratio,
                    "breadth_percentage": breadth_pct,
                },
                "volume_analysis": {
                    "total_volume": volume_stats.get("total_volume", 0),
                    "average_volume": volume_stats.get("average_volume", 0),
                    "high_volume_stocks": high_volume_participation,
                    "volume_trend": (
                        "high" if high_volume_participation > 50 else "normal"
                    ),
                },
                "sector_sentiment": {
                    "bullish_sectors": bullish_sectors,
                    "bearish_sectors": bearish_sectors,
                    "total_sectors": len(sector_performance),
                    "sector_breadth": (
                        (bullish_sectors - bearish_sectors) / len(sector_performance)
                        if sector_performance
                        else 0
                    ),
                },
                "market_indicators": market_summary.get("market_indicators", {}),
                "interpretation": self._interpret_sentiment(
                    sentiment, confidence, breadth_pct
                ),
                "timestamp": datetime.now().isoformat(),
            }

            self.cache["market_sentiment"] = result
            self._mark_calculated("market_sentiment")
            return result

        except Exception as e:
            logger.error(f"Error calculating market sentiment: {e}")
            return {"sentiment": "unknown", "error": str(e)}

    def get_volume_analysis(self, force_refresh: bool = False) -> Dict[str, Any]:
        """COMPLETE: Volume analysis with enriched data"""
        if not force_refresh and not self._should_recalculate("volume_analysis"):
            return self.cache.get("volume_analysis", {"volume_leaders": []})

        try:
            from services.instrument_registry import instrument_registry

            # Get volume leaders
            try:
                volume_leaders = instrument_registry.get_volume_leaders(20)
            except AttributeError:
                # Fallback: calculate manually
                volume_leaders = self._calculate_volume_leaders_manually(20)

            # Analyze volume patterns
            try:
                all_stocks = list(self._get_cached_enriched_data().values())
            except AttributeError:
                all_stocks = []

            volumes = [s.get("volume", 0) for s in all_stocks if s.get("volume", 0) > 0]

            if not volumes:
                return {"volume_leaders": [], "error": "No volume data available"}

            # Calculate volume statistics
            total_volume = sum(volumes)
            avg_volume = total_volume / len(volumes)
            max_volume = max(volumes)

            # Categorize by volume
            high_volume_threshold = avg_volume * 3
            unusual_volume_stocks = [
                s for s in all_stocks if s.get("volume", 0) > high_volume_threshold
            ]

            # Sector volume analysis
            sector_volumes = {}
            try:
                sector_data = instrument_registry.get_stocks_by_sector()
            except AttributeError:
                sector_data = {}

            for sector, stocks in sector_data.items():
                sector_volume = sum(s.get("volume", 0) for s in stocks)
                if sector_volume > 0:
                    sector_volumes[sector] = {
                        "total_volume": sector_volume,
                        "avg_volume": sector_volume / len(stocks),
                        "stock_count": len(stocks),
                        "high_volume_stocks": len(
                            [
                                s
                                for s in stocks
                                if s.get("volume", 0) > high_volume_threshold
                            ]
                        ),
                    }

            result = {
                "volume_leaders": volume_leaders[:15],
                "unusual_volume": unusual_volume_stocks[:10],
                "volume_statistics": {
                    "total_market_volume": total_volume,
                    "average_volume": round(avg_volume, 0),
                    "max_volume": max_volume,
                    "high_volume_threshold": round(high_volume_threshold, 0),
                    "stocks_with_volume": len(volumes),
                    "high_volume_stocks": len(unusual_volume_stocks),
                },
                "sector_volumes": dict(
                    sorted(
                        sector_volumes.items(),
                        key=lambda x: x[1]["total_volume"],
                        reverse=True,
                    )
                ),
                "volume_insights": {
                    "market_participation": (
                        "high" if len(unusual_volume_stocks) > 100 else "normal"
                    ),
                    "volume_concentration": (
                        round(
                            sum(s.get("volume", 0) for s in volume_leaders[:10])
                            / total_volume
                            * 100,
                            1,
                        )
                        if total_volume > 0
                        else 0
                    ),
                    "breadth_indicator": (
                        len([s for s in all_stocks if s.get("volume", 0) > avg_volume])
                        / len(all_stocks)
                        if all_stocks
                        else 0
                    ),
                },
                "timestamp": datetime.now().isoformat(),
            }

            self.cache["volume_analysis"] = result
            self._mark_calculated("volume_analysis")
            return result

        except Exception as e:
            logger.error(f"Error calculating volume analysis: {e}")
            return {"volume_leaders": [], "error": str(e)}

    # MISSING METHODS - ADD THESE:

    def get_gap_analysis(self) -> Dict[str, Any]:
        """Enhanced gap analysis using premarket candle builder service"""
        if not self._should_recalculate("gap_analysis"):
            return self.cache.get("gap_analysis", {"gap_up": [], "gap_down": []})

        try:
            # Use premarket candle builder for gap analysis
            import asyncio
            from services.premarket_candle_builder import get_todays_gaps

            # Get today's gaps from premarket candle builder
            try:
                # Try to get existing event loop
                loop = asyncio.get_running_loop()
                # Create a task instead of run_until_complete to avoid blocking
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_todays_gaps())
                    all_gaps = future.result(timeout=10)
            except RuntimeError:
                # No event loop running, safe to use run_until_complete
                all_gaps = asyncio.run(get_todays_gaps())

            # Separate gap up and gap down
            gap_up = [g for g in all_gaps if g["gap_percentage"] > 0]
            gap_down = [g for g in all_gaps if g["gap_percentage"] < 0]

            # Categorize by size
            gap_up_small = [g for g in gap_up if 0.5 <= g["gap_percentage"] < 2.5]
            gap_up_medium = [g for g in gap_up if 2.5 <= g["gap_percentage"] < 5.0]
            gap_up_large = [g for g in gap_up if g["gap_percentage"] >= 5.0]

            gap_down_small = [g for g in gap_down if -2.5 < g["gap_percentage"] <= -0.5]
            gap_down_medium = [
                g for g in gap_down if -5.0 < g["gap_percentage"] <= -2.5
            ]
            gap_down_large = [g for g in gap_down if g["gap_percentage"] <= -5.0]

            # Calculate averages
            avg_gap_up = (
                sum(g["gap_percentage"] for g in gap_up) / len(gap_up) if gap_up else 0
            )
            avg_gap_down = (
                sum(g["gap_percentage"] for g in gap_down) / len(gap_down)
                if gap_down
                else 0
            )

            # Sort for top gaps
            top_gap_up = sorted(
                gap_up, key=lambda x: x["gap_percentage"], reverse=True
            )[:10]
            top_gap_down = sorted(
                gap_down, key=lambda x: abs(x["gap_percentage"]), reverse=True
            )[:10]

            result = {
                "gap_up": gap_up,
                "gap_down": gap_down,
                "gap_up_small": gap_up_small,
                "gap_up_medium": gap_up_medium,
                "gap_up_large": gap_up_large,
                "gap_down_small": gap_down_small,
                "gap_down_medium": gap_down_medium,
                "gap_down_large": gap_down_large,
                "recent_gaps": all_gaps[:15],  # Most recent 15
                "top_gap_up": top_gap_up,
                "top_gap_down": top_gap_down,
                "summary": {
                    "total_gap_up": len(gap_up),
                    "total_gap_down": len(gap_down),
                    "total_gaps_today": len(all_gaps),
                    "market_status": "premarket_data",
                    "avg_gap_up": round(avg_gap_up, 2),
                    "avg_gap_down": round(avg_gap_down, 2),
                },
                "timestamp": datetime.now().isoformat(),
                "data_source": "premarket_candle_builder",
                "capture_window": "9:00-9:08 AM IST",
            }

            self.cache["gap_analysis"] = result
            self._mark_calculated("gap_analysis")

            logger.info(
                f"📊 Premarket gap analysis: {result['summary']['total_gaps_today']} gaps from 9:00-9:08 AM"
            )
            return result

        except Exception as e:
            logger.error(f"Error getting premarket gap analysis: {e}")
            # Fallback to basic calculation
            return self._calculate_gap_analysis_fallback()

    def _calculate_avg_gap(self, gaps: list, positive: bool = True) -> float:
        """Calculate average gap percentage"""
        if not gaps:
            return 0.0

        gap_percentages = [g.get("gap_percent", 0) for g in gaps]
        if positive:
            gap_percentages = [g for g in gap_percentages if g > 0]
        else:
            gap_percentages = [g for g in gap_percentages if g < 0]

        return sum(gap_percentages) / len(gap_percentages) if gap_percentages else 0.0

    def _calculate_gap_analysis_fallback(self) -> Dict[str, Any]:
        """Fallback gap analysis method"""
        try:
            stocks = self.get_all_live_stocks()
            gap_up = []
            gap_down = []

            for stock in stocks:
                gap_percent = stock.get("gap_percent", 0)
                if gap_percent > 1.0:  # Reduced threshold for better detection
                    gap_up.append(stock)
                elif gap_percent < -1.0:  # Reduced threshold for better detection
                    gap_down.append(stock)

            # Sort by gap percentage
            gap_up.sort(key=lambda x: x.get("gap_percent", 0), reverse=True)
            gap_down.sort(key=lambda x: x.get("gap_percent", 0))

            result = {
                "gap_up": gap_up[:20],
                "gap_down": gap_down[:20],
                "summary": {
                    "total_gap_up": len(gap_up),
                    "total_gap_down": len(gap_down),
                    "avg_gap_up": (
                        sum(s.get("gap_percent", 0) for s in gap_up) / len(gap_up)
                        if gap_up
                        else 0
                    ),
                    "avg_gap_down": (
                        sum(s.get("gap_percent", 0) for s in gap_down) / len(gap_down)
                        if gap_down
                        else 0
                    ),
                },
                "timestamp": datetime.now().isoformat(),
                "data_source": "fallback_calculation",
            }

            self.cache["gap_analysis"] = result
            self._mark_calculated("gap_analysis")
            return result

        except Exception as e:
            logger.error(f"Error in fallback gap analysis: {e}")
            return {
                "gap_up": [],
                "gap_down": [],
                "error": str(e),
                "data_source": "error",
            }

    def get_breakout_analysis(self) -> Dict[str, Any]:
        """Get breakout analysis using the proper breakout detection service"""
        if not self._should_recalculate("breakout_analysis"):
            return self.cache.get(
                "breakout_analysis", {"breakouts": [], "breakdowns": []}
            )

        try:
            # 🚀 PRIMARY: Use Enhanced Breakout Engine (NEW)
            if (
                ENHANCED_BREAKOUT_SERVICE_AVAILABLE
                and enhanced_breakout_engine.is_running
            ):
                logger.info("🔥 Using Enhanced Breakout Engine for real-time analysis")

                # Get comprehensive breakout data from enhanced engine
                enhanced_data = enhanced_breakout_engine.get_breakouts_summary()

                # Extract breakouts and breakdowns
                breakouts = enhanced_data.get("breakouts", [])
                breakdowns = enhanced_data.get("breakdowns", [])
                summary = enhanced_data.get("summary", {})
                engine_metrics = enhanced_data.get("engine_metrics", {})

                result = {
                    "breakouts": breakouts[:25],  # Top 25 breakouts
                    "breakdowns": breakdowns[:25],  # Top 25 breakdowns
                    "summary": {
                        "total_breakouts": summary.get(
                            "total_breakouts", len(breakouts)
                        ),
                        "total_breakdowns": summary.get(
                            "total_breakdowns", len(breakdowns)
                        ),
                        "total_today": summary.get(
                            "total_today", len(breakouts) + len(breakdowns)
                        ),
                        "detection_active": summary.get(
                            "detection_active", enhanced_breakout_engine.is_running
                        ),
                        "is_trading_hours": summary.get(
                            "is_trading_hours", enhanced_breakout_engine.is_market_open
                        ),
                        "last_update": summary.get(
                            "last_update", datetime.now().isoformat()
                        ),
                        # Enhanced metrics from the engine
                        "engine_status": "enhanced_active",
                        "instruments_tracked": engine_metrics.get(
                            "instruments_tracked", 0
                        ),
                        "avg_processing_time_ms": engine_metrics.get(
                            "avg_processing_time_ms", 0
                        ),
                        "memory_usage_mb": engine_metrics.get("memory_usage_mb", 0),
                        "detection_accuracy": engine_metrics.get(
                            "detection_accuracy", 0
                        ),
                    },
                    "timestamp": datetime.now().isoformat(),
                    "data_source": "enhanced_breakout_engine",
                    # Additional enhanced data
                    "top_breakouts": enhanced_data.get("top_breakouts", [])[:10],
                    "recent_breakouts": enhanced_data.get("recent_breakouts", [])[:10],
                    "breakouts_by_type": enhanced_data.get("breakouts_by_type", {}),
                }

            else:
                # Fallback if breakout service is not available
                logger.warning(
                    "Breakout detection service not available, returning empty result"
                )
                result = {
                    "breakouts": [],
                    "breakdowns": [],
                    "summary": {
                        "total_breakouts": 0,
                        "total_breakdowns": 0,
                        "error": "Breakout detection service not available",
                    },
                    "timestamp": datetime.now().isoformat(),
                }
                return result

        except Exception as e:
            logger.error(f"Error calculating breakout analysis: {e}")
            return {
                "breakouts": [],
                "breakdowns": [],
                "error": str(e),
                "data_source": "error",
            }

    def get_market_breadth(self) -> Dict[str, Any]:
        """Market breadth analysis"""
        try:
            stocks = self.get_all_live_stocks()

            advancing = len([s for s in stocks if s.get("change_percent", 0) > 0])
            declining = len([s for s in stocks if s.get("change_percent", 0) < 0])
            unchanged = len(stocks) - advancing - declining

            return {
                "total_stocks": len(stocks),
                "advancing": advancing,
                "declining": declining,
                "unchanged": unchanged,
                "advance_decline_ratio": (
                    advancing / declining if declining > 0 else float("inf")
                ),
                "breadth_percentage": (
                    ((advancing - declining) / len(stocks)) * 100 if stocks else 0
                ),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error calculating market breadth: {e}")
            return {"error": str(e)}

    def get_intraday_highlights(self) -> Dict[str, Any]:
        """Intraday highlights and opportunities"""
        return self.get_intraday_stocks()

    def get_intraday_stocks(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Intraday stock opportunities with enhanced FNO stock inclusion - real-time capable"""
        # Skip cache for real-time updates if requested
        if not force_refresh and not self._should_recalculate("intraday_stocks"):
            cached = self.cache.get("intraday_stocks")
            if cached:
                return cached

        try:
            stocks = self.get_all_live_stocks()

            # Get FNO-eligible stocks specifically
            fno_stocks = self._get_fno_eligible_stocks(stocks)

            # Filter for high momentum and high volume stocks
            high_momentum = [s for s in stocks if abs(s.get("change_percent", 0)) > 3]
            high_volume = [s for s in stocks if s.get("volume", 0) > 1000000]

            # FNO-specific filters with lower thresholds
            fno_momentum = [
                s for s in fno_stocks if abs(s.get("change_percent", 0)) > 1.5
            ]
            fno_volume = [s for s in fno_stocks if s.get("volume", 0) > 500000]

            # Combine all candidates with priority for FNO stocks
            all_candidates = []
            seen = set()

            # Add FNO stocks first (higher priority)
            for stock in fno_momentum + fno_volume:
                symbol = stock.get("symbol")
                if symbol not in seen:
                    stock["is_fno"] = True
                    stock["priority"] = "high"
                    all_candidates.append(stock)
                    seen.add(symbol)

            # Add other high momentum/volume stocks
            for stock in high_momentum + high_volume:
                symbol = stock.get("symbol")
                if symbol not in seen:
                    stock["is_fno"] = symbol in [s.get("symbol") for s in fno_stocks]
                    stock["priority"] = "normal"
                    all_candidates.append(stock)
                    seen.add(symbol)

            # Sort by FNO status and performance
            all_candidates.sort(
                key=lambda x: (
                    not x.get("is_fno", False),  # FNO stocks first
                    -abs(x.get("change_percent", 0)),  # Then by performance
                    -x.get("volume", 0),  # Then by volume
                )
            )

            return {
                "high_momentum": high_momentum[:15],
                "high_volume": high_volume[:15],
                "fno_momentum": fno_momentum[:15],
                "fno_volume": fno_volume[:15],
                "all_candidates": all_candidates[:50],  # Increased limit for FNO
                "fno_candidates": [s for s in all_candidates if s.get("is_fno", False)][
                    :25
                ],
                "summary": {
                    "total_high_momentum": len(high_momentum),
                    "total_high_volume": len(high_volume),
                    "total_fno_momentum": len(fno_momentum),
                    "total_fno_volume": len(fno_volume),
                    "total_candidates": len(all_candidates),
                    "total_fno_candidates": len(
                        [s for s in all_candidates if s.get("is_fno", False)]
                    ),
                },
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error calculating intraday stocks: {e}")
            return {"all_candidates": [], "error": str(e)}

    def _get_fno_eligible_stocks(
        self, stocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get FNO eligible stocks from the stock list"""
        try:
            # Try to get FNO stock list from service
            from services.fno_stock_service import get_fno_stocks_from_file

            fno_data = get_fno_stocks_from_file()
            fno_symbols = set()

            if fno_data:
                fno_symbols = {
                    stock.get("symbol", "").upper()
                    for stock in fno_data
                    if stock.get("symbol")
                }

            # Fallback: common FNO stocks if service not available
            if not fno_symbols:
                fno_symbols = {
                    "NIFTY",
                    "BANKNIFTY",
                    "FINNIFTY",
                    "MIDCPNIFTY",
                    "RELIANCE",
                    "TCS",
                    "INFY",
                    "HDFCBANK",
                    "ICICIBANK",
                    "HDFC",
                    "KOTAKBANK",
                    "SBI",
                    "BAJFINANCE",
                    "BHARTIARTL",
                    "ITC",
                    "ASIANPAINT",
                    "MARUTI",
                    "LT",
                    "ULTRACEMCO",
                }

            # Filter stocks that are FNO eligible
            fno_stocks = []
            for stock in stocks:
                symbol = stock.get("symbol", "").upper()
                if symbol in fno_symbols:
                    stock_copy = stock.copy()
                    stock_copy["has_fno"] = True
                    fno_stocks.append(stock_copy)

            logger.info(
                f"📊 Found {len(fno_stocks)} FNO eligible stocks out of {len(stocks)} total stocks"
            )
            return fno_stocks

        except Exception as e:
            logger.error(f"Error getting FNO eligible stocks: {e}")
            # Return empty list to avoid breaking the main function
            return []

    def get_performance_summary(self) -> Dict[str, Any]:
        """Performance summary statistics"""
        try:
            stocks = self.get_all_live_stocks()

            if not stocks:
                return {"error": "No stocks data available"}

            changes = [s.get("change_percent", 0) for s in stocks]

            return {
                "total_stocks": len(stocks),
                "avg_change": sum(changes) / len(changes),
                "max_gainer": max(changes),
                "max_loser": min(changes),
                "positive_stocks": len([c for c in changes if c > 0]),
                "negative_stocks": len([c for c in changes if c < 0]),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error calculating performance summary: {e}")
            return {"error": str(e)}

    def get_top_movers(self) -> Dict[str, Any]:
        """Get top moving stocks - required by auto stock selection"""
        try:
            # Use existing _calculate_top_movers_manually method
            return self._calculate_top_movers_manually(limit=20)
        except Exception as e:
            logger.error(f"Error getting top movers: {e}")
            return {"gainers": [], "losers": [], "error": str(e)}

    def get_record_movers(self) -> Dict[str, Any]:
        """Stocks making new highs and lows"""
        try:
            stocks = self.get_all_live_stocks()

            new_highs = []
            new_lows = []

            for stock in stocks:
                ltp = stock.get("last_price", 0) or stock.get(
                    "ltp", 0
                )  # Support both field names
                high = stock.get("high", 0)
                low = stock.get("low", 0)

                if ltp > 0 and high > 0:
                    # Near 52-week high (simplified)
                    if (ltp / high) >= 0.99:
                        new_highs.append(stock)
                    elif low > 0 and (ltp / low) <= 1.01:
                        new_lows.append(stock)

            return {
                "new_highs": new_highs[:20],
                "new_lows": new_lows[:20],
                "summary": {
                    "total_new_highs": len(new_highs),
                    "total_new_lows": len(new_lows),
                },
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error calculating record movers: {e}")
            return {"new_highs": [], "new_lows": [], "error": str(e)}

    # FALLBACK CALCULATION METHODS:

    def _calculate_top_movers_manually(self, limit: int = 20) -> Dict[str, Any]:
        """Manual calculation of top movers"""
        try:
            stocks = self.get_all_live_stocks()

            # Sort by change percentage
            gainers = sorted(
                stocks, key=lambda x: x.get("change_percent", 0), reverse=True
            )[:limit]
            losers = sorted(stocks, key=lambda x: x.get("change_percent", 0))[:limit]

            return {
                "gainers": gainers,
                "losers": losers,
                "total_stocks_analyzed": len(stocks),
            }
        except Exception as e:
            logger.error(f"Error in manual top movers calculation: {e}")
            return {"gainers": [], "losers": [], "total_stocks_analyzed": 0}

    def _calculate_sector_analysis_manually(self) -> Dict[str, Any]:
        """FIXED: Manual calculation of sector analysis using enriched prices"""
        try:
            # Get all enriched prices from registry
            from services.instrument_registry import instrument_registry

            all_stocks = list(self._get_cached_enriched_data().values())

            if not all_stocks:
                logger.warning("⚠️ No enriched prices available for sector analysis")
                return {"sector_analysis": {}}

            logger.info(f"📊 Analyzing {len(all_stocks)} stocks for sector breakdown")

            sectors = {}

            for stock in all_stocks:
                try:
                    sector = stock.get("sector", "OTHER")
                    if sector not in sectors:
                        sectors[sector] = {
                            "stocks": [],
                            "total_stocks": 0,
                            "advancing": 0,
                            "declining": 0,
                            "unchanged": 0,
                            "total_volume": 0,
                        }

                    sectors[sector]["stocks"].append(stock)
                    sectors[sector]["total_stocks"] += 1
                    sectors[sector]["total_volume"] += stock.get("volume", 0)

                    change_pct = stock.get("change_percent", 0)
                    if change_pct > 0:
                        sectors[sector]["advancing"] += 1
                    elif change_pct < 0:
                        sectors[sector]["declining"] += 1
                    else:
                        sectors[sector]["unchanged"] += 1

                except Exception as e:
                    logger.warning(f"⚠️ Error processing stock for sector analysis: {e}")
                    continue

            # Calculate averages and build final analysis
            sector_analysis = {}
            for sector, data in sectors.items():
                if data["stocks"]:
                    stock_changes = [s.get("change_percent", 0) for s in data["stocks"]]
                    avg_change = sum(stock_changes) / len(stock_changes)

                    # Find top and worst performers
                    top_performer = max(
                        data["stocks"], key=lambda x: x.get("change_percent", 0)
                    )
                    worst_performer = min(
                        data["stocks"], key=lambda x: x.get("change_percent", 0)
                    )

                    sector_analysis[sector] = {
                        "total_stocks": data["total_stocks"],
                        "avg_change_percent": round(avg_change, 2),
                        "advancing": data["advancing"],
                        "declining": data["declining"],
                        "unchanged": data["unchanged"],
                        "strength_score": round(
                            (data["advancing"] - data["declining"])
                            / data["total_stocks"]
                            * 100,
                            2,
                        ),
                        "total_volume": data["total_volume"],
                        "top_performer": {
                            "symbol": top_performer.get("symbol", "N/A"),
                            "name": top_performer.get("name", "N/A"),
                            "change_percent": top_performer.get("change_percent", 0),
                        },
                        "worst_performer": {
                            "symbol": worst_performer.get("symbol", "N/A"),
                            "name": worst_performer.get("name", "N/A"),
                            "change_percent": worst_performer.get("change_percent", 0),
                        },
                    }

            logger.info(
                f"📊 Manual sector analysis completed for {len(sector_analysis)} sectors"
            )
            return {"sector_analysis": sector_analysis}

        except Exception as e:
            logger.error(f"Error in manual sector analysis: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"sector_analysis": {}}

    def _calculate_breadth_ratio(self, sector_data: dict) -> float:
        """Calculate breadth ratio for a sector"""
        advancing = sector_data.get("advancing", 0)
        declining = sector_data.get("declining", 0)

        if advancing + declining == 0:
            return 0.5  # Neutral when no movement

        return round(advancing / (advancing + declining), 3)

    def _calculate_market_summary_manually(self) -> Dict[str, Any]:
        """Manual calculation of market summary"""
        try:
            stocks = self.get_all_live_stocks()

            if not stocks:
                return {"error": "No stocks data available"}

            advancing = len([s for s in stocks if s.get("change_percent", 0) > 0])
            declining = len([s for s in stocks if s.get("change_percent", 0) < 0])
            unchanged = len(stocks) - advancing - declining

            total_volume = sum(s.get("volume", 0) for s in stocks)
            avg_volume = total_volume / len(stocks) if stocks else 0
            high_volume_stocks = len(
                [s for s in stocks if s.get("volume", 0) > avg_volume * 2]
            )

            adv_dec_ratio = advancing / declining if declining > 0 else float("inf")
            breadth_pct = ((advancing - declining) / len(stocks)) * 100 if stocks else 0

            return {
                "total_stocks": len(stocks),
                "advancing": advancing,
                "declining": declining,
                "unchanged": unchanged,
                "advance_decline_ratio": adv_dec_ratio,
                "market_breadth_percent": breadth_pct,
                "volume_stats": {
                    "total_volume": total_volume,
                    "average_volume": avg_volume,
                    "high_volume_stocks": high_volume_stocks,
                },
                "sector_performance": {},  # Would need more complex calculation
                "market_indicators": {
                    "trend": (
                        "bullish"
                        if breadth_pct > 10
                        else "bearish" if breadth_pct < -10 else "neutral"
                    ),
                    "volatility": "normal",  # Placeholder
                },
            }
        except Exception as e:
            logger.error(f"Error in manual market summary: {e}")
            return {"error": str(e)}

    def _calculate_volume_leaders_manually(
        self, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Manual calculation of volume leaders"""
        try:
            stocks = self.get_all_live_stocks()

            # Filter stocks with volume data and sort by volume
            volume_stocks = [s for s in stocks if s.get("volume", 0) > 0]
            volume_leaders = sorted(
                volume_stocks, key=lambda x: x.get("volume", 0), reverse=True
            )

            return volume_leaders[:limit]
        except Exception as e:
            logger.error(f"Error in manual volume leaders calculation: {e}")
            return []

    # HELPER METHODS
    def _categorize_by_price(self, price: float) -> str:
        """Categorize stock by price range"""
        if price >= 1000:
            return "high_price"
        elif price >= 100:
            return "medium_price"
        else:
            return "low_price"

    def _categorize_volume(self, volume: int) -> str:
        """Categorize volume level"""
        if volume >= 1000000:
            return "very_high"
        elif volume >= 100000:
            return "high"
        elif volume >= 10000:
            return "medium"
        else:
            return "low"

    def _categorize_performance(self, change_percent: float) -> str:
        """Categorize performance"""
        if change_percent >= 5:
            return "strong_gainer"
        elif change_percent >= 1:
            return "gainer"
        elif change_percent <= -5:
            return "strong_loser"
        elif change_percent <= -1:
            return "loser"
        else:
            return "neutral"

    def _categorize_sector_performance(self, avg_change: float) -> str:
        """Categorize sector performance"""
        if avg_change >= 2:
            return "outperforming"
        elif avg_change >= 0.5:
            return "positive"
        elif avg_change <= -2:
            return "underperforming"
        elif avg_change <= -0.5:
            return "negative"
        else:
            return "neutral"

    def _calculate_sector_momentum(self, sector_data: dict) -> str:
        """Calculate sector momentum"""
        strength_score = sector_data.get("strength_score", 0)
        if strength_score >= 60:
            return "strong_bullish"
        elif strength_score >= 20:
            return "bullish"
        elif strength_score <= -60:
            return "strong_bearish"
        elif strength_score <= -20:
            return "bearish"
        else:
            return "sideways"

    def _interpret_sentiment(
        self, sentiment: str, confidence: float, breadth: float
    ) -> str:
        """Provide sentiment interpretation"""
        interpretations = {
            "very_bullish": f"Strong bullish sentiment with {breadth:.1f}% market breadth. Broad-based buying across sectors.",
            "bullish": f"Positive market sentiment with {breadth:.1f}% breadth. More stocks advancing than declining.",
            "neutral": f"Neutral market with {breadth:.1f}% breadth. Mixed signals across sectors.",
            "bearish": f"Negative sentiment with {breadth:.1f}% breadth. Selling pressure evident.",
            "very_bearish": f"Strong bearish sentiment with {breadth:.1f}% breadth. Broad-based selling.",
        }
        return interpretations.get(sentiment, "Market sentiment unclear.")

    def _should_recalculate(self, feature: str) -> bool:
        """Check if feature should be recalculated - optimized for real-time"""
        if feature not in self.last_calculated:
            return True

        last_calc = self.last_calculated[feature]
        # Real-time TTL for different features
        ttl = (
            0.5
            if feature in ["top_movers", "intraday_stocks", "market_sentiment"]
            else 1
        )
        return (datetime.now() - last_calc).total_seconds() > ttl

    def _mark_calculated(self, feature: str):
        """Mark feature as calculated"""
        self.last_calculated[feature] = datetime.now()

    def _get_cache_status(self) -> Dict[str, str]:
        """Get cache status for all features"""
        features = [
            "top_movers",
            "sector_heatmap",
            "market_sentiment",
            "volume_analysis",
            "gap_analysis",
            "breakout_analysis",
            "indices_data",
        ]
        status = {}

        for feature in features:
            if feature in self.last_calculated:
                age = (datetime.now() - self.last_calculated[feature]).total_seconds()
                status[feature] = f"cached_{int(age)}s_ago"
            else:
                status[feature] = "not_calculated"

        return status

    # ADD to END of enhanced_market_analytics_service.py


# 🚀 OPTIMIZED: Enhanced analytics with new callback system
def setup_analytics_events():
    """🚀 NEW: Connect enhanced analytics using optimized callback system"""
    try:
        from services.instrument_registry import instrument_registry

        def optimized_analytics_callback(analytics_payload):
            """🚀 NEW: Optimized analytics callback with selective processing"""
            try:
                updated_instruments = analytics_payload.get("updated_instruments", [])
                stats = analytics_payload.get("stats", {})

                # Only process significant updates (avoid unnecessary calculations)
                enriched_count = stats.get("enriched", 0)
                if enriched_count < 5:  # Skip minor updates
                    return

                logger.debug(
                    f"🔄 Analytics processing: {len(updated_instruments)} instruments, {enriched_count} enriched"
                )

                # Selective cache clearing instead of full clear
                cache_keys_to_remove = []
                for instrument_key in updated_instruments:
                    # Remove cache entries related to updated instruments
                    for cache_key in list(enhanced_analytics.cache.keys()):
                        if instrument_key in str(cache_key) or "top_movers" in str(
                            cache_key
                        ):
                            cache_keys_to_remove.append(cache_key)

                # Clear selective cache entries
                for key in cache_keys_to_remove:
                    enhanced_analytics.cache.pop(key, None)
                    enhanced_analytics.last_calculated.pop(key, None)

                # 🚀 NEW: Invalidate enriched data cache to force refresh
                enhanced_analytics._invalidate_enriched_data_cache()

                # Background analytics refresh (non-blocking)
                if enriched_count > 20:  # Only for significant updates
                    import asyncio

                    asyncio.create_task(background_analytics_refresh())

            except Exception as e:
                logger.error(f"❌ Error in optimized analytics callback: {e}")

        # 🚀 NEW: Register with optimized callback system (ZERO DELAY for strategies)
        success = instrument_registry.register_analytics_callback(
            optimized_analytics_callback, "enhanced_market_analytics_optimized"
        )

        if success:
            logger.info("✅ Enhanced analytics connected to OPTIMIZED callback system")
        else:
            logger.error("❌ Failed to register optimized analytics callback")

    except Exception as e:
        logger.error(f"❌ Optimized analytics setup failed: {e}")


async def background_analytics_refresh():
    """Background analytics refresh to avoid blocking real-time data"""
    try:
        logger.debug("🔄 Background analytics refresh started")
        # Refresh analytics in background without blocking strategies
        enhanced_analytics.get_complete_analytics()
        logger.debug("✅ Background analytics refresh completed")
    except Exception as e:
        logger.error(f"❌ Background analytics refresh failed: {e}")


# Create service instance
enhanced_analytics = EnhancedMarketAnalyticsService()

# ✅ REMOVED: Old redundant event setup
# Old system called get_complete_analytics() on EVERY price update (performance killer)
# New system uses selective cache clearing and background processing

# Setup optimized analytics events
setup_analytics_events()
