"""
Visual Integrity Validation Tests
=================================
Validates the mathematical consistency of the visual elements:
1. Revenue Bridge Waterfall components sum to exactly the delta.
2. Stability CV strictly matches raw statistical calculation.
"""

import sys
import os
import unittest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.revenue_bridge_service import compute_revenue_bridge
from app.services.revenue_engine import compute_volatility

class TestVisualIntegrity(unittest.TestCase):

    def setUp(self):
        # Create a synthetic dataset
        dates = pd.date_range(start="2023-01-01", periods=60, freq="D")
        self.df = pd.DataFrame({
            "Date": dates,
            "Revenue": [100 + i * 10 for i in range(60)],  # Increasing trend
            "Region": ["North", "South", "East", "West", "North"] * 12
        })
        
        # Monthly series
        self.df_monthly = self.df.copy()
        self.df_monthly["Date"] = pd.to_datetime(self.df_monthly["Date"])
        self.monthly_series = self.df_monthly.groupby(pd.Grouper(key="Date", freq="MS"))["Revenue"].sum()
        self.monthly_series.index = [pd.Timestamp(f"{d.year}-{d.month:02d}-01") for d in self.monthly_series.index]
        
    def test_waterfall_math_integrity(self):
        """Test 1: Waterfall components must exactly equal the delta between months."""
        res = compute_revenue_bridge(self.monthly_series, self.df, "Revenue", "Date")
        
        prev = res["previous_value"]
        curr = res["current_value"]
        
        # Sum of *raw* values from all dimensional components
        # Note: the engine returns top 5, so if there are >5 it might not equal exactly 
        # but in our dummy dataset there are only 4 regions, so it will contain all changes.
        components = res["components"]
        sum_components = sum(c["value"] for c in components)
        
        reconstructed = prev + sum_components
        
        # Calculate percentage difference (Tolerance: 0.01%)
        diff_pct = abs(reconstructed - curr) / abs(curr) * 100
        
        print("\n--- Waterfall Validation ---")
        print(f"Previous: {prev}, Current: {curr}, Delta: {curr - prev}")
        print(f"Sum of top components: {sum_components}")
        print(f"Reconstructed: {reconstructed} vs Target: {curr}")
        print(f"Difference: {diff_pct:.4f}%")
        
        self.assertLess(diff_pct, 0.01, f"Waterfall discrepancy too high: {diff_pct:.4f}% > 0.01%")
        print("Waterfall Math Integrity: PASS ✅")

    def test_volatility_integrity(self):
        """Test 2: CV calculation must exactly match manual pandas statistical recomputation."""
        res = compute_volatility(self.monthly_series)
        calc_cv = res["cv"]
        
        # Manual check
        mean_val = float(self.monthly_series.mean())
        std_val = float(self.monthly_series.std())
        expected_cv = round(std_val / mean_val, 4)
        
        print("\n--- Volatility Validation ---")
        print(f"Calculated CV: {calc_cv}, Expected CV: {expected_cv}")
        print(f"Label: {res['stability_label']}")
        
        self.assertAlmostEqual(calc_cv, expected_cv, places=4, msg="CV mismatch!")
        print("Volatility Integrity: PASS ✅")

if __name__ == "__main__":
    unittest.main(verbosity=2)
