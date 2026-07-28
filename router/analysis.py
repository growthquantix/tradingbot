from fastapi import APIRouter
import joblib
import pandas as pd
import logging

logging.basicConfig(level=logging.ERROR)
router = APIRouter(prefix="/api/analysis", tags=["analysis"])

@router.get("/sectoral-options")
def analyze_sectoral_options():
    try:
        model = joblib.load("models/sectoral_model.pkl")
        market_data = pd.DataFrame({
            'open': [1500, 1600],
            'high': [1515, 1615],
            'low': [1495, 1595],
            'close': [1505, 1605],
            'volume': [10000, 12000],
            'sentiment_score': [0.65, 0.80]
        })
        X = market_data[['open', 'high', 'low', 'close', 'volume', 'sentiment_score']].values
        predictions = model.predict(X)
        sector_stock_mapping = {0: "INFY", 1: "TCS"}
        recommended_stocks = [
            sector_stock_mapping.get(idx, f"SECTOR_{idx}")
            for idx, pred in enumerate(predictions) if pred == 1
        ]
        return {"recommendedStocks": recommended_stocks}
    except Exception as e:
        logging.error("Failed to load model", exc_info=True)
        return {"error": "An internal error has occurred. Please try again later."}