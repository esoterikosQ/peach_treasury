from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import psycopg2
import os
from dotenv import load_dotenv
import re
import traceback

# 프론트엔드 구현
from fastapi.responses import FileResponse

# 서브패스 구현
from fastapi import APIRouter

# 로그에 타임스탬프 추가
import logging
import sys

error_logger = logging.getLogger("peach_error")
error_handler = logging.StreamHandler(sys.stderr)
error_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
error_logger.addHandler(error_handler)
error_logger.setLevel(logging.ERROR)


# 환경변수 불러오기
load_dotenv()

# 서브패스 방식으로 접속
#app = FastAPI(root_path="/")
app = FastAPI()
router = APIRouter(prefix="/peach_treasury")

def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def get_balance():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM transactions ORDER BY tx_date DESC LIMIT 1")
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("SELECT value FROM settings WHERE key='initial_balance'")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else 0


def parse_message(text: str):

    # [신한 슈퍼SOL] 카드 사용 형식
    if "[신한 슈퍼SOL]" in text and "2363" in text and "사용" in text:
        amount_match = re.search(r'사용\s+([\d,]+)원', text)
        if not amount_match:
            return None
        amount = int(amount_match.group(1).replace(',', ''))
        date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})\s+(\d{2}:\d{2})', text)
        if date_match:
            tx_date = datetime.strptime(f"{date_match.group(1)} {date_match.group(2)}", "%Y.%m.%d %H:%M")
        else:
            tx_date = datetime.now()
        lines = text.strip().split('\n')
        merchant = ""
        for i, line in enumerate(lines):
            if '사용' in line:
                if i > 0:
                    merchant = lines[i-1].strip()
                break
        return {"type": "card", "amount": amount, "merchant": merchant, "counterpart": None, "tx_date": tx_date, "description": merchant}

    # [신한체크승인] 형식 — 체크카드 결제
    if "[신한체크승인]" in text and "2363" in text:
        amount_match = re.search(r'(?:\(금액\)|승인금액:\s*)([\d,]+)원', text)
        if not amount_match:
            return None
        amount = int(amount_match.group(1).replace(',', ''))
        date_match = re.search(r'(\d{2}/\d{2})\s+(\d{2}:\d{2})', text)
        if date_match:
            tx_date = datetime.strptime(f"2026/{date_match.group(1)} {date_match.group(2)}", "%Y/%m/%d %H:%M")
        else:
            tx_date = datetime.now()
        merchant_match = re.search(r'가맹점명:\s*(.+)', text)
        if not merchant_match:
            merchant_match = re.search(r'원\s+(.+)$', text)
        merchant = merchant_match.group(1).strip() if merchant_match else ""
        return {"type": "card", "amount": amount, "merchant": merchant, "counterpart": None, "tx_date": tx_date, "description": merchant}

    # 신한카드 승인 (기존 형식)
    if "신한카드" in text and "2363" in text and "승인" in text:
        amount_match = re.search(r'([\d,]+)원\(일시불\)', text)
        if not amount_match:
            return None
        amount = int(amount_match.group(1).replace(',', ''))
        merchant_match = re.search(r'\d{2}:\d{2}\s+(.+?)\s+누적', text)
        merchant = merchant_match.group(1) if merchant_match else ""
        date_match = re.search(r'(\d{2}/\d{2}\s+\d{2}:\d{2})', text)
        tx_date = datetime.strptime(f"2026/{date_match.group(1)}", "%Y/%m/%d %H:%M") if date_match else datetime.now()
        return {"type": "card", "amount": amount, "merchant": merchant, "counterpart": None, "tx_date": tx_date, "description": merchant}

    # [신한 슈퍼SOL] 멀티라인 형식
    if "[신한 슈퍼SOL]" in text and "80001" in text:
        is_deposit = "입금" in text
        amount_match = re.search(r'(?:입금|출금)\s+([\d,]+)\s*(?:KRW|원)', text)
        if not amount_match:
            return None
        amount = int(amount_match.group(1).replace(',', ''))
        date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})\s+(\d{2}:\d{2})', text)
        if date_match:
            tx_date = datetime.strptime(f"{date_match.group(1)} {date_match.group(2)}", "%Y.%m.%d %H:%M")
        else:
            tx_date = datetime.now()
        counterpart = ""
        lines = text.strip().split('\n')
        for i, line in enumerate(lines):
            if '입금' in line or '출금' in line:
                if i>0:
                    counterpart = lines[i-1].strip()
                break

        # 출금이면 체크카드 중복 여부 확인
        if not is_deposit:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT id FROM transactions
                WHERE type='card' AND amount=%s
                AND tx_date BETWEEN %s - INTERVAL '5 minutes' AND %s + INTERVAL '5 minutes'
            """, (amount, tx_date, tx_date))
            dup = cur.fetchone()
            conn.close()
            if dup:
                return None

        return {"type": "deposit" if is_deposit else "withdrawal", "amount": amount, "counterpart": counterpart, "tx_date": tx_date, "merchant": None, "description": counterpart}

    # 기존 입금 형식
    if "입금" in text and "80001" in text:
        # "용돈"이라는 메시지가 들어가지 않은 입금 내역은 스킵
        if "용돈" not in text:
            return None
        amount_match = re.search(r'입금\s*([\d,]+)원', text)
        if not amount_match:
            return None
        amount = int(amount_match.group(1).replace(',', ''))
        counterpart_match = re.search(r'원\s+(.+?)\s+\d{3}-', text)
        counterpart = counterpart_match.group(1) if counterpart_match else ""
        date_match = re.search(r'(\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})', text)
        tx_date = datetime.strptime(date_match.group(1), "%Y.%m.%d %H:%M:%S") if date_match else datetime.now()
        return {"type": "deposit", "amount": amount, "counterpart": counterpart, "tx_date": tx_date, "merchant": None, "description": counterpart}

    return None

class TelegramWebhook(BaseModel):
    message: dict

class ManualTransaction(BaseModel):
    type: str
    amount: int
    description: str = ""
    merchant: str = ""
    tx_date: datetime = None
    note: str = ""

class BalanceAdjustment(BaseModel):
    balance: int
    reason: str = ""

@router.post("/webhook/telegram")
async def telegram_webhook(data: TelegramWebhook):
    text = data.message.get("text", "")
    print(f"수신 메시지: {text}")
    parsed = parse_message(text)
    print(f"파싱 결과: {parsed}")
    if not parsed:
        return {"ok": True, "skipped": True}

    balance = get_balance()
    if parsed["type"] == "deposit":
        new_balance = balance + parsed["amount"]
    else:
        new_balance = balance - parsed["amount"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions (type, amount, balance, description, merchant, counterpart, tx_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        parsed["type"], parsed["amount"], new_balance,
        #text[:255], parsed.get("merchant"), parsed.get("counterpart"), parsed["tx_date"]
        parsed.get("description", text[:255]), parsed.get("merchant"), parsed.get("counterpart"), parsed["tx_date"]

    ))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/transaction/manual")
async def add_manual(tx: ManualTransaction):
    balance = get_balance()
    if tx.type == "deposit":
        new_balance = balance + tx.amount
    else:
        new_balance = balance - tx.amount
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions (type, amount, balance, description, tx_date, is_manual, note)
        VALUES (%s, %s, %s, %s, %s, TRUE, %s)
    """, (tx.type, tx.amount, new_balance, tx.description, tx.tx_date or datetime.now(), tx.note))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.post("/balance/adjust")
