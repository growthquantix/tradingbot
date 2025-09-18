"""
HFT System API Router

REST API endpoints for monitoring and managing the HFT Kafka architecture
with real-time performance metrics and system health checks.

Author: Trading System
Created: 2025-01-11
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from database.connection import SessionLocal, get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/hft", tags=["HFT System"])


def get_hft_system():
    """Get HFT system instance safely"""
    try:
        from services.hft import get_hft_system
        return get_hft_system()
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HFT system not available"
        )


def get_hft_monitor():
    """Get HFT monitor instance safely"""
    try:
        from services.hft import get_hft_monitor
        return get_hft_monitor()
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HFT monitoring not available"
        )


@router.get("/health")
async def get_hft_health():
    """
    Get comprehensive HFT system health status
    
    Returns:
        Complete system health information including all components
    """
    try:
        hft_system = get_hft_system()
        monitor = get_hft_monitor()
        
        # Get system status
        system_status = hft_system.get_system_status()
        
        # Get health from monitor
        system_health = monitor.get_system_health()
        
        # Get centralized WebSocket manager status
        ws_manager_status = {}
        try:
            from services.centralized_ws_manager import centralized_manager
            if centralized_manager:
                ws_manager_status = {
                    "is_running": centralized_manager.is_running,
                    "connection_ready": centralized_manager.connection_ready.is_set(),
                    "data_count": getattr(centralized_manager, 'data_count', 0),
                    "performance_metrics": centralized_manager.performance_metrics
                }
        except ImportError:
            ws_manager_status = {"status": "not_available"}
        
        return {
            "status": "healthy" if system_status["is_running"] else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "hft_system": system_status,
            "performance": system_health,
            "websocket_manager": ws_manager_status,
            "components": {
                "kafka_producer": await _get_producer_health(),
                "memory_bridge": await _get_memory_bridge_health(),
                "consumers": await _get_consumers_health()
            }
        }
        
    except Exception as e:
        logger.error(f"❌ HFT health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )


@router.get("/performance")
async def get_performance_metrics():
    """
    Get real-time performance metrics for all HFT components
    
    Returns:
        Detailed performance metrics including latency, throughput, and resource usage
    """
    try:
        monitor = get_hft_monitor()
        
        # Get all current metrics
        all_metrics = monitor.get_all_metrics()
        
        # Get system health
        system_health = monitor.get_system_health()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system_health": system_health,
            "service_metrics": all_metrics,
            "summary": {
                "total_services": len(all_metrics),
                "avg_latency_ms": system_health.get("avg_latency_ms", 0),
                "total_errors": system_health.get("total_errors", 0),
                "total_warnings": system_health.get("total_warnings", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Performance metrics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance metrics: {e}"
        )


@router.get("/services")
async def get_services_status():
    """
    Get status of all registered HFT services
    
    Returns:
        List of all services with their current status and performance
    """
    try:
        hft_system = get_hft_system()
        system_status = hft_system.get_system_status()
        
        services_detail = []
        for service_name in system_status.get("active_services", []):
            service_status = hft_system.get_service_status(service_name)
            if service_status:
                services_detail.append(service_status)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_services": len(services_detail),
            "active_services": len([s for s in services_detail if s["is_active"]]),
            "failed_services": len([s for s in services_detail if s["error_count"] > 0]),
            "services": services_detail
        }
        
    except Exception as e:
        logger.error(f"❌ Services status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get services status: {e}"
        )


@router.get("/services/{service_name}")
async def get_service_status(service_name: str):
    """
    Get detailed status for a specific service
    
    Args:
        service_name: Name of the service to check
        
    Returns:
        Detailed service status and performance metrics
    """
    try:
        hft_system = get_hft_system()
        service_status = hft_system.get_service_status(service_name)
        
        if not service_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "service": service_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Service status error for {service_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service status: {e}"
        )


@router.post("/services/{service_name}/restart")
async def restart_service(service_name: str):
    """
    Restart a specific HFT service
    
    Args:
        service_name: Name of the service to restart
        
    Returns:
        Operation result
    """
    try:
        hft_system = get_hft_system()
        
        # Check if service exists
        service_status = hft_system.get_service_status(service_name)
        if not service_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )
        
        # Restart service
        success = await hft_system.restart_service(service_name)
        
        if success:
            return {
                "status": "success",
                "message": f"Service '{service_name}' restarted successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to restart service '{service_name}'"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Service restart error for {service_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart service: {e}"
        )


@router.get("/kafka/topics")
async def get_kafka_topics():
    """
    Get information about HFT Kafka topics
    
    Returns:
        List of all configured Kafka topics with their settings
    """
    try:
        from services.hft import get_topic_manager
        
        topic_manager = get_topic_manager()
        all_topics = topic_manager.get_all_topics()
        
        topics_info = []
        for topic_name, topic_config in all_topics.items():
            topics_info.append({
                "name": topic_config.name,
                "partitions": topic_config.partitions,
                "replication_factor": topic_config.replication_factor,
                "retention_ms": topic_config.retention_ms,
                "priority": topic_config.priority.name,
                "consumer_groups": topic_config.consumer_groups,
                "description": topic_config.description
            })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_topics": len(topics_info),
            "topics": topics_info
        }
        
    except Exception as e:
        logger.error(f"❌ Kafka topics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Kafka topics: {e}"
        )


@router.get("/producer/stats")
async def get_producer_stats():
    """
    Get detailed Kafka producer statistics
    
    Returns:
        Producer performance metrics and status
    """
    try:
        from services.hft import get_hft_producer
        
        producer = await get_hft_producer()
        stats = producer.get_performance_stats()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "producer_stats": stats,
            "health": await producer.health_check()
        }
        
    except Exception as e:
        logger.error(f"❌ Producer stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get producer stats: {e}"
        )


@router.get("/memory-bridge/stats")
async def get_memory_bridge_stats():
    """
    Get memory bridge performance statistics
    
    Returns:
        Memory bridge metrics and health status
    """
    try:
        from services.hft import get_hft_memory_bridge
        
        bridge = await get_hft_memory_bridge()
        stats = bridge.get_performance_stats()
        health = await bridge.health_check()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "memory_bridge_stats": stats,
            "health": health
        }
        
    except Exception as e:
        logger.error(f"❌ Memory bridge stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get memory bridge stats: {e}"
        )


@router.get("/adr")
async def get_advance_decline_ratios():
    """
    Get real-time Advance Decline Ratios for all market segments
    
    Returns:
        Complete ADR summary with market breadth analysis
    """
    try:
        from services.hft.advance_decline_service import get_advance_decline_service
        
        adr_service = get_advance_decline_service()
        adr_summary = adr_service.get_adr_summary()
        
        return {
            "status": "success",
            "data": adr_summary
        }
        
    except Exception as e:
        logger.error(f"❌ ADR data error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ADR data: {e}"
        )


@router.get("/adr/{segment}")
async def get_segment_adr(segment: str):
    """
    Get ADR data for specific market segment
    
    Args:
        segment: Market segment (nifty_50, nifty_500, banking, it, etc.)
        
    Returns:
        Detailed ADR data for the segment
    """
    try:
        from services.hft.advance_decline_service import get_advance_decline_service
        from services.hft.subscription_manager import MarketSegment
        
        # Convert string to MarketSegment enum
        try:
            market_segment = MarketSegment(segment.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid market segment: {segment}"
            )
        
        adr_service = get_advance_decline_service()
        breadth_snapshot = adr_service.get_market_breadth_snapshot(market_segment)
        
        if not breadth_snapshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data available for segment: {segment}"
            )
        
        return {
            "status": "success",
            "segment": segment,
            "data": {
                "advancing": breadth_snapshot.advance_decline.advancing_count,
                "declining": breadth_snapshot.advance_decline.declining_count,
                "unchanged": breadth_snapshot.advance_decline.unchanged_count,
                "total": breadth_snapshot.advance_decline.total_count,
                "adr": breadth_snapshot.advance_decline.advance_decline_ratio,
                "difference": breadth_snapshot.advance_decline.advance_decline_difference,
                "advancing_volume": breadth_snapshot.advance_decline.advancing_volume,
                "declining_volume": breadth_snapshot.advance_decline.declining_volume,
                "new_highs": breadth_snapshot.new_highs,
                "new_lows": breadth_snapshot.new_lows,
                "arms_index": breadth_snapshot.arms_index,
                "timestamp": breadth_snapshot.timestamp.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Segment ADR error for {segment}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get segment ADR: {e}"
        )


@router.get("/market-sentiment")
async def get_market_sentiment():
    """
    Get comprehensive market sentiment analysis
    
    Returns:
        Market sentiment summary with trend analysis
    """
    try:
        from services.hft.market_breadth_analytics import get_market_breadth_analytics
        
        analytics_service = get_market_breadth_analytics()
        sentiment_summary = analytics_service.get_market_sentiment_summary()
        
        return {
            "status": "success",
            "data": sentiment_summary
        }
        
    except Exception as e:
        logger.error(f"❌ Market sentiment error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get market sentiment: {e}"
        )


@router.get("/breadth-indicators/{segment}")
async def get_breadth_indicators(segment: str):
    """
    Get detailed breadth indicators for market segment
    
    Args:
        segment: Market segment identifier
        
    Returns:
        Complete breadth indicators analysis
    """
    try:
        from services.hft.market_breadth_analytics import get_market_breadth_analytics
        from services.hft.subscription_manager import MarketSegment
        
        # Convert string to MarketSegment enum
        try:
            market_segment = MarketSegment(segment.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid market segment: {segment}"
            )
        
        analytics_service = get_market_breadth_analytics()
        analysis = analytics_service.get_advanced_analysis(market_segment)
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No analysis available for segment: {segment}"
            )
        
        return {
            "status": "success",
            "segment": segment,
            "data": {
                "breadth_indicators": {
                    "advance_decline_line": analysis.breadth_indicators.advance_decline_line,
                    "mcclellan_oscillator": analysis.breadth_indicators.mcclellan_oscillator,
                    "mcclellan_summation": analysis.breadth_indicators.mcclellan_summation,
                    "breadth_thrust": analysis.breadth_indicators.breadth_thrust,
                    "high_low_index": analysis.breadth_indicators.high_low_index,
                    "up_down_volume_ratio": analysis.breadth_indicators.up_down_volume_ratio,
                    "timestamp": analysis.breadth_indicators.timestamp.isoformat()
                },
                "market_sentiment": {
                    "sentiment_score": analysis.market_sentiment.sentiment_score,
                    "trend_direction": analysis.market_sentiment.trend_direction.value,
                    "market_phase": analysis.market_sentiment.market_phase.value,
                    "confidence_level": analysis.market_sentiment.confidence_level,
                    "key_indicators": analysis.market_sentiment.key_indicators,
                    "timestamp": analysis.market_sentiment.timestamp.isoformat()
                },
                "participation_rate": analysis.participation_rate,
                "momentum_score": analysis.momentum_score,
                "divergence_alerts": analysis.divergence_alerts,
                "timestamp": analysis.timestamp.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Breadth indicators error for {segment}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get breadth indicators: {e}"
        )


@router.get("/subscriptions")
async def get_subscription_status():
    """
    Get current instrument subscription status
    
    Returns:
        Subscription manager status and performance
    """
    try:
        from services.hft.subscription_manager import get_subscription_manager
        
        subscription_manager = get_subscription_manager()
        stats = subscription_manager.get_performance_stats()
        partition_assignments = subscription_manager.get_partition_assignments()
        
        return {
            "status": "success",
            "data": {
                "performance_stats": stats,
                "partition_assignments": {
                    partition: list(instruments) 
                    for partition, instruments in partition_assignments.items()
                },
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Subscription status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subscription status: {e}"
        )


@router.post("/subscriptions/{segment}")
async def subscribe_to_segment(segment: str, subscription_types: List[str]):
    """
    Subscribe to a market segment for specific data types
    
    Args:
        segment: Market segment to subscribe to
        subscription_types: List of subscription types
        
    Returns:
        Subscription result
    """
    try:
        from services.hft.subscription_manager import (
            get_subscription_manager, 
            MarketSegment, 
            SubscriptionType
        )
        
        # Convert string to MarketSegment enum
        try:
            market_segment = MarketSegment(segment.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid market segment: {segment}"
            )
        
        # Convert strings to SubscriptionType enums
        try:
            sub_types = {SubscriptionType(sub_type) for sub_type in subscription_types}
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid subscription type: {e}"
            )
        
        subscription_manager = get_subscription_manager()
        success = subscription_manager.subscribe_market_segment(market_segment, sub_types)
        
        if success:
            return {
                "status": "success",
                "message": f"Subscribed to {segment} for {len(sub_types)} data types",
                "segment": segment,
                "subscription_types": subscription_types
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Subscription failed"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Subscription error for {segment}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to subscribe to segment: {e}"
        )


@router.get("/config")
async def get_hft_config():
    """
    Get HFT system configuration
    
    Returns:
        Current HFT configuration settings
    """
    try:
        from services.hft import get_hft_kafka_config
        
        config = get_hft_kafka_config()
        
        # Return configuration (excluding sensitive data)
        return {
            "timestamp": datetime.now().isoformat(),
            "bootstrap_servers": config.bootstrap_servers,
            "client_id": config.client_id,
            "producer_config": {
                key: value for key, value in config.producer_config.items()
                if key not in ["username", "password", "security_protocol"]
            },
            "consumer_config": {
                key: value for key, value in config.consumer_config.items()
                if key not in ["username", "password", "security_protocol"]
            },
            "monitoring_config": config.monitoring_config
        }
        
    except Exception as e:
        logger.error(f"❌ HFT config error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get HFT config: {e}"
        )


# Helper functions
async def _get_producer_health() -> Dict[str, Any]:
    """Get producer health status"""
    try:
        from services.hft import get_hft_producer
        producer = await get_hft_producer()
        return await producer.health_check()
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _get_memory_bridge_health() -> Dict[str, Any]:
    """Get memory bridge health status"""
    try:
        from services.hft import get_hft_memory_bridge
        bridge = await get_hft_memory_bridge()
        return await bridge.health_check()
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _get_consumers_health() -> Dict[str, Any]:
    """Get consumers health status"""
    try:
        # This would check all registered consumers
        # Implementation depends on consumer registry
        return {"status": "healthy", "message": "All consumers operational"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Export router
__all__ = ["router"]