import random
import logging
import mysql.connector
from mysql.connector import Error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, BotCommand, BotCommandScopeDefault
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          MessageHandler, ContextTypes, filters, ConversationHandler)
from datetime import datetime, date

# 初始化日志
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Bot 配置
TOKEN = "7535253577:AAEfChOGkCjD9hF7PkMWQ43eO-2gxeOf1VM"
USDT_ADDRESS = "TSsNMAvZrEdJMxdV6rkT4Sb4c7C1uJvmaY"

# 数据库配置
DB_CONFIG = {
    'host': '115.29.213.131',
    'database': 'dash-fastapi',
    'user': 'root',
    'password': 'RP$zk34ns#d',  # 请修改为您的MySQL密码
    'charset': 'utf8mb4',
    'autocommit': True
}

# 内存缓存（用于临时存储验证码）
user_random_code = {}  # {user_id: code}

# 状态定义
AWAIT_CODE, AWAIT_PURCHASE_AMOUNT, AWAIT_CONFIRM_PURCHASE = range(3)

# 数据库连接池
def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        logging.error(f"数据库连接错误: {e}")
        return None

# 初始化数据库表
def init_database():
    connection = get_db_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()
        
        # 创建用户表
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            first_name VARCHAR(255),
            points INT DEFAULT 0,
            last_sign_in DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
        
        # 创建签到记录表
        create_sign_in_table = """
        CREATE TABLE IF NOT EXISTS sign_in_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            sign_in_date DATE,
            points_earned INT DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE KEY unique_daily_sign_in (user_id, sign_in_date)
        )
        """
        
        # 创建购买记录表
        create_purchase_table = """
        CREATE TABLE IF NOT EXISTS purchase_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            points_amount INT,
            usdt_amount DECIMAL(10,2),
            status ENUM('pending', 'completed', 'cancelled') DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """
        
        cursor.execute(create_users_table)
        cursor.execute(create_sign_in_table)
        cursor.execute(create_purchase_table)
        
        logging.info("数据库表初始化成功")
        return True
        
    except Error as e:
        logging.error(f"初始化数据库表错误: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# 用户数据操作类
class UserDatabase:
    @staticmethod
    def get_or_create_user(user_id, username=None, first_name=None):
        connection = get_db_connection()
        if connection is None:
            return None
            
        try:
            cursor = connection.cursor(dictionary=True)
            
            # 检查用户是否存在
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            
            if user:
                # 更新用户信息
                cursor.execute("""
                    UPDATE users 
                    SET username = %s, first_name = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (username, first_name, user_id))
                user['username'] = username
                user['first_name'] = first_name
            else:
                # 创建新用户
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, points)
                    VALUES (%s, %s, %s, 0)
                """, (user_id, username, first_name))
                user = {
                    'user_id': user_id,
                    'username': username,
                    'first_name': first_name,
                    'points': 0,
                    'last_sign_in': None
                }
            
            return user
            
        except Error as e:
            logging.error(f"获取或创建用户错误: {e}")
            return None
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    @staticmethod
    def get_user_points(user_id):
        connection = get_db_connection()
        if connection is None:
            return 0
            
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT points FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
            
        except Error as e:
            logging.error(f"获取用户积分错误: {e}")
            return 0
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    @staticmethod
    def add_points(user_id, points):
        connection = get_db_connection()
        if connection is None:
            return False
            
        try:
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE users 
                SET points = points + %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (points, user_id))
            return cursor.rowcount > 0
            
        except Error as e:
            logging.error(f"添加积分错误: {e}")
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    @staticmethod
    def can_sign_in_today(user_id):
        connection = get_db_connection()
        if connection is None:
            return True
            
        try:
            cursor = connection.cursor()
            today = date.today()
            cursor.execute("""
                SELECT COUNT(*) FROM sign_in_records 
                WHERE user_id = %s AND sign_in_date = %s
            """, (user_id, today))
            result = cursor.fetchone()
            return result[0] == 0
            
        except Error as e:
            logging.error(f"检查签到状态错误: {e}")
            return True
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    @staticmethod
    def record_sign_in(user_id, points_earned=10):
        connection = get_db_connection()
        if connection is None:
            return False
            
        try:
            cursor = connection.cursor()
            today = date.today()
            
            # 记录签到
            cursor.execute("""
                INSERT INTO sign_in_records (user_id, sign_in_date, points_earned)
                VALUES (%s, %s, %s)
            """, (user_id, today, points_earned))
            
            # 更新用户积分和最后签到日期
            cursor.execute("""
                UPDATE users 
                SET points = points + %s, last_sign_in = %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (points_earned, today, user_id))
            
            return True
            
        except Error as e:
            logging.error(f"记录签到错误: {e}")
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    @staticmethod
    def get_leaderboard(limit=10):
        connection = get_db_connection()
        if connection is None:
            return []
            
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT user_id, username, first_name, points
                FROM users 
                WHERE points > 0
                ORDER BY points DESC, updated_at ASC
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
            
        except Error as e:
            logging.error(f"获取排行榜错误: {e}")
            return []
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    @staticmethod
    def record_purchase(user_id, points_amount, usdt_amount):
        connection = get_db_connection()
        if connection is None:
            return False
            
        try:
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO purchase_records (user_id, points_amount, usdt_amount)
                VALUES (%s, %s, %s)
            """, (user_id, points_amount, usdt_amount))
            return cursor.lastrowid
            
        except Error as e:
            logging.error(f"记录购买错误: {e}")
            return False
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

