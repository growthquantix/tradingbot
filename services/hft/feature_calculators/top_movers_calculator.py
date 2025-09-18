"""
Top Movers Calculator - Real-Time Gainers and Losers Detection

Calculates live top gainers, top losers, and most active stocks
with sector-wise breakdown and volume confirmation.

Author: Trading System
Created: 2025-01-11
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
import heapq
from collections import defaultdict

from .base_calculator import BaseFeatureCalculator, calculate_percentage_change

logger = logging.getLogger(__name__)


@dataclass
class MoverStock:
    """Individual stock in top movers list"""
    symbol: str
    instrument_key: str
    current_price: float
    previous_close: float
    change: float
    change_percent: float
    volume: int
    volume_ratio: float  # Current volume vs average volume
    sector: str
    market_cap_category: str
    turnover: float
    last_update: datetime


@dataclass
class TopMoversResult:
    """Complete top movers calculation result"""
    top_gainers: List[MoverStock]
    top_losers: List[MoverStock]
    most_active_by_volume: List[MoverStock]
    most_active_by_value: List[MoverStock]
    sector_wise_leaders: Dict[str, MoverStock]
    sector_wise_laggards: Dict[str, MoverStock]
    market_summary: Dict[str, Any]
    calculation_timestamp: datetime


class TopMoversCalculator(BaseFeatureCalculator):
    """
    Real-time Top Movers Calculator
    
    Features:
    - Top gainers and losers by percentage change
    - Most active stocks by volume and value
    - Sector-wise top performers and laggards
    - Volume confirmation for moves
    - Market summary statistics
    - Configurable list sizes and filters
    """
    
    def __init__(
        self,
        top_count: int = 10,
        min_price: float = 10.0,
        min_volume: int = 10000,
        calculation_interval_ms: int = 5000  # Update every 5 seconds
    ):
        super().__init__(
            calculator_name="top_movers",
            calculation_interval_ms=calculation_interval_ms
        )
        
        self.top_count = top_count
        self.min_price = min_price
        self.min_volume = min_volume
        
        # Storage for stock data
        self._stock_data: Dict[str, Dict[str, Any]] = {}
        self._sector_mapping: Dict[str, str] = {}
        self._market_cap_mapping: Dict[str, str] = {}
        self._average_volumes: Dict[str, float] = {}
        
        # Pre-calculated lists for efficiency
        self._gainers_heap: List[Tuple[float, MoverStock]] = []
        self._losers_heap: List[Tuple[float, MoverStock]] = []
        self._volume_heap: List[Tuple[int, MoverStock]] = []
        self._value_heap: List[Tuple[float, MoverStock]] = []
        
        logger.info(f"TopMoversCalculator initialized with top_count={top_count}")
    
    def _initialize_required_fields(self) -> None:
        """Initialize required fields for top movers calculation"""
        self._required_fields = {
            'ltp', 'previous_close', 'change', 'change_percent',
            'volume', 'instrument_key'
        }
    
    async def _calculate_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate top movers from live feed data"""
        try:
            feeds = data.get('feeds', {})
            
            # Update stock data
            await self._update_stock_data(feeds)
            
            # Filter eligible stocks
            eligible_stocks = self._filter_eligible_stocks()
            
            if len(eligible_stocks) < 5:  # Need minimum stocks for meaningful results
                return self._get_empty_result()
            
            # Calculate top movers
            top_gainers = self._calculate_top_gainers(eligible_stocks)
            top_losers = self._calculate_top_losers(eligible_stocks)
            most_active_volume = self._calculate_most_active_by_volume(eligible_stocks)
            most_active_value = self._calculate_most_active_by_value(eligible_stocks)
            
            # Calculate sector-wise leaders and laggards
            sector_leaders, sector_laggards = self._calculate_sector_wise_movers(eligible_stocks)
            
            # Generate market summary
            market_summary = self._generate_market_summary(eligible_stocks)
            
            result = TopMoversResult(
                top_gainers=top_gainers,
                top_losers=top_losers,
                most_active_by_volume=most_active_volume,
                most_active_by_value=most_active_value,
                sector_wise_leaders=sector_leaders,
                sector_wise_laggards=sector_laggards,
                market_summary=market_summary,
                calculation_timestamp=datetime.now()
            )
            
            return {
                'top_gainers': [self._mover_to_dict(stock) for stock in result.top_gainers],
                'top_losers': [self._mover_to_dict(stock) for stock in result.top_losers],
                'most_active_volume': [self._mover_to_dict(stock) for stock in result.most_active_by_volume],
                'most_active_value': [self._mover_to_dict(stock) for stock in result.most_active_by_value],
                'sector_leaders': {sector: self._mover_to_dict(stock) for sector, stock in result.sector_wise_leaders.items()},
                'sector_laggards': {sector: self._mover_to_dict(stock) for sector, stock in result.sector_wise_laggards.items()},
                'market_summary': result.market_summary,
                'total_stocks_analyzed': len(eligible_stocks),
                'calculation_timestamp': result.calculation_timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Top movers calculation error: {e}")
            return self._get_empty_result()
    
    async def _update_stock_data(self, feeds: Dict[str, Any]) -> None:
        """Update internal stock data from live feeds"""
        try:
            for instrument_key, feed_data in feeds.items():
                # Extract symbol from instrument key (simplified)
                symbol = self._extract_symbol_from_key(instrument_key)
                
                # Get or create stock data entry
                if symbol not in self._stock_data:
                    self._stock_data[symbol] = {}
                
                stock_data = self._stock_data[symbol]
                
                # Update stock data
                stock_data.update({
                    'symbol': symbol,
                    'instrument_key': instrument_key,
                    'current_price': feed_data.get('ltp', 0),
                    'previous_close': feed_data.get('previous_close', 0),
                    'change': feed_data.get('change', 0),
                    'change_percent': feed_data.get('change_percent', 0),
                    'volume': feed_data.get('volume', 0),
                    'last_update': datetime.now(),
                    'open': feed_data.get('open', 0),
                    'high': feed_data.get('high', 0),
                    'low': feed_data.get('low', 0)
                })
                
                # Calculate turnover (volume * current price)
                turnover = stock_data['volume'] * stock_data['current_price']
                stock_data['turnover'] = turnover
                
                # Estimate volume ratio (simplified - would need historical average)
                avg_volume = self._average_volumes.get(symbol, stock_data['volume'])
                volume_ratio = stock_data['volume'] / avg_volume if avg_volume > 0 else 1.0
                stock_data['volume_ratio'] = volume_ratio
                
                # Set sector and market cap (would be enriched from instrument registry)
                stock_data['sector'] = self._get_sector_for_symbol(symbol)
                stock_data['market_cap_category'] = self._get_market_cap_for_symbol(symbol)
                
        except Exception as e:
            logger.error(f"Stock data update error: {e}")
    
    def _extract_symbol_from_key(self, instrument_key: str) -> str:
        """Extract trading symbol from instrument key"""
        try:
            # Format: NSE_EQ|INE318A01026 -> would need mapping to get symbol
            # For now, use a simplified approach
            parts = instrument_key.split('|')
            if len(parts) == 2:
                # Would lookup symbol from ISIN in real implementation
                return instrument_key.replace('|', '_')  # Temporary
            return instrument_key
        except Exception:
            return instrument_key
    
    def _get_sector_for_symbol(self, symbol: str) -> str:
        """Get sector for symbol (would integrate with instrument registry)"""
        # Simplified sector mapping - would be from instrument registry
        sector_mapping = {
            'RELIANCE': 'ENERGY',
            'TCS': 'IT',
            'INFY': 'IT',
            'HDFCBANK': 'BANKING',
            'ICICIBANK': 'BANKING',
            'ITC': 'FMCG'
        }
        return sector_mapping.get(symbol, 'OTHER')
    
    def _get_market_cap_for_symbol(self, symbol: str) -> str:
        """Get market cap category for symbol"""
        # Simplified market cap mapping
        large_cap_symbols = {'RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY'}
        return 'LARGE_CAP' if symbol in large_cap_symbols else 'MID_CAP'
    
    def _filter_eligible_stocks(self) -> List[Dict[str, Any]]:
        """Filter stocks based on minimum criteria"""
        eligible = []
        
        for symbol, stock_data in self._stock_data.items():
            try:
                # Apply filters
                if (stock_data.get('current_price', 0) >= self.min_price and
                    stock_data.get('volume', 0) >= self.min_volume and
                    stock_data.get('previous_close', 0) > 0):
                    
                    eligible.append(stock_data)
                    
            except Exception as e:
                logger.error(f"Stock filtering error for {symbol}: {e}")
        
        return eligible
    
    def _calculate_top_gainers(self, stocks: List[Dict[str, Any]]) -> List[MoverStock]:
        """Calculate top gainers by percentage change"""
        try:
            # Sort by change_percent descending
            sorted_stocks = sorted(
                stocks, 
                key=lambda x: x.get('change_percent', 0), 
                reverse=True
            )
            
            top_gainers = []
            for stock_data in sorted_stocks[:self.top_count]:
                if stock_data.get('change_percent', 0) > 0:  # Only positive changes
                    mover = self._create_mover_stock(stock_data)
                    if mover:
                        top_gainers.append(mover)
            
            return top_gainers
            
        except Exception as e:
            logger.error(f"Top gainers calculation error: {e}")
            return []
    
    def _calculate_top_losers(self, stocks: List[Dict[str, Any]]) -> List[MoverStock]:
        """Calculate top losers by percentage change"""
        try:
            # Sort by change_percent ascending (most negative first)
            sorted_stocks = sorted(
                stocks, 
                key=lambda x: x.get('change_percent', 0)
            )
            
            top_losers = []
            for stock_data in sorted_stocks[:self.top_count]:
                if stock_data.get('change_percent', 0) < 0:  # Only negative changes
                    mover = self._create_mover_stock(stock_data)
                    if mover:
                        top_losers.append(mover)
            
            return top_losers
            
        except Exception as e:
            logger.error(f"Top losers calculation error: {e}")
            return []
    
    def _calculate_most_active_by_volume(self, stocks: List[Dict[str, Any]]) -> List[MoverStock]:
        """Calculate most active stocks by volume"""
        try:
            # Sort by volume descending
            sorted_stocks = sorted(
                stocks, 
                key=lambda x: x.get('volume', 0), 
                reverse=True
            )
            
            most_active = []
            for stock_data in sorted_stocks[:self.top_count]:
                mover = self._create_mover_stock(stock_data)
                if mover:
                    most_active.append(mover)
            
            return most_active
            
        except Exception as e:
            logger.error(f"Most active by volume calculation error: {e}")
            return []
    
    def _calculate_most_active_by_value(self, stocks: List[Dict[str, Any]]) -> List[MoverStock]:
        """Calculate most active stocks by turnover value"""
        try:
            # Sort by turnover descending
            sorted_stocks = sorted(
                stocks, 
                key=lambda x: x.get('turnover', 0), 
                reverse=True
            )
            
            most_active = []
            for stock_data in sorted_stocks[:self.top_count]:
                mover = self._create_mover_stock(stock_data)
                if mover:
                    most_active.append(mover)
            
            return most_active
            
        except Exception as e:
            logger.error(f"Most active by value calculation error: {e}")
            return []
    
    def _calculate_sector_wise_movers(
        self, 
        stocks: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, MoverStock], Dict[str, MoverStock]]:
        """Calculate sector-wise leaders and laggards"""
        try:
            sector_stocks = defaultdict(list)
            
            # Group stocks by sector
            for stock_data in stocks:
                sector = stock_data.get('sector', 'OTHER')
                sector_stocks[sector].append(stock_data)
            
            sector_leaders = {}
            sector_laggards = {}
            
            # Find leader and laggard for each sector
            for sector, sector_stock_list in sector_stocks.items():
                if len(sector_stock_list) == 0:
                    continue
                
                # Leader: highest change_percent in sector
                leader_data = max(sector_stock_list, key=lambda x: x.get('change_percent', 0))
                leader = self._create_mover_stock(leader_data)
                if leader:
                    sector_leaders[sector] = leader
                
                # Laggard: lowest change_percent in sector
                laggard_data = min(sector_stock_list, key=lambda x: x.get('change_percent', 0))
                laggard = self._create_mover_stock(laggard_data)
                if laggard:
                    sector_laggards[sector] = laggard
            
            return sector_leaders, sector_laggards
            
        except Exception as e:
            logger.error(f"Sector-wise movers calculation error: {e}")
            return {}, {}
    
    def _generate_market_summary(self, stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate overall market summary statistics"""
        try:
            if not stocks:
                return {}
            
            total_stocks = len(stocks)
            advancing = len([s for s in stocks if s.get('change_percent', 0) > 0])
            declining = len([s for s in stocks if s.get('change_percent', 0) < 0])
            unchanged = total_stocks - advancing - declining
            
            # Calculate average change
            total_change = sum(s.get('change_percent', 0) for s in stocks)
            avg_change = total_change / total_stocks if total_stocks > 0 else 0
            
            # Calculate total volume and turnover
            total_volume = sum(s.get('volume', 0) for s in stocks)
            total_turnover = sum(s.get('turnover', 0) for s in stocks)
            
            # Advance-Decline Ratio
            adr = advancing / declining if declining > 0 else float('inf')
            
            return {
                'total_stocks': total_stocks,
                'advancing': advancing,
                'declining': declining,
                'unchanged': unchanged,
                'advance_decline_ratio': round(adr, 2),
                'average_change_percent': round(avg_change, 2),
                'total_volume': total_volume,
                'total_turnover': total_turnover,
                'market_sentiment': 'BULLISH' if advancing > declining else 'BEARISH' if declining > advancing else 'NEUTRAL'
            }
            
        except Exception as e:
            logger.error(f"Market summary generation error: {e}")
            return {}
    
    def _create_mover_stock(self, stock_data: Dict[str, Any]) -> Optional[MoverStock]:
        """Create MoverStock object from stock data"""
        try:
            return MoverStock(
                symbol=stock_data.get('symbol', ''),
                instrument_key=stock_data.get('instrument_key', ''),
                current_price=float(stock_data.get('current_price', 0)),
                previous_close=float(stock_data.get('previous_close', 0)),
                change=float(stock_data.get('change', 0)),
                change_percent=float(stock_data.get('change_percent', 0)),
                volume=int(stock_data.get('volume', 0)),
                volume_ratio=float(stock_data.get('volume_ratio', 1.0)),
                sector=stock_data.get('sector', 'OTHER'),
                market_cap_category=stock_data.get('market_cap_category', 'UNKNOWN'),
                turnover=float(stock_data.get('turnover', 0)),
                last_update=stock_data.get('last_update', datetime.now())
            )
            
        except Exception as e:
            logger.error(f"MoverStock creation error: {e}")
            return None
    
    def _mover_to_dict(self, mover: MoverStock) -> Dict[str, Any]:
        """Convert MoverStock to dictionary for JSON serialization"""
        return {
            'symbol': mover.symbol,
            'instrument_key': mover.instrument_key,
            'current_price': mover.current_price,
            'previous_close': mover.previous_close,
            'change': mover.change,
            'change_percent': round(mover.change_percent, 2),
            'volume': mover.volume,
            'volume_ratio': round(mover.volume_ratio, 2),
            'sector': mover.sector,
            'market_cap_category': mover.market_cap_category,
            'turnover': mover.turnover,
            'last_update': mover.last_update.isoformat()
        }
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """Get empty result structure"""
        return {
            'top_gainers': [],
            'top_losers': [],
            'most_active_volume': [],
            'most_active_value': [],
            'sector_leaders': {},
            'sector_laggards': {},
            'market_summary': {},
            'total_stocks_analyzed': 0,
            'calculation_timestamp': datetime.now().isoformat()
        }


# Singleton instance
_top_movers_calculator: Optional[TopMoversCalculator] = None


def get_top_movers_calculator() -> TopMoversCalculator:
    """Get singleton top movers calculator instance"""
    global _top_movers_calculator
    if _top_movers_calculator is None:
        _top_movers_calculator = TopMoversCalculator()
    return _top_movers_calculator


# Export main classes
__all__ = [
    "TopMoversCalculator",
    "MoverStock",
    "TopMoversResult",
    "get_top_movers_calculator"
]