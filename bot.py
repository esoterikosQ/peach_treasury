import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import httpx
from telegram.request import HTTPXRequest

# 로그에 타임스탬프 추가
import logging
import sys

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.getLogger("httpx").handlers=[]
logging.getLogger("telegram").handlers=[]

request = HTTPXRequest()

load_dotenv()

FASTAPI_URL = "http://localhost:8000/peach_treasury/webhook/telegram"
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    text = update.message.text or ""
    payload = {"message": {"text": text}}
    try:
        res = requests.post(FASTAPI_URL, json=payload)
        logging.info(f"전달 완료: {res.json()}") # print(f"전달 완료: {res.json()}")
    except Exception as e:
        logging.error(f"오류: {e}") # print(f"오류: {e}")

#app = ApplicationBuilder().token(TOKEN).build()
# app = ApplicationBuilder().token(TOKEN).request(request).build()

# app.add_handler(MessageHandler(filters.TEXT, handle_message))
# #print("봇 폴링 시작")
# logging.info("봇 폴링 시작")
# app.run_polling()

import asyncio

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    logging.info("봇 폴링 시작")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # 종료 시그널 대기
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
