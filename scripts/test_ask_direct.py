import sqlite3
import pandas as pd
import asyncio
from app.ai.conversational import ask_question

async def test():
    conn = sqlite3.connect('insightiq.db')
    name = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dataset_%';", conn).iloc[-1]['name']
    df = pd.read_sql(f"SELECT * FROM '{name}'", conn)
    
    res = await ask_question("what is the total revenue?", name, df)
    import pprint
    pprint.pprint(res)

if __name__ == "__main__":
    asyncio.run(test())
