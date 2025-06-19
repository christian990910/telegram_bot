# python3 -m venv venv
# source venv/bin/activate
import re
import time
import os
from telegram import Update
from telegram.ext import (
    Updater,
    MessageHandler,
    CallbackContext,
    Filters
)
from telegram.error import NetworkError, TimedOut, TelegramError

os.environ['TZ'] = 'UTC'

# 群组/用户ID配置
GROUP_A_ID = -4728363656
GROUP_B_ID = -4616403376
GROUP_C_ID = -4684453890
GROUP_D_ID = -4912623611
USER_ID = 1469613013

def clean_mentions(text: str) -> str:
    return re.sub(r'@\w+', '', text).strip()

def safe_send_message(bot, chat_id, text, max_retries=3):
    """安全发送消息，带重试机制"""
    for attempt in range(max_retries):
        try:
            bot.send_message(chat_id=chat_id, text=text)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                print(f"❌ 发送消息失败（重试{max_retries}次）: {e}")
                return False
            print(f"⚠️ 网络错误，{2}秒后重试 ({attempt + 1}/{max_retries}): {e}")
            time.sleep(2)
        except TelegramError as e:
            print(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            print(f"❌ 未知错误: {e}")
            return False

def safe_send_photo(bot, chat_id, photo, caption="", max_retries=3):
    """安全发送图片，带重试机制"""
    for attempt in range(max_retries):
        try:
            bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                print(f"❌ 发送图片失败（重试{max_retries}次）: {e}")
                return False
            print(f"⚠️ 网络错误，{2}秒后重试 ({attempt + 1}/{max_retries}): {e}")
            time.sleep(2)
        except TelegramError as e:
            print(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            print(f"❌ 未知错误: {e}")
            return False

def safe_send_document(bot, chat_id, document, caption="", max_retries=3):
    """安全发送文档，带重试机制"""
    for attempt in range(max_retries):
        try:
            bot.send_document(chat_id=chat_id, document=document, caption=caption)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                print(f"❌ 发送文档失败（重试{max_retries}次）: {e}")
                return False
            print(f"⚠️ 网络错误，{2}秒后重试 ({attempt + 1}/{max_retries}): {e}")
            time.sleep(2)
        except TelegramError as e:
            print(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            print(f"❌ 未知错误: {e}")
            return False

def safe_send_voice(bot, chat_id, voice, max_retries=3):
    """安全发送语音，带重试机制"""
    for attempt in range(max_retries):
        try:
            bot.send_voice(chat_id=chat_id, voice=voice)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                print(f"❌ 发送语音失败（重试{max_retries}次）: {e}")
                return False
            print(f"⚠️ 网络错误，{2}秒后重试 ({attempt + 1}/{max_retries}): {e}")
            time.sleep(2)
        except TelegramError as e:
            print(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            print(f"❌ 未知错误: {e}")
            return False

def safe_send_video(bot, chat_id, video, caption="", max_retries=3):
    """安全发送视频，带重试机制"""
    for attempt in range(max_retries):
        try:
            bot.send_video(chat_id=chat_id, video=video, caption=caption)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt == max_retries - 1:
                print(f"❌ 发送视频失败（重试{max_retries}次）: {e}")
                return False
            print(f"⚠️ 网络错误，{2}秒后重试 ({attempt + 1}/{max_retries}): {e}")
            time.sleep(2)
        except TelegramError as e:
            print(f"❌ Telegram错误: {e}")
            return False
        except Exception as e:
            print(f"❌ 未知错误: {e}")
            return False

def relay(update: Update, context: CallbackContext):
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
                safe_send_message(context.bot, target_id, f"{user_label}：{text}")
            elif msg.photo:
                photo = msg.photo[-1]
                caption = clean_mentions(msg.caption or "")
                safe_send_photo(context.bot, target_id, photo.file_id, f"{user_label}：{caption}")
            elif msg.document:
                caption = clean_mentions(msg.caption or "")
                safe_send_document(context.bot, target_id, msg.document.file_id, f"{user_label}：{caption}")
            elif msg.voice:
                safe_send_message(context.bot, target_id, f"{user_label} 发送了语音：")
                safe_send_voice(context.bot, target_id, msg.voice.file_id)
            elif msg.video:
                caption = clean_mentions(msg.caption or "")
                safe_send_message(context.bot, target_id, f"{user_label} 发送了视频：{caption}")
                safe_send_video(context.bot, target_id, msg.video.file_id, caption)
            else:
                print("⚠️ 未处理的私聊消息类型:", msg)
        except Exception as e:
            print("⚠️ 私聊转发异常：", e)
        return

    # 群转发逻辑
    if target_id:
        try:
            if msg.text:
                text = clean_mentions(msg.text)
                safe_send_message(context.bot, target_id, text)
            elif msg.photo:
                photo = msg.photo[-1]
                caption = clean_mentions(msg.caption or "")
                safe_send_photo(context.bot, target_id, photo.file_id, caption)
            elif msg.document:
                caption = clean_mentions(msg.caption or "")
                safe_send_document(context.bot, target_id, msg.document.file_id, caption)
            elif msg.voice:
                safe_send_voice(context.bot, target_id, msg.voice.file_id)
            elif msg.video:
                caption = clean_mentions(msg.caption or "")
                safe_send_video(context.bot, target_id, msg.video.file_id, caption)
            else:
                print("⚠️ 未处理的群消息类型:", msg)
        except Exception as e:
            print("⚠️ 群消息转发异常：", e)

def main():
    # 创建 Updater（旧版本兼容）
    updater = Updater(
        token="7925148285:AAEARkb-2OSo1OsYK73aqA0y_fi_KVEtiyg", 
        use_context=True
    )
    
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.all, relay))

    print("✅ Bot 正在启动...")
    
    # 启动时增加重试机制
    max_startup_retries = 5
    for attempt in range(max_startup_retries):
        try:
            print(f"🔄 启动尝试 {attempt + 1}/{max_startup_retries}")
            # 使用较长的超时时间
            updater.start_polling(timeout=60, clean=True)
            print("✅ Bot 已成功启动并监听消息... 按 Ctrl+C 可安全终止")
            break
        except (NetworkError, TimedOut) as e:
            if attempt == max_startup_retries - 1:
                print(f"❌ 启动失败，已重试 {max_startup_retries} 次: {e}")
                print("💡 建议检查网络连接或使用VPN")
                return
            print(f"⚠️ 启动失败，{10} 秒后重试: {e}")
            time.sleep(10)
        except Exception as e:
            print(f"❌ 启动时发生未知错误: {e}")
            return
    
    try:
        updater.idle()
    except (NetworkError, TimedOut) as e:
        print(f"⚠️ 运行时网络错误: {e}")
        print("🔄 Bot 将尝试重新连接...")

if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        print("🚫 Bot 已终止")
    except Exception as e:
        print(f"❌ 程序异常退出: {e}")