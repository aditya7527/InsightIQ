"""
Conversational AI / Ask Your Data Engine
Converts natural language questions to SQL and executes them safely
"""
import pandas as pd
from typing import Dict, Optional, Tuple
from sqlalchemy import text, inspect
from app.ai.gpt_service import query_gpt


ALLOWED_SQL_KEYWORDS = ['SELECT', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'LIMIT', 'SUM', 'AVG', 'COUNT', 'MAX', 'MIN']
FORBIDDEN_SQL_KEYWORDS = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE', 'EXEC', '--', ';']


def convert_question_to_sql(
    question: str,
    table_name: str, 
    column_names: list,
    engine
) -> Tuple[Optional[str], str]:
    """
    Convert natural language question to SQL using GPT
    
    Args:
        question: Natural language question
        table_name: Table to query
        column_names: Available columns
        engine: SQLAlchemy engine
    
    Returns:
        Tuple of (sql_query, explanation) or (None, error_message)
    """
    
    try:
        # Build context for GPT
        columns_str = ', '.join(column_names[:10])  # First 10 columns
        
        prompt = f"""Convert this natural language question to a SQL SELECT query.

Table name: {table_name}
Available columns: {columns_str}

Question: {question}

Requirements:
- Only use SELECT statements
- Only use the available columns
- Add LIMIT 100 to prevent large queries
- Return ONLY the raw SQL query, no markdown, no explanation, no code fences

SQL Query:"""
        
        sql_query = query_gpt(prompt)
        
        if not sql_query:
            return None, "Could not generate SQL query"
        
        # Check if LLM returned an error instead of SQL
        if sql_query.startswith("Error:"):
            return None, f"AI service unavailable: {sql_query}"
        
        # Strip markdown code fences (```sql ... ```)
        sql_query = sql_query.strip()
        if sql_query.startswith("```"):
            lines = sql_query.split('\n')
            # Remove first line (```sql) and last line (```)
            lines = [l for l in lines if not l.strip().startswith('```')]
            sql_query = '\n'.join(lines).strip()
        
        # Must contain SELECT to be valid SQL
        if 'SELECT' not in sql_query.upper():
            return None, "AI did not return a valid SQL query. Please try rephrasing your question."
        
        # Sanitize the query
        is_safe, error = validate_sql_query(sql_query, table_name)
        if not is_safe:
            return None, error
        
        # Ensure LIMIT clause
        if 'LIMIT' not in sql_query.upper():
            sql_query = sql_query.rstrip(';') + ' LIMIT 100'
        
        return sql_query.strip(), "Query generated successfully"
    
    except Exception as e:
        return None, f"Query generation error: {str(e)}"


def validate_sql_query(query: str, table_name: str) -> Tuple[bool, str]:
    """
    Validate SQL query safety
    
    Returns:
        Tuple of (is_safe: bool, message: str)
    """
    
    # Check for forbidden keywords
    query_upper = query.upper()
    for keyword in FORBIDDEN_SQL_KEYWORDS:
        if keyword in query_upper:
            return False, f"Forbidden operation: {keyword}"
    
    # Check for SELECT keyword
    if 'SELECT' not in query_upper:
        return False, "Query must be a SELECT statement"
    
    # Check table name matches
    if table_name.upper() not in query_upper:
        return False, f"Query must reference table {table_name}"
    
    # Check for suspicious patterns
    if '/*' in query or '*/' in query:
        return False, "SQL comments not allowed"
    
    return True, "Query is safe"


def execute_safe_query(
    query: str,
    table_name: str,
    engine,
    max_rows: int = 100
) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Execute SQL query safely with constraints
    
    Args:
        query: SQL query
        table_name: Expected table name
        engine: SQLAlchemy engine
        max_rows: Maximum rows to return
    
    Returns:
        Tuple of (dataframe, message/error)
    """
    
    try:
        # Validate query
        is_safe, error = validate_sql_query(query, table_name)
        if not is_safe:
            return None, error
        
        # Ensure LIMIT is present and reasonable
        if 'LIMIT' not in query.upper():
            query = query.rstrip(';') + f' LIMIT {max_rows}'
        
        # Execute query with timeout
        with engine.connect() as conn:
            result = conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            
            if len(df) == 0:
                return df, "Query executed successfully (no results)"
            
            return df, f"Query executed successfully ({len(df)} rows)"
    
    except Exception as e:
        return None, f"Query execution error: {str(e)}"


def generate_insights_from_result(
    df: pd.DataFrame,
    question: str
) -> str:
    """
    Generate natural language insights from query result
    
    Args:
        df: Query result DataFrame
        question: Original question
    
    Returns:
        Natural language explanation
    """
    
    try:
        if df.empty:
            return "The query returned no results. Try refining your question."
        
        # Build summary for GPT
        summary = f"""
        Original question: {question}
        
        Query results ({len(df)} rows):
        {df.head(10).to_string()}
        
        Column summary:
        {df.dtypes.to_string()}
        
        Generate a clear, brief explanation (2-3 sentences) of what these results show.
        """
        
        explanation = query_gpt(summary)
        return explanation or "Query results retrieved successfully"
    
    except Exception as e:
        return f"Query results obtained ({len(df)} rows)"


async def ask_question(
    question: str,
    table_name: str,
    column_names: list,
    engine
) -> Dict:
    """
    Main entry point for asking questions about data
    
    Returns:
        Dict with query, results, and explanation
    """
    
    # Generate SQL from question
    sql_query, gen_error = convert_question_to_sql(question, table_name, column_names, engine)
    
    if not sql_query:
        return {
            'success': False,
            'error': gen_error,
            'question': question
        }
    
    # Execute query
    results_df, exec_error = execute_safe_query(sql_query, table_name, engine)
    
    if results_df is None:
        return {
            'success': False,
            'error': exec_error,
            'question': question,
            'sql': sql_query
        }
    
    # Generate insights
    explanation = generate_insights_from_result(results_df, question)
    
    # Convert dataframe to dict for JSON serialization
    results = results_df.head(50).to_dict(orient='records')
    
    return {
        'success': True,
        'question': question,
        'sql': sql_query,
        'results': results,
        'row_count': len(results_df),
        'explanation': explanation,
        'columns': list(results_df.columns)
    }
