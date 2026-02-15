"""
Confidence Score Engine
Calculates data quality and reliability metrics
"""
import pandas as pd
from typing import Dict, Tuple


def calculate_confidence_score(df: pd.DataFrame, column_stats: Dict) -> Tuple[int, str]:
    """
    Calculate overall data confidence score (0-100)
    
    Factors:
    - Completeness (40%)
    - Row count (20%)
    - Outlier ratio (20%)
    - Column diversity (20%)
    
    Args:
        df: DataFrame to analyze
        column_stats: Column statistics dictionary
    
    Returns:
        Tuple of (confidence_score: int, data_quality: str)
    """
    
    scores = {}
    
    # 1. Completeness Score (40%)
    missing_percentages = [stats.get('missing_percent', 0) for stats in column_stats.values()]
    avg_completeness = 100 - (sum(missing_percentages) / len(missing_percentages) if missing_percentages else 0)
    scores['completeness'] = min(100, avg_completeness)
    
    # 2. Row Count Score (20%) - More rows = more confidence
    row_count = len(df)
    if row_count >= 10000:
        scores['row_count'] = 100
    elif row_count >= 1000:
        scores['row_count'] = 80
    elif row_count >= 100:
        scores['row_count'] = 60
    elif row_count >= 10:
        scores['row_count'] = 40
    else:
        scores['row_count'] = 20
    
    # 3. Outlier Ratio Score (20%)
    outlier_ratio = calculate_outlier_ratio(df)
    scores['outlier_ratio'] = max(0, 100 - (outlier_ratio * 100))
    
    # 4. Column Diversity Score (20%) - More columns = better analysis
    num_columns = len(df.columns)
    if num_columns >= 20:
        scores['diversity'] = 100
    elif num_columns >= 10:
        scores['diversity'] = 80
    elif num_columns >= 5:
        scores['diversity'] = 60
    elif num_columns >= 3:
        scores['diversity'] = 40
    else:
        scores['diversity'] = 20
    
    # Calculate weighted score
    weights = {
        'completeness': 0.40,
        'row_count': 0.20,
        'outlier_ratio': 0.20,
        'diversity': 0.20
    }
    
    confidence_score = sum(scores[key] * weights[key] for key in weights)
    confidence_score = min(100, max(0, int(confidence_score)))
    
    # Determine quality tier
    if confidence_score >= 80:
        quality = "Excellent"
    elif confidence_score >= 60:
        quality = "Good"
    elif confidence_score >= 40:
        quality = "Fair"
    else:
        quality = "Poor"
    
    return confidence_score, quality


def calculate_outlier_ratio(df: pd.DataFrame) -> float:
    """
    Calculate proportion of outliers using IQR method
    Returns ratio between 0 and 1
    """
    numeric_cols = df.select_dtypes(include=['number']).columns
    
    if len(numeric_cols) == 0:
        return 0.0
    
    total_outliers = 0
    total_points = len(df) * len(numeric_cols)
    
    for col in numeric_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)].shape[0]
        total_outliers += outliers
    
    return total_outliers / total_points if total_points > 0 else 0
