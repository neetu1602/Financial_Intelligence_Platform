from fastapi import FastAPI

app = FastAPI(title="Financial Intelligence Platform")


@app.get("/health")
def health_check():
    return {"status": "ok"}
