import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, BotCommand, BotCommandScopeDefault
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          MessageHandler, ContextTypes, filters, ConversationHandler)
# 初始化日志
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Bot 配置
TOKEN = "7535253577:AAEfChOGkCjD9hF7PkMWQ43eO-2gxeOf1VM"  # 替换为你的 Bot Token
USDT_ADDRESS = "TSsNMAvZrEdJMxdV6rkT4Sb4c7C1uJvmaY"  # 替换为你的 USDT 钱包地址

# 内存存储（可替换为数据库）
user_points = {}  # {user_id: points}
user_random_code = {}  # {user_id: code}

# 状态定义
AWAIT_CODE, AWAIT_PURCHASE_AMOUNT, AWAIT_CONFIRM_PURCHASE = range(3)

# 生成四位数验证码
def generate_code():
    return str(random.randint(1000, 9999))

# 设置左下角菜单按钮（仅视觉效果）
async def set_menu_button(application):
    commands = [
        BotCommand("start", "启动 Bot"),
        BotCommand("help", "帮助信息"),
        BotCommand("sign_in", "签到"),
        BotCommand("check_points", "查询积分"),
    ]

    # 设置全局命令
    await application.bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeDefault()
    )

    # 设置左下角菜单按钮（必须是实例！）
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
# 启动命令
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

# 回调处理
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
            name = query.from_user.username or f"用户{uid}"
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

# 验证码验证
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

# 处理购买数量输入
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

# 确认购买并提供收款地址
async def handle_purchase_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "确认":
        amount = context.user_data.get('purchase_amount', 0)
        price = amount * 0.1
        await update.message.reply_text(
            f"你要购买 {amount} 积分，总价为 {price:.2f} USDT。\n"
            f"请将 USDT 发送到以下地址：\n\n`{USDT_ADDRESS}`\n\n"
            "付款完成后请联系管理员确认。",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("已取消购买。")
    return ConversationHandler.END

# 取消操作
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("操作已取消。")
    return ConversationHandler.END

# 管理员加积分命令
async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("用法：/addpoints <user_id> <amount>")
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        user_points[user_id] = user_points.get(user_id, 0) + amount
        await update.message.reply_text(f"✅ 已为用户 {user_id} 添加 {amount} 积分。")
    except ValueError:
        await update.message.reply_text("参数错误，请输入有效的用户ID和数量。")

# ...（前面的导入和配置不变）

# 新增命令处理函数
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
✅ 签到：系统给出验证码，输入正确即可获得积分。
📊 查询积分：查看你目前的积分。
🏆 查询排名：查看排行榜前十。
💰 购买积分：通过USDT支付购买。
""")

async def handle_sign_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = generate_code()
    user_random_code[user_id] = code
    await update.message.reply_text(f"请输入以下验证码完成签到：\n\n`{code}`", parse_mode='Markdown')
    return AWAIT_CODE

async def handle_check_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    points = user_points.get(user_id, 0)
    await update.message.reply_text(f"你当前的积分为：{points}")

async def handle_buy_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("请输入你要购买的积分数量（例如 100）：")
    return AWAIT_PURCHASE_AMOUNT

# 主函数
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_callback)],
        states={
            AWAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_code)],
            AWAIT_PURCHASE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_purchase_amount)],
            AWAIT_CONFIRM_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_purchase_confirmation)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("addpoints", add_points)
        ]
    )

    # 注册所有命令
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("sign_in", handle_sign_in))
    app.add_handler(CommandHandler("check_points", handle_check_points))
    app.add_handler(CommandHandler("buy_points", handle_buy_points))
    app.add_handler(conv_handler)

    # 设置菜单按钮（仅视觉）
    app.job_queue.run_once(set_menu_button, 1)

    print("✅ Bot 正在运行...")
    app.run_polling()

if __name__ == '__main__':
    main()