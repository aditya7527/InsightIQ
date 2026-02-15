"""
Industry Type Detection Engine
Auto-detects business industry and recommends KPIs based on column names
"""
from typing import Dict, List, Tuple
import pandas as pd


INDUSTRY_KEYWORDS = {
    'insurance': ['claim', 'premium', 'policy', 'deductible', 'coverage', 'underwriter'],
    'retail': ['sales', 'store', 'sku', 'product', 'transaction', 'checkout', 'cart'],
    'ecommerce': ['order', 'cart', 'checkout', 'customer', 'purchase', 'product', 'payment'],
    'marketing': ['campaign', 'impression', 'click', 'conversion', 'roi', 'ctr', 'lead'],
    'finance': ['revenue', 'profit', 'expense', 'budget', 'forecast', 'liability', 'asset'],
    'hr': ['employee', 'salary', 'department', 'hire', 'turnover', 'performance'],
    'healthcare': ['patient', 'diagnosis', 'treatment', 'hospital', 'doctor', 'appointment'],
    'logistics': ['shipment', 'delivery', 'warehouse', 'route', 'carrier', 'tracking'],
    'saas': ['subscription', 'churn', 'mrr', 'arr', 'user', 'trial', 'license'],
}

KPI_RECOMMENDATIONS = {
    'insurance': {
        'kpis': ['Total Claims', 'Average Claim Amount', 'Claims Processing Time', 'Customer Retention'],
        'metrics': ['Claim Frequency', 'Loss Ratio', 'Premium Growth']
    },
    'retail': {
        'kpis': ['Sales Revenue', 'Average Transaction Value', 'Customer Count', 'Inventory Turnover'],
        'metrics': ['Same-Store Sales Growth', 'Gross Margin %', 'Conversion Rate']
    },
    'ecommerce': {
        'kpis': ['Total Revenue', 'Orders', 'Average Order Value', 'Customer Acquisition Cost'],
        'metrics': ['Conversion Rate', 'Cart Abandonment %', 'Customer LTV']
    },
    'marketing': {
        'kpis': ['Campaign Performance', 'Lead Generation', 'Conversion Rate', 'ROI'],
        'metrics': ['Click-Through Rate', 'Cost Per Acquisition', 'Customer Lifetime Value']
    },
    'finance': {
        'kpis': ['Total Revenue', 'Net Profit', 'Operating Margin', 'Cash Flow'],
        'metrics': ['Revenue Growth %', 'Profit Margin %', 'Expense Ratio']
    },
    'hr': {
        'kpis': ['Total Employees', 'Turnover Rate', 'Average Salary', 'Retention Rate'],
        'metrics': ['Hiring Rate', 'Performance Score', 'Cost Per Hire']
    },
    'healthcare': {
        'kpis': ['Total Patients', 'Average Wait Time', 'Treatment Success Rate', 'Patient Satisfaction'],
        'metrics': ['Readmission Rate', 'Average Length of Stay', 'Cost Per Patient']
    },
    'logistics': {
        'kpis': ['Total Shipments', 'On-Time Delivery %', 'Average Lead Time', 'Cost Per Unit'],
        'metrics': ['Delivery Efficiency', 'Warehouse Utilization %', 'Damage Rate']
    },
    'saas': {
        'kpis': ['Monthly Recurring Revenue', 'Churn Rate', 'Customer Count', 'Expansion Revenue'],
        'metrics': ['Customer Acquisition Cost', 'Gross Margin %', 'Net Revenue Retention']
    },
}


def detect_industry(df: pd.DataFrame, column_names: List[str]) -> Tuple[str, Dict]:
    """
    Detect business industry based on column names
    
    Args:
        df: DataFrame (used for size context)
        column_names: List of column names
    
    Returns:
        Tuple of (detected_industry: str, recommendations: Dict)
    """
    
    # Convert all column names to lowercase for matching
    columns_lower = [col.lower() for col in column_names]
    all_columns = ' '.join(columns_lower)
    
    # Score each industry based on keyword matches
    industry_scores = {}
    
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        matches = sum(1 for keyword in keywords if keyword in all_columns)
        industry_scores[industry] = matches
    
    # Find best match
    if max(industry_scores.values()) == 0:
        detected_industry = 'general'
    else:
        detected_industry = max(industry_scores, key=industry_scores.get)
    
    # Get recommendations
    recommendations = KPI_RECOMMENDATIONS.get(detected_industry, {
        'kpis': ['Key Metric 1', 'Key Metric 2', 'Key Metric 3'],
        'metrics': ['Performance Metric 1', 'Performance Metric 2']
    })
    
    return detected_industry, {
        'industry': detected_industry,
        'confidence': (industry_scores[detected_industry] / max(
            1, max(industry_scores.values())
        )) * 100,
        'recommended_kpis': recommendations['kpis'],
        'recommended_metrics': recommendations['metrics']
    }


def get_industry_context(industry: str) -> Dict:
    """Get context and insights for a specific industry"""
    return {
        'kpis': KPI_RECOMMENDATIONS.get(industry, {}).get('kpis', []),
        'metrics': KPI_RECOMMENDATIONS.get(industry, {}).get('metrics', [])
    }
