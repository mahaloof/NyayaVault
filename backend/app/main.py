import logging
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError,OperationalError
from app.config import settings
from app.routers import auth,cases,evidence,reporting,assistant
app=FastAPI(title="NyayaVault",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins.split(","),allow_methods=["GET","POST","PUT"],allow_headers=["Authorization","Content-Type"])
for router in (auth.router,cases.router,evidence.router,reporting.router,assistant.router): app.include_router(router)
@app.middleware("http")
async def headers(request,call_next):
    response=await call_next(request);response.headers["X-Content-Type-Options"]="nosniff";response.headers["Cache-Control"]="no-store";return response
@app.exception_handler(IntegrityError)
async def conflict(request,exc): return JSONResponse(status_code=409,content={"detail":"A record with this identifier already exists or conflicts with a relationship"})
@app.exception_handler(OperationalError)
async def unavailable(request,exc): return JSONResponse(status_code=503,content={"detail":"Database temporarily unavailable; retry shortly"})
@app.exception_handler(Exception)
async def unexpected(request,exc):
    logging.exception("Unhandled request failure",exc_info=exc)
    return JSONResponse(status_code=500,content={"detail":"The operation could not be completed"})
@app.get("/api/health")
def health(): return {"status":"ok","application":"NyayaVault"}
