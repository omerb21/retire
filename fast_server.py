"""
Fast simple server for testing
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/v1/health")
def health_v1():
    return {"status": "ok"}

@app.get("/api/v1/clients/{client_id}/pension-funds")
def get_pension_funds(client_id: int):
    return [
        {
            "id": 1,
            "fund_name": "קצבה",
            "fund_type": None,
            "input_mode": "manual",
            "balance": None,
            "annuity_factor": None,
            "pension_amount": 5000.0,
            "pension_start_date": "2025-01-01",
            "indexation_method": "none",
            "fixed_index_rate": 0.0,
            "client_id": client_id
        }
    ]

@app.get("/api/v1/clients/{client_id}/capital-assets/")
def get_capital_assets(client_id: int):
    return []

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8005)
