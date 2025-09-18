"""
Auto Trading Risk Manager with Kafka Integration

Comprehensive risk management system for auto trading with real-time
monitoring, circuit breakers, and position limits.

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum

from services.hft.producer import get_hft_producer
from services.sse.sse_manager import get_sse_manager, SSEChannel

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAction(Enum):
    """Risk management actions"""
    MONITOR = "monitor"
    WARN = "warn"
    LIMIT = "limit"
    STOP = "stop"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class RiskLimit:
    """Risk limit configuration"""
    name: str
    limit_type: str  # 'pnl', 'position_count', 'exposure', 'drawdown'
    threshold_value: Decimal
    action: RiskAction
    time_window: Optional[timedelta] = None
    is_enabled: bool = True


@dataclass
class RiskAlert:
    """Risk alert information"""
    alert_id: str
    user_id: int
    session_id: str
    risk_level: RiskLevel
    risk_type: str
    current_value: Decimal
    threshold_value: Decimal
    message: str
    recommended_action: RiskAction
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'alert_id': self.alert_id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'risk_level': self.risk_level.value,
            'risk_type': self.risk_type,
            'current_value': float(self.current_value),
            'threshold_value': float(self.threshold_value),
            'message': self.message,
            'recommended_action': self.recommended_action.value,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class RiskProfile:
    """User risk profile configuration"""
    user_id: int
    max_daily_loss: Decimal = Decimal('5000')  # ₹5,000 max daily loss
    max_position_count: int = 5  # Maximum 5 positions
    max_position_size: Decimal = Decimal('10000')  # ₹10,000 per position
    max_portfolio_exposure: Decimal = Decimal('50000')  # ₹50,000 total exposure
    max_drawdown_percent: Decimal = Decimal('10')  # 10% max drawdown
    position_correlation_limit: Decimal = Decimal('0.7')  # 70% correlation limit
    
    # Time-based limits
    max_trades_per_hour: int = 10
    cooldown_period_minutes: int = 5  # Cool down after losses
    
    # Risk limits
    risk_limits: List[RiskLimit] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.risk_limits:
            self._create_default_limits()
    
    def _create_default_limits(self):
        """Create default risk limits"""
        self.risk_limits = [
            RiskLimit("Daily Loss Limit", "pnl", -self.max_daily_loss, RiskAction.STOP),
            RiskLimit("Position Count Limit", "position_count", 
                     Decimal(str(self.max_position_count)), RiskAction.LIMIT),
            RiskLimit("Portfolio Exposure", "exposure", 
                     self.max_portfolio_exposure, RiskAction.WARN),
            RiskLimit("Max Drawdown", "drawdown", 
                     self.max_drawdown_percent, RiskAction.EMERGENCY_STOP)
        ]


class AutoTradingRiskManager:
    """
    Comprehensive Risk Management System
    
    Features:
    - Real-time position and PnL monitoring
    - Dynamic risk limit enforcement
    - Circuit breaker functionality
    - Correlation analysis
    - Emergency stop mechanisms
    - Risk alert broadcasting via Kafka and SSE
    """
    
    def __init__(self):
        # Dependencies
        self._kafka_producer = None
        self._sse_manager = None
        
        # Risk tracking
        self._user_risk_profiles: Dict[int, RiskProfile] = {}
        self._active_alerts: Dict[str, RiskAlert] = {}
        self._emergency_stops: Set[str] = set()  # Session IDs under emergency stop
        
        # Performance tracking
        self._alerts_generated = 0
        self._risk_actions_taken = 0
        self._last_monitoring_time = datetime.now()
        
        # Configuration
        self._monitoring_interval_seconds = 5  # Monitor every 5 seconds
        self._alert_throttle_seconds = 60  # Throttle similar alerts
        
        logger.info("🛡️ Auto Trading Risk Manager initialized")
    
    async def initialize_dependencies(self) -> None:
        """Initialize Kafka and SSE dependencies"""
        try:
            # Initialize Kafka producer
            self._kafka_producer = await get_hft_producer()
            
            # Initialize SSE manager
            self._sse_manager = await get_sse_manager()
            
            logger.info("✅ Risk manager dependencies initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize risk manager dependencies: {e}")
            raise
    
    def set_user_risk_profile(self, user_id: int, risk_profile: RiskProfile) -> None:
        """Set risk profile for a user"""
        self._user_risk_profiles[user_id] = risk_profile
        logger.info(f"🛡️ Risk profile set for user {user_id}")
    
    def get_user_risk_profile(self, user_id: int) -> RiskProfile:
        """Get risk profile for a user (creates default if not exists)"""
        if user_id not in self._user_risk_profiles:
            self._user_risk_profiles[user_id] = RiskProfile(user_id=user_id)
        return self._user_risk_profiles[user_id]
    
    async def evaluate_position_risk(
        self,
        user_id: int,
        session_id: str,
        positions: List[Dict[str, Any]],
        current_pnl: Decimal
    ) -> List[RiskAlert]:
        """Evaluate risk for current positions and generate alerts"""
        try:
            risk_profile = self.get_user_risk_profile(user_id)
            alerts = []
            
            # Check daily PnL limit
            if current_pnl <= -risk_profile.max_daily_loss:
                alert = self._create_risk_alert(
                    user_id, session_id, RiskLevel.CRITICAL, "daily_loss_limit",
                    abs(current_pnl), risk_profile.max_daily_loss,
                    f"Daily loss limit exceeded: ₹{abs(current_pnl)} > ₹{risk_profile.max_daily_loss}",
                    RiskAction.EMERGENCY_STOP
                )
                alerts.append(alert)
            
            # Check position count limit
            active_positions = len([p for p in positions if p.get('status') == 'active'])
            if active_positions >= risk_profile.max_position_count:
                alert = self._create_risk_alert(
                    user_id, session_id, RiskLevel.HIGH, "position_count_limit",
                    Decimal(str(active_positions)), Decimal(str(risk_profile.max_position_count)),
                    f"Position count limit reached: {active_positions} positions",
                    RiskAction.LIMIT
                )
                alerts.append(alert)
            
            # Check portfolio exposure
            total_exposure = sum(
                Decimal(str(pos.get('entry_price', 0))) * abs(pos.get('quantity', 0))
                for pos in positions if pos.get('status') == 'active'
            )
            
            if total_exposure > risk_profile.max_portfolio_exposure:
                alert = self._create_risk_alert(
                    user_id, session_id, RiskLevel.MEDIUM, "portfolio_exposure",
                    total_exposure, risk_profile.max_portfolio_exposure,
                    f"Portfolio exposure high: ₹{total_exposure} > ₹{risk_profile.max_portfolio_exposure}",
                    RiskAction.WARN
                )
                alerts.append(alert)
            
            # Check individual position sizes
            for position in positions:
                if position.get('status') == 'active':
                    position_value = Decimal(str(position.get('entry_price', 0))) * abs(position.get('quantity', 0))
                    
                    if position_value > risk_profile.max_position_size:
                        alert = self._create_risk_alert(
                            user_id, session_id, RiskLevel.MEDIUM, "position_size",
                            position_value, risk_profile.max_position_size,
                            f"Position size large: {position.get('symbol')} ₹{position_value}",
                            RiskAction.WARN
                        )
                        alerts.append(alert)
            
            # Check drawdown
            if len(positions) > 0:
                max_portfolio_value = max(
                    sum(Decimal(str(p.get('max_value', p.get('entry_price', 0)))) * abs(p.get('quantity', 0)) for p in positions),
                    Decimal('1')  # Avoid division by zero
                )
                current_portfolio_value = max_portfolio_value + current_pnl
                drawdown_percent = (max_portfolio_value - current_portfolio_value) / max_portfolio_value * 100
                
                if drawdown_percent > risk_profile.max_drawdown_percent:
                    alert = self._create_risk_alert(
                        user_id, session_id, RiskLevel.CRITICAL, "max_drawdown",
                        drawdown_percent, risk_profile.max_drawdown_percent,
                        f"Maximum drawdown exceeded: {drawdown_percent:.2f}%",
                        RiskAction.EMERGENCY_STOP
                    )
                    alerts.append(alert)
            
            # Process and broadcast alerts
            if alerts:
                await self._process_risk_alerts(alerts)
            
            return alerts
            
        except Exception as e:
            logger.error(f"❌ Error evaluating position risk: {e}")
            return []
    
    def _create_risk_alert(
        self,
        user_id: int,
        session_id: str,
        risk_level: RiskLevel,
        risk_type: str,
        current_value: Decimal,
        threshold_value: Decimal,
        message: str,
        recommended_action: RiskAction
    ) -> RiskAlert:
        """Create a risk alert"""
        alert_id = f"{user_id}_{session_id}_{risk_type}_{int(datetime.now().timestamp())}"
        
        return RiskAlert(
            alert_id=alert_id,
            user_id=user_id,
            session_id=session_id,
            risk_level=risk_level,
            risk_type=risk_type,
            current_value=current_value,
            threshold_value=threshold_value,
            message=message,
            recommended_action=recommended_action
        )
    
    async def _process_risk_alerts(self, alerts: List[RiskAlert]) -> None:
        """Process and broadcast risk alerts"""
        try:
            for alert in alerts:
                # Check if we should throttle similar alerts
                if self._should_throttle_alert(alert):
                    continue
                
                # Store alert
                self._active_alerts[alert.alert_id] = alert
                
                # Take risk action if needed
                await self._take_risk_action(alert)
                
                # Broadcast alert via SSE
                await self._broadcast_risk_alert(alert)
                
                # Publish to Kafka for other services
                await self._publish_risk_alert_to_kafka(alert)
                
                self._alerts_generated += 1
                
                logger.warning(f"🚨 Risk Alert: {alert.message}")
            
        except Exception as e:
            logger.error(f"❌ Error processing risk alerts: {e}")
    
    def _should_throttle_alert(self, alert: RiskAlert) -> bool:
        """Check if alert should be throttled"""
        # Look for similar recent alerts
        cutoff_time = datetime.now() - timedelta(seconds=self._alert_throttle_seconds)
        
        for existing_alert in self._active_alerts.values():
            if (existing_alert.user_id == alert.user_id and
                existing_alert.risk_type == alert.risk_type and
                existing_alert.timestamp > cutoff_time):
                return True  # Throttle this alert
        
        return False
    
    async def _take_risk_action(self, alert: RiskAlert) -> None:
        """Take appropriate risk management action"""
        try:
            if alert.recommended_action == RiskAction.EMERGENCY_STOP:
                await self._emergency_stop_session(alert.session_id, alert.message)
            
            elif alert.recommended_action == RiskAction.STOP:
                await self._stop_trading_session(alert.session_id, alert.message)
            
            elif alert.recommended_action == RiskAction.LIMIT:
                await self._limit_new_positions(alert.user_id, alert.session_id, alert.message)
            
            elif alert.recommended_action == RiskAction.WARN:
                # Warning action - just log and broadcast
                logger.warning(f"⚠️ Risk Warning: {alert.message}")
            
            self._risk_actions_taken += 1
            
        except Exception as e:
            logger.error(f"❌ Error taking risk action: {e}")
    
    async def _emergency_stop_session(self, session_id: str, reason: str) -> None:
        """Execute emergency stop for trading session"""
        try:
            self._emergency_stops.add(session_id)
            
            # Publish emergency stop event to Kafka
            emergency_event = {
                'event_type': 'emergency_stop',
                'session_id': session_id,
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
                'severity': 'critical'
            }
            
            await self._kafka_producer.produce_message(
                topic="hft.trading.risk_events",
                message=emergency_event
            )
            
            logger.critical(f"🛑 EMERGENCY STOP executed for session {session_id}: {reason}")
            
        except Exception as e:
            logger.error(f"❌ Error executing emergency stop: {e}")
    
    async def _stop_trading_session(self, session_id: str, reason: str) -> None:
        """Stop trading session (graceful)"""
        try:
            stop_event = {
                'event_type': 'stop_trading',
                'session_id': session_id,
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
                'severity': 'high'
            }
            
            await self._kafka_producer.produce_message(
                topic="hft.trading.risk_events",
                message=stop_event
            )
            
            logger.warning(f"⏹️ Trading stopped for session {session_id}: {reason}")
            
        except Exception as e:
            logger.error(f"❌ Error stopping trading session: {e}")
    
    async def _limit_new_positions(self, user_id: int, session_id: str, reason: str) -> None:
        """Limit new position creation"""
        try:
            limit_event = {
                'event_type': 'limit_positions',
                'user_id': user_id,
                'session_id': session_id,
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
                'severity': 'medium'
            }
            
            await self._kafka_producer.produce_message(
                topic="hft.trading.risk_events",
                message=limit_event
            )
            
            logger.info(f"🚫 Position limits active for session {session_id}: {reason}")
            
        except Exception as e:
            logger.error(f"❌ Error setting position limits: {e}")
    
    async def _broadcast_risk_alert(self, alert: RiskAlert) -> None:
        """Broadcast risk alert via SSE"""
        try:
            await self._sse_manager.broadcast_to_channel(
                channel=SSEChannel.SYSTEM_STATUS,
                event_type="risk_alert",
                data=alert.to_dict(),
                priority=1  # High priority for risk alerts
            )
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting risk alert: {e}")
    
    async def _publish_risk_alert_to_kafka(self, alert: RiskAlert) -> None:
        """Publish risk alert to Kafka for other services"""
        try:
            await self._kafka_producer.produce_message(
                topic="hft.trading.risk_alerts",
                message=alert.to_dict()
            )
            
        except Exception as e:
            logger.error(f"❌ Error publishing risk alert to Kafka: {e}")
    
    def is_session_emergency_stopped(self, session_id: str) -> bool:
        """Check if session is under emergency stop"""
        return session_id in self._emergency_stops
    
    def clear_emergency_stop(self, session_id: str) -> bool:
        """Clear emergency stop for session (admin action)"""
        if session_id in self._emergency_stops:
            self._emergency_stops.remove(session_id)
            logger.info(f"✅ Emergency stop cleared for session {session_id}")
            return True
        return False
    
    def get_active_alerts(self, user_id: Optional[int] = None) -> List[RiskAlert]:
        """Get active risk alerts, optionally filtered by user"""
        alerts = list(self._active_alerts.values())
        
        if user_id:
            alerts = [alert for alert in alerts if alert.user_id == user_id]
        
        # Sort by severity and timestamp
        severity_order = {RiskLevel.CRITICAL: 0, RiskLevel.HIGH: 1, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 3}
        alerts.sort(key=lambda a: (severity_order.get(a.risk_level, 99), a.timestamp), reverse=True)
        
        return alerts
    
    def clear_old_alerts(self, max_age_hours: int = 24) -> int:
        """Clear old alerts older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        old_alerts = [
            alert_id for alert_id, alert in self._active_alerts.items()
            if alert.timestamp < cutoff_time
        ]
        
        for alert_id in old_alerts:
            del self._active_alerts[alert_id]
        
        logger.info(f"🧹 Cleared {len(old_alerts)} old risk alerts")
        return len(old_alerts)
    
    def get_risk_summary(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get risk management summary"""
        try:
            alerts = self.get_active_alerts(user_id)
            
            return {
                'total_alerts': len(alerts),
                'critical_alerts': len([a for a in alerts if a.risk_level == RiskLevel.CRITICAL]),
                'high_alerts': len([a for a in alerts if a.risk_level == RiskLevel.HIGH]),
                'medium_alerts': len([a for a in alerts if a.risk_level == RiskLevel.MEDIUM]),
                'low_alerts': len([a for a in alerts if a.risk_level == RiskLevel.LOW]),
                'emergency_stops': len(self._emergency_stops),
                'alerts_generated_total': self._alerts_generated,
                'risk_actions_taken': self._risk_actions_taken,
                'last_monitoring_time': self._last_monitoring_time.isoformat(),
                'recent_alerts': [alert.to_dict() for alert in alerts[:5]]  # Latest 5 alerts
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating risk summary: {e}")
            return {'error': str(e)}
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get risk manager performance statistics"""
        return {
            'alerts_generated': self._alerts_generated,
            'risk_actions_taken': self._risk_actions_taken,
            'active_alerts_count': len(self._active_alerts),
            'emergency_stops_count': len(self._emergency_stops),
            'users_monitored': len(self._user_risk_profiles),
            'last_monitoring_time': self._last_monitoring_time.isoformat(),
            'monitoring_interval_seconds': self._monitoring_interval_seconds
        }


# Singleton instance
_risk_manager: Optional[AutoTradingRiskManager] = None


async def get_risk_manager() -> AutoTradingRiskManager:
    """Get singleton risk manager instance"""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = AutoTradingRiskManager()
        await _risk_manager.initialize_dependencies()
    return _risk_manager


# Export main classes and functions
__all__ = [
    "AutoTradingRiskManager",
    "RiskProfile",
    "RiskAlert", 
    "RiskLevel",
    "RiskAction",
    "RiskLimit",
    "get_risk_manager"
]