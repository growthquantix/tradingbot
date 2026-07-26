from fastapi import APIRouter, HTTPException, Depends
from typing import Dict

import json
from services.config_service import ConfigService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["configuration"])

config_service = ConfigService()

@router.post("/save")
async def save_trading_config(config: Dict):
    """Save trading configuration from UI"""
    try:
        # Validate config data
        required_fields = ['sectors', 'risk_parameters', 'trading_parameters']
        for field in required_fields:
            if field not in config:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )
        
        # Save configuration
        result = await config_service.save_config(config)
        return result
        
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/current")
async def get_current_config():
    """Get current trading configuration"""
    try:
        with open(config_service.config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"message": "No configuration found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))