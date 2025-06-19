import re
import asyncio
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
    AIORateLimiter
)

os.environ['TZ'] = 'UTC'

# 群组/用户ID配置
GROUP_A_ID = -4728363656
GROUP_B_ID = -4616403376
GROUP_C_ID = -4912623611
GROUP_D_ID = -4912623611  # 请替换为 D 群实际 ID
USER_ID = 123456789       # 替换成你的个人 ID

def clean_mentions(text: str) -> str:
    return re.sub(r'@\w+', '', text).strip()

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    from_id = msg.chat.id
    chat_type = msg.chat.type
    target_id = None

    if from_id == GROUP_A_ID:
        target_id = GROUP_B_ID
    elif from_id == GROUP_B_ID:
        target_id = GROUP_A_ID
    elif from_id == GROUP_C_ID:
        target_id = GROUP_D_ID
    elif from_id == GROUP_D_ID:
        target_id = GROUP_C_ID
    elif chat_type == "private":
        sender = update.effective_user
        target_id = USER_ID
        user_label = f"{sender.full_name} ({sender.id})"

        try:
            if msg.text:
                text = clean_mentions(msg.text)
                await context.bot.send_message(chat_id=target_id, text=f"{user_label}：{text}")
            elif msg.photo:
                photo = msg.photo[-1]
                caption = clean_mentions(msg.caption or "")
                await context.bot.send_photo(chat_id=target_id, photo=photo.file_id, caption=f"{user_label}：{caption}")
            elif msg.document:
                caption = clean_mentions(msg.caption or "")
                await context.bot.send_document(chat_id=target_id, document=msg.document.file_id, caption=f"{user_label}：{caption}")
            elif msg.voice:
                await context.bot.send_message(chat_id=target_id, text=f"{user_label} 发送了语音：")
                await context.bot.send_voice(chat_id=target_id, voice=msg.voice.file_id)
            elif msg.video:
                caption = clean_mentions(msg.caption or "")
                await context.bot.send_message(chat_id=target_id, text=f"{user_label} 发送了视频：{caption}")
                await context.bot.send_video(chat_id=target_id, video=msg.video.file_id, caption=caption)
            else:
                print("⚠️ 未处理的私聊消息类型:", msg)
            await asyncio.sleep(4)
        except Exception as e:
            print("⚠️ 私聊转发异常：", e)
        return

    # 群转发逻辑
    try:
        if msg.text:
            text = clean_mentions(msg.text)
            await context.bot.send_message(chat_id=target_id, text=text)
        elif msg.photo:
            photo = msg.photo[-1]
            caption = clean_mentions(msg.caption or "")
            await context.bot.send_photo(chat_id=target_id, photo=photo.file_id, caption=caption)
        elif msg.document:
            caption = clean_mentions(msg.caption or "")
            await context.bot.send_document(chat_id=target_id, document=msg.document.file_id, caption=caption)
        elif msg.voice:
            await context.bot.send_voice(chat_id=target_id, voice=msg.voice.file_id)
        elif msg.video:
            caption = clean_mentions(msg.caption or "")
            await context.bot.send_video(chat_id=target_id, video=msg.video.file_id, caption=caption)
        else:
            print("⚠️ 未处理的群消息类型:", msg)
        await asyncio.sleep(4)
    except Exception as e:
        print("⚠️ 群消息转发异常：", e)

async def main():
    app = (
        ApplicationBuilder()
        .token("7925148285:AAEARkb-2OSo1OsYK73aqA0y_fi_KVEtiyg")
        .rate_limiter(AIORateLimiter())
        .build()
    )

    app.add_handler(MessageHandler(filters.ALL, relay))

    print("✅ Bot 已启动并监听消息... 按 Ctrl+C 可安全终止")

    await app.run_polling(shutdown_on_signals=True)  # 支持 Ctrl+C 安全退出

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🚫 Bot 已终止")
