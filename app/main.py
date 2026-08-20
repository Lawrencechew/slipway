from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import ServiceSpec
from .planner import create_plan, fingerprint_spec
import uvicorn

app = FastAPI(title="PavedPath API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/specs", status_code=201)
def create_spec(spec: ServiceSpec):
    # For v1 we keep specs in-memory or persist later
    # Validate basic fields
    if not spec.metadata.name:
        raise HTTPException(status_code=400, detail="metadata.name required")
    fp = fingerprint_spec(spec)
    return {"fingerprint": fp}


@app.post("/plans", status_code=201)
def plans_create(spec: ServiceSpec):
    plan = create_plan(spec)
    return plan.dict()


def run():
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
