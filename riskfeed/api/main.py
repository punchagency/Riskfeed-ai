from fastapi import FastAPI
from riskfeed.api.routes import router

app = FastAPI(title="RiskFeed Assistant", version="0.1.0")

app.include_router(router)