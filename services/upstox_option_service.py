# services/upstox_option_service.py
"""
Upstox Option Chain Service - Clean API Integration
Handles option contracts and option chain data using Upstox APIs
Optimized for F&O-only application with pandas data processing
"""

import logging
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from database.models import BrokerConfig, User

logger = logging.getLogger(__name__)

UPSTOX_BASE_URL = "https://api.upstox.com/v2"


class UpstoxOptionService:
    """Clean, optimized Upstox option service for F&O-only application"""

    def __init__(self):
        self.base_url = UPSTOX_BASE_URL
        self.cache: Dict[str, Any] = {}
        self.cache_timeout = 300  # 5 minutes
        self.last_error = None
        self.api_calls_count = 0

    def get_status(self) -> Dict[str, Any]:
        """Get service status for system health monitoring"""
        return {
            "status": "healthy" if not self.last_error else "error",
            "api_calls": self.api_calls_count,
            "cache_size": len(self.cache),
            "last_error": self.last_error,
            "timestamp": datetime.now().isoformat()
        }

    def _get_admin_token(self, db: Session) -> Optional[str]:
        """Get admin Upstox token for API calls"""
        try:
            admin_config = (
                db.query(BrokerConfig)
                .join(User)
                .filter(
                    User.role == "admin",
                    BrokerConfig.broker_name.ilike("upstox"),
                    BrokerConfig.is_active == True,
                    BrokerConfig.access_token.isnot(None),
                )
                .first()
            )

            if admin_config and admin_config.access_token:
                if (
                    admin_config.access_token_expiry
                    and admin_config.access_token_expiry > datetime.now()
                ):
                    return admin_config.access_token

            logger.warning("No valid admin Upstox token found")
            return None

        except Exception as e:
            logger.error(f"Error getting admin token: {e}")
            return None

    def _make_upstox_request(
        self, endpoint: str, params: Dict = None, db: Session = None
    ) -> Optional[Any]:
        """Make authenticated request to Upstox API with retry logic and return `data` on success"""
        self.api_calls_count += 1
        
        # Retry configuration
        max_retries = 3
        retry_delay = 1  # starting delay in seconds
        
        for attempt in range(max_retries + 1):
            try:
                token = self._get_admin_token(db)
                if not token:
                    error_msg = "No valid Upstox token available"
                    self.last_error = error_msg
                    logger.error(error_msg)
                    return None

                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }

                url = f"{self.base_url}{endpoint}"
                logger.info(f"Upstox API call (attempt {attempt+1}): {endpoint} params={params!r}")

                response = requests.get(url, headers=headers, params=params, timeout=15)

                if response.status_code == 200:
                    payload = response.json()
                    if payload.get("status") == "success":
                        self.last_error = None
                        return payload.get("data", {})
                    else:
                        error_msg = f"Upstox API error payload: {payload}"
                        self.last_error = error_msg
                        logger.error(error_msg)
                        return None
                elif response.status_code == 401:
                    error_msg = "Upstox token expired or invalid (401)"
                    self.last_error = error_msg
                    logger.error(error_msg)
                    return None
                elif response.status_code in [500, 502, 503, 504]:
                    # Server errors - potential candidates for retry
                    if attempt < max_retries:
                        import time
                        logger.warning(f"Upstox server error {response.status_code}. Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    
                    error_msg = f"Upstox API server error {response.status_code}: {response.text}"
                    self.last_error = error_msg
                    logger.error(error_msg)
                    return None
                else:
                    error_msg = f"Upstox API error {response.status_code}: {response.text}"
                    self.last_error = error_msg
                    logger.error(error_msg)
                    return None

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # Connection errors (including NameResolutionError) and timeouts are retried
                if attempt < max_retries:
                    import time
                    logger.warning(f"Network error on attempt {attempt+1}: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                
                self.last_error = str(e)
                logger.error(f"Error making Upstox request after {max_retries+1} attempts: {e}")
                return None
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Unexpected error making Upstox request: {e}")
                return None
        
        return None

    def get_fast_option_selection_data(
        self, instrument_key: str, db: Session
    ) -> Optional[Dict[str, Any]]:
        """
        Optimized fetch of expiries and lot size for an underlying.
        Returns: {"expiries": List[str], "lot_size": int, "nearest_expiry": str, "chain": Dict}
        """
        try:
            contracts = self.get_option_contracts(instrument_key, db)
            if not contracts:
                return None

            # Extract unique expiries and sort them
            expiries = sorted(list(set(c.get("expiry") for c in contracts if c.get("expiry"))))
            if not expiries:
                return None
                
            nearest_expiry = expiries[0]
            
            # Get chain for nearest expiry
            chain = self.get_option_chain(instrument_key, nearest_expiry, db)

            # Extract lot size from the first contract
            lot_size = contracts[0].get("lot_size") or contracts[0].get("minimum_lot", 0)

            return {
                "expiries": expiries,
                "lot_size": int(lot_size),
                "nearest_expiry": nearest_expiry,
                "chain": chain
            }
        except Exception as e:
            logger.error(f"Error in get_fast_option_selection_data: {e}")
            return None

    def get_option_contracts(
        self, instrument_key: str, db: Session, expiry_date: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get option contracts - EXACT Upstox API implementation
        Returns the raw Upstox items (pass-through) so fields like exchange_token,
        underlying_type, minimum_lot, freeze_quantity, weekly are preserved.
        """
        try:
            cache_key = f"contracts_{instrument_key}_{expiry_date or 'all'}"

            # Check cache
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if datetime.now() - timestamp < timedelta(seconds=self.cache_timeout):
                    return cached_data

            # API call exactly as per documentation
            endpoint = "/option/contract"
            params = {"instrument_key": instrument_key}
            if expiry_date:
                params["expiry_date"] = expiry_date

            logger.info(f"Fetching option contracts for {instrument_key}")
            response_data = self._make_upstox_request(endpoint, params, db)

            if response_data is None:
                return None

            # Cache and return EXACT Upstox data list
            self.cache[cache_key] = (response_data, datetime.now())
            logger.info(f"Retrieved {len(response_data)} option contracts")
            return response_data

        except Exception as e:
            logger.error(f"Error getting option contracts: {e}")
            return None

    def get_option_chain(
        self, instrument_key: str, expiry_date: str, db: Session,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get option chain - EXACT Upstox API implementation with pandas optimization.
        Returns:
          {
            "status": "success",
            "data": [ ... Upstox items with call_options/put_options ... ],
            # plus helpful extras:
            "underlying_key": ...,
            "expiry": ...,
            "spot_price": ...,
            "atm_strike": ...,
            "total_strikes": ...,
            "analytics": {...}
          }

        Args:
            force_refresh: If True, bypass the 60-second cache and fetch fresh data.
                           Use for intraday ATM strike refresh when market has moved.
        """
        try:
            cache_key = f"chain_{instrument_key}_{expiry_date}"

            # Check cache (1 minute for live data) — skipped when force_refresh=True
            if not force_refresh and cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if datetime.now() - timestamp < timedelta(seconds=60):
                    return cached_data

            # API call exactly as per documentation
            endpoint = "/option/chain"
            params = {
                "instrument_key": instrument_key,
                "expiry_date": expiry_date,
            }

            logger.info(
                f"Fetching option chain for {instrument_key}, expiry: {expiry_date}"
            )
            response_data = self._make_upstox_request(endpoint, params, db)

            if not response_data:
                return None

            # Process with pandas for optional analytics (keeps raw `data` intact)
            chain_rows: List[Dict[str, Any]] = []
            for item in response_data:
                # CRITICAL: Robust strike price extraction
                strike_price = item.get("strike_price")
                if strike_price is None:
                    continue
                
                row = {
                    "expiry": item.get("expiry"),
                    "strike_price": float(strike_price),
                    "underlying_key": item.get("underlying_key"),
                    "underlying_spot_price": item.get("underlying_spot_price"),
                    "pcr": item.get("pcr"),
                }

                # Add call option data
                if "call_options" in item and item["call_options"]:
                    call_data = item["call_options"]
                    row.update(
                        {
                            "call_instrument_key": call_data.get("instrument_key"),
                            "call_ltp": call_data.get("market_data", {}).get("ltp", 0),
                            "call_volume": call_data.get("market_data", {}).get(
                                "volume", 0
                            ),
                            "call_oi": call_data.get("market_data", {}).get("oi", 0),
                            "call_bid_price": call_data.get("market_data", {}).get(
                                "bid_price", 0
                            ),
                            "call_ask_price": call_data.get("market_data", {}).get(
                                "ask_price", 0
                            ),
                            "call_delta": call_data.get("option_greeks", {}).get(
                                "delta", 0
                            ),
                            "call_gamma": call_data.get("option_greeks", {}).get(
                                "gamma", 0
                            ),
                            "call_theta": call_data.get("option_greeks", {}).get(
                                "theta", 0
                            ),
                            "call_vega": call_data.get("option_greeks", {}).get(
                                "vega", 0
                            ),
                            "call_iv": call_data.get("option_greeks", {}).get("iv", 0),
                        }
                    )

                # Add put option data
                if "put_options" in item and item["put_options"]:
                    put_data = item["put_options"]
                    row.update(
                        {
                            "put_instrument_key": put_data.get("instrument_key"),
                            "put_ltp": put_data.get("market_data", {}).get("ltp", 0),
                            "put_volume": put_data.get("market_data", {}).get(
                                "volume", 0
                            ),
                            "put_oi": put_data.get("market_data", {}).get("oi", 0),
                            "put_bid_price": put_data.get("market_data", {}).get(
                                "bid_price", 0
                            ),
                            "put_ask_price": put_data.get("market_data", {}).get(
                                "ask_price", 0
                            ),
                            "put_delta": put_data.get("option_greeks", {}).get(
                                "delta", 0
                            ),
                            "put_gamma": put_data.get("option_greeks", {}).get(
                                "gamma", 0
                            ),
                            "put_theta": put_data.get("option_greeks", {}).get(
                                "theta", 0
                            ),
                            "put_vega": put_data.get("option_greeks", {}).get(
                                "vega", 0
                            ),
                            "put_iv": put_data.get("option_greeks", {}).get("iv", 0),
                        }
                    )

                chain_rows.append(row)

            df = pd.DataFrame(chain_rows)

            if len(df) > 0:
                # Ensure numeric cols and safe math
                for col in ["call_oi", "put_oi", "call_iv", "put_iv", "strike_price"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                # Simple analytics
                if "call_oi" in df.columns and "put_oi" in df.columns:
                    df["call_put_ratio"] = df["call_oi"] / df["put_oi"].replace(
                        0, np.nan
                    )
                df["total_oi"] = df.get("call_oi", 0).fillna(0) + df.get(
                    "put_oi", 0
                ).fillna(0)
                df["net_oi"] = df.get("call_oi", 0).fillna(0) - df.get(
                    "put_oi", 0
                ).fillna(0)

                spot_price = (
                    float(df["underlying_spot_price"].iloc[0]) if "underlying_spot_price" in df.columns else 0.0
                )
                df["distance_from_spot"] = abs(df["strike_price"] - spot_price)
                atm_strike = float(
                    df.loc[df["distance_from_spot"].idxmin(), "strike_price"]
                )

                processed_data: Dict[str, Any] = {
                    "status": "success",
                    "underlying_key": instrument_key,
                    "expiry": expiry_date,
                    "spot_price": spot_price,
                    "atm_strike": atm_strike,
                    "total_strikes": int(len(df)),
                    "data": response_data,  # Original Upstox format for UI
                    "analytics": {
                        "total_call_oi": (
                            float(df.get("call_oi", 0).fillna(0).sum())
                            if "call_oi" in df.columns
                            else 0.0
                        ),
                        "total_put_oi": (
                            float(df.get("put_oi", 0).fillna(0).sum())
                            if "put_oi" in df.columns
                            else 0.0
                        ),
                        "pcr": (
                            float(df.get("put_oi", 0).fillna(0).sum())
                            / max(float(df.get("call_oi", 0).fillna(0).sum()), 1e-9)
                            if "call_oi" in df.columns and "put_oi" in df.columns
                            else 0.0
                        ),
                        "max_pain": self._calculate_max_pain(df),
                        "volatility_smile": self._calculate_volatility_smile(df),
                    },
                }
            else:
                # Fallback if no valid rows were processed
                spot_price = 0.0
                if response_data and len(response_data) > 0:
                    spot_price = float(response_data[0].get("underlying_spot_price", 0.0))

                processed_data = {
                    "status": "success",
                    "underlying_key": instrument_key,
                    "expiry": expiry_date,
                    "spot_price": spot_price,
                    "atm_strike": 0.0,
                    "total_strikes": 0,
                    "data": response_data,
                    "analytics": {},
                }

            # Cache results
            self.cache[cache_key] = (processed_data, datetime.now())

            logger.info(f"Retrieved option chain with {len(response_data)} strikes")
            return processed_data

        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            return None

    def get_atm_keys(
        self, instrument_key: str, expiry_date: str, db: Session,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get current ATM CE and PE keys with live premiums.

        Args:
            force_refresh: If True, bypasses the option-chain cache and fetches
                           fresh data from Upstox. Use at BUY-signal time to get
                           the true current ATM, not the 9 AM cached value.

        Returns:
            {
                "ce_key": str,
                "pe_key": str,
                "atm_strike": float,
                "lot_size": int,
                "ce_premium": float,   # live LTP of ATM CE (from chain data)
                "pe_premium": float,   # live LTP of ATM PE (from chain data)
                "spot_price": float,   # underlying spot price from Upstox
            }
        """
        try:
            chain_data = self.get_option_chain(
                instrument_key, expiry_date, db, force_refresh=force_refresh
            )
            if not chain_data or not chain_data.get("data"):
                return None

            atm_strike = chain_data.get("atm_strike")
            spot_price = chain_data.get("spot_price", 0.0)
            if not atm_strike:
                return None

            ce_key = None
            pe_key = None
            ce_premium = 0.0
            pe_premium = 0.0

            # Find the specific ATM strike in the chain data
            for item in chain_data["data"]:
                if float(item.get("strike_price", 0)) == atm_strike:
                    if "call_options" in item and item["call_options"]:
                        ce_key = item["call_options"].get("instrument_key")
                        # Live CE premium comes directly from the chain response
                        ce_premium = float(
                            item["call_options"].get("market_data", {}).get("ltp", 0) or 0
                        )
                    if "put_options" in item and item["put_options"]:
                        pe_key = item["put_options"].get("instrument_key")
                        # Live PE premium comes directly from the chain response
                        pe_premium = float(
                            item["put_options"].get("market_data", {}).get("ltp", 0) or 0
                        )
                    break

            # Fallback: floating-point miss — pick nearest strike
            if not ce_key or not pe_key:
                closest_item = min(
                    chain_data["data"],
                    key=lambda x: abs(float(x.get("strike_price", 0)) - atm_strike),
                )
                if "call_options" in closest_item and closest_item["call_options"]:
                    ce_key = closest_item["call_options"].get("instrument_key")
                    ce_premium = float(
                        closest_item["call_options"].get("market_data", {}).get("ltp", 0) or 0
                    )
                if "put_options" in closest_item and closest_item["put_options"]:
                    pe_key = closest_item["put_options"].get("instrument_key")
                    pe_premium = float(
                        closest_item["put_options"].get("market_data", {}).get("ltp", 0) or 0
                    )

            # Get lot size from contracts (contracts cache is 5 min — acceptable)
            contracts = self.get_option_contracts(instrument_key, db, expiry_date)
            lot_size = 0
            if contracts:
                lot_size = int(
                    contracts[0].get("lot_size") or contracts[0].get("minimum_lot", 0)
                )

            logger.info(
                f"ATM keys for {instrument_key}: strike={atm_strike}, "
                f"spot={spot_price:.2f}, CE={ce_key} @{ce_premium:.2f}, "
                f"PE={pe_key} @{pe_premium:.2f} (force_refresh={force_refresh})"
            )

            return {
                "ce_key": ce_key,
                "pe_key": pe_key,
                "atm_strike": atm_strike,
                "lot_size": lot_size,
                "ce_premium": ce_premium,
                "pe_premium": pe_premium,
                "spot_price": spot_price,
            }
        except Exception as e:
            logger.error(f"Error in get_atm_keys: {e}")
            return None

    def _calculate_max_pain(self, df: pd.DataFrame) -> float:
        """Calculate max pain point using pandas"""
        try:
            if len(df) == 0:
                return 0.0

            strikes = df["strike_price"].values
            max_pain_values: List[float] = []

            for strike in strikes:
                call_part = df[df["strike_price"] < strike]
                put_part = df[df["strike_price"] > strike]

                call_pain = float(call_part.get("call_oi", 0).fillna(0).sum()) * float(
                    (strike - call_part["strike_price"]).fillna(0).sum()
                )
                put_pain = float(put_part.get("put_oi", 0).fillna(0).sum()) * float(
                    (put_part["strike_price"] - strike).fillna(0).sum()
                )
                total_pain = call_pain + put_pain
                max_pain_values.append(total_pain)

            if max_pain_values:
                max_pain_index = int(np.argmin(max_pain_values))
                return float(strikes[max_pain_index])

            return 0.0

        except Exception as e:
            logger.error(f"Error calculating max pain: {e}")
            return 0.0

    def _calculate_volatility_smile(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate volatility smile using pandas"""
        try:
            if len(df) == 0:
                return {}

            # Calculate IV smile for calls and puts
            call_cols = [c for c in ["strike_price", "call_iv"] if c in df.columns]
            put_cols = [c for c in ["strike_price", "put_iv"] if c in df.columns]

            call_smile = (
                df[call_cols].dropna() if len(call_cols) == 2 else pd.DataFrame()
            )
            put_smile = df[put_cols].dropna() if len(put_cols) == 2 else pd.DataFrame()

            return {
                "call_iv_data": (
                    call_smile.to_dict("records") if not call_smile.empty else []
                ),
                "put_iv_data": (
                    put_smile.to_dict("records") if not put_smile.empty else []
                ),
                "avg_call_iv": (
                    float(call_smile["call_iv"].mean()) if not call_smile.empty else 0.0
                ),
                "avg_put_iv": (
                    float(put_smile["put_iv"].mean()) if not put_smile.empty else 0.0
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating volatility smile: {e}")
            return {}

    def get_futures_contracts(
        self, instrument_key: str, db: Session
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get futures contracts for symbol.
        NOTE: Placeholder – extend when Upstox futures API details are available.
        """
        try:
            cache_key = f"futures_{instrument_key}"

            # Check cache
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if datetime.now() - timestamp < timedelta(seconds=self.cache_timeout):
                    return cached_data

            # Placeholder: no futures call implemented yet
            futures: List[Dict[str, Any]] = []

            # Cache results
            self.cache[cache_key] = (futures, datetime.now())

            return futures

        except Exception as e:
            logger.error(f"Error getting futures contracts: {e}")
            return None

    def get_live_prices_batch(
        self, instrument_keys: List[str], db: Session
    ) -> Dict[str, Dict[str, Any]]:
        """Get live prices for multiple instruments efficiently"""
        try:
            if not instrument_keys:
                return {}

            # Check cache
            cached_prices: Dict[str, Dict[str, Any]] = {}
            uncached_keys: List[str] = []
            current_time = datetime.now()

            for key in instrument_keys:
                cache_key = f"price_{key}"
                if cache_key in self.cache:
                    cached_data, timestamp = self.cache[cache_key]
                    if current_time - timestamp < timedelta(seconds=30):
                        cached_prices[key] = cached_data
                    else:
                        uncached_keys.append(key)
                else:
                    uncached_keys.append(key)

            if not uncached_keys:
                return cached_prices

            # Batch API call
            endpoint = "/market-quote/quotes"
            params = {"instrument_key": ",".join(uncached_keys)}

            response_data = self._make_upstox_request(endpoint, params, db)
            batch_prices: Dict[str, Dict[str, Any]] = {}

            if response_data:
                for key in uncached_keys:
                    quote_data = response_data.get(key, {})
                    if quote_data:
                        price_data = {
                            "ltp": quote_data.get("last_price", 0),
                            "volume": quote_data.get("volume", 0),
                            "oi": quote_data.get("oi", 0),
                            "close_price": quote_data.get("close_price", 0),
                            "change": quote_data.get("net_change", 0),
                            "change_percent": quote_data.get("percentage_change", 0),
                            "high": quote_data.get("ohlc", {}).get("high", 0),
                            "low": quote_data.get("ohlc", {}).get("low", 0),
                            # Add more fields if needed
                        }

                        cache_key = f"price_{key}"
                        self.cache[cache_key] = (price_data, current_time)
                        batch_prices[key] = price_data

            return {**cached_prices, **batch_prices}

        except Exception as e:
            logger.error(f"Error getting batch prices: {e}")
            return {}

    def clear_cache(self):
        """Clear service cache"""
        self.cache.clear()
        logger.info("Cache cleared")


# Singleton instance
upstox_option_service = UpstoxOptionService()
