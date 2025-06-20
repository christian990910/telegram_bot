# python3 -m venv venv
# source venv/bin/activate
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, BotCommand, BotCommandScopeDefault
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          MessageHandler, ContextTypes, filters, ConversationHandler)

# 初始化日志
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Bot 配置
TOKEN = "7535253577:AAEfChOGkCjD9hF7PkMWQ43eO-2gxeOf1VM"
USDT_ADDRESS = "TSsNMAvZrEdJMxdV6rkT4Sb4c7C1uJvmaY"

# 内存存储
user_points = {}  # {user_id: points}
user_random_code = {}  # {user_id: code}
user_info = {}  # {user_id: {'username': username, 'first_name': first_name}}

# 状态定义
AWAIT_CODE, AWAIT_PURCHASE_AMOUNT, AWAIT_CONFIRM_PURCHASE = range(3)

# 生成四位数验证码
def generate_code():
    return str(random.randint(1000, 9999))

# 保存用户信息
def save_user_info(user):
    user_info[user.id] = {
        'username': user.username,
        'first_name': user.first_name or "未知用户"
    }

# 设置左下角菜单按钮
async def set_menu_button(context: ContextTypes.DEFAULT_TYPE):
    commands = [
        BotCommand("start", "启动 Bot"),
        BotCommand("help", "帮助信息"),
        BotCommand("sign_in", "签到"),
        BotCommand("check_points", "查询积分"),
        BotCommand("buy_points", "购买积分"),
    ]

    await context.bot.set_my_commands(commands=commands, scope=BotCommandScopeDefault())
    await context.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

# 启动命令
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_info(update.effective_user)
    keyboard = [
        [InlineKeyboardButton("✅ 签到", callback_data="sign_in")],
        [InlineKeyboardButton("📊 查询积分", callback_data="check_points")],
        [InlineKeyboardButton("🏆 查询排名", callback_data="check_rank")],
        [InlineKeyboardButton("❓ 查询帮助", callback_data="help")],
        [InlineKeyboardButton("💰 购买积分", callback_data="buy_points")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("欢迎使用积分系统！请选择操作：", reply_markup=reply_markup)

# 签到命令
async def sign_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_info(update.effective_user)
    user_id = update.effective_user.id
    code = generate_code()
    user_random_code[user_id] = code
    await update.message.reply_text(f"请输入以下验证码完成签到：\n\n`{code}`", parse_mode='Markdown')
    return AWAIT_CODE

# 查询积分命令
async def check_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_info(update.effective_user)
    user_id = update.effective_user.id
    points = user_points.get(user_id, 0)
    await update.message.reply_text(f"你当前的积分为：{points}")

# 购买积分命令
async def buy_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_info(update.effective_user)
    await update.message.reply_text("请输入你要购买的积分数量（例如 100）：")
    return AWAIT_PURCHASE_AMOUNT

# 回调处理
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    save_user_info(query.from_user)

    if query.data == "sign_in":
        code = generate_code()
        user_random_code[user_id] = code
        await query.message.reply_text(f"请输入以下验证码完成签到：\n\n`{code}`", parse_mode='Markdown')
        return AWAIT_CODE

    elif query.data == "check_points":
        points = user_points.get(user_id, 0)
        await query.message.reply_text(f"你当前的积分为：{points}")

    elif query.data == "check_rank":
        if not user_points:
            await query.message.reply_text("暂无积分排名数据。")
            return ConversationHandler.END
            
        sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
        message = "🏆 当前积分排名：\n"
        for i, (uid, pts) in enumerate(sorted_users[:10], 1):
            user_data = user_info.get(uid, {})
            username = user_data.get('username')
            first_name = user_data.get('first_name', '未知用户')
            
            if username:
                name = f"@{username}"
            else:
                name = first_name
                
            message += f"{i}. {name} - {pts}分\n"
        await query.message.reply_text(message)

    elif query.data == "help":
        await query.message.reply_text("""
📖 使用帮助：

✅ 签到：系统给出验证码，输入正确即可获得10积分
📊 查询积分：查看你目前的积分余额
🏆 查询排名：查看排行榜前十名
💰 购买积分：通过USDT支付购买积分（1积分=0.1USDT）

💡 提示：每次签到成功可获得10积分！
""")

    elif query.data == "buy_points":
        await query.message.reply_text("请输入你要购买的积分数量（例如 100）：")
        return AWAIT_PURCHASE_AMOUNT

    return ConversationHandler.END

# 验证码验证
async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user_info(update.effective_user)
    input_code = update.message.text.strip()
    correct_code = user_random_code.get(user_id)

    if input_code == correct_code:
        user_points[user_id] = user_points.get(user_id, 0) + 10
        await update.message.reply_text("🎉 签到成功！积分 +10")
        # 清除验证码
        user_random_code.pop(user_id, None)
    else:
        await update.message.reply_text("❌ 验证码错误，签到失败。请重新签到获取新的验证码。")
    return ConversationHandler.END

# 处理购买数量输入
async def handle_purchase_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("请输入大于0的积分数量。")
            return AWAIT_PURCHASE_AMOUNT
            
        context.user_data['purchase_amount'] = amount
        price = amount * 0.1
        await update.message.reply_text(
            f"你要购买 {amount} 积分，总价为 {price:.2f} USDT。\n\n"
            "确认购买请回复 `确认`\n"
            "取消购买请回复 `取消`",
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
            f"📋 购买订单详情：\n"
            f"积分数量：{amount}\n"
            f"总价：{price:.2f} USDT\n\n"
            f"💰 请将 {price:.2f} USDT 发送到以下地址：\n\n"
            f"`{USDT_ADDRESS}`\n\n"
            f"💡 付款完成后请联系管理员确认，积分将在确认后添加到您的账户。",
            parse_mode='Markdown'
        )
    elif text == "取消":
        await update.message.reply_text("❌ 已取消购买。")
    else:
        await update.message.reply_text("请回复 `确认` 或 `取消`")
        return AWAIT_CONFIRM_PURCHASE
    return ConversationHandler.END

# 取消操作
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ 操作已取消。")
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

# 帮助命令
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📖 使用帮助：

✅ 签到：系统给出验证码，输入正确即可获得10积分
📊 查询积分：查看你目前的积分余额
🏆 查询排名：查看排行榜前十名
💰 购买积分：通过USDT支付购买积分（1积分=0.1USDT）

💡 提示：每次签到成功可获得10积分！

🔧 管理员命令：
/addpoints <user_id> <amount> - 为指定用户添加积分
""")

# 主函数
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # 会话处理器
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_callback),
            CommandHandler("sign_in", sign_in),
            CommandHandler("buy_points", buy_points)
        ],
        states={
            AWAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_code)],
            AWAIT_PURCHASE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_purchase_amount)],
            AWAIT_CONFIRM_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_purchase_confirmation)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ]
    )

    # 添加处理器
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("check_points", check_points))
    app.add_handler(CommandHandler("addpoints", add_points))

    # 设置菜单按钮
    app.job_queue.run_once(set_menu_button, 1)

    print("✅ Bot 正在运行...")
    app.run_polling()

if __name__ == '__main__':
    main()