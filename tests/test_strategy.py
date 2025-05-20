# tests/test_strategy.py

import unittest
import pandas as pd
from strategies.strategy import TradingStrategy

# Dummy predictor for testing.
class DummyPredictor:
    def predict(self, features):
        return "BUY"

class TestTradingStrategy(unittest.TestCase):
    def setUp(self):
        data = {
            'date': pd.date_range(start='2025-01-01', periods=250),
            'open': [2000 + i for i in range(250)],
            'high': [2010 + i for i in range(250)],
            'low': [1990 + i for i in range(250)],
            'close': [2000 + i for i in range(250)],
            'volume': [1000 + i * 10 for i in range(250)]
        }
        self.market_data = pd.DataFrame(data)
        self.predictor = DummyPredictor()
        self.strategy = TradingStrategy(self.predictor)
    
    def test_generate_signal(self):
        signal = self.strategy.generate_signal(self.market_data)
        # For this dummy predictor and test data, expect "BUY"
        self.assertEqual(signal, "BUY")
//est

if __name__ == '__main__':
    unittest.main()
