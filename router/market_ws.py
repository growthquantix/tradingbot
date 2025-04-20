import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jwt.exceptions import ExpiredSignatureError, DecodeError
from services.auth_service import get_current_user
from services.upstox.ws_client import UpstoxWebSocketClient
from database.connection import get_db
from database.models import BrokerConfig

logger = logging.getLogger("market_ws")
router = APIRouter()

clients = {}
ws_clients = {}
market_status = {}
received_ltp_flag = {}

MAX_CHUNKS = 2
CHUNK_SIZE = 1500


@router.websocket("/ws/market")
async def market_data_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.send_json({"type": "error", "reason": "missing_token"})
        await websocket.close()
        return

    logger.info(f"📥 WebSocket request received: {token}")

    try:
        db = next(get_db())
        try:
            user = get_current_user(token=token, db=db)
        except ExpiredSignatureError:
            await websocket.accept()
            await notify_token_expired(token)
            return
        except DecodeError:
            await websocket.accept()
            await websocket.send_json({"type": "error", "reason": "token_invalid"})
            await websocket.close()
            return

        broker = (
            db.query(BrokerConfig)
            .filter(
                BrokerConfig.user_id == user.id,
                BrokerConfig.broker_name.ilike("upstox"),
            )
            .first()
        )

        if not broker or not broker.access_token:
            await websocket.accept()
            await websocket.send_json({"type": "error", "reason": "upstox_not_linked"})
            await websocket.close()
            return

        instrument_keys = load_today_instrument_keys()
        if not instrument_keys:
            await websocket.accept()
            await websocket.send_json({"type": "error", "reason": "no_instruments"})
            await websocket.close()
            return

        # Accept WebSocket connection before any await that can raise errors
        await websocket.accept()

        # Cleanup any stale state
        await cleanup_connection(token)
        clients[token] = websocket
        ws_clients[token] = []

        logger.info(f"✅ WebSocket accepted: {token}")

        # Split into two 1500-key chunks max
        chunks = [
            instrument_keys[i : i + CHUNK_SIZE]
            for i in range(
                0, min(len(instrument_keys), MAX_CHUNKS * CHUNK_SIZE), CHUNK_SIZE
            )
        ]

        for chunk in chunks:
            client = UpstoxWebSocketClient(
                access_token=broker.access_token,
                instrument_keys=chunk,
                callback=lambda data: asyncio.create_task(broadcast(token, data)),
                stop_callback=lambda: logger.info("🛑 One WS stream stopped."),
                on_auth_error=lambda: asyncio.create_task(
                    handle_auth_failure_and_close(token)
                ),
            )
            ws_clients[token].append(client)
            asyncio.create_task(client.connect_and_stream())

        # Main receive loop
        while token in clients:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=60)
            except (WebSocketDisconnect, asyncio.TimeoutError):
                logger.info(f"❎ WebSocket timeout/disconnect for {token}")
                break
            except RuntimeError as e:
                logger.warning(f"⚠️ WebSocket RuntimeError: {e}")
                break

    finally:
        await cleanup_connection(token)


async def broadcast(token: str, data: dict):
    ws = clients.get(token)
    if not ws:
        logger.warning(f"⚠️ No WebSocket client to broadcast to {token}")
        return

    try:
        if data.get("type") == "market_info":
            status = data.get("status", "").lower()
            market_status[token] = status
            await ws.send_json({"type": "market_info", "marketStatus": status})

            if status in ["normal_close", "closing_end"] and received_ltp_flag.get(
                token
            ):
                await cleanup_connection(token)

        elif data.get("type") == "live_feed":
            payload = data["data"]
            if not isinstance(payload, dict):
                return
            parsed = parse_live_feed(payload)
            received_ltp_flag[token] = True
            await ws.send_json(
                {
                    "type": "live_feed",
                    "data": parsed,
                    "market_open": market_status.get(token) == "open",
                }
            )

            if market_status.get(token) in ["normal_close", "closing_end"]:
                await asyncio.sleep(1)
                await cleanup_connection(token)

    except Exception as e:
        logger.error(f"❌ Broadcast error for {token}: {e}")


async def handle_auth_failure_and_close(token: str):
    logger.warning(f"🔐 Auth failed for {token}")
    await notify_token_expired(token)
    await cleanup_connection(token)


async def notify_token_expired(token: str):
    ws = clients.get(token)
    if ws:
        try:
            await ws.send_json({"type": "error", "reason": "token_expired"})
        except Exception:
            pass
    await cleanup_connection(token)


async def cleanup_connection(token: str):
    logger.info(f"🧹 Cleaning up for {token}")

    ws = clients.pop(token, None)
    if ws:
        try:
            if ws.client_state.name != "DISCONNECTED":
                await ws.close()
        except Exception:
            pass

    for client in ws_clients.pop(token, []):
        if client:
            client.stop()

    market_status.pop(token, None)
    received_ltp_flag.pop(token, None)


def parse_live_feed(raw_data: dict):
    parsed = {}
    for instrument_key, details in raw_data.items():
        try:
            feed = details.get("fullFeed", {}).get("marketFF", {})
            ltpc = feed.get("ltpc", {})
            parsed[instrument_key] = {
                "ltp": ltpc.get("ltp"),
                "ltq": ltpc.get("ltq"),
                "cp": ltpc.get("cp"),
                "last_trade_time": ltpc.get("ltt"),
                "bid_ask": feed.get("marketLevel", {}).get("bidAskQuote", []),
                "greeks": feed.get("optionGreeks", {}),
                "ohlc": feed.get("marketOHLC", {}).get("ohlc", []),
                "atp": feed.get("atp"),
                "oi": feed.get("oi"),
                "iv": feed.get("iv"),
                "tbq": feed.get("tbq"),
                "tsq": feed.get("tsq"),
            }
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse tick for {instrument_key}: {e}")
    return parsed


def load_today_instrument_keys():
    file_path = Path(gettempdir()) / "today_instrument_keys.json"

    if not file_path.exists():
        logger.warning("⚠️ Instrument keys file does not exist.")
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
            if isinstance(content, list):
                return content
            elif isinstance(content, dict):
                if content.get("timestamp") == datetime.now().strftime("%Y-%m-%d"):
                    return content.get("keys", [])
    except Exception as e:
        logger.warning(f"❌ Failed to load instrument keys: {e}")

    return []
