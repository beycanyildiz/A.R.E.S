"""
Simple FastAPI Server for Testing
Minimal backend to test frontend connection
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="A.R.E.S. Test API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "A.R.E.S. Backend Running", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/stats")
async def stats():
    """Stats for frontend dashboard"""
    return {
        "total_missions": 5,
        "active_missions": 2,
        "success_rate": 0.73,
        "hosts_discovered": 12,
        "vulnerabilities_found": 8,
        "exploits_successful": 6
    }

if __name__ == "__main__":
    print("="*60)
    print("A.R.E.S. Test Backend Starting...")
    print("Frontend: http://localhost:3000")
    print("Backend API: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("="*60)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
