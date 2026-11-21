# Import necessary modules
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import ssl
import websockets.connection
import logging
import websockets
import requests
from google.protobuf.json_format import MessageToDict
import MarketDataFeed_pb2 as pb

logger = logging.getLogger("ws_relay")


def get_market_data_feed_authorize_v3():
    """Get authorization for market data feed."""
    access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("UPSTOX_ACCESS_TOKEN is not set; export a current Upstox access token")
    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
    url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
    api_response = requests.get(url=url, headers=headers)
    print("Response:", api_response.status_code, api_response.text)
    if api_response.status_code != 200:
        print("Failed to authorize market data feed")
    return api_response.json()


def decode_protobuf(buffer):
    """Decode protobuf message."""
    feed_response = pb.FeedResponse()
    feed_response.ParseFromString(buffer)
    return feed_response


async def fetch_market_data():
    """Fetch market data using WebSocket and print it."""

    # Create default SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Get market data feed authorization
    authorize_response = get_market_data_feed_authorize_v3()
    print("Authorize Response:", authorize_response)
    if authorize_response["status"] != "success":
        print("Failed to authorize market data feed", authorize_response["errors"])
        if "errors" in authorize_response:
            for error in authorize_response["errors"]:
                print("Error:", error)
            else:
                print("No errors found in authorization response")

        return
    # response = get_market_data_feed_authorize_v3()
    # Connect to the WebSocket with SSL context
    async with websockets.connect(
        authorize_response["data"]["authorized_redirect_uri"], ssl=ssl_context
    ) as websocket:
        print("Connection established")

        await asyncio.sleep(1)  # Wait for 1 second

        # Data to be sent over the WebSocket
        data = {
            "guid": "someguid",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": ["NSE_EQ|INE009A01021"],
            },
        }

        # Convert data to binary and send over WebSocket
        binary_data = json.dumps(data).encode("utf-8")
        await websocket.send(binary_data)

        # Continuously receive and decode data from WebSocket
        while True:
            message = await websocket.recv()
            decoded_data = decode_protobuf(message)

            # Convert the decoded data to a dictionary
            data_dict = MessageToDict(decoded_data)

            # Print the dictionary representation
            print(json.dumps(data_dict))


def get_default_instrument_keys():
    from collections import defaultdict

    top_stocks_path = Path("data/top_stocks.json")
    instrument_path = Path("data/upstox_instruments.json")

    if not top_stocks_path.exists() or not instrument_path.exists():
        logger.error("❌ Missing required JSON files for instrument keys.")
        return []

    try:
        with open(top_stocks_path, "r", encoding="utf-8") as f:
            top_stocks = json.load(f).get("securities", [])

        with open(instrument_path, "r", encoding="utf-8") as f:
            all_instruments = json.load(f)
    except Exception as e:
        logger.error(f"❌ Failed to load instrument key files: {e}")
        return []

    now = datetime.now()
    instrument_keys = set()

    # ✅ Pre-index instruments by (exchange, symbol)
    indexed = defaultdict(list)
    for instr in all_instruments:
        if not instr.get("instrument_key"):
            continue

        expiry = instr.get("expiry")
        if expiry and datetime.fromtimestamp(expiry / 1000) < now:
            continue

        exchange = instr.get("exchange", "").upper()
        for field in ("trading_symbol", "asset_symbol", "underlying_symbol"):
            symbol = instr.get(field, "").upper()
            if symbol:
                indexed[(exchange, symbol)].append(instr)

    def normalize_type(t):
        return (t or "").strip().upper()

    for stock in top_stocks:
        symbol = stock.get("symbol", "").strip().upper()
        exchange = stock.get("exchange", "").strip().upper()

        if not symbol or not exchange:
            continue

        # ✅ Handle optional aliases
        symbol_aliases = [symbol]
        if symbol == "CRUDEOIL":
            symbol_aliases.append("CRUDEOILM")
        elif symbol == "GOLD":
            symbol_aliases.append("GOLDM")

        # ✅ Collect all matches
        all_matches = []
        for alias in symbol_aliases:
            all_matches.extend(indexed.get((exchange, alias), []))

        if not all_matches:
            logger.error(f"⚠️ No instruments found for {symbol} on {exchange}")
            continue

        # ✅ Group by type
        instrument_types = {
            "EQ": [],
            "INDEX": [],
            "FUT": [],
            "CE": [],
            "PE": [],
        }

        for m in all_matches:
            t = normalize_type(m.get("instrument_type"))
            if t in instrument_types:
                instrument_types[t].append(m)

        # ✅ Add EQ/INDEX/FUT always
        for t in ["EQ", "INDEX", "FUT"]:
            for m in instrument_types[t]:
                instrument_keys.add(m["instrument_key"])

        # ✅ For CE/PE, calculate spot LTP
        all_options = instrument_types["CE"] + instrument_types["PE"]

        spot_ltp = None
        for m in instrument_types["EQ"] + instrument_types["INDEX"]:
            spot_ltp = m.get("last_price") or m.get("close_price")
            if spot_ltp:
                break

        if not spot_ltp:
            strikes = [
                m.get("strike_price") for m in all_options if m.get("strike_price")
            ]
            if strikes:
                spot_ltp = sum(strikes) / len(strikes)

        if spot_ltp:
            for opt in all_options:
                strike = opt.get("strike_price") or 0
                if abs(strike - spot_ltp) <= 20:
                    instrument_keys.add(opt["instrument_key"])

    logger.info(f"✅ Final instrument keys resolved: {len(instrument_keys)}")
    return list("NSE_FO|108985")
    # return list(instrument_keys)


# Execute the function to fetch market data
asyncio.run(fetch_market_data())
