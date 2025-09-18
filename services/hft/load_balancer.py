"""
HFT Load Distribution and Performance Monitor

Production-grade load balancing and monitoring system for HFT operations:
- Dynamic partition load balancing
- Real-time performance monitoring
- Automatic failover and recovery
- Memory and CPU optimization
- Kafka consumer group rebalancing

Author: Trading System
Created: 2025-01-11
"""

import asyncio
import logging
import time
import psutil
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import json
import statistics

import numpy as np

from .config import get_hft_kafka_config
from .producer import get_hft_producer
from .partition_strategy import get_enhanced_partition_manager, ServiceType

logger = logging.getLogger(__name__)


class LoadMetricType(Enum):
    """Types of load metrics"""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"  
    PROCESSING_TIME = "processing_time"
    MESSAGE_RATE = "message_rate"
    ERROR_RATE = "error_rate"
    PARTITION_LAG = "partition_lag"


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class LoadMetric:
    """Load metric data point"""
    metric_type: LoadMetricType
    value: float
    timestamp: datetime
    service_type: Optional[ServiceType] = None
    partition_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceThreshold:
    """Performance threshold configuration"""
    metric_type: LoadMetricType
    warning_threshold: float
    critical_threshold: float
    emergency_threshold: float
    measurement_window_seconds: int = 300  # 5 minutes


@dataclass
class LoadBalancingAction:
    """Load balancing action"""
    action_type: str  # 'redistribute', 'scale_up', 'scale_down', 'failover'
    service_type: ServiceType
    source_partition: Optional[int] = None
    target_partition: Optional[int] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SystemHealth:
    """Overall system health status"""
    overall_status: str  # 'healthy', 'degraded', 'critical', 'emergency'
    cpu_usage_percent: float
    memory_usage_percent: float
    active_services: int
    error_rate_percent: float
    avg_processing_time_ms: float
    message_throughput_per_second: float
    last_updated: datetime = field(default_factory=datetime.now)


