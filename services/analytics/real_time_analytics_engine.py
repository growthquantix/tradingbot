"""
Real-Time Analytics Engine

Kafka consumer that processes live market data and calculates advanced analytics.
Publishes results to both Kafka topics and SSE channels for UI updates.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from collections import defaultdict
import json

from services.hft.consumers import BaseHFTConsumer
from services.hft.producer import get_hft_producer
from services.sse.sse_manager import get_sse_manager, SSEChannel

from .interfaces import IAnalyticsCalculator, CalculatedFeatures, AnalyticsResult, MarketTick
from .live_feed_calculator import LiveFeedCalculator

logger = logging.getLogger(__name__)


class RealTimeAnalyticsEngine(BaseHFTConsumer, IAnalyticsCalculator):
    """
    Real-time analytics engine that:
    1. Consumes from Kafka topics
    2. Calculates advanced analytics 
    3. Publishes to Kafka and SSE
    
    Implements clean separation of concerns with modular design.
    """
    
    def __init__(self):
        super().__init__(
            service_name="real_time_analytics",
            topics=["hft.analytics.market_data"],
            group_id="real_time_analytics_group"
        )
        
        # Dependencies
        self._feature_calculator = LiveFeedCalculator()
        self._kafka_producer = None
        self._sse_manager = None
        
        # Analytics state
        self._current_features: Dict[str, CalculatedFeatures] = {}
        self._top_movers_cache = {'gainers': [], 'losers': [], 'most_active': []}
        self._breakout_candidates: Set[str] = set()
        self._volume_alerts: Set[str] = set()
        self._sector_performance: Dict[str, Dict] = defaultdict(dict)
        
        # Performance tracking
        self._processed_ticks = 0
        self._analytics_calculated = 0
        self._last_calculation_time = datetime.now()
        
        logger.info("✅ Real-Time Analytics Engine initialized")
    
    async def initialize_dependencies(self) -> None:
        """Initialize Kafka producer and SSE manager"""
        try:
            self._kafka_producer = await get_hft_producer()
            self._sse_manager = get_sse_manager()
            logger.info("✅ Analytics engine dependencies initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize dependencies: {e}")
            raise
    
    async def process_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Process batch of messages from Kafka - required by BaseHFTConsumer"""
        await self._process_message_batch(messages)
    
    async def _process_message_batch(self, messages: List[Dict[str, Any]]) -> None:
        """Process batch of messages from Kafka"""
        try:
            if not messages:
                return
            
            # Extract market ticks from messages
            market_ticks = []
            for message in messages:
                ticks = self._extract_market_ticks(message)
                market_ticks.extend(ticks)
            
            if not market_ticks:
                return
            
            # Calculate features for all ticks
            features_list = await self._feature_calculator.calculate_batch_features(market_ticks)
            
            # Update current features cache
            for features in features_list:
                self._current_features[features.symbol] = features
            
            # Calculate analytics
            await self._calculate_all_analytics(features_list)
            
            # Update metrics
            self._processed_ticks += len(market_ticks)
            self._analytics_calculated += 1
            self._last_calculation_time = datetime.now()
            
            logger.debug(f"📊 Processed {len(market_ticks)} ticks, calculated analytics")
            
        except Exception as e:
            logger.error(f"❌ Error processing message batch: {e}")
    
    def _extract_market_ticks(self, message: Dict[str, Any]) -> List[MarketTick]:
        """Extract MarketTick objects from Kafka message"""
        try:
            ticks = []
            
            # Handle different message formats
            if 'feeds' in message:
                feeds = message['feeds']
                for instrument_key, feed_data in feeds.items():
                    tick = self._create_market_tick(instrument_key, feed_data)
                    if tick:
                        ticks.append(tick)
            
            elif 'data' in message and isinstance(message['data'], dict):
                # Handle analytics data format
                for symbol, symbol_data in message['data'].items():
                    tick = self._create_market_tick_from_data(symbol, symbol_data)
                    if tick:
                        ticks.append(tick)
            
            return ticks
            
        except Exception as e:
            logger.error(f"❌ Error extracting market ticks: {e}")
            return []
    
    def _create_market_tick(self, instrument_key: str, feed_data: Dict) -> Optional[MarketTick]:
        """Create MarketTick from raw feed data"""
        try:
            # Extract symbol from instrument key
            symbol = self._extract_symbol(instrument_key)
            
            # Extract price data from feed
            full_feed = feed_data.get('fullFeed', {})
            market_data = full_feed.get('marketFF') or full_feed.get('indexFF')
            
            if not market_data or 'ltpc' not in market_data:
                return None
            
            ltpc = market_data['ltpc']
            
            return MarketTick(
                instrument_key=instrument_key,
                symbol=symbol,
                last_price=self._safe_decimal(ltpc.get('ltp')),
                volume=self._safe_int(ltpc.get('ltq', 0)),
                timestamp=datetime.now(),
                change=self._safe_decimal(ltpc.get('ltp', 0)) - self._safe_decimal(ltpc.get('cp', 0)),
                change_percent=self._calculate_change_percent(
                    self._safe_decimal(ltpc.get('ltp')),
                    self._safe_decimal(ltpc.get('cp'))
                ),
                previous_close=self._safe_decimal(ltpc.get('cp'))
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating market tick: {e}")
            return None
    
    def _create_market_tick_from_data(self, symbol: str, data: Dict) -> Optional[MarketTick]:
        """Create MarketTick from processed data"""
        try:
            return MarketTick(
                instrument_key=data.get('instrument_key', symbol),
                symbol=symbol,
                last_price=self._safe_decimal(data.get('price')),
                volume=self._safe_int(data.get('volume', 0)),
                timestamp=datetime.now(),
                change=self._safe_decimal(data.get('change')),
                change_percent=self._safe_decimal(data.get('change_percent'))
            )
        except Exception as e:
            logger.error(f"❌ Error creating tick from data: {e}")
            return None
    
    async def _calculate_all_analytics(self, features_list: List[CalculatedFeatures]) -> None:
        """Calculate all analytics types"""
        try:
            # Calculate analytics in parallel
            analytics_tasks = [
                self.calculate_top_movers(features_list),
                self.calculate_breakout_candidates(features_list),
                self.calculate_volume_alerts(features_list),
                self.calculate_sector_performance(features_list)
            ]
            
            results = await asyncio.gather(*analytics_tasks, return_exceptions=True)
            
            # Publish valid results
            for result in results:
                if isinstance(result, AnalyticsResult):
                    await self._publish_analytics_result(result)
                    await self._broadcast_via_sse(result)
            
        except Exception as e:
            logger.error(f"❌ Error calculating analytics: {e}")
    
    async def calculate_top_movers(self, features: List[CalculatedFeatures]) -> AnalyticsResult:
        """Calculate top movers (gainers/losers)"""
        try:
            gainers = []
            losers = []
            most_active = []
            
            for feature in features:
                # Skip indices
                if 'INDEX' in feature.symbol or 'NIFTY' in feature.symbol:
                    continue
                
                change_percent = float(feature.price_change_percent)
                volume_ratio = float(feature.volume_ratio or 1.0)
                
                stock_data = {
                    'symbol': feature.symbol,
                    'change_percent': change_percent,
                    'volume_ratio': volume_ratio,
                    'sector': feature.sector,
                    'timestamp': feature.timestamp.isoformat()
                }
                
                # Gainers (> 2% increase)
                if change_percent > 2.0:
                    gainers.append(stock_data)
                
                # Losers (> 2% decrease)  
                elif change_percent < -2.0:
                    losers.append(stock_data)
                
                # Most active (high volume ratio)
                if volume_ratio > 2.0:
                    most_active.append(stock_data)
            
            # Sort and limit results
            gainers = sorted(gainers, key=lambda x: x['change_percent'], reverse=True)[:20]
            losers = sorted(losers, key=lambda x: x['change_percent'])[:20]
            most_active = sorted(most_active, key=lambda x: x['volume_ratio'], reverse=True)[:20]
            
            # Cache results
            self._top_movers_cache = {
                'gainers': gainers,
                'losers': losers,
                'most_active': most_active
            }
            
            return AnalyticsResult(
                calculation_type="top_movers",
                symbol="MARKET",
                timestamp=datetime.now(),
                data={
                    'gainers': gainers,
                    'losers': losers,
                    'most_active': most_active,
                    'summary': {
                        'total_gainers': len(gainers),
                        'total_losers': len(losers),
                        'total_active': len(most_active)
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Error calculating top movers: {e}")
            return AnalyticsResult("top_movers", "MARKET", datetime.now(), {})
    
    async def calculate_breakout_candidates(self, features: List[CalculatedFeatures]) -> AnalyticsResult:
        """Identify breakout candidates"""
        try:
            breakout_candidates = []
            
            for feature in features:
                # Breakout criteria: High momentum + volume
                momentum = float(feature.momentum_score or 0)
                volume_ratio = float(feature.volume_ratio or 1.0)
                change_percent = float(feature.price_change_percent)
                
                # Breakout conditions
                is_breakout = (
                    (momentum > 5.0 and volume_ratio > 1.5) or
                    (abs(change_percent) > 3.0 and volume_ratio > 2.0)
                )
                
                if is_breakout:
                    breakout_data = {
                        'symbol': feature.symbol,
                        'momentum_score': momentum,
                        'volume_ratio': volume_ratio,
                        'change_percent': change_percent,
                        'sector': feature.sector,
                        'breakout_type': 'bullish' if change_percent > 0 else 'bearish',
                        'confidence': min(100, (abs(momentum) + volume_ratio) * 10),
                        'timestamp': feature.timestamp.isoformat()
                    }
                    breakout_candidates.append(breakout_data)
                    self._breakout_candidates.add(feature.symbol)
            
            # Sort by confidence
            breakout_candidates = sorted(
                breakout_candidates, 
                key=lambda x: x['confidence'], 
                reverse=True
            )[:15]
            
            return AnalyticsResult(
                calculation_type="breakout_candidates",
                symbol="MARKET", 
                timestamp=datetime.now(),
                data={
                    'breakouts': breakout_candidates,
                    'count': len(breakout_candidates)
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Error calculating breakout candidates: {e}")
            return AnalyticsResult("breakout_candidates", "MARKET", datetime.now(), {})
    
    async def calculate_volume_alerts(self, features: List[CalculatedFeatures]) -> AnalyticsResult:
        """Identify volume spike alerts"""
        try:
            volume_alerts = []
            
            for feature in features:
                volume_ratio = float(feature.volume_ratio or 1.0)
                
                # Volume alert criteria
                if volume_ratio > 3.0:  # 3x normal volume
                    alert_data = {
                        'symbol': feature.symbol,
                        'volume_ratio': volume_ratio,
                        'change_percent': float(feature.price_change_percent),
                        'sector': feature.sector,
                        'alert_level': 'high' if volume_ratio > 5.0 else 'medium',
                        'timestamp': feature.timestamp.isoformat()
                    }
                    volume_alerts.append(alert_data)
                    self._volume_alerts.add(feature.symbol)
            
            # Sort by volume ratio
            volume_alerts = sorted(
                volume_alerts,
                key=lambda x: x['volume_ratio'], 
                reverse=True
            )[:10]
            
            return AnalyticsResult(
                calculation_type="volume_alerts",
                symbol="MARKET",
                timestamp=datetime.now(),
                data={
                    'alerts': volume_alerts,
                    'count': len(volume_alerts)
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Error calculating volume alerts: {e}")
            return AnalyticsResult("volume_alerts", "MARKET", datetime.now(), {})
    
    async def calculate_sector_performance(self, features: List[CalculatedFeatures]) -> AnalyticsResult:
        """Calculate sector performance metrics"""
        try:
            sector_data = defaultdict(list)
            
            # Group by sector
            for feature in features:
                sector = feature.sector or 'Unknown'
                if sector != 'Unknown':
                    sector_data[sector].append({
                        'symbol': feature.symbol,
                        'change_percent': float(feature.price_change_percent),
                        'volume_ratio': float(feature.volume_ratio or 1.0)
                    })
            
            # Calculate sector metrics
            sector_performance = {}
            for sector, stocks in sector_data.items():
                if stocks:
                    avg_change = sum(s['change_percent'] for s in stocks) / len(stocks)
                    avg_volume_ratio = sum(s['volume_ratio'] for s in stocks) / len(stocks)
                    
                    sector_performance[sector] = {
                        'average_change_percent': round(avg_change, 2),
                        'average_volume_ratio': round(avg_volume_ratio, 2),
                        'stock_count': len(stocks),
                        'top_performers': sorted(stocks, key=lambda x: x['change_percent'], reverse=True)[:3]
                    }
            
            # Cache results
            self._sector_performance = sector_performance
            
            return AnalyticsResult(
                calculation_type="sector_performance",
                symbol="MARKET",
                timestamp=datetime.now(),
                data={
                    'sectors': sector_performance,
                    'total_sectors': len(sector_performance)
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Error calculating sector performance: {e}")
            return AnalyticsResult("sector_performance", "MARKET", datetime.now(), {})
    
    async def _publish_analytics_result(self, result: AnalyticsResult) -> None:
        """Publish analytics result to Kafka topic"""
        try:
            if not self._kafka_producer:
                return
            
            await self._kafka_producer.send_analytics_data(
                analytics_type=result.calculation_type,
                data=result.data,
                instrument_keys=[result.symbol]
            )
            
        except Exception as e:
            logger.error(f"❌ Error publishing analytics result: {e}")
    
    async def _broadcast_via_sse(self, result: AnalyticsResult) -> None:
        """Broadcast analytics result via SSE"""
        try:
            if not self._sse_manager:
                return
            
            # Map calculation types to SSE channels
            channel_mapping = {
                'top_movers': SSEChannel.TOP_MOVERS,
                'breakout_candidates': SSEChannel.BREAKOUTS,
                'volume_alerts': SSEChannel.VOLUME_ALERTS,
                'sector_performance': SSEChannel.SECTOR_PERFORMANCE
            }
            
            channel = channel_mapping.get(result.calculation_type)
            if channel:
                await self._sse_manager.broadcast_to_channel(
                    channel=channel,
                    event_type=f"{result.calculation_type}_update",
                    data=result.data,
                    priority=2
                )
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting via SSE: {e}")
    
    def _safe_decimal(self, value) -> float:
        """Safely convert value to float"""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _safe_int(self, value) -> int:
        """Safely convert value to int"""
        try:
            return int(float(value)) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _extract_symbol(self, instrument_key: str) -> str:
        """Extract symbol from instrument key"""
        try:
            if '|' in instrument_key:
                return instrument_key.split('|')[-1]
            return instrument_key
        except Exception:
            return instrument_key
    
    def _calculate_change_percent(self, current_price: float, previous_close: float) -> float:
        """Calculate percentage change"""
        try:
            if previous_close and previous_close != 0:
                return ((current_price - previous_close) / previous_close) * 100
            return 0.0
        except Exception:
            return 0.0
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get analytics engine performance statistics"""
        return {
            'processed_ticks': self._processed_ticks,
            'analytics_calculated': self._analytics_calculated,
            'last_calculation_time': self._last_calculation_time.isoformat(),
            'features_cached': len(self._current_features),
            'breakout_candidates': len(self._breakout_candidates),
            'volume_alerts': len(self._volume_alerts),
            'sectors_tracked': len(self._sector_performance)
        }


# Singleton instance
_analytics_engine: Optional[RealTimeAnalyticsEngine] = None


async def get_analytics_engine() -> RealTimeAnalyticsEngine:
    """Get singleton analytics engine instance"""
    global _analytics_engine
    if _analytics_engine is None:
        _analytics_engine = RealTimeAnalyticsEngine()
        await _analytics_engine.initialize_dependencies()
    return _analytics_engine


async def start_analytics_engine() -> None:
    """Start the analytics engine consumer"""
    engine = await get_analytics_engine()
    await engine.start_consuming()


async def cleanup_analytics_engine() -> None:
    """Cleanup analytics engine resources"""
    global _analytics_engine
    if _analytics_engine:
        await _analytics_engine.stop_consuming()
        _analytics_engine = None