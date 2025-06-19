# python3 -m venv venv
# source venv/bin/activate
# pip install python-telegram-bot
import re
import time
import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.error import NetworkError, TimedOut, TelegramError

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

os.environ['TZ'] = 'UTC'

# 群组/用户ID配置
GROUP_A_ID = -4728363656
GROUP_B_ID = -4616403376
GROUP_C_ID = -4684453890
GROUP_D_ID = -4912623611
USER_ID = 1469613013

def clean_mentions(text: str) -> str:
    """清理文本中的@提及"""
    if not text:
        return ""
    return re.sub(r'@\w+', '', text).strip()

async def safe_send_message(bot, chat_id, text, max_retries=3):
    """安全发送消息，带重试机制"""
    for attempt in range(max_retries):
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ 发送消息失败（重试{max_retries}次）: {e}")
                return False
            logger.warning(f"⚠️ 网络错误，2秒后重试 ({attempt + 1}/{max_retries}): {e}")
            await asyncio.sleep(2)
        except TelegramError as e:
            logger.error(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 未知错误: {e}")
            return False

async def safe_send_photo(bot, chat_id, photo, caption="", max_retries=3):
    """安全发送图片，带重试机制"""
    for attempt in range(max_retries):
        try:
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ 发送图片失败（重试{max_retries}次）: {e}")
                return False
            logger.warning(f"⚠️ 网络错误，2秒后重试 ({attempt + 1}/{max_retries}): {e}")
            await asyncio.sleep(2)
        except TelegramError as e:
            logger.error(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 未知错误: {e}")
            return False

async def safe_send_document(bot, chat_id, document, caption="", max_retries=3):
    """安全发送文档，带重试机制"""
    for attempt in range(max_retries):
        try:
            await bot.send_document(chat_id=chat_id, document=document, caption=caption)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ 发送文档失败（重试{max_retries}次）: {e}")
                return False
            logger.warning(f"⚠️ 网络错误，2秒后重试 ({attempt + 1}/{max_retries}): {e}")
            await asyncio.sleep(2)
        except TelegramError as e:
            logger.error(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 未知错误: {e}")
            return False

async def safe_send_voice(bot, chat_id, voice, max_retries=3):
    """安全发送语音，带重试机制"""
    for attempt in range(max_retries):
        try:
            await bot.send_voice(chat_id=chat_id, voice=voice)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ 发送语音失败（重试{max_retries}次）: {e}")
                return False
            logger.warning(f"⚠️ 网络错误，2秒后重试 ({attempt + 1}/{max_retries}): {e}")
            await asyncio.sleep(2)
        except TelegramError as e:
            logger.error(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 未知错误: {e}")
            return False

async def safe_send_video(bot, chat_id, video, caption="", max_retries=3):
    """安全发送视频，带重试机制"""
    for attempt in range(max_retries):
        try:
            await bot.send_video(chat_id=chat_id, video=video, caption=caption)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ 发送视频失败（重试{max_retries}次）: {e}")
                return False
            logger.warning(f"⚠️ 网络错误，2秒后重试 ({attempt + 1}/{max_retries}): {e}")
            await asyncio.sleep(2)
        except TelegramError as e:
            logger.error(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 未知错误: {e}")
            return False

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """消息转发处理函数"""
    msg = update.effective_message
    from_id = msg.chat.id
    chat_type = msg.chat.type
    target_id = None

    # 确定转发目标
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
                await safe_send_message(context.bot, target_id, f"{user_label}：{text}")
            elif msg.photo:
                photo = msg.photo[-1]
                caption = clean_mentions(msg.caption or "")
                await safe_send_photo(context.bot, target_id, photo.file_id, f"{user_label}：{caption}")
            elif msg.document:
                caption = clean_mentions(msg.caption or "")
                await safe_send_document(context.bot, target_id, msg.document.file_id, f"{user_label}：{caption}")
            elif msg.voice:
                await safe_send_message(context.bot, target_id, f"{user_label} 发送了语音：")
                await safe_send_voice(context.bot, target_id, msg.voice.file_id)
            elif msg.video:
                caption = clean_mentions(msg.caption or "")
                await safe_send_message(context.bot, target_id, f"{user_label} 发送了视频：{caption}")
                await safe_send_video(context.bot, target_id, msg.video.file_id, caption)
            else:
                logger.warning("⚠️ 未处理的私聊消息类型: %s", type(msg))
        except Exception as e:
            logger.error("⚠️ 私聊转发异常: %s", e)
        return

    # 群转发逻辑
    if target_id:
        try:
            if msg.text:
                text = clean_mentions(msg.text)
                await safe_send_message(context.bot, target_id, text)
            elif msg.photo:
                photo = msg.photo[-1]
                caption = clean_mentions(msg.caption or "")
                await safe_send_photo(context.bot, target_id, photo.file_id, caption)
            elif msg.document:
                caption = clean_mentions(msg.caption or "")
                await safe_send_document(context.bot, target_id, msg.document.file_id, caption)
            elif msg.voice:
                await safe_send_voice(context.bot, target_id, msg.voice.file_id)
            elif msg.video:
                caption = clean_mentions(msg.caption or "")
                await safe_send_video(context.bot, target_id, msg.video.file_id, caption)
            else:
                logger.warning("⚠️ 未处理的群消息类型: %s", type(msg))
        except Exception as e:
            logger.error("⚠️ 群消息转发异常: %s", e)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """错误处理函数"""
    logger.error("Update %s caused error %s", update, context.error)

def main():
    """主函数"""
    # 创建 Application
    application = Application.builder().token("7925148285:AAEARkb-2OSo1OsYK73aqA0y_fi_KVEtiyg").build()
    
    # 添加消息处理器
    application.add_handler(MessageHandler(filters.ALL, relay))
    
    # 添加错误处理器
    application.add_error_handler(error_handler)

    logger.info("✅ Bot 正在启动...")
    
    try:
        # 启动机器人
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"❌ 程序异常退出: {e}")

if __name__ == '__main__':
    import asyncio
    
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("🚫 Bot 已终止")
    except Exception as e:
        logger.error(f"❌ 程序异常退出: {e}")