class HFTLoadBalancer:
    """
    HFT Load Distribution and Performance Monitor
    
    Features:
    - Real-time load monitoring across all services
    - Dynamic partition rebalancing
    - Performance threshold monitoring with alerts
    - Automatic scaling recommendations
    - Resource usage optimization
    - Historical performance analysis
    """
    
    def __init__(self):
        self.config = get_hft_kafka_config()
        self.producer = get_hft_producer()
        self.partition_manager = get_enhanced_partition_manager()
        
        # Monitoring state
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.alert_task: Optional[asyncio.Task] = None
        
        # Metrics storage
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.current_metrics: Dict[str, LoadMetric] = {}
        
        # Performance thresholds
        self.thresholds = self._initialize_performance_thresholds()
        
        # Load balancing state
        self.partition_loads: Dict[Tuple[ServiceType, int], float] = {}
        self.service_health_scores: Dict[ServiceType, float] = {}
        self.recent_actions: deque = deque(maxlen=100)
        
        # System resources
        self.system_stats = {
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'process': psutil.Process()
        }
        
        logger.info("HFT Load Balancer initialized")
    
    def _initialize_performance_thresholds(self) -> Dict[LoadMetricType, PerformanceThreshold]:
        """Initialize performance monitoring thresholds"""
        
        return {
            LoadMetricType.CPU_USAGE: PerformanceThreshold(
                metric_type=LoadMetricType.CPU_USAGE,
                warning_threshold=70.0,     # 70% CPU usage
                critical_threshold=85.0,    # 85% CPU usage
                emergency_threshold=95.0,   # 95% CPU usage
                measurement_window_seconds=60
            ),
            
            LoadMetricType.MEMORY_USAGE: PerformanceThreshold(
                metric_type=LoadMetricType.MEMORY_USAGE,
                warning_threshold=75.0,     # 75% memory usage
                critical_threshold=90.0,    # 90% memory usage  
                emergency_threshold=98.0,   # 98% memory usage
                measurement_window_seconds=60
            ),
            
            LoadMetricType.PROCESSING_TIME: PerformanceThreshold(
                metric_type=LoadMetricType.PROCESSING_TIME,
                warning_threshold=100.0,    # 100ms processing time
                critical_threshold=500.0,   # 500ms processing time
                emergency_threshold=1000.0, # 1 second processing time
                measurement_window_seconds=300
            ),
            
            LoadMetricType.MESSAGE_RATE: PerformanceThreshold(
                metric_type=LoadMetricType.MESSAGE_RATE,
                warning_threshold=1000.0,   # 1000 messages/second
                critical_threshold=5000.0,  # 5000 messages/second
                emergency_threshold=10000.0,# 10000 messages/second
                measurement_window_seconds=60
            ),
            
            LoadMetricType.ERROR_RATE: PerformanceThreshold(
                metric_type=LoadMetricType.ERROR_RATE,
                warning_threshold=1.0,      # 1% error rate
                critical_threshold=5.0,     # 5% error rate
                emergency_threshold=10.0,   # 10% error rate
                measurement_window_seconds=300
            ),
            
            LoadMetricType.PARTITION_LAG: PerformanceThreshold(
                metric_type=LoadMetricType.PARTITION_LAG,
                warning_threshold=1000.0,   # 1000 messages behind
                critical_threshold=10000.0, # 10000 messages behind
                emergency_threshold=50000.0,# 50000 messages behind
                measurement_window_seconds=120
            )
        }
    
    async def start_monitoring(self) -> bool:
        """Start load balancing and monitoring"""
        
        if self.is_monitoring:
            logger.warning("Load balancer monitoring is already running")
            return True
        
        try:
            self.is_monitoring = True
            
            # Start monitoring tasks
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            self.alert_task = asyncio.create_task(self._alert_processing_loop())
            
            logger.info("HFT Load Balancer monitoring started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start load balancer monitoring: {e}")
            self.is_monitoring = False
            return False
    
    async def stop_monitoring(self) -> None:
        """Stop load balancing and monitoring"""
        
        if not self.is_monitoring:
            return
        
        try:
            self.is_monitoring = False
            
            # Cancel monitoring tasks
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            if self.alert_task and not self.alert_task.done():
                self.alert_task.cancel()
                try:
                    await self.alert_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("HFT Load Balancer monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping load balancer monitoring: {e}")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        
        while self.is_monitoring:
            try:
                # Collect system metrics
                await self._collect_system_metrics()
                
                # Collect service metrics
                await self._collect_service_metrics()
                
                # Analyze load distribution
                await self._analyze_load_distribution()
                
                # Check for rebalancing needs
                await self._check_rebalancing_needs()
                
                # Wait before next monitoring cycle
                await asyncio.sleep(10)  # Monitor every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
    
    async def _alert_processing_loop(self) -> None:
        """Alert processing loop"""
        
        while self.is_monitoring:
            try:
                # Check performance thresholds
                alerts = await self._check_performance_thresholds()
                
                # Process alerts
                for alert in alerts:
                    await self._handle_alert(alert)
                
                # Wait before next alert check
                await asyncio.sleep(30)  # Check alerts every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in alert processing loop: {e}")
                await asyncio.sleep(30)
    
    async def _collect_system_metrics(self) -> None:
        """Collect system-wide performance metrics"""
        
        try:
            now = datetime.now()
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_metric = LoadMetric(
                metric_type=LoadMetricType.CPU_USAGE,
                value=cpu_percent,
                timestamp=now
            )
            self._store_metric(cpu_metric)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_metric = LoadMetric(
                metric_type=LoadMetricType.MEMORY_USAGE,
                value=memory.percent,
                timestamp=now,
                metadata={'available_mb': memory.available / 1024 / 1024}
            )
            self._store_metric(memory_metric)
            
            # Process-specific metrics
            process = self.system_stats['process']
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent()
            
            # Store process metrics
            process_memory_mb = process_memory.rss / 1024 / 1024
            process_metric = LoadMetric(
                metric_type=LoadMetricType.MEMORY_USAGE,
                value=process_memory_mb,
                timestamp=now,
                metadata={'process_memory_mb': process_memory_mb, 'process_cpu_percent': process_cpu}
            )
            
            self._store_metric(process_metric, key_suffix='_process')
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    async def _collect_service_metrics(self) -> None:
        """Collect service-specific performance metrics"""
        
        try:
            # Get partition load statistics
            partition_stats = self.partition_manager.get_partition_load_stats()
            
            # Process service distributions
            for service_name, partition_counts in partition_stats.get('service_distributions', {}).items():
                try:
                    service_type = ServiceType(service_name)
                    
                    # Calculate load metrics for this service
                    total_instruments = sum(partition_counts.values())
                    partition_load_variance = self._calculate_partition_variance(partition_counts)
                    
                    # Store service load metrics
                    load_metric = LoadMetric(
                        metric_type=LoadMetricType.MESSAGE_RATE,
                        value=total_instruments,
                        timestamp=datetime.now(),
                        service_type=service_type,
                        metadata={
                            'partition_counts': partition_counts,
                            'load_variance': partition_load_variance,
                            'partition_count': len(partition_counts)
                        }
                    )
                    
                    self._store_metric(load_metric, key_suffix=f'_{service_name}')
                    
                    # Update service health score
                    health_score = self._calculate_service_health_score(service_type, partition_counts)
                    self.service_health_scores[service_type] = health_score
                    
                except ValueError:
                    # Skip unknown service types
                    continue
                    
        except Exception as e:
            logger.error(f"Error collecting service metrics: {e}")
    
    def _calculate_partition_variance(self, partition_counts: Dict[int, int]) -> float:
        """Calculate variance in partition loads"""
        
        if len(partition_counts) < 2:
            return 0.0
        
        values = list(partition_counts.values())
        return float(statistics.variance(values))
    
    def _calculate_service_health_score(self, service_type: ServiceType, partition_counts: Dict[int, int]) -> float:
        """Calculate health score for a service (0-100)"""
        
        try:
            if not partition_counts:
                return 0.0
            
            # Factors for health score
            load_balance_score = 0.0
            throughput_score = 0.0
            error_score = 100.0  # Start with perfect score
            
            # Load balance score (based on variance)
            values = list(partition_counts.values())
            if len(values) > 1:
                variance = statistics.variance(values)
                mean_load = statistics.mean(values)
                if mean_load > 0:
                    coefficient_of_variation = (variance ** 0.5) / mean_load
                    load_balance_score = max(0, 100 - (coefficient_of_variation * 100))
                else:
                    load_balance_score = 100
            else:
                load_balance_score = 100
            
            # Throughput score (based on total message rate)
            total_throughput = sum(values)
            if total_throughput > 0:
                throughput_score = min(100, (total_throughput / 1000) * 10)  # Scale appropriately
            
            # Error score (check recent error metrics)
            error_metrics = self._get_recent_metrics(LoadMetricType.ERROR_RATE, service_type)
            if error_metrics:
                recent_error_rate = error_metrics[-1].value
                error_score = max(0, 100 - (recent_error_rate * 10))
            
            # Weighted health score
            health_score = (
                load_balance_score * 0.4 +
                throughput_score * 0.3 +
                error_score * 0.3
            )
            
            return round(health_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculating health score for {service_type.value}: {e}")
            return 50.0  # Return neutral score on error
    
    def _store_metric(self, metric: LoadMetric, key_suffix: str = "") -> None:
        """Store metric in history and current metrics"""
        
        metric_key = f"{metric.metric_type.value}_{metric.service_type.value if metric.service_type else 'system'}{key_suffix}"
        
        # Add to history
        self.metrics_history[metric_key].append(metric)
        
        # Update current metrics
        self.current_metrics[metric_key] = metric
    
    def _get_recent_metrics(
        self, 
        metric_type: LoadMetricType, 
        service_type: Optional[ServiceType] = None,
        window_seconds: int = 300
    ) -> List[LoadMetric]:
        """Get recent metrics for analysis"""
        
        metric_key = f"{metric_type.value}_{service_type.value if service_type else 'system'}"
        
        if metric_key not in self.metrics_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(seconds=window_seconds)
        recent_metrics = []
        
        for metric in reversed(self.metrics_history[metric_key]):
            if metric.timestamp >= cutoff_time:
                recent_metrics.append(metric)
            else:
                break
        
        return list(reversed(recent_metrics))
    
    async def _analyze_load_distribution(self) -> None:
        """Analyze current load distribution across partitions"""
        
        try:
            # Get current partition loads
            partition_stats = self.partition_manager.get_partition_load_stats()
            
            for service_name, partition_counts in partition_stats.get('service_distributions', {}).items():
                try:
                    service_type = ServiceType(service_name)
                    
                    # Analyze load distribution for this service
                    analysis = self._analyze_service_load_distribution(service_type, partition_counts)
                    
                    # Store analysis results
                    if analysis['needs_rebalancing']:
                        logger.info(f"Service {service_name} needs rebalancing: {analysis['reason']}")
                        
                        # Store rebalancing recommendation
                        recommendation = LoadBalancingAction(
                            action_type='redistribute',
                            service_type=service_type,
                            reason=analysis['reason']
                        )
                        
                        self.recent_actions.append(recommendation)
                    
                except ValueError:
                    continue
                    
        except Exception as e:
            logger.error(f"Error analyzing load distribution: {e}")
    
    def _analyze_service_load_distribution(
        self, 
        service_type: ServiceType, 
        partition_counts: Dict[int, int]
    ) -> Dict[str, Any]:
        """Analyze load distribution for a specific service"""
        
        analysis = {
            'service_type': service_type.value,
            'needs_rebalancing': False,
            'reason': '',
            'recommendations': []
        }
        
        try:
            if len(partition_counts) < 2:
                return analysis
            
            values = list(partition_counts.values())
            total_load = sum(values)
            
            if total_load == 0:
                return analysis
            
            # Calculate load distribution metrics
            mean_load = statistics.mean(values)
            max_load = max(values)
            min_load = min(values)
            load_ratio = max_load / min_load if min_load > 0 else float('inf')
            
            # Check for imbalanced partitions
            imbalance_threshold = 2.0  # Max partition should not be more than 2x min partition
            
            if load_ratio > imbalance_threshold:
                analysis['needs_rebalancing'] = True
                analysis['reason'] = f"Load imbalance detected (ratio: {load_ratio:.2f})"
                
                # Find partitions to rebalance
                max_partition = max(partition_counts, key=partition_counts.get)
                min_partition = min(partition_counts, key=partition_counts.get)
                
                analysis['recommendations'].append({
                    'action': 'move_instruments',
                    'from_partition': max_partition,
                    'to_partition': min_partition,
                    'instrument_count': (partition_counts[max_partition] - mean_load) // 2
                })
            
            # Check for overloaded partitions
            overload_threshold = mean_load * 1.5
            overloaded_partitions = [
                partition_id for partition_id, count in partition_counts.items() 
                if count > overload_threshold
            ]
            
            if overloaded_partitions:
                analysis['needs_rebalancing'] = True
                analysis['reason'] += f" Overloaded partitions: {overloaded_partitions}"
                
                for partition_id in overloaded_partitions:
                    analysis['recommendations'].append({
                        'action': 'scale_partition',
                        'partition_id': partition_id,
                        'current_load': partition_counts[partition_id],
                        'recommended_action': 'split_partition'
                    })
            
        except Exception as e:
            logger.error(f"Error analyzing service load distribution: {e}")
        
        return analysis
    
    async def _check_rebalancing_needs(self) -> None:
        """Check if any services need rebalancing and take action"""
        
        try:
            # Review recent rebalancing actions to avoid thrashing
            recent_actions_count = sum(
                1 for action in self.recent_actions 
                if (datetime.now() - action.timestamp).seconds < 300  # Last 5 minutes
            )
            
            if recent_actions_count > 3:
                logger.info("Skipping rebalancing - too many recent actions")
                return
            
            # Check each service for rebalancing needs
            for service_type, health_score in self.service_health_scores.items():
                if health_score < 60.0:  # Health score below 60%
                    await self._perform_rebalancing(service_type)
            
        except Exception as e:
            logger.error(f"Error checking rebalancing needs: {e}")
    
    async def _perform_rebalancing(self, service_type: ServiceType) -> None:
        """Perform load rebalancing for a service"""
        
        try:
            logger.info(f"Performing rebalancing for {service_type.value}")
            
            # Create rebalancing message
            rebalancing_message = {
                'action': 'rebalance',
                'service_type': service_type.value,
                'timestamp': datetime.now().isoformat(),
                'reason': 'low_health_score',
                'current_health_score': self.service_health_scores.get(service_type, 0)
            }
            
            # Send rebalancing command to appropriate consumers
            topic_name = f"hft.control.{service_type.value}"
            await self.producer.send_to_topic(topic_name, rebalancing_message)
            
            # Record action
            action = LoadBalancingAction(
                action_type='rebalance',
                service_type=service_type,
                reason=f"Health score: {self.service_health_scores.get(service_type, 0):.1f}%"
            )
            self.recent_actions.append(action)
            
        except Exception as e:
            logger.error(f"Error performing rebalancing for {service_type.value}: {e}")
    
    async def _check_performance_thresholds(self) -> List[Dict[str, Any]]:
        """Check performance metrics against thresholds"""
        
        alerts = []
        
        try:
            for metric_type, threshold in self.thresholds.items():
                recent_metrics = self._get_recent_metrics(
                    metric_type, 
                    window_seconds=threshold.measurement_window_seconds
                )
                
                if not recent_metrics:
                    continue
                
                # Calculate average value over window
                avg_value = statistics.mean([m.value for m in recent_metrics])
                
                # Check threshold levels
                severity = None
                if avg_value >= threshold.emergency_threshold:
                    severity = AlertSeverity.EMERGENCY
                elif avg_value >= threshold.critical_threshold:
                    severity = AlertSeverity.CRITICAL
                elif avg_value >= threshold.warning_threshold:
                    severity = AlertSeverity.WARNING
                
                if severity:
                    alert = {
                        'metric_type': metric_type.value,
                        'severity': severity.value,
                        'current_value': avg_value,
                        'threshold_exceeded': getattr(threshold, f"{severity.value}_threshold"),
                        'measurement_window_seconds': threshold.measurement_window_seconds,
                        'timestamp': datetime.now().isoformat(),
                        'recommendations': self._get_threshold_recommendations(metric_type, avg_value, severity)
                    }
                    
                    alerts.append(alert)
            
        except Exception as e:
            logger.error(f"Error checking performance thresholds: {e}")
        
        return alerts
    
    def _get_threshold_recommendations(
        self, 
        metric_type: LoadMetricType, 
        value: float, 
        severity: AlertSeverity
    ) -> List[str]:
        """Get recommendations for threshold violations"""
        
        recommendations = []
        
        if metric_type == LoadMetricType.CPU_USAGE:
            if severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
                recommendations.extend([
                    "Consider scaling horizontally by adding more processing nodes",
                    "Review CPU-intensive operations for optimization opportunities",
                    "Enable processor throttling if available"
                ])
            else:
                recommendations.append("Monitor CPU usage trends")
        
        elif metric_type == LoadMetricType.MEMORY_USAGE:
            if severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
                recommendations.extend([
                    "Clear memory caches and buffers",
                    "Reduce batch sizes to lower memory footprint",
                    "Consider increasing available memory"
                ])
            else:
                recommendations.append("Monitor memory usage patterns")
        
        elif metric_type == LoadMetricType.PROCESSING_TIME:
            if severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
                recommendations.extend([
                    "Review processing algorithms for optimization",
                    "Consider parallel processing where possible",
                    "Reduce processing batch sizes"
                ])
            
        elif metric_type == LoadMetricType.ERROR_RATE:
            recommendations.extend([
                "Investigate error logs for root causes",
                "Consider implementing circuit breakers",
                "Review error handling and retry mechanisms"
            ])
        
        return recommendations
    
    async def _handle_alert(self, alert: Dict[str, Any]) -> None:
        """Handle a performance alert"""
        
        try:
            severity = AlertSeverity(alert['severity'])
            
            # Log alert
            logger.log(
                logging.ERROR if severity == AlertSeverity.EMERGENCY else logging.WARNING,
                f"Performance Alert - {alert['metric_type']}: {alert['current_value']:.2f} "
                f"(Threshold: {alert['threshold_exceeded']:.2f}) - Severity: {severity.value}"
            )
            
            # Send alert to monitoring topic
            alert_message = {
                **alert,
                'system_info': {
                    'cpu_count': self.system_stats['cpu_count'],
                    'memory_total_mb': self.system_stats['memory_total'] / 1024 / 1024,
                    'active_services': len(self.service_health_scores)
                }
            }
            
            await self.producer.send_to_topic("hft.alerts.performance", alert_message)
            
            # Take automatic actions for critical alerts
            if severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
                await self._handle_critical_alert(alert)
            
        except Exception as e:
            logger.error(f"Error handling alert: {e}")
    
    async def _handle_critical_alert(self, alert: Dict[str, Any]) -> None:
        """Handle critical performance alerts with automatic actions"""
        
        try:
            metric_type = LoadMetricType(alert['metric_type'])
            
            if metric_type == LoadMetricType.CPU_USAGE:
                # Reduce processing load
                await self._reduce_processing_load()
                
            elif metric_type == LoadMetricType.MEMORY_USAGE:
                # Clear caches and reduce memory usage
                await self._reduce_memory_usage()
                
            elif metric_type == LoadMetricType.ERROR_RATE:
                # Enable circuit breaker mode
                await self._enable_circuit_breaker_mode()
            
        except Exception as e:
            logger.error(f"Error handling critical alert: {e}")
    
    async def _reduce_processing_load(self) -> None:
        """Reduce processing load during high CPU usage"""
        
        try:
            # Send load reduction commands to all services
            for service_type in ServiceType:
                control_message = {
                    'action': 'reduce_load',
                    'parameters': {
                        'batch_size_reduction': 0.5,  # Reduce batch size by 50%
                        'processing_interval_increase': 2.0  # Double processing intervals
                    },
                    'timestamp': datetime.now().isoformat(),
                    'reason': 'high_cpu_usage'
                }
                
                topic_name = f"hft.control.{service_type.value}"
                await self.producer.send_to_topic(topic_name, control_message)
            
            logger.info("Sent load reduction commands to all services")
            
        except Exception as e:
            logger.error(f"Error reducing processing load: {e}")
    
    async def _reduce_memory_usage(self) -> None:
        """Reduce memory usage during high memory pressure"""
        
        try:
            # Send memory optimization commands
            for service_type in ServiceType:
                control_message = {
                    'action': 'optimize_memory',
                    'parameters': {
                        'clear_caches': True,
                        'reduce_buffer_sizes': True,
                        'enable_compression': True
                    },
                    'timestamp': datetime.now().isoformat(),
                    'reason': 'high_memory_usage'
                }
                
                topic_name = f"hft.control.{service_type.value}"
                await self.producer.send_to_topic(topic_name, control_message)
            
            logger.info("Sent memory optimization commands to all services")
            
        except Exception as e:
            logger.error(f"Error reducing memory usage: {e}")
    
    async def _enable_circuit_breaker_mode(self) -> None:
        """Enable circuit breaker mode during high error rates"""
        
        try:
            for service_type in ServiceType:
                control_message = {
                    'action': 'enable_circuit_breaker',
                    'parameters': {
                        'error_threshold': 5.0,  # 5% error threshold
                        'timeout_seconds': 300,   # 5 minute timeout
                        'half_open_requests': 10  # Allow 10 requests in half-open state
                    },
                    'timestamp': datetime.now().isoformat(),
                    'reason': 'high_error_rate'
                }
                
                topic_name = f"hft.control.{service_type.value}"
                await self.producer.send_to_topic(topic_name, control_message)
            
            logger.info("Enabled circuit breaker mode for all services")
            
        except Exception as e:
            logger.error(f"Error enabling circuit breaker mode: {e}")
    
    def get_system_health(self) -> SystemHealth:
        """Get current system health status"""
        
        try:
            # Get recent system metrics
            cpu_metrics = self._get_recent_metrics(LoadMetricType.CPU_USAGE, window_seconds=60)
            memory_metrics = self._get_recent_metrics(LoadMetricType.MEMORY_USAGE, window_seconds=60)
            error_metrics = self._get_recent_metrics(LoadMetricType.ERROR_RATE, window_seconds=300)
            processing_metrics = self._get_recent_metrics(LoadMetricType.PROCESSING_TIME, window_seconds=300)
            message_metrics = self._get_recent_metrics(LoadMetricType.MESSAGE_RATE, window_seconds=60)
            
            # Calculate averages
            cpu_usage = statistics.mean([m.value for m in cpu_metrics]) if cpu_metrics else 0.0
            memory_usage = statistics.mean([m.value for m in memory_metrics]) if memory_metrics else 0.0
            error_rate = statistics.mean([m.value for m in error_metrics]) if error_metrics else 0.0
            avg_processing_time = statistics.mean([m.value for m in processing_metrics]) if processing_metrics else 0.0
            message_throughput = statistics.mean([m.value for m in message_metrics]) if message_metrics else 0.0
            
            # Determine overall status
            overall_status = "healthy"
            
            if cpu_usage > 90 or memory_usage > 95 or error_rate > 10:
                overall_status = "emergency"
            elif cpu_usage > 80 or memory_usage > 85 or error_rate > 5:
                overall_status = "critical"
            elif cpu_usage > 70 or memory_usage > 75 or error_rate > 1:
                overall_status = "degraded"
            
            return SystemHealth(
                overall_status=overall_status,
                cpu_usage_percent=round(cpu_usage, 2),
                memory_usage_percent=round(memory_usage, 2),
                active_services=len(self.service_health_scores),
                error_rate_percent=round(error_rate, 2),
                avg_processing_time_ms=round(avg_processing_time, 2),
                message_throughput_per_second=round(message_throughput, 2)
            )
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return SystemHealth(
                overall_status="unknown",
                cpu_usage_percent=0.0,
                memory_usage_percent=0.0,
                active_services=0,
                error_rate_percent=0.0,
                avg_processing_time_ms=0.0,
                message_throughput_per_second=0.0
            )
    
    def get_load_balancing_stats(self) -> Dict[str, Any]:
        """Get load balancing statistics"""
        
        try:
            return {
                'is_monitoring': self.is_monitoring,
                'service_health_scores': {k.value: v for k, v in self.service_health_scores.items()},
                'recent_actions_count': len(self.recent_actions),
                'recent_actions': [
                    {
                        'action_type': action.action_type,
                        'service_type': action.service_type.value,
                        'reason': action.reason,
                        'timestamp': action.timestamp.isoformat()
                    }
                    for action in list(self.recent_actions)[-10:]  # Last 10 actions
                ],
                'metrics_count': {key: len(history) for key, history in self.metrics_history.items()},
                'system_health': self.get_system_health().__dict__,
                'performance_thresholds': {
                    metric_type.value: {
                        'warning': threshold.warning_threshold,
                        'critical': threshold.critical_threshold,
                        'emergency': threshold.emergency_threshold
                    }
                    for metric_type, threshold in self.thresholds.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting load balancing stats: {e}")
            return {'error': str(e)}


# Singleton instance
_load_balancer: Optional[HFTLoadBalancer] = None


def get_hft_load_balancer() -> HFTLoadBalancer:
    """Get singleton HFT load balancer instance"""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = HFTLoadBalancer()
    return _load_balancer


async def initialize_hft_load_balancer() -> bool:
    """Initialize and start the HFT load balancer"""
    try:
        load_balancer = get_hft_load_balancer()
        success = await load_balancer.start_monitoring()
        
        if success:
            logger.info("HFT Load Balancer initialized and started successfully")
        else:
            logger.error("Failed to initialize HFT Load Balancer")
        
        return success
        
    except Exception as e:
        logger.error(f"Error initializing HFT load balancer: {e}")
        return False


async def cleanup_hft_load_balancer() -> None:
    """Cleanup the HFT load balancer"""
    try:
        global _load_balancer
        if _load_balancer:
            await _load_balancer.stop_monitoring()
            _load_balancer = None
        logger.info("HFT Load Balancer cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up HFT load balancer: {e}")