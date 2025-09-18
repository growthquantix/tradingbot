"""
Auto Stock Selection Service - Modular and Comprehensive
Runs at 9 AM premarket to select stocks based on ADR, market sentiment, and sector analysis
Uses live market data with fast numpy/pandas processing
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, date, time
from typing import Dict, List, Optional, Any, Tuple
import pytz
import json
from dataclasses import dataclass

# Database imports
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import SelectedStock, AutoTradingSession, DailyStockSummary

# Service imports
from services.enhanced_market_analytics import enhanced_analytics
from services.trading_stock_selector import TradingStockSelector
from services.upstox_option_service import upstox_option_service
from services.market_schedule_service import MarketScheduleService

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")


@dataclass
class StockSelectionResult:
    """Result of stock selection process"""

    symbol: str
    sector: str
    selection_score: float
    selection_reason: str
    price_at_selection: float
    option_type: str  # CE/PE/NEUTRAL
    option_contract: Optional[Dict]
    atm_strike: Optional[float]
    market_sentiment_alignment: bool
    adr_score: float
    sector_momentum: float
    volume_score: float
    technical_score: float
    expiry_date: Optional[str]
    instrument_key: str


class AutoStockSelectionService:
    """
    Modular Auto Stock Selection Service

    Features:
    - Runs at 9 AM premarket via MarketScheduleService integration
    - ADR (American Depositary Receipt) analysis for global cues
    - Market sentiment analysis (bullish -> CE, bearish -> PE)
    - Sector sentiment evaluation
    - Live feed data processing with numpy/pandas
    - ATM strike price calculation
    - Modular architecture for easy testing/modification
    """

    def __init__(self, user_id: int = 1):
        self.user_id = user_id
        self.analytics = enhanced_analytics
        self.option_service = upstox_option_service

        # Configuration
        self.max_stocks_to_select = 2  # Focus on 2 high-quality stocks
        self.sectors_to_analyze = 1  # Top performing sector only
        self.min_volume_threshold = 100000  # Minimum daily volume
        self.min_adr_correlation = 0.3  # Minimum ADR correlation score

        # Initialize stock selector with options integration
        self.stock_selector = TradingStockSelector(
            analytics=self.analytics,
            db_session_factory=SessionLocal,
            option_service=self.option_service,
            sectors_to_pick=self.sectors_to_analyze,
            per_sector_limit=2,
            max_total_stocks=self.max_stocks_to_select,
            user_id=self.user_id,
        )

        # F&O Selection Configuration
        self.fno_selection_config = {
            "volume_threshold": 100000,  # Daily volume > 1L
            "option_liquidity": {
                "min_oi": 10000,  # Open Interest > 10K
                "bid_ask_spread": 0.05,  # Max 5 paisa spread
            },
            "price_range": {"min_price": 50, "max_price": 5000},
            "volatility": {
                "min_historical_vol": 0.15,  # 15% annual volatility
                "max_historical_vol": 0.80,  # 80% annual volatility
            },
            "fibonacci_criteria": {
                "min_swing_clarity": 0.6,  # Clear swing highs/lows
                "min_ema_alignment": 0.5,  # EMA trend strength
                "min_fib_respect": 0.4,  # Historical Fibonacci respect
            },
        }

        # F&O Indices (only stocks from these 5 indices)
        self.fno_indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]

        logger.info(f"✅ AutoStockSelectionService initialized for user {self.user_id}")

    async def run_premarket_selection(self) -> List[StockSelectionResult]:
        """
        Main entry point - runs at 9 AM premarket
        Called by MarketScheduleService
        """
        logger.info("🎯 Starting premarket auto stock selection...")

        try:
            # Step 1: Market sentiment analysis
            market_sentiment = await self._analyze_market_sentiment()
            logger.info(f"📊 Market sentiment: {market_sentiment['sentiment']}")

            # Step 2: ADR analysis for global market cues
            adr_analysis = await self._analyze_adr_sentiment()
            logger.info(
                f"🌍 ADR sentiment score: {adr_analysis['composite_score']:.2f}"
            )

            # Step 3: Sector momentum analysis
            sector_analysis = await self._analyze_sector_momentum(market_sentiment)
            logger.info(
                f"📈 Top sector: {sector_analysis['top_sector']} ({sector_analysis['momentum']:.2f}%)"
            )

            # Step 4: Stock filtering and selection
            selected_stocks = await self._select_stocks_with_options(
                market_sentiment, adr_analysis, sector_analysis
            )

            # Step 5: Calculate ATM strikes and prepare options data
            enhanced_results = await self._enhance_with_options_data(
                selected_stocks, market_sentiment
            )

            # Step 6: Store results in database
            await self._store_selection_results(enhanced_results)

            logger.info(
                f"✅ Premarket selection complete: {len(enhanced_results)} stocks selected"
            )
            return enhanced_results

        except Exception as e:
            logger.error(f"❌ Premarket selection failed: {e}")
            return []

    async def _analyze_market_sentiment(self) -> Dict[str, Any]:
        """Analyze overall market sentiment using multiple indicators"""
        try:
            # Get sentiment from enhanced analytics
            base_sentiment = self.analytics.get_market_sentiment()

            # Get Nifty data for trend analysis
            nifty_data = self.analytics.get_top_movers()

            # Analyze FII/DII data if available
            institutional_flow = await self._get_institutional_flow()

            # VIX analysis for volatility
            vix_data = await self._get_vix_analysis()

            # Composite sentiment calculation
            sentiment_score = self._calculate_composite_sentiment(
                base_sentiment, nifty_data, institutional_flow, vix_data
            )

            return {
                "sentiment": sentiment_score["sentiment"],
                "confidence": sentiment_score["confidence"],
                "factors": {
                    "base_sentiment": base_sentiment,
                    "nifty_trend": nifty_data.get("trend", "neutral"),
                    "institutional_flow": institutional_flow,
                    "vix_level": vix_data.get("level", "normal"),
                },
                "option_bias": (
                    "CE"
                    if sentiment_score["sentiment"] in ["bullish", "very_bullish"]
                    else "PE"
                ),
            }

        except Exception as e:
            logger.error(f"❌ Market sentiment analysis failed: {e}")
            return {"sentiment": "neutral", "confidence": 0.5, "option_bias": "NEUTRAL"}

    async def _analyze_adr_sentiment(self) -> Dict[str, Any]:
        """
        Analyze ADR (American Depositary Receipt) data for global market cues
        This helps understand how Indian stocks performed in US markets overnight
        """
        try:
            # ADR symbols for major Indian companies
            adr_symbols = [
                "INFY",  # Infosys
                "WIT",  # Wipro
                "HDB",  # HDFC Bank
                "IBN",  # ICICI Bank
                "TTM",  # Tata Motors
                "VEDL",  # Vedanta
                "RDY",  # Dr. Reddy's
                "SIFY",  # Sify Technologies
            ]

            # Get US market performance (approximate using global market data)
            us_market_performance = await self._get_us_market_data()

            # Calculate ADR correlation score
            adr_scores = []
            for symbol in adr_symbols:
                try:
                    # Get corresponding Indian stock data
                    indian_symbol = self._map_adr_to_indian_symbol(symbol)
                    if indian_symbol:
                        indian_stock_data = self.analytics.get_stock_data(indian_symbol)
                        if indian_stock_data:
                            correlation = self._calculate_adr_correlation(
                                us_market_performance, indian_stock_data
                            )
                            adr_scores.append(
                                {
                                    "adr_symbol": symbol,
                                    "indian_symbol": indian_symbol,
                                    "correlation": correlation,
                                    "us_performance": us_market_performance.get(
                                        "change_percent", 0
                                    ),
                                    "indian_premarket": indian_stock_data.get(
                                        "change_percent", 0
                                    ),
                                }
                            )
                except Exception as e:
                    logger.debug(f"ADR analysis failed for {symbol}: {e}")
                    continue

            # Calculate composite ADR score
            composite_score = (
                np.mean([score["correlation"] for score in adr_scores])
                if adr_scores
                else 0.5
            )

            # Determine ADR sentiment
            if composite_score > 0.6:
                adr_sentiment = "positive"
            elif composite_score < 0.4:
                adr_sentiment = "negative"
            else:
                adr_sentiment = "neutral"

            return {
                "composite_score": composite_score,
                "sentiment": adr_sentiment,
                "individual_scores": adr_scores,
                "us_market_performance": us_market_performance,
                "confidence": min(len(adr_scores) / len(adr_symbols), 1.0),
            }

        except Exception as e:
            logger.error(f"❌ ADR sentiment analysis failed: {e}")
            return {"composite_score": 0.5, "sentiment": "neutral", "confidence": 0.0}

    async def _analyze_sector_momentum(self, market_sentiment: Dict) -> Dict[str, Any]:
        """Analyze sector-wise momentum to identify the top performing sector"""
        try:
            # Get sector heatmap from analytics
            sector_heatmap = self.analytics.get_sector_heatmap()

            if not sector_heatmap or not isinstance(sector_heatmap, dict):
                logger.warning("No sector heatmap data available - using fallback")
                return self._get_fallback_sector_analysis(market_sentiment)

            sectors = sector_heatmap.get("sectors", [])
            if not sectors:
                logger.warning(
                    "No sector data in heatmap - using fallback for premarket"
                )
                return self._get_fallback_sector_analysis(market_sentiment)

            # Calculate sector scores based on multiple factors
            sector_scores = {}
            for sector_data in sectors:
                if isinstance(sector_data, dict):
                    sector_name = sector_data.get("name", "UNKNOWN")
                    change_percent = sector_data.get("change_percent", 0)
                    volume_ratio = sector_data.get("volume_ratio", 1.0)

                    # Composite sector score
                    # Higher weight for momentum, moderate weight for volume
                    sector_score = (change_percent * 0.7) + (volume_ratio * 0.3)

                    sector_scores[sector_name] = {
                        "momentum": change_percent,
                        "volume_ratio": volume_ratio,
                        "composite_score": sector_score,
                    }

            # Sort sectors by composite score
            sorted_sectors = sorted(
                sector_scores.items(),
                key=lambda x: x[1]["composite_score"],
                reverse=True,
            )

            # Select top sector based on market sentiment
            if market_sentiment.get("sentiment") in ["bearish", "very_bearish"]:
                # In bearish market, select least declining sector
                top_sector_name = min(
                    sector_scores.keys(), key=lambda k: sector_scores[k]["momentum"]
                )
            else:
                # In bullish/neutral market, select best performing sector
                top_sector_name = sorted_sectors[0][0] if sorted_sectors else "BANKING"

            top_sector_data = sector_scores.get(top_sector_name, {"momentum": 0.0})

            return {
                "top_sector": top_sector_name,
                "momentum": top_sector_data["momentum"],
                "volume_ratio": top_sector_data.get("volume_ratio", 1.0),
                "sectors": sector_scores,
                "selection_reason": f"Top momentum sector in {market_sentiment.get('sentiment')} market",
            }

        except Exception as e:
            logger.error(f"❌ Sector momentum analysis failed: {e}")
            return self._get_fallback_sector_analysis(market_sentiment)

    def _get_fallback_sector_analysis(self, market_sentiment: Dict) -> Dict[str, Any]:
        """Fallback sector analysis for premarket hours when live data isn't available"""

        # Predefined sector rotation based on market conditions
        bullish_sectors = [
            "TECHNOLOGY",
            "BANKING",
            "AUTOMOBILE",
            "PHARMACEUTICAL",
            "FMCG",
        ]
        bearish_sectors = ["BANKING", "FMCG", "PHARMACEUTICAL", "ENERGY", "METAL"]
        neutral_sectors = [
            "BANKING",
            "FMCG",
            "TECHNOLOGY",
            "AUTOMOBILE",
            "PHARMACEUTICAL",
        ]

        sentiment = market_sentiment.get("sentiment", "neutral").lower()

        # Select sector based on market sentiment
        if sentiment in ["bullish", "very_bullish"]:
            selected_sectors = bullish_sectors
            momentum_range = (0.5, 1.5)
        elif sentiment in ["bearish", "very_bearish"]:
            selected_sectors = bearish_sectors
            momentum_range = (-1.0, 0.2)
        else:
            selected_sectors = neutral_sectors
            momentum_range = (-0.3, 0.8)

        # Build sector scores with simulated momentum
        import random

        sector_scores = {}
        for i, sector in enumerate(selected_sectors[:5]):  # Top 5 sectors
            # Higher momentum for top sectors
            base_momentum = momentum_range[1] - (i * 0.2)
            momentum = max(
                momentum_range[0],
                min(momentum_range[1], base_momentum + random.uniform(-0.2, 0.2)),
            )

            sector_scores[sector] = {
                "momentum": round(momentum, 2),
                "volume_ratio": round(1.0 + random.uniform(-0.1, 0.3), 2),
                "composite_score": round(momentum * 0.7 + 1.0 * 0.3, 2),
            }

        top_sector = selected_sectors[0]

        logger.info(f"📈 Using fallback sector analysis for premarket")
        logger.info(
            f"📈 Top sector: {top_sector} ({sector_scores[top_sector]['momentum']:.2f}%)"
        )

        return {
            "top_sector": top_sector,
            "momentum": sector_scores[top_sector]["momentum"],
            "volume_ratio": sector_scores[top_sector]["volume_ratio"],
            "sectors": sector_scores,
            "selection_reason": f"Fallback sector rotation for {sentiment} market during premarket",
        }

    async def _select_stocks_with_options(
        self, market_sentiment: Dict, adr_analysis: Dict, sector_analysis: Dict
    ) -> List[Dict[str, Any]]:
        """Select stocks with options trading capability"""
        try:
            # Use the existing TradingStockSelector with enhanced criteria
            logger.info(
                f"🔍 Selecting stocks from {sector_analysis['top_sector']} sector"
            )

            # Run the selection process
            selected_candidates = self.stock_selector.run_selection_sync()

            if not selected_candidates:
                logger.warning("No stocks selected by TradingStockSelector")
                return []

            # Filter and enhance candidates with our additional criteria
            enhanced_candidates = []

            for candidate in selected_candidates:
                try:
                    # Apply additional filters
                    if not self._meets_selection_criteria(
                        candidate, adr_analysis, sector_analysis
                    ):
                        continue

                    # Add our additional analysis
                    enhanced_candidate = candidate.copy()
                    enhanced_candidate.update(
                        {
                            "adr_alignment": self._calculate_adr_alignment(
                                candidate, adr_analysis
                            ),
                            "sector_momentum": sector_analysis["momentum"],
                            "market_sentiment_alignment": market_sentiment.get(
                                "sentiment", "neutral"
                            ),
                            "volume_score": self._calculate_volume_score(candidate),
                            "technical_score": self._calculate_technical_score(
                                candidate
                            ),
                        }
                    )

                    enhanced_candidates.append(enhanced_candidate)

                except Exception as e:
                    logger.error(
                        f"Error enhancing candidate {candidate.get('symbol')}: {e}"
                    )
                    continue

            # Sort by composite score and take top selections (with safety checks)
            enhanced_candidates.sort(
                key=lambda x: (
                    float(
                        x.get("selection_score", 0)
                        if isinstance(x.get("selection_score", 0), (int, float))
                        else 0
                    )
                    + float(
                        x.get("adr_alignment", 0)
                        if isinstance(x.get("adr_alignment", 0), (int, float))
                        else 0
                    )
                ),
                reverse=True,
            )

            final_selection = enhanced_candidates[: self.max_stocks_to_select]

            logger.info(f"✅ Selected {len(final_selection)} stocks for trading")
            return final_selection

        except Exception as e:
            logger.error(f"❌ Stock selection with options failed: {e}")
            return []

    async def _enhance_with_options_data(
        self, selected_stocks: List[Dict], market_sentiment: Dict
    ) -> List[StockSelectionResult]:
        """Enhance selected stocks with ATM options data"""
        results = []

        for stock_data in selected_stocks:
            try:
                symbol = stock_data.get("symbol")
                if not symbol:
                    continue

                # Calculate ATM strike price
                current_price = stock_data.get("price_at_selection", 0)
                if current_price <= 0:
                    # Try to get current price from live feed
                    instrument_key = stock_data.get("instrument_key")
                    if instrument_key:
                        price_data = self.live_adapter.get_latest_price(instrument_key)
                        current_price = price_data.get("ltp", 0) if price_data else 0

                if current_price <= 0:
                    logger.warning(f"No valid price data for {symbol}")
                    continue

                atm_strike = self._calculate_atm_strike(current_price)

                # Determine option type based on market sentiment
                option_type = self._determine_option_type(market_sentiment, stock_data)

                # Get option contract data
                option_contract = stock_data.get("option_contract")
                expiry_date = stock_data.get("option_expiry_date")

                # Create result object
                result = StockSelectionResult(
                    symbol=symbol,
                    sector=stock_data.get("sector", "OTHER"),
                    selection_score=stock_data.get("selection_score", 0.0),
                    selection_reason=stock_data.get("selection_reason", ""),
                    price_at_selection=current_price,
                    option_type=option_type,
                    option_contract=option_contract,
                    atm_strike=atm_strike,
                    market_sentiment_alignment=option_type != "NEUTRAL",
                    adr_score=stock_data.get("adr_alignment", 0.5),
                    sector_momentum=stock_data.get("sector_momentum", 0.0),
                    volume_score=stock_data.get("volume_score", 0.0),
                    technical_score=stock_data.get("technical_score", 0.0),
                    expiry_date=expiry_date,
                    instrument_key=stock_data.get("instrument_key", ""),
                )

                results.append(result)

                logger.info(
                    f"📊 {symbol}: ATM {atm_strike} {option_type} "
                    f"(Price: ₹{current_price:.2f}, Score: {result.selection_score:.2f})"
                )

            except Exception as e:
                logger.error(
                    f"❌ Error enhancing {stock_data.get('symbol')} with options: {e}"
                )
                continue

        return results

    async def _store_selection_results(self, results: List[StockSelectionResult]):
        """Store selection results in database"""
        if not results:
            return

        db = SessionLocal()
        try:
            # Create auto trading session
            session = AutoTradingSession(
                user_id=self.user_id,
                session_date=date.today(),
                selected_stocks=[
                    {
                        "symbol": r.symbol,
                        "sector": r.sector,
                        "option_type": r.option_type,
                        "atm_strike": r.atm_strike,
                        "selection_score": r.selection_score,
                    }
                    for r in results
                ],
                screening_config={
                    "max_stocks": self.max_stocks_to_select,
                    "sectors_analyzed": self.sectors_to_analyze,
                    "min_volume": self.min_volume_threshold,
                },
                stocks_screened=len(results),
                session_type="AUTO_PREMARKET_SELECTION",
                status="ACTIVE",
            )

            db.add(session)
            db.flush()  # Get session ID

            # Store individual stock selections
            for result in results:
                selected_stock = SelectedStock(
                    symbol=result.symbol,
                    instrument_key=result.instrument_key,
                    selection_date=date.today(),
                    selection_score=result.selection_score,
                    selection_reason=result.selection_reason,
                    price_at_selection=result.price_at_selection,
                    sector=result.sector,
                    option_type=result.option_type,
                    option_contract=(
                        json.dumps(result.option_contract)
                        if result.option_contract
                        else None
                    ),
                    option_expiry_date=result.expiry_date,
                    score_breakdown=json.dumps(
                        {
                            "adr_score": result.adr_score,
                            "sector_momentum": result.sector_momentum,
                            "volume_score": result.volume_score,
                            "technical_score": result.technical_score,
                            "atm_strike": result.atm_strike,
                        }
                    ),
                    is_active=True,
                )

                db.add(selected_stock)

            db.commit()
            logger.info(f"✅ Stored {len(results)} stock selections in database")

            # 🚀 NEW: Update high-speed market data for selected stocks
            try:
                await self._update_high_speed_data_access(results)
            except Exception as e:
                logger.error(f"❌ Failed to update high-speed data access: {e}")

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to store selection results: {e}")
        finally:
            db.close()

    async def _update_high_speed_data_access(self, results: List[StockSelectionResult]):
        """Update high-speed market data system with selected stocks"""
        try:
            # Prepare data for high-speed system
            selected_stocks_data = []

            for result in results:
                stock_data = {
                    "symbol": result.symbol,
                    "instrument_key": result.instrument_key,
                    "option_type": result.option_type,
                    "atm_strike": result.atm_strike,
                    "expiry_date": result.expiry_date,
                    "price_at_selection": result.price_at_selection,
                    "sector": result.sector,
                    "selection_score": result.selection_score,
                    "adr_score": result.adr_score,
                    "technical_score": result.technical_score,
                    "volume_score": result.volume_score,
                    "sector_momentum": result.sector_momentum,
                    "selection_reason": result.selection_reason,
                }

                # Add option instrument key if available
                if result.option_contract and isinstance(result.option_contract, dict):
                    stock_data["option_instrument_key"] = result.option_contract.get(
                        "instrument_key"
                    )
                    stock_data["lot_size"] = result.option_contract.get("lot_size", 1)

                selected_stocks_data.append(stock_data)

            # Update high-speed market data system
            high_speed_market_data.update_selected_stocks(selected_stocks_data)

            logger.info(
                f"🚀 Updated high-speed market data for {len(selected_stocks_data)} selected stocks"
            )

            # Print summary for monitoring
            summary = high_speed_market_data.get_auto_trading_summary()
            logger.info(f"📊 Auto trading data access summary: {summary}")

        except Exception as e:
            logger.error(f"❌ Error updating high-speed data access: {e}")

    # Helper methods for calculations and analysis

    def _calculate_composite_sentiment(
        self,
        base_sentiment: Dict,
        nifty_data: Dict,
        institutional_flow: Dict,
        vix_data: Dict,
    ) -> Dict[str, Any]:
        """Calculate composite market sentiment score"""
        try:
            scores = []

            # Base sentiment score
            base_score = self._sentiment_to_score(
                base_sentiment.get("sentiment", "neutral")
            )
            scores.append(base_score * 0.4)  # 40% weight

            # Nifty trend score
            nifty_trend = nifty_data.get("trend", "neutral")
            nifty_score = self._sentiment_to_score(nifty_trend)
            scores.append(nifty_score * 0.3)  # 30% weight

            # Institutional flow score
            fii_flow = institutional_flow.get("fii_flow", 0)
            flow_score = 0.7 if fii_flow > 0 else (0.3 if fii_flow < 0 else 0.5)
            scores.append(flow_score * 0.2)  # 20% weight

            # VIX score (lower VIX = more bullish)
            vix_level = vix_data.get("value", 20)
            vix_score = max(0, min(1, (30 - vix_level) / 20))  # Normalize VIX
            scores.append(vix_score * 0.1)  # 10% weight

            composite_score = sum(scores)

            # Convert score to sentiment
            if composite_score > 0.7:
                sentiment = "very_bullish"
                confidence = 0.9
            elif composite_score > 0.6:
                sentiment = "bullish"
                confidence = 0.8
            elif composite_score > 0.4:
                sentiment = "neutral"
                confidence = 0.6
            elif composite_score > 0.3:
                sentiment = "bearish"
                confidence = 0.8
            else:
                sentiment = "very_bearish"
                confidence = 0.9

            return {
                "sentiment": sentiment,
                "confidence": confidence,
                "score": composite_score,
            }

        except Exception as e:
            logger.error(f"Composite sentiment calculation failed: {e}")
            return {"sentiment": "neutral", "confidence": 0.5, "score": 0.5}

    def _sentiment_to_score(self, sentiment: str) -> float:
        """Convert sentiment string to numerical score"""
        sentiment_map = {
            "very_bullish": 0.9,
            "bullish": 0.7,
            "neutral": 0.5,
            "bearish": 0.3,
            "very_bearish": 0.1,
        }
        return sentiment_map.get(sentiment.lower(), 0.5)

    def _calculate_atm_strike(self, current_price: float) -> float:
        """Calculate At-The-Money strike price"""
        if current_price <= 50:
            # For stocks under ₹50, use ₹2.5 interval
            return round(current_price / 2.5) * 2.5
        elif current_price <= 200:
            # For stocks ₹50-200, use ₹5 interval
            return round(current_price / 5) * 5
        elif current_price <= 1000:
            # For stocks ₹200-1000, use ₹10 interval
            return round(current_price / 10) * 10
        else:
            # For stocks above ₹1000, use ₹50 interval
            return round(current_price / 50) * 50

    def _determine_option_type(self, market_sentiment: Dict, stock_data: Dict) -> str:
        """Determine whether to trade CE or PE based on sentiment"""
        sentiment = market_sentiment.get("sentiment", "neutral").lower()

        # Check if stock is moving against market sentiment (contrarian play)
        stock_change = stock_data.get("change_percent_at_selection", 0)

        # Safety check: ensure stock_change is a number
        if isinstance(stock_change, list):
            stock_change = stock_change[0] if stock_change else 0
        if not isinstance(stock_change, (int, float)):
            stock_change = 0

        if sentiment in ["bullish", "very_bullish"]:
            if stock_change > 0:
                return "CE"  # Bullish market, stock rising -> CE
            elif stock_change < -2:
                return "PE"  # Bullish market but stock falling hard -> PE (contrarian)
            else:
                return "CE"  # Default to CE in bullish market
        elif sentiment in ["bearish", "very_bearish"]:
            if stock_change < 0:
                return "PE"  # Bearish market, stock falling -> PE
            elif stock_change > 2:
                return "CE"  # Bearish market but stock rising -> CE (contrarian)
            else:
                return "PE"  # Default to PE in bearish market
        else:
            # Neutral market - choose based on stock's own momentum
            # Safety check: ensure stock_change is a number
            if isinstance(stock_change, list):
                stock_change = stock_change[0] if stock_change else 0
            if not isinstance(stock_change, (int, float)):
                stock_change = 0

            if abs(stock_change) > 1:
                return "CE" if stock_change > 0 else "PE"
            else:
                return "NEUTRAL"

    def _meets_selection_criteria(
        self, candidate: Dict, adr_analysis: Dict, sector_analysis: Dict
    ) -> bool:
        """Check if candidate meets our additional selection criteria"""
        try:
            # Volume check
            volume = candidate.get("volume", 0)
            if volume < self.min_volume_threshold:
                return False

            # ADR correlation check (if available)
            adr_score = self._calculate_adr_alignment(candidate, adr_analysis)
            if adr_score < self.min_adr_correlation:
                return False

            # Sector alignment check
            candidate_sector = candidate.get("sector", "")
            if candidate_sector != sector_analysis.get("top_sector", ""):
                return False

            return True

        except Exception as e:
            logger.debug(f"Criteria check failed for {candidate.get('symbol')}: {e}")
            return False

    def _calculate_adr_alignment(self, candidate: Dict, adr_analysis: Dict) -> float:
        """Calculate how well the stock aligns with ADR sentiment"""
        try:
            symbol = candidate.get("symbol", "")

            # Check if this stock has ADR representation
            adr_scores = adr_analysis.get("individual_scores", [])
            for score_data in adr_scores:
                if score_data.get("indian_symbol") == symbol:
                    return score_data.get("correlation", 0.5)

            # If no direct ADR mapping, use composite score
            return adr_analysis.get("composite_score", 0.5)

        except Exception:
            return 0.5

    def _calculate_volume_score(self, candidate: Dict) -> float:
        """Calculate volume-based score"""
        try:
            volume = candidate.get("volume", 0)
            # Normalize volume score (higher volume = higher score)
            if volume >= 1000000:  # 10L+
                return 1.0
            elif volume >= 500000:  # 5L+
                return 0.8
            elif volume >= 100000:  # 1L+
                return 0.6
            else:
                return 0.4
        except Exception:
            return 0.5

    def _calculate_technical_score(self, candidate: Dict) -> float:
        """Calculate technical analysis score"""
        try:
            # Use existing strategy score if available
            strategy_score = candidate.get("strategy_score", 0)

            # Combine with momentum indicators
            change_percent = abs(candidate.get("change_percent", 0))
            momentum_score = min(change_percent / 5.0, 1.0)  # Normalize to 0-1

            return (strategy_score * 0.7) + (momentum_score * 0.3)

        except Exception:
            return 0.5

    # External data fetch methods (placeholders - implement based on available APIs)

    async def _get_institutional_flow(self) -> Dict[str, float]:
        """Get FII/DII flow data"""
        # Placeholder - implement with actual data source
        return {"fii_flow": 100, "dii_flow": 50}

    async def _get_vix_analysis(self) -> Dict[str, Any]:
        """Get VIX data for volatility analysis"""
        # Placeholder - implement with actual VIX data
        return {"level": "normal", "value": 18.5}

    async def _get_us_market_data(self) -> Dict[str, float]:
        """Get US market performance data"""
        # Placeholder - implement with actual US market data
        return {"change_percent": 0.5, "trend": "positive"}

    def _map_adr_to_indian_symbol(self, adr_symbol: str) -> Optional[str]:
        """Map ADR symbols to Indian stock symbols"""
        adr_mapping = {
            "INFY": "INFY",
            "WIT": "WIPRO",
            "HDB": "HDFCBANK",
            "IBN": "ICICIBANK",
            "TTM": "TATAMOTORS",
            "VEDL": "VEDL",
            "RDY": "DRREDDY",
            "SIFY": "SIFY",
        }
        return adr_mapping.get(adr_symbol)

    def _calculate_adr_correlation(self, us_data: Dict, indian_data: Dict) -> float:
        """Calculate correlation between ADR and Indian stock movement"""
        try:
            us_change = us_data.get("change_percent", 0)
            indian_change = indian_data.get("change_percent", 0)

            # Simple correlation calculation
            if us_change == 0 and indian_change == 0:
                return 0.5

            if (us_change > 0 and indian_change > 0) or (
                us_change < 0 and indian_change < 0
            ):
                # Same direction movement
                correlation = min(abs(us_change), abs(indian_change)) / max(
                    abs(us_change), abs(indian_change), 0.1
                )
                return min(correlation + 0.5, 1.0)
            else:
                # Opposite direction movement
                return 0.3

        except Exception:
            return 0.5

    # ==================================================================================
    # F&O STOCK SELECTION METHODS (Phase 2 Implementation)
    # ==================================================================================

    async def get_fno_stocks_from_indices(self) -> List[Dict[str, Any]]:
        """
        Get all F&O stocks from the 5 supported indices with current market data

        Returns:
            List of F&O stocks with metadata
        """
        try:
            fno_stocks = []

            # Get stocks from each F&O index
            for index_name in self.fno_indices:
                try:
                    # Get index constituents from enhanced analytics
                    index_stocks = self.analytics.get_index_stocks(index_name)

                    for stock_data in index_stocks:
                        # Validate if stock has F&O availability
                        if await self._validate_fno_availability(stock_data["symbol"]):
                            enhanced_stock = {
                                "symbol": stock_data["symbol"],
                                "index_membership": [index_name],
                                "current_price": stock_data.get("ltp", 0),
                                "volume": stock_data.get("volume", 0),
                                "change_percent": stock_data.get("change_percent", 0),
                                "sector": stock_data.get("sector", "Unknown"),
                                "market_cap": stock_data.get("market_cap", 0),
                                "avg_volume_30d": stock_data.get("avg_volume", 0),
                            }
                            fno_stocks.append(enhanced_stock)

                except Exception as e:
                    logger.warning(f"⚠️ Failed to get stocks from {index_name}: {e}")

            # Remove duplicates (stocks present in multiple indices)
            unique_stocks = {}
            for stock in fno_stocks:
                symbol = stock["symbol"]
                if symbol in unique_stocks:
                    # Add additional index membership
                    unique_stocks[symbol]["index_membership"].extend(
                        stock["index_membership"]
                    )
                else:
                    unique_stocks[symbol] = stock

            result = list(unique_stocks.values())
            logger.info(
                f"✅ Found {len(result)} unique F&O stocks from {len(self.fno_indices)} indices"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Failed to get F&O stocks from indices: {e}")
            return []

    async def score_fno_stocks_for_fibonacci_strategy(
        self, stocks: List[Dict[str, Any]]
    ) -> List[Tuple[str, float]]:
        """
        Score F&O stocks based on Fibonacci strategy suitability

        Args:
            stocks: List of F&O stock data

        Returns:
            List of (symbol, score) tuples sorted by score (highest first)
        """
        try:
            scores = {}

            for stock in stocks:
                try:
                    symbol = stock["symbol"]
                    score = 0.0

                    # Technical Score (40%)
                    swing_clarity = await self._calculate_swing_clarity(symbol)
                    ema_alignment = await self._check_ema_alignment(symbol)
                    fibonacci_respect = await self._historical_fibonacci_respect(symbol)
                    technical_score = (
                        swing_clarity + ema_alignment + fibonacci_respect
                    ) / 3

                    # Liquidity Score (30%)
                    volume_score = min(
                        stock.get("avg_volume_30d", 0) / 500000, 1.0
                    )  # Normalize to 5L volume
                    option_liquidity_score = (
                        await self._calculate_option_liquidity_score(symbol)
                    )
                    liquidity_score = (volume_score + option_liquidity_score) / 2

                    # Market Score (30%)
                    index_correlation = await self._get_index_correlation(
                        symbol, stock.get("index_membership", [])
                    )
                    sector_momentum = await self._get_sector_momentum_score(
                        stock.get("sector", "")
                    )
                    market_score = (index_correlation + sector_momentum) / 2

                    # Final Score
                    final_score = (
                        (technical_score * 0.4)
                        + (liquidity_score * 0.3)
                        + (market_score * 0.3)
                    )
                    scores[symbol] = final_score

                    logger.debug(
                        f"📊 {symbol}: Technical={technical_score:.2f}, Liquidity={liquidity_score:.2f}, "
                        f"Market={market_score:.2f}, Final={final_score:.2f}"
                    )

                except Exception as e:
                    logger.warning(
                        f"⚠️ Failed to score {stock.get('symbol', 'Unknown')}: {e}"
                    )
                    scores[stock.get("symbol", "Unknown")] = 0.0

            # Return top stocks sorted by score
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

            logger.info(
                f"✅ Scored {len(sorted_scores)} F&O stocks for Fibonacci strategy"
            )
            logger.info(f"🏆 Top 3 scores: {sorted_scores[:3]}")

            return sorted_scores

        except Exception as e:
            logger.error(f"❌ Failed to score F&O stocks: {e}")
            return []

    async def validate_option_liquidity(self, symbol: str) -> Dict[str, Any]:
        """
        Validate option liquidity for CE/PE contracts

        Args:
            symbol: Stock symbol to check

        Returns:
            Dict with liquidity validation results
        """
        try:
            # Get option chain data
            option_chain = await self.option_service.get_option_chain(symbol)

            if not option_chain or "data" not in option_chain:
                return {
                    "is_liquid": False,
                    "reason": "No option chain data available",
                    "ce_liquidity": 0,
                    "pe_liquidity": 0,
                }

            current_price = option_chain.get("underlyingValue", 0)
            atm_strike = self._find_atm_strike(current_price, option_chain)

            # Check ATM and nearby strikes liquidity
            liquid_ce_count = 0
            liquid_pe_count = 0
            total_ce_oi = 0
            total_pe_oi = 0

            for strike_data in option_chain.get("data", []):
                strike_price = float(strike_data.get("strikePrice", 0))

                # Check strikes within ±10% of ATM
                if abs(strike_price - atm_strike) / atm_strike <= 0.10:
                    # Call option (CE) liquidity
                    ce_data = strike_data.get("CE", {})
                    ce_oi = ce_data.get("openInterest", 0)
                    ce_volume = ce_data.get("totalTradedVolume", 0)
                    ce_bid_ask_spread = abs(
                        ce_data.get("askPrice", 0) - ce_data.get("bidPrice", 0)
                    )

                    if (
                        ce_oi >= self.fno_selection_config["option_liquidity"]["min_oi"]
                        and ce_bid_ask_spread
                        <= self.fno_selection_config["option_liquidity"][
                            "bid_ask_spread"
                        ]
                    ):
                        liquid_ce_count += 1
                        total_ce_oi += ce_oi

                    # Put option (PE) liquidity
                    pe_data = strike_data.get("PE", {})
                    pe_oi = pe_data.get("openInterest", 0)
                    pe_volume = pe_data.get("totalTradedVolume", 0)
                    pe_bid_ask_spread = abs(
                        pe_data.get("askPrice", 0) - pe_data.get("bidPrice", 0)
                    )

                    if (
                        pe_oi >= self.fno_selection_config["option_liquidity"]["min_oi"]
                        and pe_bid_ask_spread
                        <= self.fno_selection_config["option_liquidity"][
                            "bid_ask_spread"
                        ]
                    ):
                        liquid_pe_count += 1
                        total_pe_oi += pe_oi

            # Determine if stock has sufficient option liquidity
            is_liquid = (
                liquid_ce_count >= 3
                and liquid_pe_count >= 3
                and total_ce_oi >= 50000
                and total_pe_oi >= 50000
            )

            return {
                "is_liquid": is_liquid,
                "liquid_ce_strikes": liquid_ce_count,
                "liquid_pe_strikes": liquid_pe_count,
                "total_ce_oi": total_ce_oi,
                "total_pe_oi": total_pe_oi,
                "atm_strike": atm_strike,
                "reason": (
                    "Sufficient liquidity"
                    if is_liquid
                    else "Insufficient option liquidity"
                ),
            }

        except Exception as e:
            logger.error(f"❌ Failed to validate option liquidity for {symbol}: {e}")
            return {
                "is_liquid": False,
                "reason": f"Validation error: {str(e)}",
                "ce_liquidity": 0,
                "pe_liquidity": 0,
            }

    async def fibonacci_friendly_stocks_filter(
        self, stocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter stocks that are friendly to Fibonacci strategy (clear swings, EMA respect)

        Args:
            stocks: List of stock data

        Returns:
            Filtered list of Fibonacci-friendly stocks
        """
        try:
            fibonacci_friendly = []

            for stock in stocks:
                try:
                    symbol = stock["symbol"]

                    # Get historical data for analysis
                    historical_data = await self._get_historical_data_for_analysis(
                        symbol, days=60
                    )

                    if not historical_data or len(historical_data) < 30:
                        logger.debug(f"⚠️ Insufficient data for {symbol}")
                        continue

                    # Calculate Fibonacci-friendly metrics
                    swing_clarity = await self._calculate_swing_clarity(
                        symbol, historical_data
                    )
                    ema_respect = await self._check_ema_alignment(
                        symbol, historical_data
                    )
                    fib_level_respect = await self._historical_fibonacci_respect(
                        symbol, historical_data
                    )

                    # Apply minimum thresholds
                    config = self.fno_selection_config["fibonacci_criteria"]

                    if (
                        swing_clarity >= config["min_swing_clarity"]
                        and ema_respect >= config["min_ema_alignment"]
                        and fib_level_respect >= config["min_fib_respect"]
                    ):

                        # Add Fibonacci metrics to stock data
                        enhanced_stock = stock.copy()
                        enhanced_stock.update(
                            {
                                "fibonacci_metrics": {
                                    "swing_clarity": swing_clarity,
                                    "ema_respect": ema_respect,
                                    "fib_level_respect": fib_level_respect,
                                    "fibonacci_score": (
                                        swing_clarity + ema_respect + fib_level_respect
                                    )
                                    / 3,
                                }
                            }
                        )

                        fibonacci_friendly.append(enhanced_stock)
                        logger.debug(
                            f"✅ {symbol} is Fibonacci-friendly: "
                            f"Swing={swing_clarity:.2f}, EMA={ema_respect:.2f}, Fib={fib_level_respect:.2f}"
                        )
                    else:
                        logger.debug(
                            f"❌ {symbol} filtered out: "
                            f"Swing={swing_clarity:.2f}, EMA={ema_respect:.2f}, Fib={fib_level_respect:.2f}"
                        )

                except Exception as e:
                    logger.warning(
                        f"⚠️ Error filtering {stock.get('symbol', 'Unknown')}: {e}"
                    )

            logger.info(
                f"✅ Fibonacci filtering: {len(fibonacci_friendly)}/{len(stocks)} stocks passed"
            )
            return fibonacci_friendly

        except Exception as e:
            logger.error(f"❌ Failed to filter Fibonacci-friendly stocks: {e}")
            return []

    async def stock_correlation_analysis(
        self, selected_stocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analyze correlation between selected stocks to avoid highly correlated positions

        Args:
            selected_stocks: List of selected stock data

        Returns:
            Filtered list with correlation analysis
        """
        try:
            if len(selected_stocks) <= 1:
                return selected_stocks

            # Calculate correlation matrix
            correlation_matrix = {}

            for i, stock1 in enumerate(selected_stocks):
                for j, stock2 in enumerate(selected_stocks):
                    if i < j:  # Avoid duplicate pairs
                        symbol1 = stock1["symbol"]
                        symbol2 = stock2["symbol"]

                        # Calculate correlation between stocks
                        correlation = await self._calculate_stock_correlation(
                            symbol1, symbol2
                        )

                        key = f"{symbol1}_{symbol2}"
                        correlation_matrix[key] = {
                            "stock1": symbol1,
                            "stock2": symbol2,
                            "correlation": correlation,
                            "sector1": stock1.get("sector", ""),
                            "sector2": stock2.get("sector", ""),
                        }

            # Filter out highly correlated stocks (correlation > 0.7)
            filtered_stocks = []
            excluded_stocks = set()

            for stock in selected_stocks:
                symbol = stock["symbol"]

                if symbol in excluded_stocks:
                    continue

                # Check correlation with already selected stocks
                is_correlated = False
                for selected_stock in filtered_stocks:
                    selected_symbol = selected_stock["symbol"]

                    # Find correlation between current and selected stock
                    key1 = f"{symbol}_{selected_symbol}"
                    key2 = f"{selected_symbol}_{symbol}"

                    correlation_data = correlation_matrix.get(
                        key1
                    ) or correlation_matrix.get(key2)

                    if correlation_data and correlation_data["correlation"] > 0.7:
                        is_correlated = True
                        logger.info(
                            f"⚠️ {symbol} highly correlated with {selected_symbol} "
                            f"({correlation_data['correlation']:.2f}), excluding"
                        )
                        break

                if not is_correlated:
                    # Add correlation analysis to stock data
                    enhanced_stock = stock.copy()
                    enhanced_stock["correlation_analysis"] = {
                        "max_correlation": max(
                            [
                                data["correlation"]
                                for data in correlation_matrix.values()
                                if data["stock1"] == symbol or data["stock2"] == symbol
                            ],
                            default=0.0,
                        ),
                        "is_independent": True,
                    }
                    filtered_stocks.append(enhanced_stock)
                else:
                    excluded_stocks.add(symbol)

            logger.info(
                f"✅ Correlation analysis: {len(filtered_stocks)}/{len(selected_stocks)} stocks remain"
            )
            return filtered_stocks

        except Exception as e:
            logger.error(f"❌ Stock correlation analysis failed: {e}")
            return selected_stocks  # Return original list if analysis fails

    # Supporting methods for F&O selection

    async def _validate_fno_availability(self, symbol: str) -> bool:
        """Check if symbol has F&O availability"""
        try:
            # Try to get option chain data
            option_data = await self.option_service.get_option_chain(symbol)
            return bool(option_data and "data" in option_data)
        except:
            return False

    async def _calculate_swing_clarity(
        self, symbol: str, historical_data: Optional[pd.DataFrame] = None
    ) -> float:
        """Calculate swing clarity score (0-1) based on clear highs and lows"""
        try:
            if historical_data is None:
                historical_data = await self._get_historical_data_for_analysis(
                    symbol, days=30
                )

            if historical_data is None or len(historical_data) < 10:
                return 0.0

            highs = historical_data["high"].values
            lows = historical_data["low"].values
            closes = historical_data["close"].values

            # Calculate swing points using simple peak/trough detection
            swing_highs = []
            swing_lows = []

            for i in range(1, len(highs) - 1):
                # Swing high: higher than both neighbors
                if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                    swing_highs.append(highs[i])

                # Swing low: lower than both neighbors
                if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                    swing_lows.append(lows[i])

            # Calculate clarity score based on swing frequency and amplitude
            if len(swing_highs) < 2 or len(swing_lows) < 2:
                return 0.2

            # Score based on swing amplitude (higher amplitude = clearer swings)
            price_range = max(highs) - min(lows)
            avg_swing_range = np.mean([max(swing_highs) - min(swing_lows)])

            amplitude_score = (
                min(avg_swing_range / price_range, 1.0) if price_range > 0 else 0
            )

            # Score based on swing frequency (moderate frequency is good)
            swing_frequency = (len(swing_highs) + len(swing_lows)) / len(
                historical_data
            )
            frequency_score = 1 - abs(swing_frequency - 0.2) / 0.2  # Optimal around 20%
            frequency_score = max(0, frequency_score)

            clarity_score = (amplitude_score * 0.6) + (frequency_score * 0.4)
            return min(max(clarity_score, 0), 1)

        except Exception as e:
            logger.debug(f"Swing clarity calculation failed for {symbol}: {e}")
            return 0.5

    async def _check_ema_alignment(
        self, symbol: str, historical_data: Optional[pd.DataFrame] = None
    ) -> float:
        """Check EMA alignment strength (0-1)"""
        try:
            if historical_data is None:
                historical_data = await self._get_historical_data_for_analysis(
                    symbol, days=50
                )

            if historical_data is None or len(historical_data) < 50:
                return 0.0

            closes = historical_data["close"]

            # Calculate EMAs
            ema_9 = closes.ewm(span=9).mean()
            ema_21 = closes.ewm(span=21).mean()
            ema_50 = closes.ewm(span=50).mean()

            # Get recent values
            recent_close = closes.iloc[-1]
            recent_ema9 = ema_9.iloc[-1]
            recent_ema21 = ema_21.iloc[-1]
            recent_ema50 = ema_50.iloc[-1]

            # Calculate alignment score
            alignment_score = 0.0

            # Perfect bullish alignment: Price > EMA9 > EMA21 > EMA50
            if recent_close > recent_ema9 > recent_ema21 > recent_ema50:
                alignment_score = 1.0
            # Perfect bearish alignment: Price < EMA9 < EMA21 < EMA50
            elif recent_close < recent_ema9 < recent_ema21 < recent_ema50:
                alignment_score = 1.0
            # Partial alignment
            elif recent_close > recent_ema21:
                alignment_score = 0.7
            elif recent_close < recent_ema21:
                alignment_score = 0.7
            else:
                alignment_score = 0.3

            return alignment_score

        except Exception as e:
            logger.debug(f"EMA alignment check failed for {symbol}: {e}")
            return 0.5

    async def _historical_fibonacci_respect(
        self, symbol: str, historical_data: Optional[pd.DataFrame] = None
    ) -> float:
        """Calculate how well stock historically respects Fibonacci levels"""
        try:
            if historical_data is None:
                historical_data = await self._get_historical_data_for_analysis(
                    symbol, days=60
                )

            if historical_data is None or len(historical_data) < 30:
                return 0.0

            # Simplified Fibonacci respect calculation
            # In a real implementation, this would analyze multiple swing cycles
            highs = historical_data["high"].values
            lows = historical_data["low"].values
            closes = historical_data["close"].values

            # Find major swing high and low
            swing_high = np.max(highs)
            swing_low = np.min(lows)

            if swing_high == swing_low:
                return 0.0

            # Calculate Fibonacci levels
            diff = swing_high - swing_low
            fib_levels = {
                "fib_23_6": swing_high - (diff * 0.236),
                "fib_38_2": swing_high - (diff * 0.382),
                "fib_50_0": swing_high - (diff * 0.500),
                "fib_61_8": swing_high - (diff * 0.618),
                "fib_78_6": swing_high - (diff * 0.786),
            }

            # Count price reactions near Fibonacci levels
            respect_count = 0
            total_checks = 0

            for i, close in enumerate(closes):
                for fib_level in fib_levels.values():
                    # Check if price came within 1% of Fibonacci level
                    if abs(close - fib_level) / fib_level < 0.01:
                        # Check if price bounced (simplified check)
                        if i > 0 and i < len(closes) - 1:
                            prev_close = closes[i - 1]
                            next_close = closes[i + 1]

                            # Simple bounce detection
                            if (prev_close > close < next_close) or (
                                prev_close < close > next_close
                            ):
                                respect_count += 1
                        total_checks += 1

            respect_score = respect_count / total_checks if total_checks > 0 else 0.5
            return min(max(respect_score, 0), 1)

        except Exception as e:
            logger.debug(f"Fibonacci respect calculation failed for {symbol}: {e}")
            return 0.5

    async def _calculate_option_liquidity_score(self, symbol: str) -> float:
        """Calculate option liquidity score (0-1)"""
        try:
            liquidity_data = await self.validate_option_liquidity(symbol)

            if not liquidity_data["is_liquid"]:
                return 0.0

            # Score based on number of liquid strikes and OI
            ce_strikes = liquidity_data.get("liquid_ce_strikes", 0)
            pe_strikes = liquidity_data.get("liquid_pe_strikes", 0)
            total_oi = liquidity_data.get("total_ce_oi", 0) + liquidity_data.get(
                "total_pe_oi", 0
            )

            # Normalize scores
            strikes_score = min((ce_strikes + pe_strikes) / 10, 1.0)  # Max 10 strikes
            oi_score = min(total_oi / 1000000, 1.0)  # Max 10L OI

            return (strikes_score * 0.6) + (oi_score * 0.4)

        except Exception as e:
            logger.debug(f"Option liquidity score calculation failed for {symbol}: {e}")
            return 0.5

    async def _get_index_correlation(
        self, symbol: str, index_memberships: List[str]
    ) -> float:
        """Get correlation score with indices"""
        try:
            if not index_memberships:
                return 0.3

            # Higher score for membership in multiple indices
            membership_score = min(len(index_memberships) / 3, 1.0)

            # Priority scoring for different indices
            index_priority = {
                "NIFTY": 1.0,
                "BANKNIFTY": 0.9,
                "FINNIFTY": 0.8,
                "MIDCPNIFTY": 0.7,
                "SENSEX": 0.8,
            }

            priority_score = max(
                [index_priority.get(idx, 0.5) for idx in index_memberships]
            )

            return (membership_score * 0.4) + (priority_score * 0.6)

        except Exception as e:
            logger.debug(f"Index correlation calculation failed for {symbol}: {e}")
            return 0.5

    async def _get_sector_momentum_score(self, sector: str) -> float:
        """Get sector momentum score"""
        try:
            # Use existing sector analysis
            sector_data = self.analytics.get_sector_performance()

            for sector_info in sector_data:
                if sector_info.get("name", "").upper() == sector.upper():
                    change_percent = sector_info.get("change_percent", 0)
                    # Convert percentage change to 0-1 score
                    return min(
                        max((change_percent + 10) / 20, 0), 1
                    )  # -10% to +10% mapped to 0-1

            return 0.5  # Default if sector not found

        except Exception as e:
            logger.debug(f"Sector momentum calculation failed for {sector}: {e}")
            return 0.5

    async def _get_historical_data_for_analysis(
        self, symbol: str, days: int = 30
    ) -> Optional[pd.DataFrame]:
        """Get historical data for technical analysis"""
        try:
            # Try to get from live adapter first
            if hasattr(self.live_adapter, "get_1m_df"):
                df = self.live_adapter.get_1m_df(
                    symbol, window_minutes=days * 390
                )  # Trading minutes per day
                if not df.empty:
                    return df

            # Fallback to high-speed market data service
            if hasattr(high_speed_market_data, "get_historical_data"):
                return high_speed_market_data.get_historical_data(symbol, days=days)

            # Return None if no data source available
            return None

        except Exception as e:
            logger.debug(f"Historical data fetch failed for {symbol}: {e}")
            return None

    async def _calculate_stock_correlation(
        self, symbol1: str, symbol2: str, days: int = 30
    ) -> float:
        """Calculate correlation between two stocks"""
        try:
            # Get historical data for both stocks
            data1 = await self._get_historical_data_for_analysis(symbol1, days)
            data2 = await self._get_historical_data_for_analysis(symbol2, days)

            if data1 is None or data2 is None or len(data1) < 10 or len(data2) < 10:
                return 0.0

            # Align data by timestamp and calculate correlation
            merged_data = pd.merge(
                data1[["timestamp", "close"]],
                data2[["timestamp", "close"]],
                on="timestamp",
                suffixes=("_1", "_2"),
            )

            if len(merged_data) < 10:
                return 0.0

            correlation = merged_data["close_1"].corr(merged_data["close_2"])
            return abs(correlation) if not pd.isna(correlation) else 0.0

        except Exception as e:
            logger.debug(f"Correlation calculation failed for {symbol1}-{symbol2}: {e}")
            return 0.0

    def _find_atm_strike(self, current_price: float, option_chain: Dict) -> float:
        """Find ATM (At-The-Money) strike price"""
        try:
            strikes = []
            for strike_data in option_chain.get("data", []):
                strike_price = float(strike_data.get("strikePrice", 0))
                if strike_price > 0:
                    strikes.append(strike_price)

            if not strikes:
                return current_price

            # Find closest strike to current price
            closest_strike = min(strikes, key=lambda x: abs(x - current_price))
            return closest_strike

        except Exception:
            return current_price


# Global service instance
auto_stock_selection_service = AutoStockSelectionService()


async def start_auto_stock_selection():
    """Start the auto stock selection service"""
    logger.info("🚀 Starting Auto Stock Selection Service...")
    return auto_stock_selection_service


def get_selected_fo_instruments() -> List[Dict[str, Any]]:
    """Get selected F&O instruments for live feed subscription from actual data sources"""
    try:
        # Get F&O stocks from JSON file
        import json
        from pathlib import Path

        fno_file = Path("data/fno_stock_list.json")
        if not fno_file.exists():
            logger.error(f"❌ F&O instruments file not found: {fno_file}")
            return []

        with open(fno_file, "r") as f:
            fno_data = json.load(f)

        instruments = []
        securities = fno_data.get("securities", [])

        if not securities:
            logger.error("❌ No securities found in F&O data file")
            return []

        # Convert to instrument format with keys
        for security in securities:  # Use all securities, no artificial limit
            symbol = security.get("symbol", "")
            if symbol and symbol not in [
                "NIFTY",
                "BANKNIFTY",
                "FINNIFTY",
                "MIDCPNIFTY",
                "SENSEX",
            ]:  # Skip indices
                # Try to get actual instrument key from instrument registry or data
                instrument_key = _get_actual_instrument_key_sync(
                    symbol, security.get("exchange", "NSE")
                )

                if instrument_key:
                    instruments.append(
                        {
                            "symbol": symbol,
                            "instrument_key": instrument_key,
                            "exchange": security.get("exchange", "NSE"),
                            "name": security.get("name", symbol),
                            "type": "equity",
                        }
                    )

        if not instruments:
            logger.error("❌ No valid F&O instruments found")
            return []

        logger.info(f"✅ Loaded {len(instruments)} F&O instruments for live feed")
        return instruments

    except Exception as e:
        logger.error(f"❌ Error loading F&O instruments: {e}")
        return []


async def _get_actual_instrument_key(
    symbol: str, exchange: str = "NSE"
) -> Optional[str]:
    """Get actual instrument key from instrument registry or data files"""
    try:
        # Try to get from instrument registry first
        try:
            from services.instrument_registry import instrument_registry

            if instrument_registry and hasattr(instrument_registry, "_symbols_map"):
                symbol_data = instrument_registry._symbols_map.get(symbol)
                if symbol_data and symbol_data.get("spot"):
                    # Return the first spot instrument key
                    return (
                        symbol_data["spot"][0]
                        if isinstance(symbol_data["spot"], list)
                        else symbol_data["spot"]
                    )
        except ImportError:
            pass

        # Try to get from upstox instruments file
        import json
        from pathlib import Path

        upstox_file = Path("data/upstox_instruments.json")
        if upstox_file.exists():
            with open(upstox_file, "r") as f:
                instruments_data = json.load(f)

            for instrument in instruments_data:
                if (
                    instrument.get("trading_symbol") == symbol
                    and instrument.get("exchange") == exchange
                    and instrument.get("instrument_type") == "EQ"
                ):
                    return instrument.get("instrument_key")

        # Try to get from filtered instruments file
        filtered_file = Path("data/filtered_instruments.json")
        if filtered_file.exists():
            with open(filtered_file, "r") as f:
                filtered_data = json.load(f)

            for instrument in filtered_data:
                if (
                    instrument.get("tradingsymbol") == symbol
                    and instrument.get("exchange") == exchange
                ):
                    return instrument.get("instrument_token") or instrument.get(
                        "instrument_key"
                    )

        return None

    except Exception as e:
        logger.error(f"❌ Error getting instrument key for {symbol}: {e}")
        return None


def _get_actual_instrument_key_sync(
    symbol: str, exchange: str = "NSE"
) -> Optional[str]:
    """Synchronous version: Get actual instrument key from instrument registry or data files"""
    try:
        # Try to get from instrument registry first
        try:
            from services.instrument_registry import instrument_registry

            if instrument_registry and hasattr(instrument_registry, "_symbols_map"):
                symbol_data = instrument_registry._symbols_map.get(symbol)
                if symbol_data and symbol_data.get("spot"):
                    # Return the first spot instrument key
                    return (
                        symbol_data["spot"][0]
                        if isinstance(symbol_data["spot"], list)
                        else symbol_data["spot"]
                    )
        except ImportError:
            pass

        # Try to get from upstox instruments file
        import json
        from pathlib import Path

        upstox_file = Path("data/upstox_instruments.json")
        if upstox_file.exists():
            with open(upstox_file, "r") as f:
                instruments_data = json.load(f)

            for instrument in instruments_data:
                if (
                    instrument.get("trading_symbol") == symbol
                    and instrument.get("exchange") == exchange
                    and instrument.get("instrument_type") == "EQ"
                ):
                    return instrument.get("instrument_key")

        # Try to get from filtered instruments file
        filtered_file = Path("data/filtered_instruments.json")
        if filtered_file.exists():
            with open(filtered_file, "r") as f:
                filtered_data = json.load(f)

            for instrument in filtered_data:
                if (
                    instrument.get("tradingsymbol") == symbol
                    and instrument.get("exchange") == exchange
                ):
                    return instrument.get("instrument_token") or instrument.get(
                        "instrument_key"
                    )

        return None

    except Exception as e:
        logger.error(f"❌ Error getting instrument key for {symbol}: {e}")
        return None


async def get_premarket_watchlist_instruments() -> List[str]:
    """Get instrument keys for premarket gap analysis from actual data sources"""
    try:
        # Get all F&O instruments first
        fo_instruments = await get_selected_fo_instruments_async()

        if not fo_instruments:
            logger.error("❌ No F&O instruments available for premarket watchlist")
            return []

        # Get liquid stocks based on actual market cap/volume data
        liquid_instruments = await _filter_liquid_stocks(fo_instruments)

        if not liquid_instruments:
            logger.error("❌ No liquid stocks found for premarket monitoring")
            return []

        # Return instrument keys for liquid stocks
        watchlist_keys = [
            instrument["instrument_key"] for instrument in liquid_instruments
        ]

        logger.info(
            f"✅ Selected {len(watchlist_keys)} liquid stocks for premarket gap analysis"
        )
        return watchlist_keys

    except Exception as e:
        logger.error(f"❌ Error getting premarket watchlist: {e}")
        return []


async def _filter_liquid_stocks(
    instruments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter instruments to get most liquid stocks for premarket analysis"""
    try:
        # Try to get market cap/volume data from analytics service
        try:
            from services.enhanced_market_analytics import enhanced_analytics

            if enhanced_analytics:
                # Get market data for filtering
                liquid_instruments = []
                for instrument in instruments:
                    try:
                        # Get market data for this symbol
                        market_data = await enhanced_analytics.get_stock_data(
                            instrument["symbol"]
                        )

                        # Filter based on actual liquidity criteria
                        if (
                            market_data
                            and market_data.get("market_cap", 0)
                            > 10000  # Market cap > 10k cr
                            and market_data.get("avg_volume", 0) > 100000
                        ):  # Avg volume > 1L
                            liquid_instruments.append(instrument)

                    except Exception:
                        continue  # Skip instruments with no data

                if liquid_instruments:
                    # Sort by market cap and return top liquid stocks
                    liquid_instruments.sort(
                        key=lambda x: enhanced_analytics.get_stock_data(
                            x["symbol"]
                        ).get("market_cap", 0),
                        reverse=True,
                    )
                    return liquid_instruments[:50]  # Top 50 liquid stocks

        except ImportError:
            pass

        # Fallback: Try to get from top_stocks.json if available
        import json
        from pathlib import Path

        top_stocks_file = Path("data/top_stocks.json")
        if top_stocks_file.exists():
            with open(top_stocks_file, "r") as f:
                top_stocks_data = json.load(f)

            top_symbols = [
                stock.get("symbol") for stock in top_stocks_data if stock.get("symbol")
            ]

            # Filter F&O instruments to match top stocks
            liquid_instruments = []
            for instrument in instruments:
                if instrument["symbol"] in top_symbols:
                    liquid_instruments.append(instrument)

            if liquid_instruments:
                return liquid_instruments[:50]  # Top 50 from the list

        # If no data available, return empty (no hardcoded fallback)
        logger.warning("⚠️ No market data available for liquidity filtering")
        return []

    except Exception as e:
        logger.error(f"❌ Error filtering liquid stocks: {e}")
        return []


async def get_selected_fo_instruments_async() -> List[Dict[str, Any]]:
    """Async wrapper for get_selected_fo_instruments"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_selected_fo_instruments)


async def get_index_instruments() -> List[Dict[str, Any]]:
    """Get index instrument data from actual data sources"""
    try:
        import json
        from pathlib import Path

        # Get indices from F&O data file
        fno_file = Path("data/fno_stock_list.json")
        if not fno_file.exists():
            logger.error(f"❌ F&O data file not found: {fno_file}")
            return []

        with open(fno_file, "r") as f:
            fno_data = json.load(f)

        indices = []
        securities = fno_data.get("securities", [])

        # Filter for indices only
        for security in securities:
            symbol = security.get("symbol", "")
            if symbol and symbol in [
                "NIFTY",
                "BANKNIFTY",
                "FINNIFTY",
                "MIDCPNIFTY",
                "SENSEX",
            ]:
                # Try to get actual instrument key from data sources
                instrument_key = await _get_actual_index_instrument_key(
                    symbol, security.get("exchange", "NSE")
                )

                if instrument_key:
                    indices.append(
                        {
                            "symbol": symbol,
                            "instrument_key": instrument_key,
                            "exchange": security.get("exchange", "NSE"),
                            "name": security.get("name", symbol),
                            "type": "index",
                        }
                    )

        if not indices:
            logger.error("❌ No valid index instruments found")
            return []

        logger.info(f"✅ Loaded {len(indices)} index instruments")
        return indices

    except Exception as e:
        logger.error(f"❌ Error loading index instruments: {e}")
        return []


async def _get_actual_index_instrument_key(
    symbol: str, exchange: str = "NSE"
) -> Optional[str]:
    """Get actual index instrument key from data sources"""
    try:
        # Try to get from instrument registry first
        try:
            from services.instrument_registry import instrument_registry

            if instrument_registry and hasattr(instrument_registry, "_symbols_map"):
                symbol_data = instrument_registry._symbols_map.get(symbol)
                if symbol_data and symbol_data.get("index"):
                    return (
                        symbol_data["index"][0]
                        if isinstance(symbol_data["index"], list)
                        else symbol_data["index"]
                    )
        except ImportError:
            pass

        # Try to get from upstox instruments file
        import json
        from pathlib import Path

        upstox_file = Path("data/upstox_instruments.json")
        if upstox_file.exists():
            with open(upstox_file, "r") as f:
                instruments_data = json.load(f)

            for instrument in instruments_data:
                if (
                    instrument.get("trading_symbol") == symbol
                    and instrument.get("exchange") == exchange
                    and instrument.get("instrument_type") in ["INDEX", "IDX"]
                ):
                    return instrument.get("instrument_key")

        # Try to get from filtered instruments file
        filtered_file = Path("data/filtered_instruments.json")
        if filtered_file.exists():
            with open(filtered_file, "r") as f:
                filtered_data = json.load(f)

            for instrument in filtered_data:
                if (
                    instrument.get("tradingsymbol") == symbol
                    and instrument.get("exchange") == exchange
                    and "INDEX" in str(instrument.get("instrument_type", "").upper())
                ):
                    return instrument.get("instrument_token") or instrument.get(
                        "instrument_key"
                    )

        return None

    except Exception as e:
        logger.error(f"❌ Error getting index instrument key for {symbol}: {e}")
        return None
