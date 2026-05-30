# 변경 이력

## 2026-05-30

### 신한체크승인 SMS 파서 업데이트
- 변경된 SMS 형식(`승인금액:`, `가맹점명:` 라벨 형식)을 파싱하지 못하던 문제 수정
- 금액 regex: `(금액)800원`과 `승인금액: 800원` 둘 다 매칭하도록 변경
- 가맹점 regex: `가맹점명:` 라벨 형식 우선 매칭, 기존 형식 fallback

### 거래 삭제 기능 수정
- 삭제 버튼 클릭 시 실제 삭제가 되지 않던 버그 수정
- 원인: `app.mount("/peach_treasury", StaticFiles(...))` 가 `/peach_treasury/*` 경로를 통째로 가로채 DELETE 요청이 StaticFiles로 빠짐
- 수정: mount 제거, `@router.get("/")` 라우트로 `index.html` 직접 서빙
- `@app.exception_handler` 데코레이터 `@` 누락 수정
- `contetn` → `content` 오타 수정

### 체크카드 중복 거래 방지 로직 수정
- 체크카드 결제 시 카드승인 + 출금알림이 동시에 들어와 이중 기록되던 버그 수정
- 원인: `[신한 슈퍼SOL]` 멀티라인 블록(line 107)이 출금 알림을 먼저 처리하여 중복 방지 로직(line 132)에 도달하지 못함
- 수정: 멀티라인 블록 내 출금 분기에 카드 중복 체크 추가, 기존 dead code 제거

### 백업 파일 정리 및 git 도입
- `main0.py`, `main.py'`, `main.py.save`, `static/index0.html` 삭제
- git 초기화 및 `.gitignore` 생성 (`.env`, `__pycache__/`, `*.log`, `*.pyc`)
- 버전 관리를 수동 백업에서 git으로 전환

### CLAUDE.md 작성
- 프로젝트 아키텍처, 실행 방법, DB 스키마, API 엔드포인트, 개발 주의사항 정리
