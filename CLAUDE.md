# Peach Treasury — 용돈 관리 시스템

개인 금융(용돈) 추적 시스템. 신한은행 SMS를 텔레그램 봇으로 수신하여 자동으로 거래내역을 기록하고, 웹 대시보드에서 조회/관리한다.

## 아키텍처

```
신한은행 SMS → 텔레그램 → bot.py (폴링) → FastAPI (main.py) → PostgreSQL
                                                    ↑
                                          웹 대시보드 (static/index.html)
```

- **main.py** — FastAPI 백엔드 서버 (포트 8000). API 라우팅, SMS 파싱, DB CRUD
- **bot.py** — 텔레그램 봇. 메시지를 수신하여 FastAPI webhook으로 전달
- **static/index.html** — 바닐라 JS SPA 프론트엔드 (Chart.js 사용)
- **log_config.py** — 로깅 설정 모듈

## 실행

```bash
# API 서버
python main.py          # 0.0.0.0:8000

# 텔레그램 봇 (별도 프로세스)
python bot.py
```

## 의존성

Python 3.14+, PostgreSQL. 패키지: fastapi, uvicorn, psycopg2, pydantic, requests, python-telegram-bot, httpx, python-dotenv

## DB 스키마

- **transactions** — id, type(deposit|withdrawal|card|manual), amount, balance, description, merchant, counterpart, tx_date, is_manual, note
- **balance_adjustments** — balance, reason
- **settings** — key, value (initial_balance 등)

## API 엔드포인트 (prefix: `/peach_treasury`)

| Method | Path | 설명 |
|--------|------|------|
| GET | /balance | 현재 잔액 |
| GET | /transactions?limit=&offset= | 거래내역 목록 |
| GET | /summary?period=week\|month\|3month\|all | 기간별 요약 + 가맹점 통계 |
| POST | /webhook/telegram | 텔레그램 메시지 수신 |
| POST | /transaction/manual | 수동 거래 입력 |
| POST | /balance/adjust | 잔액 보정 |
| DELETE | /transactions/{tx_id} | 거래 삭제 |

## 코드 컨벤션

- 한국어 주석 사용
- 변수/함수명은 영어 snake_case
- 프론트엔드 텍스트는 한국어
- SMS 파싱은 `parse_message()` 함수에 집중 — 신한은행 포맷별로 분기

## 개발 시 주의사항

- `.env`에 DB 접속정보와 텔레그램 토큰이 있음 — 커밋 금지
- `main0.py`, `main.py'`, `main.py.save`는 백업 파일 — 건드리지 말 것
- SMS 파싱(`parse_message`)에 연도 "2026"이 하드코딩되어 있음 (line 87, 103)
- 체크카드 결제 시 카드승인 + 출금알림이 동시에 옴 → 중복 방지 로직 있음 (line 132-162)
- `summary` 엔드포인트의 f-string SQL은 `period` 값이 코드 내에서 분기되므로 사용자 입력이 직접 들어가지 않음
- DB 커넥션은 요청마다 새로 생성 — 커넥션 풀링 없음
- 프론트엔드는 30초 간격 폴링으로 자동 새로고침
- `global_exception_handler`에 `contetn` 오타 있음 (line 326) — `content`이어야 함
- 이 시스템은 24/7 운영 중 — 서버 재시작이나 DB 스키마 변경 시 주의
