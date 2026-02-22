"""
Cohort Retention Validation Tests
=================================
Validates the mathematical consistency of the customer cohort engine.
"""

import sys
import os
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cohort_service import compute_cohort_retention, detect_customer_column

class TestCohortIntegrity(unittest.TestCase):

    def setUp(self):
        # Create synthetic cohort dataset
        # 3 Customers
        # C1: Jan, Feb, Mar, Apr (100% retention, $10 each)
        # C2: Feb, Mar (drops in Apr, $20 each)
        # C3: Mar (drops in Apr, $50 each)
        
        data = []
        # C1
        data.extend([("C1", "2023-01-15", 10), ("C1", "2023-02-15", 10), ("C1", "2023-03-15", 10), ("C1", "2023-04-15", 10)])
        # C2
        data.extend([("C2", "2023-02-15", 20), ("C2", "2023-03-15", 20)])
        # C3
        data.extend([("C3", "2023-03-15", 50)])
        
        self.df = pd.DataFrame(data, columns=["CustomerID", "Date", "Revenue"])
        
    def test_cohort_math_integrity(self):
        """Test logical guarantees of Cohort matrix."""
        res = compute_cohort_retention(self.df, "Date", "Revenue")
        
        self.assertEqual(res["status"], "ok", "Cohort computation failed")
        
        # Test 1: Month 0 retention MUST be 100%
        matrix = res["retention_matrix"]
        
        # Verify Month 0 is 100
        for row in matrix:
            self.assertEqual(row.get("month_0"), 100.0, f"Month 0 retention for {row['cohort']} is not 100%")
            
        # Test 2: Cohort Sizes
        sizes = res["cohort_sizes"]
        self.assertEqual(sizes["2023-01"], 1) # C1
        self.assertEqual(sizes["2023-02"], 1) # C2
        self.assertEqual(sizes["2023-03"], 1) # C3
        
        # Test 3: Revenue Weighted Calculation
        rev_matrix = res["revenue_retention_matrix"]
        
        jan_rev = next(r for r in rev_matrix if r["cohort"] == "2023-01")
        feb_rev = next(r for r in rev_matrix if r["cohort"] == "2023-02")
        
        self.assertEqual(jan_rev["month_1"], 100.0) # $10 / $10
        self.assertEqual(feb_rev["month_1"], 100.0) # $20 / $20
        
        # Test 4: Retention cannot be greater than month 0
        for row in matrix:
            m0 = row.get("month_0") or 0
            m1 = row.get("month_1") or 0
            self.assertLessEqual(m1, m0, "Retention increased in subsequent months (impossible in this dataset)")

        print("Cohort Matrix Mathematics: PASS")

    def test_edge_cases(self):
        """Test edge case handling (too few months, no customer column)."""
        df_invalid = pd.DataFrame({
            "Date": ["2023-01-01", "2023-02-01"],
            "Revenue": [10, 20],
            "NoCustomer": ["X", "Y"]
        })
        
        res = compute_cohort_retention(df_invalid, "Date", "Revenue")
        self.assertEqual(res["status"], "insufficient_data", "Failed to catch missing customer column context.")
        print("Cohort Edge Cases: PASS")

if __name__ == "__main__":
    unittest.main(verbosity=2)
