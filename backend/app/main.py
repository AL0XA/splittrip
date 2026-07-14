"""FastAPI-сервер: события («тусовки»), участники, траты и расчёт долгов.

Авторизация — по подписи Telegram initData (заголовок X-Init-Data).
Денежные суммы наружу отдаются в рублях (float), внутри хранятся в копейках.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import database as db
from . import split
from .auth import validate_init_data
from .config import BOT_USERNAME, FRONTEND_DIR

app = FastAPI(title="Split Party Mini App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# ---------- Авторизация ----------

def current_user(x_init_data: str = Header(default="")) -> dict:
    user = validate_init_data(x_init_data)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid initData")
    db.upsert_user(user["id"], user.get("username"), user.get("first_name"))
    return user


def _require_member(event_id: int, user_id: int) -> dict:
    event = db.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if not db.is_member(event_id, user_id):
        raise HTTPException(status_code=403, detail="Not a member of this event")
    return event


# ---------- Представление данных ----------

def _display_name(u: dict) -> str:
    return u.get("username") or u.get("first_name") or f"user{u['user_id']}"


def _invite_link(code: str) -> str | None:
    if not BOT_USERNAME:
        return None
    return f"https://t.me/{BOT_USERNAME}?startapp={code}"


def _event_summary(event: dict) -> dict:
    return {
        "id": event["id"],
        "title": event["title"],
        "currency": event["currency"],
        "member_count": event.get("member_count", 0),
    }


def _event_detail(event: dict, me_id: int) -> dict:
    members = db.list_members(event["id"])
    expenses = db.list_expenses(event["id"])
    names = {m["user_id"]: _display_name(m) for m in members}
    member_ids = [m["user_id"] for m in members]

    net = split.compute_net(member_ids, expenses)
    transfers = split.settle(net)

    return {
        "id": event["id"],
        "title": event["title"],
        "currency": event["currency"],
        "owner_id": event["owner_id"],
        "code": event["code"],
        "invite_link": _invite_link(event["code"]),
        "me_id": me_id,
        "members": [
            {"user_id": m["user_id"], "name": names[m["user_id"]],
             "balance": net.get(m["user_id"], 0) / 100}
            for m in members
        ],
        "expenses": [
            {
                "id": e["id"],
                "payer_id": e["payer_id"],
                "payer_name": names.get(e["payer_id"], f"user{e['payer_id']}"),
                "amount": e["amount"] / 100,
                "description": e["description"],
                "participants": e["participants"],
                "participant_count": len(e["participants"]) or len(member_ids),
            }
            for e in expenses
        ],
        "settlement": [
            {
                "from_id": t["from"], "from_name": names.get(t["from"], "?"),
                "to_id": t["to"], "to_name": names.get(t["to"], "?"),
                "amount": t["amount"] / 100,
            }
            for t in transfers
        ],
    }


# ---------- События ----------

class CreateEventBody(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    currency: str = Field(default="₽", max_length=8)


@app.post("/api/events")
def create_event(body: CreateEventBody, user: dict = Depends(current_user)):
    event = db.create_event(body.title.strip(), user["id"], body.currency)
    return _event_detail(event, user["id"])


@app.get("/api/events")
def list_events(user: dict = Depends(current_user)):
    events = db.list_user_events(user["id"])
    return {"events": [_event_summary(e) for e in events]}


class JoinBody(BaseModel):
    code: str


@app.post("/api/events/join")
def join_event(body: JoinBody, user: dict = Depends(current_user)):
    event = db.get_event_by_code(body.code.strip())
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    db.add_member(event["id"], user["id"])
    return _event_detail(event, user["id"])


@app.get("/api/events/{event_id}")
def get_event(event_id: int = Path(...), user: dict = Depends(current_user)):
    event = _require_member(event_id, user["id"])
    return _event_detail(event, user["id"])


# ---------- Траты ----------

class ExpenseBody(BaseModel):
    amount: float = Field(gt=0)
    description: str = Field(min_length=1, max_length=140)
    payer_id: int | None = None
    participant_ids: list[int] | None = None


@app.post("/api/events/{event_id}/expenses")
def add_expense(event_id: int, body: ExpenseBody, user: dict = Depends(current_user)):
    event = _require_member(event_id, user["id"])
    member_ids = {m["user_id"] for m in db.list_members(event_id)}

    payer_id = body.payer_id or user["id"]
    if payer_id not in member_ids:
        raise HTTPException(status_code=400, detail="Payer is not a member")

    participants = body.participant_ids or list(member_ids)
    participants = [p for p in participants if p in member_ids]
    if not participants:
        raise HTTPException(status_code=400, detail="No valid participants")

    amount_cents = round(body.amount * 100)
    if amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    db.add_expense(event_id, payer_id, amount_cents, body.description.strip(), participants)
    return _event_detail(event, user["id"])


@app.delete("/api/events/{event_id}/expenses/{expense_id}")
def delete_expense(event_id: int, expense_id: int, user: dict = Depends(current_user)):
    event = _require_member(event_id, user["id"])
    expense = db.get_expense(expense_id)
    if expense is None or expense["event_id"] != event_id:
        raise HTTPException(status_code=404, detail="Expense not found")
    # Удалять может тот, кто внёс трату, или владелец события.
    if user["id"] not in (expense["payer_id"], event["owner_id"]):
        raise HTTPException(status_code=403, detail="Not allowed")
    db.delete_expense(expense_id)
    return _event_detail(event, user["id"])


# ---------- Статика фронтенда (монтируем последней) ----------
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
