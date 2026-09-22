from datetime import date
from decimal import Decimal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Financial Intelligence Platform")


class TransactionCreate(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    merchant: str = Field(min_length=1, max_length=100)
    category: str
    transaction_date: date


class Transaction(TransactionCreate):
    id: int


transactions: dict[int, Transaction] = {}
next_id = 1


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/transactions", response_model=Transaction, status_code=201)
def create_transaction(payload: TransactionCreate):
    global next_id
    transaction = Transaction(id=next_id, **payload.model_dump())
    transactions[next_id] = transaction
    next_id += 1
    return transaction


@app.get("/transactions", response_model=list[Transaction])
def list_transactions(category: str | None = None):
    results = list(transactions.values())
    if category is not None:
        results = [t for t in results if t.category == category]
    return results


@app.get("/transactions/{transaction_id}", response_model=Transaction)
def get_transaction(transaction_id: int):
    transaction = transactions.get(transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@app.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int):
    transaction = transactions.pop(transaction_id, None)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction Not Found")
