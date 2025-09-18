"""
Enhanced Breakout Detection Calculator

Production-grade breakout detection with:
- Vectorized NumPy operations for performance
- Multiple breakout pattern recognition
- Volume confirmation analysis
- Support/resistance level detection
- Real-time and batch processing modes

Author: Trading System
Created: 2025-01-11
"""

import logging
from typing import Dict, List, Any, Tuple
import numpy as np
import pandas as pd
from datetime import datetime

from .enhanced_base_calculator import EnhancedBaseCalculator, CalculationConfig, CalculationType
from ..partition_strategy import ServiceType

logger = logging.getLogger(__name__)


class EnhancedBreakoutCalculator(EnhancedBaseCalculator):
    """
    Enhanced breakout detection calculator with multiple pattern recognition
    
    Detects:
    - Resistance breakouts with volume confirmation
    - Support breakdowns with volume analysis
    - Range breakouts (consolidation patterns)
    - High-tight flag patterns
    - Cup and handle breakouts
    - Triangle breakout patterns
    """
    
    def __init__(self, config: CalculationConfig = None):
        if config is None:
            config = CalculationConfig(
                calculation_type=CalculationType.STREAMING,
                window_size=20,
                min_data_points=10,
                precision=4
            )
        
        super().__init__(config)
        
        # Breakout detection parameters
        self.lookback_periods = 20
        self.volume_threshold_multiplier = 1.5
        self.min_consolidation_periods = 5
        self.breakout_percentage_threshold = 0.5  # 0.5% minimum breakout
        self.support_resistance_touch_threshold = 0.2  # 0.2% proximity for S/R
        
    def get_feature_name(self) -> str:
        return "enhanced_breakout_detection"
    
    def get_service_type(self) -> ServiceType:
        return ServiceType.BREAKOUT_DETECTION
    
    def get_required_fields(self) -> List[str]:
        return ['ltp', 'high', 'low', 'volume', 'timestamp', 'instrument_key', 'symbol']
    
    async def _calculate_vectorized_impl(
        self,
        df: pd.DataFrame,
        price_arrays: Dict[str, np.ndarray],
        volume_arrays: Dict[str, np.ndarray]
    ) -> List[Dict[str, Any]]:
        """Vectorized breakout detection for streaming mode"""
        
        results = []
        
        # Group by instrument for individual analysis
        for instrument_key, group in df.groupby('instrument_key'):
            try:
                # Get historical arrays for this instrument
                price_history = price_arrays.get(instrument_key, np.array([]))
                volume_history = volume_arrays.get(instrument_key, np.array([]))
                
                if len(price_history) < self.config.min_data_points:
                    continue
                
                # Calculate breakouts for this instrument
                breakouts = self._detect_breakouts_vectorized(
                    group, price_history, volume_history
                )
                
                results.extend(breakouts)
                
            except Exception as e:
                logger.error(f"Error calculating breakouts for {instrument_key}: {e}")
                continue
        
        return results
    
    async def _calculate_batch_impl(
        self,
        df: pd.DataFrame,
        price_arrays: Dict[str, np.ndarray],
        volume_arrays: Dict[str, np.ndarray]
    ) -> List[Dict[str, Any]]:
        """Batch breakout detection with historical analysis"""
        
        results = []
        
        # Process all instruments in batch mode
        for instrument_key in df['instrument_key'].unique():
            try:
                instrument_df = df[df['instrument_key'] == instrument_key].copy()
                
                # Sort by timestamp for proper analysis
                instrument_df = instrument_df.sort_values('timestamp')
                
                # Calculate comprehensive breakout analysis
                breakouts = self._analyze_historical_breakouts(instrument_df)
                
                results.extend(breakouts)
                
            except Exception as e:
                logger.error(f"Error in batch breakout analysis for {instrument_key}: {e}")
                continue
        
        return results
    
    def _detect_breakouts_vectorized(
        self,
        df: pd.DataFrame,
        price_history: np.ndarray,
        volume_history: np.ndarray
    ) -> List[Dict[str, Any]]:
        """Detect breakouts using vectorized operations"""
        
        breakouts = []
        
        if len(df) == 0 or len(price_history) < self.lookback_periods:
            return breakouts
        
        try:
            # Get current data point
            current_row = df.iloc[-1]
            current_price = current_row['ltp']
            current_volume = current_row['volume'] if 'volume' in df.columns else 0
            current_high = current_row['high'] if 'high' in df.columns else current_price
            current_low = current_row['low'] if 'low' in df.columns else current_price
            
            # Calculate support and resistance levels
            lookback_highs = price_history[-self.lookback_periods:]
            lookback_lows = price_history[-self.lookback_periods:] if 'low' in df.columns else lookback_highs
            lookback_volumes = volume_history[-self.lookback_periods:] if len(volume_history) >= self.lookback_periods else np.zeros(self.lookback_periods)
            
            # Calculate key levels
            resistance_level = np.max(lookback_highs)
            support_level = np.min(lookback_lows)
            avg_volume = np.mean(lookback_volumes) if np.sum(lookback_volumes) > 0 else 1
            range_size = resistance_level - support_level
            
            # Volume confirmation
            volume_spike = current_volume > (avg_volume * self.volume_threshold_multiplier)
            
            # Resistance breakout detection
            if current_price > resistance_level:
                breakout_strength = (current_price - resistance_level) / resistance_level * 100
                
                if breakout_strength > self.breakout_percentage_threshold:
                    breakout = {
                        'instrument_key': current_row['instrument_key'],
                        'symbol': current_row['symbol'],
                        'breakout_type': 'resistance_breakout',
                        'current_price': float(current_price),
                        'breakout_level': float(resistance_level),
                        'breakout_strength_percent': round(breakout_strength, 4),
                        'volume_confirmation': volume_spike,
                        'current_volume': int(current_volume),
                        'avg_volume': float(avg_volume),
                        'volume_ratio': float(current_volume / avg_volume) if avg_volume > 0 else 0,
                        'range_size': float(range_size),
                        'support_level': float(support_level),
                        'timestamp': datetime.now().isoformat(),
                        'confidence_score': self._calculate_confidence_score(
                            breakout_strength, volume_spike, range_size, resistance_level
                        )
                    }
                    
                    breakouts.append(breakout)
            
            # Support breakdown detection
            elif current_price < support_level:
                breakdown_strength = (support_level - current_price) / support_level * 100
                
                if breakdown_strength > self.breakout_percentage_threshold:
                    breakout = {
                        'instrument_key': current_row['instrument_key'],
                        'symbol': current_row['symbol'],
                        'breakout_type': 'support_breakdown',
                        'current_price': float(current_price),
                        'breakout_level': float(support_level),
                        'breakout_strength_percent': round(breakdown_strength, 4),
                        'volume_confirmation': volume_spike,
                        'current_volume': int(current_volume),
                        'avg_volume': float(avg_volume),
                        'volume_ratio': float(current_volume / avg_volume) if avg_volume > 0 else 0,
                        'range_size': float(range_size),
                        'resistance_level': float(resistance_level),
                        'timestamp': datetime.now().isoformat(),
                        'confidence_score': self._calculate_confidence_score(
                            breakdown_strength, volume_spike, range_size, support_level
                        )
                    }
                    
                    breakouts.append(breakout)
            
            # Range breakout detection (for consolidation patterns)
            elif range_size > 0:
                range_position = (current_price - support_level) / range_size
                
                # Check for range expansion with volume
                if volume_spike and (range_position > 0.8 or range_position < 0.2):
                    breakout_type = "range_expansion_up" if range_position > 0.8 else "range_expansion_down"
                    
                    breakout = {
                        'instrument_key': current_row['instrument_key'],
                        'symbol': current_row['symbol'],
                        'breakout_type': breakout_type,
                        'current_price': float(current_price),
                        'range_position': round(range_position, 4),
                        'resistance_level': float(resistance_level),
                        'support_level': float(support_level),
                        'volume_confirmation': volume_spike,
                        'current_volume': int(current_volume),
                        'volume_ratio': float(current_volume / avg_volume) if avg_volume > 0 else 0,
                        'range_size': float(range_size),
                        'timestamp': datetime.now().isoformat(),
                        'confidence_score': self._calculate_confidence_score(
                            abs(range_position - 0.5) * 100, volume_spike, range_size, current_price
                        )
                    }
                    
                    breakouts.append(breakout)
            
        except Exception as e:
            logger.error(f"Error in vectorized breakout detection: {e}")
        
        return breakouts
    
    def _analyze_historical_breakouts(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Analyze historical breakouts for batch processing"""
        
        breakouts = []
        
        if len(df) < self.lookback_periods:
            return breakouts
        
        try:
            # Convert to numpy arrays for efficient processing
            prices = df['ltp'].values
            volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
            timestamps = pd.to_datetime(df['timestamp']).values
            
            # Calculate rolling support and resistance
            resistance_levels = self._calculate_rolling_resistance(prices, self.lookback_periods)
            support_levels = self._calculate_rolling_support(prices, self.lookback_periods)
            
            # Calculate rolling volume averages
            volume_averages = self._calculate_rolling_average(volumes, self.lookback_periods)
            
            # Detect breakouts at each point
            for i in range(self.lookback_periods, len(prices)):
                try:
                    current_price = prices[i]
                    current_volume = volumes[i]
                    resistance = resistance_levels[i]
                    support = support_levels[i]
                    avg_volume = volume_averages[i]
                    
                    # Volume spike detection
                    volume_spike = current_volume > (avg_volume * self.volume_threshold_multiplier)
                    
                    # Resistance breakout
                    if current_price > resistance and resistance > 0:
                        strength = (current_price - resistance) / resistance * 100
                        
                        if strength > self.breakout_percentage_threshold:
                            breakout = {
                                'instrument_key': df.iloc[i]['instrument_key'],
                                'symbol': df.iloc[i]['symbol'],
                                'breakout_type': 'historical_resistance_breakout',
                                'price': float(current_price),
                                'breakout_level': float(resistance),
                                'strength_percent': round(strength, 4),
                                'volume_confirmation': volume_spike,
                                'volume_ratio': float(current_volume / avg_volume) if avg_volume > 0 else 0,
                                'timestamp': timestamps[i].isoformat(),
                                'data_index': i
                            }
                            breakouts.append(breakout)
                    
                    # Support breakdown
                    elif current_price < support and support > 0:
                        strength = (support - current_price) / support * 100
                        
                        if strength > self.breakout_percentage_threshold:
                            breakout = {
                                'instrument_key': df.iloc[i]['instrument_key'],
                                'symbol': df.iloc[i]['symbol'],
                                'breakout_type': 'historical_support_breakdown',
                                'price': float(current_price),
                                'breakout_level': float(support),
                                'strength_percent': round(strength, 4),
                                'volume_confirmation': volume_spike,
                                'volume_ratio': float(current_volume / avg_volume) if avg_volume > 0 else 0,
                                'timestamp': timestamps[i].isoformat(),
                                'data_index': i
                            }
                            breakouts.append(breakout)
                            
                except Exception as e:
                    logger.error(f"Error analyzing breakout at index {i}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in historical breakout analysis: {e}")
        
        return breakouts
    
    def _calculate_rolling_resistance(self, prices: np.ndarray, window: int) -> np.ndarray:
        """Calculate rolling resistance levels using NumPy"""
        
        resistance_levels = np.full(len(prices), np.nan)
        
        for i in range(window - 1, len(prices)):
            window_data = prices[i - window + 1:i + 1]
            resistance_levels[i] = np.max(window_data)
        
        return resistance_levels
    
    def _calculate_rolling_support(self, prices: np.ndarray, window: int) -> np.ndarray:
        """Calculate rolling support levels using NumPy"""
        
        support_levels = np.full(len(prices), np.nan)
        
        for i in range(window - 1, len(prices)):
            window_data = prices[i - window + 1:i + 1]
            support_levels[i] = np.min(window_data)
        
        return support_levels
    
    def _calculate_rolling_average(self, values: np.ndarray, window: int) -> np.ndarray:
        """Calculate rolling average using NumPy convolution"""
        
        if len(values) < window:
            return np.full(len(values), np.nan)
        
        kernel = np.ones(window) / window
        rolling_avg = np.convolve(values, kernel, mode='valid')
        
        # Pad with NaN for consistent length
        return np.concatenate([np.full(window - 1, np.nan), rolling_avg])
    
    def _calculate_confidence_score(
        self,
        strength_percent: float,
        volume_confirmation: bool,
        range_size: float,
        price_level: float
    ) -> float:
        """Calculate confidence score for breakout"""
        
        score = 0.0
        
        # Strength component (0-40 points)
        strength_score = min(strength_percent * 8, 40.0)  # Max 40 points for 5% strength
        score += strength_score
        
        # Volume confirmation (0-30 points)
        if volume_confirmation:
            score += 30.0
        
        # Range size component (0-20 points)
        if price_level > 0:
            range_percent = (range_size / price_level) * 100
            range_score = min(range_percent * 4, 20.0)  # Max 20 points for 5% range
            score += range_score
        
        # Technical pattern bonus (0-10 points)
        if strength_percent > 2.0 and volume_confirmation:
            score += 10.0
        
        # Normalize to 0-100 scale
        return min(round(score, 2), 100.0)
    
    def detect_pattern_breakouts(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect specific chart pattern breakouts"""
        
        pattern_breakouts = []
        
        if len(df) < 50:  # Need sufficient data for pattern recognition
            return pattern_breakouts
        
        try:
            prices = df['ltp'].values
            volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
            
            # Cup and Handle pattern detection
            cup_handle_breakouts = self._detect_cup_and_handle(prices, volumes)
            pattern_breakouts.extend(cup_handle_breakouts)
            
            # Triangle breakout detection
            triangle_breakouts = self._detect_triangle_breakouts(prices, volumes)
            pattern_breakouts.extend(triangle_breakouts)
            
            # Flag pattern detection
            flag_breakouts = self._detect_flag_patterns(prices, volumes)
            pattern_breakouts.extend(flag_breakouts)
            
            # Add instrument info to all patterns
            for breakout in pattern_breakouts:
                breakout.update({
                    'instrument_key': df.iloc[-1]['instrument_key'],
                    'symbol': df.iloc[-1]['symbol'],
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Error detecting pattern breakouts: {e}")
        
        return pattern_breakouts
    
    def _detect_cup_and_handle(self, prices: np.ndarray, volumes: np.ndarray) -> List[Dict[str, Any]]:
        """Detect cup and handle pattern breakouts"""
        
        patterns = []
        
        # Implementation of cup and handle pattern detection
        # This is a simplified version - full implementation would be more complex
        
        if len(prices) < 30:
            return patterns
        
        try:
            # Look for cup formation (U-shaped pattern)
            recent_prices = prices[-30:]
            
            # Find potential cup base (lowest point in recent history)
            cup_base_idx = np.argmin(recent_prices)
            
            if cup_base_idx < 5 or cup_base_idx > 25:  # Base should be in middle portion
                return patterns
            
            cup_base_price = recent_prices[cup_base_idx]
            left_rim = recent_prices[:cup_base_idx]
            right_rim = recent_prices[cup_base_idx:]
            
            # Check for cup characteristics
            left_high = np.max(left_rim)
            right_high = np.max(right_rim)
            
            # Cup should have relatively equal rims
            rim_difference = abs(left_high - right_high) / max(left_high, right_high)
            
            if rim_difference < 0.1 and right_high > cup_base_price * 1.05:  # Valid cup
                handle_start = len(recent_prices) - 10  # Look for handle in last 10 periods
                
                if handle_start > cup_base_idx:
                    handle_prices = recent_prices[handle_start:]
                    handle_low = np.min(handle_prices)
                    
                    # Handle should be above cup base but below rim
                    if cup_base_price < handle_low < right_high * 0.95:
                        current_price = prices[-1]
                        
                        # Breakout occurs when price exceeds right rim
                        if current_price > right_high:
                            patterns.append({
                                'pattern_type': 'cup_and_handle_breakout',
                                'current_price': float(current_price),
                                'breakout_level': float(right_high),
                                'cup_base': float(cup_base_price),
                                'handle_low': float(handle_low),
                                'pattern_depth_percent': float((right_high - cup_base_price) / right_high * 100),
                                'confidence_score': 75.0  # High confidence for cup and handle
                            })
            
        except Exception as e:
            logger.error(f"Error detecting cup and handle pattern: {e}")
        
        return patterns
    
    def _detect_triangle_breakouts(self, prices: np.ndarray, volumes: np.ndarray) -> List[Dict[str, Any]]:
        """Detect triangle pattern breakouts"""
        
        patterns = []
        
        if len(prices) < 20:
            return patterns
        
        try:
            recent_prices = prices[-20:]
            
            # Calculate trend lines for triangle detection
            highs = []
            lows = []
            
            # Find local highs and lows
            for i in range(1, len(recent_prices) - 1):
                if recent_prices[i] > recent_prices[i-1] and recent_prices[i] > recent_prices[i+1]:
                    highs.append((i, recent_prices[i]))
                elif recent_prices[i] < recent_prices[i-1] and recent_prices[i] < recent_prices[i+1]:
                    lows.append((i, recent_prices[i]))
            
            if len(highs) >= 2 and len(lows) >= 2:
                # Calculate trend line slopes
                high_slope = (highs[-1][1] - highs[0][1]) / (highs[-1][0] - highs[0][0])
                low_slope = (lows[-1][1] - lows[0][1]) / (lows[-1][0] - lows[0][0])
                
                # Check for converging trend lines (triangle pattern)
                if abs(high_slope) < 0.1 or abs(low_slope) < 0.1 or (high_slope * low_slope < 0):
                    current_price = prices[-1]
                    resistance = highs[-1][1]
                    support = lows[-1][1]
                    
                    # Breakout detection
                    if current_price > resistance:
                        patterns.append({
                            'pattern_type': 'triangle_upward_breakout',
                            'current_price': float(current_price),
                            'resistance_level': float(resistance),
                            'support_level': float(support),
                            'breakout_strength': float((current_price - resistance) / resistance * 100),
                            'confidence_score': 65.0
                        })
                    elif current_price < support:
                        patterns.append({
                            'pattern_type': 'triangle_downward_breakout',
                            'current_price': float(current_price),
                            'resistance_level': float(resistance),
                            'support_level': float(support),
                            'breakout_strength': float((support - current_price) / support * 100),
                            'confidence_score': 65.0
                        })
            
        except Exception as e:
            logger.error(f"Error detecting triangle breakouts: {e}")
        
        return patterns
    
    def _detect_flag_patterns(self, prices: np.ndarray, volumes: np.ndarray) -> List[Dict[str, Any]]:
        """Detect flag pattern breakouts"""
        
        patterns = []
        
        if len(prices) < 15:
            return patterns
        
        try:
            # Flag pattern consists of a strong move followed by consolidation
            recent_prices = prices[-15:]
            
            # Look for initial strong move (flagpole)
            flagpole_start = 0
            flagpole_end = 5
            
            flagpole_move = recent_prices[flagpole_end] - recent_prices[flagpole_start]
            flagpole_strength = abs(flagpole_move) / recent_prices[flagpole_start] * 100
            
            if flagpole_strength > 3.0:  # Strong initial move
                # Check for consolidation (flag)
                flag_prices = recent_prices[flagpole_end:]
                flag_range = np.max(flag_prices) - np.min(flag_prices)
                flag_range_percent = flag_range / np.mean(flag_prices) * 100
                
                if flag_range_percent < 2.0:  # Tight consolidation
                    current_price = prices[-1]
                    consolidation_high = np.max(flag_prices[:-1])  # Exclude current price
                    consolidation_low = np.min(flag_prices[:-1])
                    
                    # Breakout from consolidation
                    if flagpole_move > 0 and current_price > consolidation_high:  # Bull flag
                        patterns.append({
                            'pattern_type': 'bull_flag_breakout',
                            'current_price': float(current_price),
                            'breakout_level': float(consolidation_high),
                            'flagpole_strength': round(flagpole_strength, 2),
                            'consolidation_range': float(flag_range_percent),
                            'confidence_score': 70.0
                        })
                    elif flagpole_move < 0 and current_price < consolidation_low:  # Bear flag
                        patterns.append({
                            'pattern_type': 'bear_flag_breakout',
                            'current_price': float(current_price),
                            'breakout_level': float(consolidation_low),
                            'flagpole_strength': round(flagpole_strength, 2),
                            'consolidation_range': float(flag_range_percent),
                            'confidence_score': 70.0
                        })
            
        except Exception as e:
            logger.error(f"Error detecting flag patterns: {e}")
        
        return patterns
    
    def get_breakout_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get summary of breakout detection results"""
        
        if not results:
            return {'total_breakouts': 0}
        
        summary = {
            'total_breakouts': len(results),
            'breakout_types': {},
            'avg_confidence_score': 0.0,
            'volume_confirmed_count': 0,
            'high_confidence_count': 0  # Confidence > 70
        }
        
        confidence_scores = []
        
        for result in results:
            # Count breakout types
            breakout_type = result.get('breakout_type', 'unknown')
            summary['breakout_types'][breakout_type] = summary['breakout_types'].get(breakout_type, 0) + 1
            
            # Collect confidence scores
            confidence = result.get('confidence_score', 0)
            confidence_scores.append(confidence)
            
            if confidence > 70:
                summary['high_confidence_count'] += 1
            
            # Count volume confirmed breakouts
            if result.get('volume_confirmation', False):
                summary['volume_confirmed_count'] += 1
        
        # Calculate average confidence
        if confidence_scores:
            summary['avg_confidence_score'] = round(np.mean(confidence_scores), 2)
        
        return summary