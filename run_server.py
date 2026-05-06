import sys
sys.path.insert(0, r"C:\Users\nvclo\Documents\ai_trading_final_project\.venv\Lib\site-packages")

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