# 生成四位数验证码
def generate_code():
    return str(random.randint(1000, 9999))

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
    user = update.effective_user
    UserDatabase.get_or_create_user(user.id, user.username, user.first_name)
    
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
    user = update.effective_user
    UserDatabase.get_or_create_user(user.id, user.username, user.first_name)
    
    if not UserDatabase.can_sign_in_today(user.id):
        await update.message.reply_text("❌ 今天已经签到过了，请明天再来！")
        return ConversationHandler.END
    
    code = generate_code()
    user_random_code[user.id] = code
    await update.message.reply_text(f"请输入以下验证码完成签到：\n\n`{code}`", parse_mode='Markdown')
    return AWAIT_CODE

# 查询积分命令
async def check_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    UserDatabase.get_or_create_user(user.id, user.username, user.first_name)
    points = UserDatabase.get_user_points(user.id)
    await update.message.reply_text(f"你当前的积分为：{points}")

# 购买积分命令
async def buy_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    UserDatabase.get_or_create_user(user.id, user.username, user.first_name)
    await update.message.reply_text("请输入你要购买的积分数量（例如 100）：")
    return AWAIT_PURCHASE_AMOUNT

# 回调处理
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    UserDatabase.get_or_create_user(user.id, user.username, user.first_name)

    if query.data == "sign_in":
        if not UserDatabase.can_sign_in_today(user.id):
            await query.message.reply_text("❌ 今天已经签到过了，请明天再来！")
            return ConversationHandler.END
            
        code = generate_code()
        user_random_code[user.id] = code
        await query.message.reply_text(f"请输入以下验证码完成签到：\n\n`{code}`", parse_mode='Markdown')
        return AWAIT_CODE

    elif query.data == "check_points":
        points = UserDatabase.get_user_points(user.id)
        await query.message.reply_text(f"你当前的积分为：{points}")

    elif query.data == "check_rank":
        leaderboard = UserDatabase.get_leaderboard()
        if not leaderboard:
            await query.message.reply_text("暂无积分排名数据。")
            return ConversationHandler.END
            
        message = "🏆 当前积分排名：\n"
        for i, user_data in enumerate(leaderboard, 1):
            username = user_data.get('username')
            first_name = user_data.get('first_name', '未知用户')
            points = user_data.get('points', 0)
            
            if username:
                name = f"@{username}"
            else:
                name = first_name
                
            message += f"{i}. {name} - {points}分\n"
        await query.message.reply_text(message)

    elif query.data == "help":
        await query.message.reply_text("""
📖 使用帮助：

✅ 签到：系统给出验证码，输入正确即可获得10积分（每天只能签到一次）
📊 查询积分：查看你目前的积分余额
🏆 查询排名：查看排行榜前十名
💰 购买积分：通过USDT支付购买积分（1积分=0.1USDT）

💡 提示：每次签到成功可获得10积分，每天只能签到一次！
""")

    elif query.data == "buy_points":
        await query.message.reply_text("请输入你要购买的积分数量（例如 100）：")
        return AWAIT_PURCHASE_AMOUNT

    return ConversationHandler.END

# 验证码验证
async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    input_code = update.message.text.strip()
    correct_code = user_random_code.get(user.id)

    if input_code == correct_code:
        if UserDatabase.record_sign_in(user.id, 10):
            await update.message.reply_text("🎉 签到成功！积分 +10")
        else:
            await update.message.reply_text("❌ 签到失败，请稍后重试。")
        # 清除验证码
        user_random_code.pop(user.id, None)
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
        user_id = update.effective_user.id
        amount = context.user_data.get('purchase_amount', 0)
        price = amount * 0.1
        
        # 记录购买订单
        order_id = UserDatabase.record_purchase(user_id, amount, price)
        
        await update.message.reply_text(
            f"📋 购买订单详情：\n"
            f"订单号：{order_id}\n"
            f"积分数量：{amount}\n"
            f"总价：{price:.2f} USDT\n\n"
            f"💰 请将 {price:.2f} USDT 发送到以下地址：\n\n"
            f"`{USDT_ADDRESS}`\n\n"
            f"💡 付款完成后请联系管理员确认（提供订单号：{order_id}），积分将在确认后添加到您的账户。",
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
        
        if UserDatabase.add_points(user_id, amount):
            await update.message.reply_text(f"✅ 已为用户 {user_id} 添加 {amount} 积分。")
        else:
            await update.message.reply_text("❌ 添加积分失败，请检查用户ID是否正确。")
    except ValueError:
        await update.message.reply_text("参数错误，请输入有效的用户ID和数量。")

# 帮助命令
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📖 使用帮助：

✅ 签到：系统给出验证码，输入正确即可获得10积分（每天只能签到一次）
📊 查询积分：查看你目前的积分余额
🏆 查询排名：查看排行榜前十名
💰 购买积分：通过USDT支付购买积分（1积分=0.1USDT）

💡 提示：每次签到成功可获得10积分，每天只能签到一次！

🔧 管理员命令：
/addpoints <user_id> <amount> - 为指定用户添加积分
""")

# 主函数
def main():
    # 初始化数据库
    if not init_database():
        print("❌ 数据库初始化失败，请检查配置")
        return
    
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