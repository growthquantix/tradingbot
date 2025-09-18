"""
Analytics Module Interfaces

Clean interfaces for analytics services following SOLID principles.
Defines contracts for different types of analytics calculations.

Author: Trading System  
Created: 2025-01-11
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime


@dataclass
class MarketTick:
    """Standardized market tick data structure"""
    instrument_key: str
    symbol: str
    last_price: Decimal
    volume: int
    timestamp: datetime
    change: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    open_price: Optional[Decimal] = None
    previous_close: Optional[Decimal] = None


@dataclass
class CalculatedFeatures:
    """Calculated features from market data"""
    symbol: str
    timestamp: datetime
    
    # Price-based features
    price_change: Decimal
    price_change_percent: Decimal
    momentum_score: Optional[Decimal] = None
    volatility_score: Optional[Decimal] = None
    
    # Volume-based features  
    volume_ratio: Optional[Decimal] = None
    volume_moving_avg: Optional[Decimal] = None
    
    # Technical indicators
    rsi: Optional[Decimal] = None
    moving_avg_20: Optional[Decimal] = None
    bollinger_upper: Optional[Decimal] = None
    bollinger_lower: Optional[Decimal] = None
    
    # Market context
    sector: Optional[str] = None
    market_cap_category: Optional[str] = None


@dataclass
class AnalyticsResult:
    """Result of analytics calculation"""
    calculation_type: str
    symbol: str
    timestamp: datetime
    data: Dict[str, Any]
    confidence_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class IFeatureCalculator(ABC):
    """Interface for feature calculation services"""
    
    @abstractmethod
    async def calculate_features(self, tick: MarketTick) -> CalculatedFeatures:
        """Calculate features for a market tick"""
        pass
    
    @abstractmethod
    async def calculate_batch_features(self, ticks: List[MarketTick]) -> List[CalculatedFeatures]:
        """Calculate features for a batch of ticks"""
        pass


class IAnalyticsCalculator(ABC):
    """Interface for analytics calculation services"""
    
    @abstractmethod
    async def calculate_top_movers(self, features: List[CalculatedFeatures]) -> AnalyticsResult:
        """Calculate top movers (gainers/losers)"""
        pass
    
    @abstractmethod
    async def calculate_breakout_candidates(self, features: List[CalculatedFeatures]) -> AnalyticsResult:
        """Identify breakout candidates"""
        pass
    
    @abstractmethod
    async def calculate_volume_alerts(self, features: List[CalculatedFeatures]) -> AnalyticsResult:
        """Identify volume spike alerts"""
        pass
    
    @abstractmethod
    async def calculate_sector_performance(self, features: List[CalculatedFeatures]) -> AnalyticsResult:
        """Calculate sector performance metrics"""
        pass


class IKafkaPublisher(ABC):
    """Interface for Kafka publishing"""
    
    @abstractmethod
    async def publish_to_analytics_topic(self, data: Dict[str, Any], topic: str) -> bool:
        """Publish data to analytics Kafka topic"""
        pass
    
    @abstractmethod
    async def publish_to_ui_topic(self, data: Dict[str, Any]) -> bool:
        """Publish data to UI Kafka topic"""
        pass


class ISSEBroadcaster(ABC):
    """Interface for SSE broadcasting"""
    
    @abstractmethod
    async def broadcast_analytics_update(self, analytics_result: AnalyticsResult) -> bool:
        """Broadcast analytics update via SSE"""
        pass
    
    @abstractmethod
    async def broadcast_feature_update(self, features: List[CalculatedFeatures]) -> bool:
        """Broadcast feature updates via SSE"""
        pass