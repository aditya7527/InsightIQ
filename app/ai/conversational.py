import pandas as pd
from typing import Dict, Optional, Tuple
from app.ai.gpt_service import query_gpt
import logging
import re

logger = logging.getLogger(__name__)

FORBIDDEN_BUILTINS = ['import ', 'open(', 'os.', 'subprocess', 'eval(', 'exec(', '__']

async def ask_question(
    question: str,
    table_name: str,
    df: pd.DataFrame
) -> Dict:
    """
    Main entry point for asking questions about data using Schema-Aware Pandas Engine
    """
    
    # 1. Generate Schema Metadata
    # Convert dtypes to string dict
    schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
    columns_list = list(schema.keys())
    
    # 2. Build Structured Prompt Template
    prompt = f"""You are a data analyst. `df` columns: {columns_list}
Answer: "{question}"
Rules:
1. Write pandas code assigning to `result`.
2. ONLY return 1-2 lines of code. No markdown, no explanation.
3. Use only df. No imports. No files.
"""

    try:
        code = query_gpt(prompt).strip()
        
        # Check for AI Service error
        if '"error":' in code:
            import json
            try:
                err_dict = json.loads(code)
                err_msg = err_dict.get("error", "AI service is temporarily busy. Please try again in 10 seconds.")
            except:
                err_msg = "AI service is temporarily busy. Please try again in 10 seconds."
            return {
                "success": False,
                "error": err_msg,
                "question": question
            }
        
        # Clean code: remove markdown if still present
        if code.startswith("```"):
            lines = code.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```') and not l.strip().startswith('python')]
            code = '\n'.join(lines).strip()

        # 3. Validate Generated Code
        for bad in FORBIDDEN_BUILTINS:
            if bad in code:
                return {
                    "success": False,
                    "error": f"AI generated unsafe code (contains {bad}). Please rephrase.",
                    "question": question
                }
                
        # Check if code references columns that don't exist
        col_refs = re.findall(r"df\[['\"](.*?)['\"]\]", code)
        for col in col_refs:
            if col not in columns_list:
                return {
                    "success": False,
                    "error": f"AI referenced an unknown column '{col}'. Please refine your question.",
                    "question": question
                }

        # 4. Safe Execution
        allowed_locals = {"df": df}
        try:
            exec(code, {}, allowed_locals)
            result = allowed_locals.get("result", "No result generated. Ensure your code assigns to a variable `result`.")
        except Exception as e:
            logger.error(f"Error executing pandas code: {e}")
            return {
                "success": False,
                "error": "I couldn't generate a valid answer for this question. Please try asking differently.",
                "question": question
            }

        # Formulate output safely
        if isinstance(result, pd.DataFrame):
            # fillna to avoid JSON serialization NaN errors
            result_list = result.fillna("").head(50).to_dict(orient="records")
        elif isinstance(result, pd.Series):
            df_res = result.to_frame(name="Value").reset_index()
            result_list = df_res.fillna("").head(50).to_dict(orient="records")
        else:
            # For single numbers or strings
            result_list = [{"Answer": str(result)}]
            
        return {
            "success": True,
            "question": question,
            "sql": code,  # keeping key as 'sql' for backward-compatible frontend
            "results": result_list,
            "row_count": len(result_list) if isinstance(result_list, list) else 1,
            "explanation": "Here is the result based on the loaded dataset.",
            "columns": list(result_list[0].keys()) if isinstance(result_list, list) and len(result_list) > 0 else ["Answer"]
        }
        
    except Exception as e:
        logger.error(f"Ask question internal error: {e}")
        return {
            "success": False,
            "error": "Internal AI error while generating answer.",
            "question": question
        }