async def adjust_balance(adj: BalanceAdjustment):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO balance_adjustments (balance, reason) VALUES (%s, %s)", (adj.balance, adj.reason))
    cur.execute("""
        INSERT INTO transactions (type, amount, balance, description, tx_date, is_manual, note)
        VALUES ('manual', 0, %s, '잔액 보정', NOW(), TRUE, %s)
    """, (adj.balance, adj.reason))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.get("/transactions")
async def get_transactions(limit: int = 50, offset: int = 0):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, type, amount, balance, description, merchant, counterpart, tx_date, is_manual, note
        FROM transactions ORDER BY tx_date DESC LIMIT %s OFFSET %s
    """, (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "type": r[1], "amount": r[2], "balance": r[3],
             "description": r[4], "merchant": r[5], "counterpart": r[6],
             "tx_date": r[7], "is_manual": r[8], "note": r[9]} for r in rows]

@router.get("/balance")
async def current_balance():
    return {"balance": get_balance()}

@router.get("/summary")
async def summary(period: str = "month"):
    conn = get_db()
    cur = conn.cursor()
    if period == "week":
        where = "tx_date >= NOW() - INTERVAL '7 days'"
    elif period == "month":
        where = "tx_date >= DATE_TRUNC('month', NOW())"
    elif period == "3month":
        where = "tx_date >= NOW() - INTERVAL '90 days'"
    else:
        where = "1=1"
    cur.execute(f"""
        SELECT 
            COALESCE(SUM(CASE WHEN type='deposit' THEN amount ELSE 0 END), 0) as total_in,
            COALESCE(SUM(CASE WHEN type IN ('withdrawal','card','manual') AND amount > 0 THEN amount ELSE 0 END), 0) as total_out,
            COUNT(*) as cnt
        FROM transactions WHERE {where}
    """)
    row = cur.fetchone()
    cur.execute(f"""
        SELECT merchant, SUM(amount) as total
        FROM transactions 
        WHERE type='card' AND {where}
        GROUP BY merchant ORDER BY total DESC LIMIT 10
    """)
    merchants = cur.fetchall()
    conn.close()
    return {
        "total_in": row[0], "total_out": row[1], "count": row[2],
        "merchants": [{"name": m[0], "amount": m[1]} for m in merchants]
    }

@router.get("/test-error")
async def test_error():
    raise Exception("테스트 에러")

# 거래내역 삭제 엔드포인트
@router.delete("/transactions/{tx_id}")
async def delete_transaction(tx_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM transactions WHERE id = %s", (tx_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.get("/")
async def serve_index():
    return FileResponse("static/index.html")

from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    error_logger.error(f"{request.url.path} - {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=True, log_config={
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "access": {
                "format": "%(asctime)s %(levelname)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "default": {"formatter": "default", "class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
            "error": {"formatter": "default", "class": "logging.StreamHandler", "stream": "ext://sys.stderr"},
            "access": {"formatter": "access", "class": "logging.StreamHandler", "stream": "ext://sys.stdout"}
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.error": {"handlers": ["error"], "level": "INFO"},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False}
        }
    })
