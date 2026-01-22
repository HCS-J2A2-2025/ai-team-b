# backend/yacht_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from collections import Counter
import random

router = APIRouter(prefix="/api/yacht", tags=["yacht"])

CATEGORIES = [
    "ヨット","ビッグストレート","スモールストレート","フォーナンバーズ","フルハウス","チョイス",
    "シックス","ファイブ","フォー","スリー","デュース","エース",
]
UPPER_MAP = {"エース":1,"デュース":2,"スリー":3,"フォー":4,"ファイブ":5,"シックス":6}

def score_category(dice, category: str) -> int:
    dice = sorted(dice)
    cnt = Counter(dice)
    total = sum(dice)

    if category in UPPER_MAP:
        n = UPPER_MAP[category]
        return n * cnt[n]
    if category == "チョイス":
        return total
    if category == "ヨット":
        return 50 if len(cnt) == 1 else 0
    if category == "ビッグストレート":
        return 30 if dice == [1,2,3,4,5] or dice == [2,3,4,5,6] else 0
    if category == "スモールストレート":
        s = set(dice)
        runs = [{1,2,3,4},{2,3,4,5},{3,4,5,6}]
        return 15 if any(r.issubset(s) for r in runs) else 0
    if category == "フルハウス":
        vals = sorted(cnt.values())
        return total if vals == [2,3] else 0
    if category == "フォーナンバーズ":
        return total if max(cnt.values()) >= 4 else 0
    raise ValueError("Unknown category")

def roll5():
    return [random.randint(1,6) for _ in range(5)]

def reroll(dice, keep_idx: set[int]):
    out = []
    for i in range(5):
        out.append(dice[i] if i in keep_idx else random.randint(1,6))
    return out

class StartRes(BaseModel):
    dice: list[int]
    rolls_left: int

class RerollReq(BaseModel):
    dice: list[int]
    keep: list[int]  # 残すindex (0-4)
    rolls_left: int

class RerollRes(BaseModel):
    dice: list[int]
    rolls_left: int

class ScoreReq(BaseModel):
    dice: list[int]
    category: str

class ScoreRes(BaseModel):
    category: str
    score: int

@router.get("/start", response_model=StartRes)
def start():
    return {"dice": roll5(), "rolls_left": 2}

@router.post("/reroll", response_model=RerollRes)
def do_reroll(req: RerollReq):
    if req.rolls_left <= 0:
        raise HTTPException(status_code=400, detail="No rerolls left")
    keep = set(req.keep)
    if any(i < 0 or i > 4 for i in keep):
        raise HTTPException(status_code=400, detail="keep index must be 0-4")
    return {"dice": reroll(req.dice, keep), "rolls_left": req.rolls_left - 1}

@router.post("/score", response_model=ScoreRes)
def score(req: ScoreReq):
    if req.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown category")
    return {"category": req.category, "score": score_category(req.dice, req.category)}
