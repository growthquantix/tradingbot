"""
Modular Stock Selection Service with Analytics Integration

Comprehensive stock selection engine that integrates with market analytics,
sector heatmap, advance decline ratio, gap detection, and breakout analysis
to select optimal stocks/indices for auto-trading.

Features:
- Multi-factor stock selection algorithm
- Integration with HFT analytics (ADR, heatmap, breakouts, gaps)
- Option chain analysis and ATM strike calculation
- Risk-reward assessment and position sizing
- Market sentiment-based selection criteria
- Sector rotation analysis
- Real-time analytics integration via Kafka

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, time as dt_time
from enum import Enum
from collections import defaultdict
import json

import numpy as np
import pandas as pd

from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import SelectedStock, AutoTradingSession, DailyStockSummary

logger = logging.getLogger(__name__)


class SelectionCriteria(Enum):
    """Stock selection criteria"""
    MARKET_SENTIMENT = "market_sentiment"
    SECTOR_MOMENTUM = "sector_momentum"
    ADR_ALIGNMENT = "adr_alignment"
    BREAKOUT_SIGNALS = "breakout_signals"
    GAP_OPPORTUNITIES = "gap_opportunities"
    VOLUME_CONFIRMATION = "volume_confirmation"
    OPTIONS_LIQUIDITY = "options_liquidity"
    TECHNICAL_STRENGTH = "technical_strength"
    RISK_REWARD_RATIO = "risk_reward_ratio"


class MarketCondition(Enum):
    """Overall market condition assessment"""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"
    VOLATILE = "volatile"
    RANGE_BOUND = "range_bound"


class SelectionMode(Enum):
    """Stock selection modes"""
    MOMENTUM_BASED = "momentum_based"           # Trend following
    MEAN_REVERSION = "mean_reversion"          # Contrarian approach
    BREAKOUT_FOCUSED = "breakout_focused"      # Breakout opportunities
    GAP_TRADING = "gap_trading"                # Gap up/down trading
    SECTOR_ROTATION = "sector_rotation"        # Sector momentum
    HYBRID = "hybrid"                          # Multi-strategy approach


@dataclass
class SelectionWeights:
    """Configurable weights for selection criteria"""
    market_sentiment: float = 0.20
    sector_momentum: float = 0.15
    adr_alignment: float = 0.10
    breakout_signals: float = 0.15
    gap_opportunities: float = 0.10
    volume_confirmation: float = 0.10
    options_liquidity: float = 0.10
    technical_strength: float = 0.10


@dataclass
class StockSelectionConfig:
    """Configuration for stock selection process"""
    max_stocks: int = 3
    max_indices: int = 2
    sectors_to_analyze: int = 3
    min_volume_threshold: int = 100000
    min_options_oi: int = 10000
    min_liquidity_score: float = 0.7
    risk_appetite: str = "MODERATE"  # CONSERVATIVE/MODERATE/AGGRESSIVE
    market_cap_preference: List[str] = field(default_factory=lambda: ["LARGE_CAP", "MID_CAP"])
    selection_mode: SelectionMode = SelectionMode.HYBRID
    selection_weights: SelectionWeights = field(default_factory=SelectionWeights)


@dataclass
class StockAnalytics:
    """Comprehensive analytics for a stock"""
    symbol: str
    instrument_key: str
    
    # Price and market data
    current_price: float
    previous_close: float
    change_percent: float
    volume: int
    avg_volume: float
    volume_ratio: float
    
    # Technical analysis
    breakout_signals: List[Dict[str, Any]] = field(default_factory=list)
    gap_analysis: Optional[Dict[str, Any]] = None
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    technical_score: float = 0.0
    
    # Market context
    sector: str = "OTHER"
    market_cap_category: str = "UNKNOWN"
    sector_momentum: float = 0.0
    market_sentiment_alignment: float = 0.0
    adr_contribution: float = 0.0
    
    # Options data
    options_chain: Optional[Dict[str, Any]] = None
    atm_strike: Optional[float] = None
    options_liquidity_score: float = 0.0
    iv_percentile: float = 0.0
    
    # Risk metrics
    volatility: float = 0.0
    beta: float = 1.0
    risk_score: float = 0.5
    
    # Selection scoring
    overall_score: float = 0.0
    selection_reasons: List[str] = field(default_factory=list)
    confidence_level: float = 0.0


@dataclass
class SelectionResult:
    """Final stock selection result"""
    symbol: str
    instrument_key: str
    selection_score: float
    selection_reasons: List[str]
    
    # Price and market data
    current_price: float
    expected_direction: str  # BULLISH/BEARISH/NEUTRAL
    confidence_level: float
    
    # Options recommendations
    recommended_option_type: str  # CE/PE/STRADDLE
    atm_strike: Optional[float]
    option_contract: Optional[Dict[str, Any]]
    
    # Risk management
    position_size: int
    stop_loss: float
    target_price: float
    risk_reward_ratio: float
    max_risk_amount: float
    
    # Strategy context
    primary_strategy: str
    market_condition: MarketCondition
    selection_timestamp: datetime = field(default_factory=datetime.now)


class ModularStockSelector:
    """
    Advanced Modular Stock Selection Engine
    
    Features:
    - Multi-factor analysis with configurable weights
    - Real-time analytics integration via Kafka
    - Market condition adaptive selection
    - Options chain integration
    - Risk-based position sizing
    - Comprehensive selection scoring
    """
    
    def __init__(self, config: StockSelectionConfig):
        self.config = config
        
        # Initialize analytics integration
        self._initialize_analytics_integration()
        
        # Selection criteria processors
        self._criteria_processors = {
            SelectionCriteria.MARKET_SENTIMENT: self._analyze_market_sentiment_alignment,
            SelectionCriteria.SECTOR_MOMENTUM: self._analyze_sector_momentum,
            SelectionCriteria.ADR_ALIGNMENT: self._analyze_adr_alignment,
            SelectionCriteria.BREAKOUT_SIGNALS: self._analyze_breakout_signals,
            SelectionCriteria.GAP_OPPORTUNITIES: self._analyze_gap_opportunities,
            SelectionCriteria.VOLUME_CONFIRMATION: self._analyze_volume_confirmation,
            SelectionCriteria.OPTIONS_LIQUIDITY: self._analyze_options_liquidity,
            SelectionCriteria.TECHNICAL_STRENGTH: self._analyze_technical_strength,
            SelectionCriteria.RISK_REWARD_RATIO: self._analyze_risk_reward_ratio
        }
        
        # Analytics data cache
        self._market_analytics_cache: Dict[str, Any] = {}
        self._sector_analytics_cache: Dict[str, Any] = {}
        self._breakout_cache: Dict[str, Any] = {}
        self._gap_cache: Dict[str, Any] = {}
        self._adr_cache: Dict[str, Any] = {}
        
        logger.info(f"ModularStockSelector initialized with {config.selection_mode.value} mode")
    
    def _initialize_analytics_integration(self) -> None:
        """Initialize integration with analytics services"""
        try:
            # Import analytics services
            from services.hft.feature_calculators.top_movers_calculator import get_top_movers_calculator
            from services.hft.feature_calculators.gap_detection_calculator import get_gap_detection_calculator
            from services.hft.feature_calculators.breakout_detection_calculator import get_breakout_detection_calculator
            from services.hft.advance_decline_service import get_advance_decline_service
            from services.hft.market_breadth_analytics import get_market_breadth_analytics
            from services.enhanced_market_analytics import enhanced_analytics
            from services.upstox_option_service import upstox_option_service
            
            # Initialize calculators
            self.top_movers_calculator = get_top_movers_calculator()
            self.gap_calculator = get_gap_detection_calculator()
            self.breakout_calculator = get_breakout_detection_calculator()
            self.adr_service = get_advance_decline_service()
            self.market_breadth_analytics = get_market_breadth_analytics()
            self.enhanced_analytics = enhanced_analytics
            self.option_service = upstox_option_service
            
            logger.info("Analytics integration initialized successfully")
            
        except ImportError as e:
            logger.warning(f"Some analytics services not available: {e}")
            # Initialize with None for graceful degradation
            self.top_movers_calculator = None
            self.gap_calculator = None
            self.breakout_calculator = None
            self.adr_service = None
            self.market_breadth_analytics = None
            self.enhanced_analytics = None
            self.option_service = None
    
    async def select_stocks_for_trading(
        self,
        market_condition: Optional[MarketCondition] = None
    ) -> List[SelectionResult]:
        """
        Main stock selection method with comprehensive analysis
        
        Args:
            market_condition: Optional market condition override
            
        Returns:
            List of selected stocks/indices with full analysis
        """
        try:
            logger.info(f"🎯 Starting stock selection with {self.config.selection_mode.value} mode")
            
            # Step 1: Evaluate market conditions
            if not market_condition:
                market_condition = await self._evaluate_market_conditions()
            
            logger.info(f"📊 Market condition: {market_condition.value}")
            
            # Step 2: Update analytics cache
            await self._update_analytics_cache()
            
            # Step 3: Get candidate instruments
            candidates = await self._get_candidate_instruments()
            logger.info(f"📋 Analyzing {len(candidates)} candidate instruments")
            
            # Step 4: Analyze each candidate
            analyzed_stocks = []
            for candidate in candidates:
                stock_analytics = await self._analyze_stock_comprehensive(candidate)
                if stock_analytics and stock_analytics.overall_score > 0.5:
                    analyzed_stocks.append(stock_analytics)
            
            logger.info(f"✅ {len(analyzed_stocks)} stocks passed initial analysis")
            
            # Step 5: Apply selection criteria based on mode
            filtered_stocks = await self._apply_selection_mode_filter(
                analyzed_stocks, market_condition
            )
            
            # Step 6: Rank and select top stocks
            selected_stocks = await self._rank_and_select_stocks(
                filtered_stocks, market_condition
            )
            
            # Step 7: Generate final selection results
            selection_results = []
            for stock in selected_stocks:
                result = await self._generate_selection_result(stock, market_condition)
                if result:
                    selection_results.append(result)
            
            logger.info(f"🚀 Final selection: {len(selection_results)} stocks/indices selected")
            
            return selection_results
            
        except Exception as e:
            logger.error(f"❌ Stock selection failed: {e}")
            return []
    
    async def _evaluate_market_conditions(self) -> MarketCondition:
        """Evaluate overall market conditions using multiple indicators"""
        try:
            # Get market sentiment from enhanced analytics
            market_sentiment = self.enhanced_analytics.get_market_sentiment() if self.enhanced_analytics else {}
            
            # Get ADR data
            adr_data = self.adr_service.get_adr_summary() if self.adr_service else {}
            
            # Get market breadth data
            breadth_data = self.market_breadth_analytics.get_latest_analysis() if self.market_breadth_analytics else {}
            
            # Get top movers data
            movers_data = self.top_movers_calculator.get_latest_result() if self.top_movers_calculator else None
            movers_result = movers_data.data if movers_data else {}
            
            # Calculate composite score
            condition_score = self._calculate_market_condition_score(
                market_sentiment, adr_data, breadth_data, movers_result
            )
            
            # Determine market condition
            if condition_score >= 0.8:
                return MarketCondition.STRONG_BULLISH
            elif condition_score >= 0.6:
                return MarketCondition.BULLISH
            elif condition_score >= 0.4:
                return MarketCondition.NEUTRAL
            elif condition_score >= 0.2:
                return MarketCondition.BEARISH
            else:
                return MarketCondition.STRONG_BEARISH
                
        except Exception as e:
            logger.error(f"Market condition evaluation error: {e}")
            return MarketCondition.NEUTRAL
    
    def _calculate_market_condition_score(
        self,
        sentiment: Dict[str, Any],
        adr: Dict[str, Any],
        breadth: Dict[str, Any],
        movers: Dict[str, Any]
    ) -> float:
        """Calculate composite market condition score"""
        try:
            score = 0.5  # Neutral baseline
            
            # Market sentiment factor (30% weight)
            if sentiment:
                sentiment_value = sentiment.get('sentiment', 'neutral')
                if sentiment_value in ['bullish', 'very_bullish']:
                    score += 0.15
                elif sentiment_value in ['bearish', 'very_bearish']:
                    score -= 0.15
            
            # ADR factor (25% weight)
            if adr:
                for segment_data in adr.values():
                    if isinstance(segment_data, dict):
                        adr_ratio = segment_data.get('advance_decline_ratio', 1.0)
                        if adr_ratio > 1.5:
                            score += 0.125
                        elif adr_ratio < 0.5:
                            score -= 0.125
                        break
            
            # Market breadth factor (25% weight)
            if breadth:
                breadth_sentiment = breadth.get('market_sentiment', 'NEUTRAL')
                if breadth_sentiment == 'BULLISH':
                    score += 0.125
                elif breadth_sentiment == 'BEARISH':
                    score -= 0.125
            
            # Top movers factor (20% weight)
            if movers:
                market_summary = movers.get('market_summary', {})
                if market_summary:
                    sentiment_str = market_summary.get('market_sentiment', 'NEUTRAL')
                    if sentiment_str == 'BULLISH':
                        score += 0.1
                    elif sentiment_str == 'BEARISH':
                        score -= 0.1
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.error(f"Market condition score calculation error: {e}")
            return 0.5
    
    async def _update_analytics_cache(self) -> None:
        """Update all analytics data caches"""
        try:
            # Update market analytics cache
            if self.enhanced_analytics:
                self._market_analytics_cache = {
                    'sentiment': self.enhanced_analytics.get_market_sentiment(),
                    'top_movers': self.enhanced_analytics.get_top_movers(),
                    'sector_performance': self.enhanced_analytics.get_sector_performance()
                }
            
            # Update ADR cache
            if self.adr_service:
                self._adr_cache = self.adr_service.get_adr_summary()
            
            # Update breakout cache
            if self.breakout_calculator:
                breakout_result = self.breakout_calculator.get_latest_result()
                self._breakout_cache = breakout_result.data if breakout_result else {}
            
            # Update gap cache
            if self.gap_calculator:
                gap_result = self.gap_calculator.get_latest_result()
                self._gap_cache = gap_result.data if gap_result else {}
            
            # Update sector analytics
            if self.market_breadth_analytics:
                self._sector_analytics_cache = self.market_breadth_analytics.get_latest_analysis()
            
            logger.debug("Analytics cache updated successfully")
            
        except Exception as e:
            logger.error(f"Analytics cache update error: {e}")
    
    async def _get_candidate_instruments(self) -> List[Dict[str, Any]]:
        """Get list of candidate instruments for analysis"""
        try:
            candidates = []
            
            # Get top movers as candidates
            if self._market_analytics_cache.get('top_movers'):
                movers = self._market_analytics_cache['top_movers']
                
                # Add top gainers
                for gainer in movers.get('gainers', [])[:10]:
                    candidates.append({
                        'symbol': gainer.get('symbol', ''),
                        'instrument_key': gainer.get('instrument_key', ''),
                        'type': 'EQUITY',
                        'source': 'TOP_GAINER'
                    })
                
                # Add most active stocks
                for active in movers.get('most_active', [])[:5]:
                    candidates.append({
                        'symbol': active.get('symbol', ''),
                        'instrument_key': active.get('instrument_key', ''),
                        'type': 'EQUITY',
                        'source': 'MOST_ACTIVE'
                    })
            
            # Add gap stocks
            if self._gap_cache.get('gap_signals'):
                for gap_signal in self._gap_cache['gap_signals'][:5]:
                    candidates.append({
                        'symbol': gap_signal.get('symbol', ''),
                        'instrument_key': gap_signal.get('instrument_key', ''),
                        'type': 'EQUITY',
                        'source': 'GAP_SIGNAL'
                    })
            
            # Add breakout stocks
            if self._breakout_cache.get('breakout_signals'):
                for breakout in self._breakout_cache['breakout_signals'][:5]:
                    candidates.append({
                        'symbol': breakout.get('symbol', ''),
                        'instrument_key': breakout.get('instrument_key', ''),
                        'type': 'EQUITY',
                        'source': 'BREAKOUT_SIGNAL'
                    })
            
            # Add major indices
            major_indices = [
                {'symbol': 'NIFTY', 'instrument_key': 'NSE_INDEX|Nifty 50', 'type': 'INDEX', 'source': 'MAJOR_INDEX'},
                {'symbol': 'BANKNIFTY', 'instrument_key': 'NSE_INDEX|Nifty Bank', 'type': 'INDEX', 'source': 'MAJOR_INDEX'},
                {'symbol': 'FINNIFTY', 'instrument_key': 'NSE_INDEX|Nifty Fin Service', 'type': 'INDEX', 'source': 'MAJOR_INDEX'}
            ]
            candidates.extend(major_indices)
            
            # Remove duplicates based on instrument_key
            unique_candidates = []
            seen_keys = set()
            for candidate in candidates:
                key = candidate.get('instrument_key', '')
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    unique_candidates.append(candidate)
            
            return unique_candidates
            
        except Exception as e:
            logger.error(f"Candidate instruments error: {e}")
            return []
    
    async def _analyze_stock_comprehensive(
        self, 
        candidate: Dict[str, Any]
    ) -> Optional[StockAnalytics]:
        """Perform comprehensive analysis of a stock/instrument"""
        try:
            symbol = candidate.get('symbol', '')
            instrument_key = candidate.get('instrument_key', '')
            
            if not symbol or not instrument_key:
                return None
            
            # Initialize stock analytics
            analytics = StockAnalytics(
                symbol=symbol,
                instrument_key=instrument_key,
                current_price=0.0,
                previous_close=0.0,
                change_percent=0.0,
                volume=0,
                avg_volume=0.0,
                volume_ratio=0.0
            )
            
            # Extract basic market data
            await self._extract_basic_market_data(analytics, candidate)
            
            # Analyze using each criteria
            total_score = 0.0
            weights = self.config.selection_weights
            
            for criteria, processor in self._criteria_processors.items():
                try:
                    score = await processor(analytics)
                    weight = getattr(weights, criteria.value, 0.1)
                    weighted_score = score * weight
                    total_score += weighted_score
                    
                    if score > 0.7:  # Strong signal
                        analytics.selection_reasons.append(f"Strong {criteria.value}")
                    
                except Exception as e:
                    logger.debug(f"Criteria {criteria.value} analysis error: {e}")
                    continue
            
            analytics.overall_score = total_score
            analytics.confidence_level = min(total_score, 1.0)
            
            return analytics
            
        except Exception as e:
            logger.error(f"Comprehensive analysis error for {candidate}: {e}")
            return None
    
    async def _extract_basic_market_data(
        self, 
        analytics: StockAnalytics, 
        candidate: Dict[str, Any]
    ) -> None:
        """Extract basic market data for the instrument"""
        try:
            # Try to get data from top movers cache
            if self._market_analytics_cache.get('top_movers'):
                movers = self._market_analytics_cache['top_movers']
                
                # Search in gainers
                for item in movers.get('gainers', []):
                    if item.get('symbol') == analytics.symbol:
                        analytics.current_price = float(item.get('current_price', 0))
                        analytics.previous_close = float(item.get('previous_close', 0))
                        analytics.change_percent = float(item.get('change_percent', 0))
                        analytics.volume = int(item.get('volume', 0))
                        analytics.volume_ratio = float(item.get('volume_ratio', 1.0))
                        return
                
                # Search in losers
                for item in movers.get('losers', []):
                    if item.get('symbol') == analytics.symbol:
                        analytics.current_price = float(item.get('current_price', 0))
                        analytics.previous_close = float(item.get('previous_close', 0))
                        analytics.change_percent = float(item.get('change_percent', 0))
                        analytics.volume = int(item.get('volume', 0))
                        analytics.volume_ratio = float(item.get('volume_ratio', 1.0))
                        return
            
            # Default values if not found
            analytics.current_price = 100.0  # Placeholder
            analytics.previous_close = 100.0
            analytics.change_percent = 0.0
            analytics.volume = 100000
            analytics.volume_ratio = 1.0
            
        except Exception as e:
            logger.error(f"Basic market data extraction error: {e}")
    
    # Criteria analysis methods
    async def _analyze_market_sentiment_alignment(self, analytics: StockAnalytics) -> float:
        """Analyze alignment with overall market sentiment"""
        try:
            market_sentiment = self._market_analytics_cache.get('sentiment', {})
            sentiment_value = market_sentiment.get('sentiment', 'neutral')
            
            # Check if stock movement aligns with market sentiment
            if sentiment_value in ['bullish', 'very_bullish'] and analytics.change_percent > 0:
                return 0.8
            elif sentiment_value in ['bearish', 'very_bearish'] and analytics.change_percent < 0:
                return 0.8
            elif sentiment_value == 'neutral':
                return 0.5
            else:
                return 0.2  # Counter-trend
                
        except Exception:
            return 0.5
    
    async def _analyze_sector_momentum(self, analytics: StockAnalytics) -> float:
        """Analyze sector momentum alignment"""
        try:
            sector_performance = self._market_analytics_cache.get('sector_performance', {})
            
            # Would need to map symbol to sector and check sector performance
            # For now, return moderate score
            return 0.6
            
        except Exception:
            return 0.5
    
    async def _analyze_adr_alignment(self, analytics: StockAnalytics) -> float:
        """Analyze alignment with Advance Decline Ratio"""
        try:
            # Check if stock contributes positively to ADR
            if analytics.change_percent > 0:
                return 0.7  # Contributing to advancing count
            else:
                return 0.3  # Contributing to declining count
                
        except Exception:
            return 0.5
    
    async def _analyze_breakout_signals(self, analytics: StockAnalytics) -> float:
        """Analyze breakout signals for the stock"""
        try:
            breakout_signals = self._breakout_cache.get('breakout_signals', [])
            
            # Find breakout signals for this stock
            stock_breakouts = [
                signal for signal in breakout_signals 
                if signal.get('symbol') == analytics.symbol
            ]
            
            if stock_breakouts:
                # Get the strongest breakout signal
                strongest = max(stock_breakouts, key=lambda x: x.get('confidence_score', 0))
                analytics.breakout_signals = stock_breakouts
                return strongest.get('confidence_score', 0.5)
            
            return 0.4  # No breakout signals
            
        except Exception:
            return 0.4
    
    async def _analyze_gap_opportunities(self, analytics: StockAnalytics) -> float:
        """Analyze gap trading opportunities"""
        try:
            gap_signals = self._gap_cache.get('gap_signals', [])
            
            # Find gap signals for this stock
            stock_gaps = [
                signal for signal in gap_signals 
                if signal.get('symbol') == analytics.symbol
            ]
            
            if stock_gaps:
                # Get the strongest gap signal
                strongest = max(stock_gaps, key=lambda x: x.get('confidence_score', 0))
                analytics.gap_analysis = strongest
                return strongest.get('confidence_score', 0.5)
            
            return 0.4  # No gap opportunities
            
        except Exception:
            return 0.4
    
    async def _analyze_volume_confirmation(self, analytics: StockAnalytics) -> float:
        """Analyze volume confirmation"""
        try:
            if analytics.volume_ratio >= 3.0:
                return 0.9  # Very high volume
            elif analytics.volume_ratio >= 2.0:
                return 0.8  # High volume
            elif analytics.volume_ratio >= 1.5:
                return 0.7  # Above average volume
            elif analytics.volume_ratio >= 1.0:
                return 0.5  # Average volume
            else:
                return 0.3  # Below average volume
                
        except Exception:
            return 0.5
    
    async def _analyze_options_liquidity(self, analytics: StockAnalytics) -> float:
        """Analyze options liquidity and availability"""
        try:
            # This would integrate with option service to check liquidity
            # For now, return moderate score for major stocks
            if analytics.symbol in ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS', 'HDFCBANK']:
                return 0.8  # High liquidity expected
            else:
                return 0.5  # Moderate liquidity
                
        except Exception:
            return 0.5
    
    async def _analyze_technical_strength(self, analytics: StockAnalytics) -> float:
        """Analyze overall technical strength"""
        try:
            score = 0.5  # Base score
            
            # Price momentum factor
            if abs(analytics.change_percent) >= 3.0:
                score += 0.2
            elif abs(analytics.change_percent) >= 1.5:
                score += 0.1
            
            # Volume factor
            if analytics.volume_ratio >= 2.0:
                score += 0.2
            elif analytics.volume_ratio >= 1.5:
                score += 0.1
            
            # Breakout factor
            if analytics.breakout_signals:
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception:
            return 0.5
    
    async def _analyze_risk_reward_ratio(self, analytics: StockAnalytics) -> float:
        """Analyze risk-reward potential"""
        try:
            # Simple risk-reward based on volatility and momentum
            if abs(analytics.change_percent) >= 2.0 and analytics.volume_ratio >= 1.5:
                return 0.8  # Good risk-reward
            elif abs(analytics.change_percent) >= 1.0:
                return 0.6  # Moderate risk-reward
            else:
                return 0.4  # Lower risk-reward
                
        except Exception:
            return 0.5
    
    async def _apply_selection_mode_filter(
        self,
        analyzed_stocks: List[StockAnalytics],
        market_condition: MarketCondition
    ) -> List[StockAnalytics]:
        """Apply selection mode specific filtering"""
        try:
            if self.config.selection_mode == SelectionMode.MOMENTUM_BASED:
                return self._filter_momentum_stocks(analyzed_stocks, market_condition)
            elif self.config.selection_mode == SelectionMode.BREAKOUT_FOCUSED:
                return self._filter_breakout_stocks(analyzed_stocks)
            elif self.config.selection_mode == SelectionMode.GAP_TRADING:
                return self._filter_gap_stocks(analyzed_stocks)
            elif self.config.selection_mode == SelectionMode.MEAN_REVERSION:
                return self._filter_mean_reversion_stocks(analyzed_stocks)
            elif self.config.selection_mode == SelectionMode.SECTOR_ROTATION:
                return self._filter_sector_rotation_stocks(analyzed_stocks)
            else:  # HYBRID
                return analyzed_stocks  # Use all qualifying stocks
                
        except Exception as e:
            logger.error(f"Selection mode filter error: {e}")
            return analyzed_stocks
    
    def _filter_momentum_stocks(
        self, 
        stocks: List[StockAnalytics], 
        market_condition: MarketCondition
    ) -> List[StockAnalytics]:
        """Filter stocks for momentum trading"""
        filtered = []
        for stock in stocks:
            if (abs(stock.change_percent) >= 1.5 and 
                stock.volume_ratio >= 1.5 and
                stock.overall_score >= 0.6):
                filtered.append(stock)
        return filtered
    
    def _filter_breakout_stocks(self, stocks: List[StockAnalytics]) -> List[StockAnalytics]:
        """Filter stocks with breakout signals"""
        return [stock for stock in stocks if stock.breakout_signals and stock.overall_score >= 0.6]
    
    def _filter_gap_stocks(self, stocks: List[StockAnalytics]) -> List[StockAnalytics]:
        """Filter stocks with gap opportunities"""
        return [stock for stock in stocks if stock.gap_analysis and stock.overall_score >= 0.6]
    
    def _filter_mean_reversion_stocks(self, stocks: List[StockAnalytics]) -> List[StockAnalytics]:
        """Filter stocks for mean reversion trading"""
        filtered = []
        for stock in stocks:
            # Look for oversold/overbought conditions
            if (abs(stock.change_percent) >= 2.0 and 
                stock.volume_ratio >= 1.5 and
                stock.overall_score >= 0.5):
                filtered.append(stock)
        return filtered
    
    def _filter_sector_rotation_stocks(self, stocks: List[StockAnalytics]) -> List[StockAnalytics]:
        """Filter stocks based on sector rotation"""
        # Group by sector and select best from each
        sector_groups = defaultdict(list)
        for stock in stocks:
            sector_groups[stock.sector].append(stock)
        
        filtered = []
        for sector_stocks in sector_groups.values():
            if sector_stocks:
                best_stock = max(sector_stocks, key=lambda x: x.overall_score)
                if best_stock.overall_score >= 0.6:
                    filtered.append(best_stock)
        
        return filtered
    
    async def _rank_and_select_stocks(
        self,
        filtered_stocks: List[StockAnalytics],
        market_condition: MarketCondition
    ) -> List[StockAnalytics]:
        """Rank filtered stocks and select top candidates"""
        try:
            # Sort by overall score
            ranked_stocks = sorted(filtered_stocks, key=lambda x: x.overall_score, reverse=True)
            
            # Select top stocks based on configuration
            max_total = self.config.max_stocks + self.config.max_indices
            
            selected = []
            stock_count = 0
            index_count = 0
            
            for stock in ranked_stocks:
                if len(selected) >= max_total:
                    break
                
                if stock.symbol in ['NIFTY', 'BANKNIFTY', 'FINNIFTY']:
                    if index_count < self.config.max_indices:
                        selected.append(stock)
                        index_count += 1
                else:
                    if stock_count < self.config.max_stocks:
                        selected.append(stock)
                        stock_count += 1
            
            return selected
            
        except Exception as e:
            logger.error(f"Ranking and selection error: {e}")
            return filtered_stocks[:self.config.max_stocks]
    
    async def _generate_selection_result(
        self,
        stock_analytics: StockAnalytics,
        market_condition: MarketCondition
    ) -> Optional[SelectionResult]:
        """Generate final selection result with trading recommendations"""
        try:
            # Determine expected direction
            expected_direction = "NEUTRAL"
            if stock_analytics.change_percent > 1.0:
                expected_direction = "BULLISH"
            elif stock_analytics.change_percent < -1.0:
                expected_direction = "BEARISH"
            
            # Determine option recommendation
            recommended_option_type = "CE" if expected_direction == "BULLISH" else "PE"
            if market_condition in [MarketCondition.VOLATILE, MarketCondition.NEUTRAL]:
                recommended_option_type = "STRADDLE"
            
            # Calculate risk management parameters
            stop_loss = self._calculate_stop_loss(stock_analytics, expected_direction)
            target_price = self._calculate_target_price(stock_analytics, expected_direction)
            position_size = self._calculate_position_size(stock_analytics)
            
            # Calculate risk-reward ratio
            current_price = stock_analytics.current_price
            risk = abs(current_price - stop_loss)
            reward = abs(target_price - current_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Determine primary strategy
            primary_strategy = self._determine_primary_strategy(stock_analytics, market_condition)
            
            return SelectionResult(
                symbol=stock_analytics.symbol,
                instrument_key=stock_analytics.instrument_key,
                selection_score=stock_analytics.overall_score,
                selection_reasons=stock_analytics.selection_reasons,
                current_price=current_price,
                expected_direction=expected_direction,
                confidence_level=stock_analytics.confidence_level,
                recommended_option_type=recommended_option_type,
                atm_strike=stock_analytics.atm_strike,
                option_contract=None,  # Would be populated by option service
                position_size=position_size,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_reward_ratio=risk_reward_ratio,
                max_risk_amount=risk * position_size,
                primary_strategy=primary_strategy,
                market_condition=market_condition
            )
            
        except Exception as e:
            logger.error(f"Selection result generation error: {e}")
            return None
    
    def _calculate_stop_loss(
        self, 
        analytics: StockAnalytics, 
        direction: str
    ) -> float:
        """Calculate stop loss level"""
        current_price = analytics.current_price
        
        if direction == "BULLISH":
            # Stop loss below current price
            return current_price * 0.97  # 3% stop loss
        elif direction == "BEARISH":
            # Stop loss above current price
            return current_price * 1.03  # 3% stop loss
        else:
            # Neutral - tight stop loss
            return current_price * 0.99
    
    def _calculate_target_price(
        self, 
        analytics: StockAnalytics, 
        direction: str
    ) -> float:
        """Calculate target price"""
        current_price = analytics.current_price
        
        if direction == "BULLISH":
            # Target above current price
            return current_price * 1.05  # 5% target
        elif direction == "BEARISH":
            # Target below current price
            return current_price * 0.95  # 5% target
        else:
            # Neutral - modest target
            return current_price * 1.02
    
    def _calculate_position_size(self, analytics: StockAnalytics) -> int:
        """Calculate appropriate position size"""
        # Simple position sizing based on risk appetite and stock characteristics
        base_size = 100
        
        if analytics.overall_score >= 0.8:
            return base_size * 2  # High confidence
        elif analytics.overall_score >= 0.6:
            return base_size  # Medium confidence
        else:
            return base_size // 2  # Low confidence
    
    def _determine_primary_strategy(
        self, 
        analytics: StockAnalytics, 
        market_condition: MarketCondition
    ) -> str:
        """Determine primary trading strategy"""
        if analytics.breakout_signals:
            return "BREAKOUT_MOMENTUM"
        elif analytics.gap_analysis:
            return "GAP_TRADING"
        elif market_condition in [MarketCondition.STRONG_BULLISH, MarketCondition.STRONG_BEARISH]:
            return "TREND_FOLLOWING"
        elif market_condition == MarketCondition.VOLATILE:
            return "VOLATILITY_TRADING"
        else:
            return "MARKET_NEUTRAL"


# Singleton instance
_modular_stock_selector: Optional[ModularStockSelector] = None


def get_modular_stock_selector(config: Optional[StockSelectionConfig] = None) -> ModularStockSelector:
    """Get singleton modular stock selector instance"""
    global _modular_stock_selector
    if _modular_stock_selector is None:
        if not config:
            config = StockSelectionConfig()  # Use default config
        _modular_stock_selector = ModularStockSelector(config)
    return _modular_stock_selector


# Export main classes
__all__ = [
    "ModularStockSelector",
    "StockSelectionConfig",
    "SelectionResult",
    "StockAnalytics",
    "MarketCondition",
    "SelectionMode",
    "SelectionCriteria",
    "get_modular_stock_selector"
]