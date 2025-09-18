#!/usr/bin/env python3
"""
Unified Gap Detection Service

This service provides centralized gap up/down detection for all market instruments
with real-time analysis and alert generation.

Key Features:
- Real-time gap detection from live market data
- Support for multiple gap types (gap up, gap down, no gap)
- Gap strength classification (weak, moderate, strong, very strong)
- Volume confirmation analysis
- Sector-wise gap analysis
- Alert generation and broadcasting
- Performance tracking and analytics
"""

import asyncio
import logging
from datetime import datetime, time as dt_time, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class GapType(Enum):
    """Gap types"""
    GAP_UP = "GAP_UP"
    GAP_DOWN = "GAP_DOWN"
    NO_GAP = "NO_GAP"


class GapStrength(Enum):
    """Gap strength levels"""
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


class AlertPriority(Enum):
    """Alert priority levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class GapAnalysis:
    """Gap analysis result for a single instrument"""
    symbol: str
    instrument_key: str
    current_price: Decimal
    previous_close: Decimal
    open_price: Decimal
    gap_percentage: Decimal
    gap_type: GapType
    gap_strength: GapStrength
    volume: int
    volume_ratio: Optional[Decimal] = None
    has_volume_confirmation: bool = False
    sector: str = "OTHER"
    market_cap_category: str = "UNKNOWN"
    timestamp: datetime = field(default_factory=datetime.now)
    confidence_score: Decimal = field(default_factory=lambda: Decimal("0.5"))
    alert_priority: AlertPriority = AlertPriority.LOW
    is_significant: bool = False


@dataclass
class GapDetectionStats:
    """Gap detection statistics"""
    total_instruments_analyzed: int = 0
    gaps_detected: int = 0
    gap_up_count: int = 0
    gap_down_count: int = 0
    significant_gaps: int = 0
    alerts_generated: int = 0
    avg_processing_time_ms: float = 0.0
    last_analysis_time: Optional[datetime] = None
    session_date: date = field(default_factory=date.today)


class UnifiedGapDetectionService:
    """
    Unified service for real-time gap detection across all market instruments
    """
    
    def __init__(self):
        # Gap thresholds (configurable)
        self.min_gap_threshold = Decimal("0.5")      # 0.5% minimum for gap
        self.moderate_gap_threshold = Decimal("2.5")  # 2.5% for moderate
        self.strong_gap_threshold = Decimal("5.0")    # 5.0% for strong
        self.very_strong_gap_threshold = Decimal("8.0")  # 8.0% for very strong
        
        # Significant gap threshold
        self.significant_gap_threshold = Decimal("1.0")  # 1.0% for significance
        
        # Current session data
        self.current_gaps: Dict[str, GapAnalysis] = {}
        self.previous_closes: Dict[str, Decimal] = {}
        self.session_stats = GapDetectionStats()
        
        # Performance tracking
        self.processing_times: List[float] = []
        self.last_snapshot_time: Optional[datetime] = None
        
        # Market timing
        self.premarket_start = dt_time(9, 0)
        self.premarket_end = dt_time(9, 8)
        self.market_open = dt_time(9, 15)
        
        # Hub integration
        self.registered_with_hub = False
        
        logger.info("✅ Unified Gap Detection Service initialized")

    async def register_with_realtime_hub(self) -> bool:
        """Register this service with the real-time data hub"""
        try:
            from services.realtime_data_hub import get_realtime_data_hub
            
            hub = get_realtime_data_hub()
            
            success = hub.register_gap_detection_service(
                callback=self._handle_market_data
            )
            
            if success:
                self.registered_with_hub = True
                logger.info("✅ Gap detection service registered with real-time hub")
                return True
            else:
                logger.error("❌ Failed to register with real-time hub")
                return False
                
        except ImportError as e:
            logger.error(f"Real-time hub not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error registering with real-time hub: {e}")
            return False

    async def _handle_market_data(self, raw_data: Dict[str, Any]) -> None:
        """Handle incoming market data for gap detection"""
        start_time = datetime.now()
        
        try:
            # Only process feeds data for gap detection
            if "feeds" not in raw_data:
                return
            
            feeds = raw_data.get("feeds", {})
            if not feeds:
                return
            
            # Determine if this is a snapshot (initial data load)
            is_snapshot = len(feeds) > 100
            
            if is_snapshot:
                logger.info(f"📸 Processing snapshot with {len(feeds)} instruments for gap detection")
                # Load previous closes for gap calculation
                await self._load_previous_closes()
            
            # Process all instruments
            gap_analyses = []
            for instrument_key, feed_data in feeds.items():
                try:
                    analysis = await self._analyze_instrument_gap(instrument_key, feed_data)
                    if analysis:
                        gap_analyses.append(analysis)
                        self.current_gaps[analysis.symbol] = analysis
                        
                except Exception as e:
                    logger.debug(f"Error analyzing gap for {instrument_key}: {e}")
                    continue
            
            # Update statistics
            self.session_stats.total_instruments_analyzed = len(gap_analyses)
            self.session_stats.gaps_detected = len([g for g in gap_analyses if g.gap_type != GapType.NO_GAP])
            self.session_stats.gap_up_count = len([g for g in gap_analyses if g.gap_type == GapType.GAP_UP])
            self.session_stats.gap_down_count = len([g for g in gap_analyses if g.gap_type == GapType.GAP_DOWN])
            self.session_stats.significant_gaps = len([g for g in gap_analyses if g.is_significant])
            self.session_stats.last_analysis_time = datetime.now()
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self.processing_times.append(processing_time)
            if len(self.processing_times) > 100:
                self.processing_times.pop(0)  # Keep only last 100 measurements
            
            self.session_stats.avg_processing_time_ms = sum(self.processing_times) / len(self.processing_times)
            
            # Generate alerts for significant gaps
            significant_gaps = [g for g in gap_analyses if g.is_significant]
            if significant_gaps:
                await self._generate_gap_alerts(significant_gaps)
            
            # Log summary for snapshots or significant findings
            if is_snapshot or significant_gaps:
                logger.info(
                    f"🔍 Gap Analysis Complete: {self.session_stats.gaps_detected} gaps detected "
                    f"({self.session_stats.gap_up_count} up, {self.session_stats.gap_down_count} down), "
                    f"{len(significant_gaps)} significant"
                )
                
        except Exception as e:
            logger.error(f"❌ Error handling market data for gap detection: {e}")

    async def _analyze_instrument_gap(
        self, instrument_key: str, feed_data: Dict[str, Any]
    ) -> Optional[GapAnalysis]:
        """Analyze gap for a single instrument"""
        try:
            # Extract price data from feed
            price_info = self._extract_price_data(instrument_key, feed_data)
            if not price_info:
                return None
            
            symbol = price_info["symbol"]
            current_price = Decimal(str(price_info["ltp"]))
            previous_close = Decimal(str(price_info["prev_close"]))
            open_price = Decimal(str(price_info.get("open", current_price)))
            volume = price_info.get("volume", 0)
            
            # Calculate gap percentage using opening price vs previous close
            if previous_close <= 0:
                return None
            
            gap_percentage = ((open_price - previous_close) / previous_close * 100).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            
            # Determine gap type
            gap_type = self._determine_gap_type(gap_percentage)
            
            # Determine gap strength
            gap_strength = self._determine_gap_strength(gap_percentage)
            
            # Calculate significance and priority
            is_significant = abs(gap_percentage) >= self.significant_gap_threshold
            alert_priority = self._determine_alert_priority(gap_percentage, volume)
            confidence_score = self._calculate_confidence_score(gap_percentage, volume)
            
            # Volume analysis
            volume_ratio = self._calculate_volume_ratio(symbol, volume)
            has_volume_confirmation = self._check_volume_confirmation(volume, volume_ratio)
            
            # Market categorization
            sector = self._get_sector(symbol)
            market_cap_category = self._estimate_market_cap_category(current_price)
            
            return GapAnalysis(
                symbol=symbol,
                instrument_key=instrument_key,
                current_price=current_price,
                previous_close=previous_close,
                open_price=open_price,
                gap_percentage=gap_percentage,
                gap_type=gap_type,
                gap_strength=gap_strength,
                volume=volume,
                volume_ratio=volume_ratio,
                has_volume_confirmation=has_volume_confirmation,
                sector=sector,
                market_cap_category=market_cap_category,
                confidence_score=confidence_score,
                alert_priority=alert_priority,
                is_significant=is_significant
            )
            
        except Exception as e:
            logger.debug(f"Error analyzing gap for {instrument_key}: {e}")
            return None

    def _extract_price_data(self, instrument_key: str, feed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract price data from feed data"""
        try:
            # Handle different feed data formats
            if "fullFeed" in feed_data:
                # Raw Upstox format
                return self._extract_from_upstox_format(instrument_key, feed_data)
            elif "ltp" in feed_data or "last_price" in feed_data:
                # Normalized format
                ltp = feed_data.get("ltp") or feed_data.get("last_price", 0)
                prev_close = feed_data.get("cp") or feed_data.get("previous_close", ltp)
                symbol = feed_data.get("symbol") or self._extract_symbol_from_key(instrument_key)
                
                return {
                    "symbol": symbol,
                    "ltp": float(ltp),
                    "prev_close": float(prev_close),
                    "open": float(feed_data.get("open", ltp)),
                    "volume": int(feed_data.get("volume", 0))
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting price data for {instrument_key}: {e}")
            return None

    def _extract_from_upstox_format(self, instrument_key: str, feed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract from raw Upstox WebSocket format"""
        try:
            full_feed = feed_data.get("fullFeed", {})
            
            # Try market feed (equity stocks)
            market_ff = full_feed.get("marketFF", {})
            if market_ff:
                ltpc = market_ff.get("ltpc", {})
                ohlc_data = market_ff.get("marketOHLC", {}).get("ohlc", [])
                
                # Get daily OHLC data
                daily_ohlc = next(
                    (item for item in ohlc_data if item.get("interval") == "1d"), {}
                )
                
                return {
                    "symbol": self._extract_symbol_from_key(instrument_key),
                    "ltp": float(ltpc.get("ltp", 0)),
                    "prev_close": float(ltpc.get("cp", ltpc.get("ltp", 0))),
                    "open": float(daily_ohlc.get("open", ltpc.get("ltp", 0))),
                    "volume": int(daily_ohlc.get("vol", 0)) if daily_ohlc.get("vol") else 0
                }
            
            # Try index feed format
            index_ff = full_feed.get("indexFF", {})
            if index_ff:
                ltpc = index_ff.get("ltpc", {})
                ohlc_data = index_ff.get("marketOHLC", {}).get("ohlc", [])
                daily_ohlc = next(
                    (item for item in ohlc_data if item.get("interval") == "1d"), {}
                )
                
                return {
                    "symbol": self._extract_symbol_from_key(instrument_key),
                    "ltp": float(ltpc.get("ltp", 0)),
                    "prev_close": float(ltpc.get("cp", ltpc.get("ltp", 0))),
                    "open": float(daily_ohlc.get("open", ltpc.get("ltp", 0))),
                    "volume": 0  # Indices don't have volume
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting from Upstox format: {e}")
            return None

    def _extract_symbol_from_key(self, instrument_key: str) -> str:
        """Extract symbol from instrument key"""
        try:
            if "|" in instrument_key:
                parts = instrument_key.split("|")
                symbol_part = parts[-1]
                
                # Handle index names
                if "INDEX" in instrument_key:
                    return symbol_part
                
                # Clean equity symbols
                return symbol_part.replace("-EQ", "").replace("_EQ", "")
            
            return instrument_key
            
        except Exception as e:
            logger.debug(f"Error extracting symbol: {e}")
            return instrument_key.split("|")[-1] if "|" in instrument_key else instrument_key

    def _determine_gap_type(self, gap_percentage: Decimal) -> GapType:
        """Determine gap type based on percentage"""
        if gap_percentage > self.min_gap_threshold:
            return GapType.GAP_UP
        elif gap_percentage < -self.min_gap_threshold:
            return GapType.GAP_DOWN
        else:
            return GapType.NO_GAP

    def _determine_gap_strength(self, gap_percentage: Decimal) -> GapStrength:
        """Determine gap strength based on percentage"""
        abs_gap = abs(gap_percentage)
        
        if abs_gap >= self.very_strong_gap_threshold:
            return GapStrength.VERY_STRONG
        elif abs_gap >= self.strong_gap_threshold:
            return GapStrength.STRONG
        elif abs_gap >= self.moderate_gap_threshold:
            return GapStrength.MODERATE
        else:
            return GapStrength.WEAK

    def _determine_alert_priority(self, gap_percentage: Decimal, volume: int) -> AlertPriority:
        """Determine alert priority based on gap size and volume"""
        abs_gap = abs(gap_percentage)
        
        if abs_gap >= Decimal("8.0") and volume > 10000:
            return AlertPriority.CRITICAL
        elif abs_gap >= Decimal("5.0") and volume > 5000:
            return AlertPriority.HIGH
        elif abs_gap >= Decimal("2.5") and volume > 1000:
            return AlertPriority.MEDIUM
        else:
            return AlertPriority.LOW

    def _calculate_confidence_score(self, gap_percentage: Decimal, volume: int) -> Decimal:
        """Calculate confidence score for gap analysis"""
        # Base confidence from gap size
        abs_gap = abs(gap_percentage)
        gap_confidence = min(abs_gap / Decimal("10.0"), Decimal("0.6"))
        
        # Volume confidence
        volume_confidence = min(Decimal(str(volume)) / Decimal("100000"), Decimal("0.3"))
        
        # Time-based confidence (higher during premarket)
        current_time = datetime.now().time()
        time_confidence = Decimal("0.1")
        if self.premarket_start <= current_time <= self.premarket_end:
            time_confidence = Decimal("0.2")  # Higher confidence during premarket
        
        total_confidence = gap_confidence + volume_confidence + time_confidence
        return min(total_confidence, Decimal("1.0")).quantize(Decimal("0.001"))

    def _calculate_volume_ratio(self, symbol: str, current_volume: int) -> Optional[Decimal]:
        """Calculate volume ratio vs historical average (placeholder)"""
        # This would need historical volume data - simplified for now
        return Decimal("1.0")

    def _check_volume_confirmation(self, volume: int, volume_ratio: Optional[Decimal]) -> bool:
        """Check if volume confirms the price gap"""
        # Basic volume threshold check
        return volume > 1000 and (volume_ratio is None or volume_ratio > Decimal("0.8"))

    def _get_sector(self, symbol: str) -> str:
        """Get sector for symbol (simplified mapping)"""
        sector_map = {
            "RELIANCE": "ENERGY",
            "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "TECHM": "IT",
            "HDFCBANK": "BANKING", "ICICIBANK": "BANKING", "SBIN": "BANKING",
            "KOTAKBANK": "BANKING", "AXISBANK": "BANKING",
            "MARUTI": "AUTO", "M&M": "AUTO", "TATAMOTORS": "AUTO",
            "BAJFINANCE": "FINANCE", "HDFCLIFE": "FINANCE",
            "ITC": "FMCG", "HINDUNILVR": "FMCG", "NESTLEIND": "FMCG"
        }
        return sector_map.get(symbol, "OTHER")

    def _estimate_market_cap_category(self, price: Decimal) -> str:
        """Estimate market cap category based on price (simplified)"""
        if price > Decimal("2000"):
            return "LARGE_CAP"
        elif price > Decimal("500"):
            return "MID_CAP"
        else:
            return "SMALL_CAP"

    async def _load_previous_closes(self) -> None:
        """Load previous day's closing prices"""
        try:
            # This would typically load from database or external source
            # For now, we'll rely on the live data providing previous close
            logger.info("📊 Previous closes will be extracted from live feed data")
            
        except Exception as e:
            logger.error(f"❌ Error loading previous closes: {e}")

    async def _generate_gap_alerts(self, significant_gaps: List[GapAnalysis]) -> None:
        """Generate and broadcast gap alerts"""
        try:
            alerts_generated = 0
            
            for gap in significant_gaps:
                # Create alert data
                alert_data = {
                    "type": "gap_alert",
                    "symbol": gap.symbol,
                    "gap_type": gap.gap_type.value,
                    "gap_percentage": float(gap.gap_percentage),
                    "gap_strength": gap.gap_strength.value,
                    "current_price": float(gap.current_price),
                    "previous_close": float(gap.previous_close),
                    "open_price": float(gap.open_price),
                    "volume": gap.volume,
                    "priority": gap.alert_priority.value,
                    "confidence": float(gap.confidence_score),
                    "sector": gap.sector,
                    "market_cap": gap.market_cap_category,
                    "timestamp": gap.timestamp.isoformat(),
                    "is_significant": gap.is_significant
                }
                
                # Broadcast via WebSocket (if unified manager available)
                await self._broadcast_gap_alert(alert_data)
                alerts_generated += 1
                
                logger.info(
                    f"🚨 GAP ALERT: {gap.symbol} {gap.gap_type.value} "
                    f"{gap.gap_percentage}% ({gap.gap_strength.value}) "
                    f"Priority: {gap.alert_priority.value}"
                )
            
            self.session_stats.alerts_generated += alerts_generated
            
        except Exception as e:
            logger.error(f"❌ Error generating gap alerts: {e}")

    async def _broadcast_gap_alert(self, alert_data: Dict[str, Any]) -> None:
        """Broadcast gap alert via WebSocket"""
        try:
            from services.unified_websocket_manager import unified_manager
            
            if unified_manager:
                unified_manager.emit_event(
                    "gap_alert", alert_data, priority=2  # High priority
                )
                
        except ImportError:
            logger.debug("Unified WebSocket manager not available for alerts")
        except Exception as e:
            logger.error(f"❌ Error broadcasting gap alert: {e}")

    def get_current_gaps(
        self, 
        gap_type: Optional[GapType] = None,
        min_strength: Optional[GapStrength] = None,
        sector: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get current gap analysis results with filtering"""
        filtered_gaps = []
        
        for gap in self.current_gaps.values():
            # Apply filters
            if gap_type and gap.gap_type != gap_type:
                continue
            if min_strength and gap.gap_strength.value < min_strength.value:
                continue
            if sector and gap.sector != sector:
                continue
            
            filtered_gaps.append({
                "symbol": gap.symbol,
                "gap_type": gap.gap_type.value,
                "gap_percentage": float(gap.gap_percentage),
                "gap_strength": gap.gap_strength.value,
                "current_price": float(gap.current_price),
                "previous_close": float(gap.previous_close),
                "open_price": float(gap.open_price),
                "volume": gap.volume,
                "volume_ratio": float(gap.volume_ratio) if gap.volume_ratio else None,
                "has_volume_confirmation": gap.has_volume_confirmation,
                "sector": gap.sector,
                "market_cap_category": gap.market_cap_category,
                "confidence_score": float(gap.confidence_score),
                "alert_priority": gap.alert_priority.value,
                "is_significant": gap.is_significant,
                "timestamp": gap.timestamp.isoformat()
            })
        
        # Sort by gap percentage (descending absolute value)
        filtered_gaps.sort(
            key=lambda x: abs(x["gap_percentage"]), reverse=True
        )
        
        return filtered_gaps

    def get_session_statistics(self) -> Dict[str, Any]:
        """Get current session statistics"""
        return {
            "session_date": self.session_stats.session_date.isoformat(),
            "total_instruments_analyzed": self.session_stats.total_instruments_analyzed,
            "gaps_detected": self.session_stats.gaps_detected,
            "gap_up_count": self.session_stats.gap_up_count,
            "gap_down_count": self.session_stats.gap_down_count,
            "significant_gaps": self.session_stats.significant_gaps,
            "alerts_generated": self.session_stats.alerts_generated,
            "avg_processing_time_ms": self.session_stats.avg_processing_time_ms,
            "last_analysis_time": (
                self.session_stats.last_analysis_time.isoformat() 
                if self.session_stats.last_analysis_time else None
            ),
            "registered_with_hub": self.registered_with_hub,
            "gap_detection_rate": (
                (self.session_stats.gaps_detected / self.session_stats.total_instruments_analyzed * 100)
                if self.session_stats.total_instruments_analyzed > 0 else 0
            )
        }


# Singleton instance
_gap_detection_service = None


def get_unified_gap_detection_service() -> UnifiedGapDetectionService:
    """Get singleton unified gap detection service"""
    global _gap_detection_service
    if _gap_detection_service is None:
        _gap_detection_service = UnifiedGapDetectionService()
    return _gap_detection_service


# Convenience functions
async def start_gap_detection_service() -> bool:
    """Start the gap detection service and register with real-time hub"""
    service = get_unified_gap_detection_service()
    return await service.register_with_realtime_hub()


def get_current_gaps(**filters) -> List[Dict[str, Any]]:
    """Get current gap analysis results"""
    service = get_unified_gap_detection_service()
    return service.get_current_gaps(**filters)


def get_gap_detection_stats() -> Dict[str, Any]:
    """Get gap detection statistics"""
    service = get_unified_gap_detection_service()
    return service.get_session_statistics()