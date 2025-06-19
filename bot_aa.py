import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          MessageHandler, ContextTypes, filters, ConversationHandler)
import pytz
from telegram.ext._jobqueue import JobQueue

# 初始化日志
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = "7535253577:AAEfChOGkCjD9hF7PkMWQ43eO-2gxeOf1VM"
USDT_ADDRESS = "YOUR_USDT_WALLET_ADDRESS"

# 简单内存积分存储（可替换为数据库）
user_points = {}
user_random_code = {}

# 状态
AWAIT_CODE, AWAIT_PURCHASE_AMOUNT, AWAIT_CONFIRM_PURCHASE = range(3)

# 签到生成随机数
def generate_code():
    return str(random.randint(1000, 9999))

# 菜单
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ 签到", callback_data="sign_in")],
        [InlineKeyboardButton("📊 查询积分", callback_data="check_points")],
        [InlineKeyboardButton("🏆 查询排名", callback_data="check_rank")],
        [InlineKeyboardButton("❓ 查询帮助", callback_data="help")],
        [InlineKeyboardButton("💰 购买积分", callback_data="buy_points")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("请选择操作：", reply_markup=reply_markup)

# 回调处理器
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "sign_in":
        code = generate_code()
        user_random_code[user_id] = code
        await query.message.reply_text(f"请输入以下验证码完成签到：\n\n`{code}`", parse_mode='Markdown')
        return AWAIT_CODE

    elif query.data == "check_points":
        points = user_points.get(user_id, 0)
        await query.message.reply_text(f"你当前的积分为：{points}")

    elif query.data == "check_rank":
        sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
        message = "🏆 当前积分排名：\n"
        for i, (uid, pts) in enumerate(sorted_users[:10], 1):
            name = context.bot.get_chat(uid).username or f"用户{uid}"
            message += f"{i}. {name} - {pts}分\n"
        await query.message.reply_text(message)

    elif query.data == "help":
        await query.message.reply_text("""
✅ 签到：系统给出验证码，输入正确即可获得积分。
📊 查询积分：查看你目前的积分。
🏆 查询排名：查看排行榜前十。
💰 购买积分：通过USDT支付购买。
""")

    elif query.data == "buy_points":
        await query.message.reply_text("请输入你要购买的积分数量（例如 100）：")
        return AWAIT_PURCHASE_AMOUNT

    return ConversationHandler.END

# 签到验证码输入处理
async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    input_code = update.message.text.strip()
    correct_code = user_random_code.get(user_id)

    if input_code == correct_code:
        user_points[user_id] = user_points.get(user_id, 0) + 10
        await update.message.reply_text("🎉 签到成功，积分 +10")
    else:
        await update.message.reply_text("❌ 验证码错误，签到失败。")
    return ConversationHandler.END

# 处理购买积分输入
async def handle_purchase_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text.strip())
        context.user_data['purchase_amount'] = amount
        price = amount * 0.1  # 每积分0.1 USDT
        await update.message.reply_text(
            f"你要购买 {amount} 积分，总价为 {price:.2f} USDT。\n"
            "确认购买请回复 `确认`，否则回复 `取消`。",
            parse_mode='Markdown'
        )
        return AWAIT_CONFIRM_PURCHASE
    except ValueError:
        await update.message.reply_text("请输入有效的数字。")
        return AWAIT_PURCHASE_AMOUNT

# 确认购买
async def handle_purchase_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "确认":
        amount = context.user_data.get('purchase_amount', 0)
        price = amount * 0.1
        await update.message.reply_text(
            f"请将 {price:.2f} USDT 转入以下地址，付款成功后管理员会为你加积分：\n\n`{USDT_ADDRESS}`",
            parse_mode='Markdown')
    else:
        await update.message.reply_text("已取消购买。")
    return ConversationHandler.END

# 取消处理
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("操作已取消。")
    return ConversationHandler.END

# 主函数
def main():
    

    
    app = ApplicationBuilder().token(TOKEN).job_queue(JobQueue).build()

    # 会话控制器
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_callback)],
        states={
            AWAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_code)],
            AWAIT_PURCHASE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_purchase_amount)],
            AWAIT_CONFIRM_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_purchase_confirmation)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == '__main__':
    main()
