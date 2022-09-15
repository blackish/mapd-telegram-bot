#! /usr/bin/env python3
import logging
import asyncio
import datetime
from telegram import Bot, ReplyKeyboardRemove, Message
from telegram.error import Forbidden, NetworkError
import sysv_ipc
import json
import argparse

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
sm = sysv_ipc.SharedMemory(2015)
CHAT_ID = 0
TOKEN = "0"

async def parse_message(msg: Message):
    global sm
    if msg.text.lower() == "ping":
        await msg.reply_text("bot is alive")
    elif msg.text.lower() == "status":
        data = sm.read()
        raw = data.decode('utf-8').strip('\x00')
        txt = raw.strip('{} ')
        endstr = txt.find('_flagUnet2')-2
        txt = "{"+txt[:endstr]+"}"
        j = json.loads(txt)
        if j['_MODE'] == "3":
            reply = "Mode: power from grid\n"
        elif j['_MODE'] == "4":
            reply = "Mode: Charging\n"
        else:
            reply = "Mode: No power from grid\n"
        reply += f"Unet: {j['_UNET']}\nInet: {j['_INET_16_4']}\nUout: {j['_UOUTmed']}\nPnet: {j['_PNET']}\nUacc: {j['_Uacc']}\nIacc: {j['_IAcc_med_A_u16']}"
        await msg.reply_text(reply)

async def main():
    global sm, CHAT_ID, TOKEN
    mapd = False
    Uinput = False
    date_loss = datetime.datetime.now()
    async with Bot(TOKEN) as bot:
        last_update = 0
        while True:
            try:
                updates = (await bot.get_updates(offset=last_update))
                for i in updates:
                    last_update = i.update_id+1
                    if int(i.message.chat.id) == int(CHAT_ID):
                        await parse_message(i.message)
            except Exception as e:
                print(e)
            await asyncio.sleep(5)
            data = sm.read()
            raw = data.decode('utf-8').strip('\x00')
            txt = raw.strip('{} ')
            endstr = txt.find('_flagUnet2')-2
            txt = "{"+txt[:endstr]+"}"
            try:
                j = json.loads(txt)
                now = datetime.datetime.now()
                last_check = datetime.datetime.strptime(f"{now.year}-{now.month}-{now.day} {j['time']}","%Y-%m-%d %H:%M:%S")
            except Exception:
                await bot.send_message(CHAT_ID,f"Failed to parse data: {txt}")
                continue
            try:
                if (now-last_check).seconds > 3600 and mapd:
                    await bot.send_message(CHAT_ID, "MAPD is probably dead. Please fix")
                    mapd = False
                if (now-last_check).seconds < 3600 and not mapd:
                    await bot.send_message(CHAT_ID, "MAPD is back to normal")
                    mapd = True
                if not j["_MODE"] in ("3","4") and Uinput:
                    date_loss = datetime.datetime.now()
                    Uinput = False
                    await bot.send_message(CHAT_ID,f"Lost power from grid at {date_loss} UTC")
                if j["_MODE"] in ("3","4") and not Uinput:
                    date_loss = datetime.datetime.now()
                    await bot.send_message(CHAT_ID,f"Power from grid restored at {date_loss} UTC\nUacc: {j['_Uacc']}")
                    Uinput = True
                if not j["_MODE"] in ("3","4") and not Uinput:
                    diff = datetime.datetime.now() - date_loss
                    if diff.seconds%600 == 0:
                        await bot.send_message(CHAT_ID,f"No power from grid.\nUacc: {j['_Uacc']}\nIacc: {j['_IAcc_med_A_u16']}")
            except Exception as e:
                await bot.send_message(CHAT_ID,f"Exception {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", "-t", help="token")
    parser.add_argument("--chatid", "-c", help="chatid")
    args = parser.parse_args()
    CHAT_ID = args.chatid
    TOKEN = args.token
    asyncio.run(main())
