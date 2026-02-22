"""
Confidence Score Engine — data-driven integrity scores.
Replaces arbitrary "95% Excellent" with evidence-based penalties.

Delegates integrity computation to revenue_engine.compute_integrity_score()
for any analytics run that has a revenue result available.
"""
import pandas as pd
from typing import Dict, Tuple


def calculate_confidence_score(df: pd.DataFrame, column_stats: Dict) -> Tuple[int, str]:
    """
    Calculate overall data confidence score (0–100).

    Factors:
    - Completeness     (40%)
    - Row Count        (20%)
    - Outlier Ratio    (20%)
    - Column Diversity (20%)

    Returns: (confidence_score: int, quality: str)
    """
    scores = {}

    # 1. Completeness (40%)
    missing_pcts = [s.get('missing_percent', 0) for s in column_stats.values()]
    avg_completeness = 100 - (sum(missing_pcts) / len(missing_pcts) if missing_pcts else 0)
    scores['completeness'] = min(100, avg_completeness)

    # 2. Row Count (20%)
    n = len(df)
    if n >= 10_000:  scores['row_count'] = 100
    elif n >= 1_000: scores['row_count'] = 80
    elif n >= 100:   scores['row_count'] = 60
    elif n >= 10:    scores['row_count'] = 40
    else:            scores['row_count'] = 20

    # 3. Outlier Ratio (20%)
    scores['outlier_ratio'] = max(0, 100 - (calculate_outlier_ratio(df) * 100))

    # 4. Column Diversity (20%)
    nc = len(df.columns)
    if nc >= 20:  scores['diversity'] = 100
    elif nc >= 10: scores['diversity'] = 80
    elif nc >= 5:  scores['diversity'] = 60
    elif nc >= 3:  scores['diversity'] = 40
    else:          scores['diversity'] = 20

    weights = {'completeness': 0.40, 'row_count': 0.20, 'outlier_ratio': 0.20, 'diversity': 0.20}
    confidence_score = int(min(100, max(0, sum(scores[k] * weights[k] for k in weights))))

    if confidence_score >= 80:   quality = "Excellent"
    elif confidence_score >= 60: quality = "Good"
    elif confidence_score >= 40: quality = "Fair"
    else:                        quality = "Poor"

    return confidence_score, quality


def calculate_confidence_score_from_revenue(revenue_result: Dict, df: pd.DataFrame, revenue_col: str) -> Tuple[int, str, list]:
    """
    Data-driven integrity score based on revenue engine output.
    Returns (score, quality, reasons).

    Used by /analytics route when a full revenue result is available.
    """
    # Import here to avoid circular import at module load time
    from app.services.revenue_engine import compute_integrity_score
    return compute_integrity_score(revenue_result, df, revenue_col)


def calculate_outlier_ratio(df: pd.DataFrame) -> float:
    """Proportion of outliers using IQR method (0–1)."""
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) == 0:
        return 0.0

    total_outliers = 0
    total_points   = len(df) * len(numeric_cols)

    for col in numeric_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        total_outliers += int(df[(df[col] < lower) | (df[col] > upper)].shape[0])

    return total_outliers / total_points if total_points > 0 else 0.0
