import random
import logging
import mysql.connector
from mysql.connector import Error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, BotCommand, BotCommandScopeDefault
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          MessageHandler, ContextTypes, filters, ConversationHandler)
from datetime import datetime, date, timedelta
import asyncio
import aiohttp
import time
import random
from typing import Dict, List, Optional
import atexit


# 初始化日志
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Bot 配置
TOKEN = "7535253577:AAEfChOGkCjD9hF7PkMWQ43eO-2gxeOf1VM"
USDT_ADDRESS = "TSsNMAvZrEdJMxdV6rkT4Sb4c7C1uJvmaY"
TRONSCAN_API_BASE = "https://apilist.tronscanapi.com/api"
ORDER_TIMEOUT_MINUTES = 30  # 订单超时时间（分钟）
CHECK_INTERVAL_SECONDS = 30  # 检查间隔（秒）

# 管理员配置
ADMIN_IDS = [
       # 请替换为您的用户ID
    1469613013,    # 可以添加多个管理员ID
    # 添加更多管理员ID...
]

# 超级管理员（只有超级管理员可以添加/删除其他管理员）
SUPER_ADMIN_ID = 1469613013  # 请替换为您的用户ID


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
        
        # 创建管理员表
        create_admin_table = """
        CREATE TABLE IF NOT EXISTS admins (
            user_id BIGINT PRIMARY KEY,
            added_by BIGINT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (added_by) REFERENCES users(user_id)
        )
        """
        
        cursor.execute(create_users_table)
        cursor.execute(create_sign_in_table)
        cursor.execute(create_purchase_table)
        cursor.execute(create_admin_table)
        
        # 初始化超级管理员
        cursor.execute("""
            INSERT IGNORE INTO admins (user_id, added_by)
            VALUES (%s, %s)
        """, (SUPER_ADMIN_ID, SUPER_ADMIN_ID))
        
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

# 权限检查函数
def is_admin(user_id):
    """检查用户是否为管理员（包括配置文件中的管理员和数据库中的管理员）"""
    # 检查配置文件中的管理员
    if user_id in ADMIN_IDS:
        return True
    
    # 检查数据库中的管理员
    connection = get_db_connection()
    if connection is None:
        return False
        
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM admins WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        return result[0] > 0
        
    except Error as e:
        logging.error(f"检查管理员权限错误: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def is_super_admin(user_id):
    """检查用户是否为超级管理员"""
    return user_id == SUPER_ADMIN_ID

def add_admin_to_db(user_id, added_by):
    """添加管理员到数据库"""
    connection = get_db_connection()
    if connection is None:
        return False
        
    try:
        cursor = connection.cursor()
        # 先确保用户存在
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = %s", (user_id,))
        if cursor.fetchone()[0] == 0:
            return False
            
        cursor.execute("""
            INSERT INTO admins (user_id, added_by)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE added_by = %s, added_at = CURRENT_TIMESTAMP
        """, (user_id, added_by, added_by))
        return True
        
    except Error as e:
        logging.error(f"添加管理员错误: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def remove_admin_from_db(user_id):
    """从数据库中移除管理员"""
    connection = get_db_connection()
    if connection is None:
        return False
        
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = %s", (user_id,))
        return cursor.rowcount > 0
        
    except Error as e:
        logging.error(f"移除管理员错误: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_admin_list():
    """获取所有管理员列表"""
    admins = []
    
    # 添加配置文件中的管理员
    for admin_id in ADMIN_IDS:
        admins.append({
            'user_id': admin_id,
            'source': 'config',
            'added_by': None,
            'added_at': None
        })
    
    # 添加数据库中的管理员
    connection = get_db_connection()
    if connection is None:
        return admins
        
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.user_id, a.added_by, a.added_at, u.username, u.first_name
            FROM admins a
            LEFT JOIN users u ON a.user_id = u.user_id
        """)
        db_admins = cursor.fetchall()
        
        for admin in db_admins:
            admin['source'] = 'database'
            admins.append(admin)
            
        return admins
        
    except Error as e:
        logging.error(f"获取管理员列表错误: {e}")
        return admins
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
        BotCommand("check_rank", "查询排名"),
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

# 查询积分排行
async def check_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    UserDatabase.get_or_create_user(user.id, user.username, user.first_name)
    query = update.callback_query
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
        # 生成带随机小额的订单金额
        # amount_with_random = generate_order_amount_with_random(price)
        await update.message.reply_text(
            f"你要购买 {amount} 积分，总价为 {price:.2f} 左右USDT。\n\n"
            "确认购买请回复 `确认`\n"
            "取消购买请回复 `取消`",
            parse_mode='Markdown'
        )
        return AWAIT_CONFIRM_PURCHASE
    except ValueError:
        await update.message.reply_text("请输入有效的数字。")
        return AWAIT_PURCHASE_AMOUNT

# 确认购买
# 全局变量存储订单和检测任务
pending_orders: Dict[str, dict] = {}
detection_task = None

logger = logging.getLogger(__name__)

class USDTDetector:
    """USDT自动检测类"""
    
    def __init__(self):
        self.session = None
        self.last_check_timestamp = int(time.time() * 1000)
    
    async def init_session(self):
        """初始化HTTP会话"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_usdt_transactions(self, address: str, limit: int = 50) -> List[dict]:
        """获取USDT交易记录"""
        try:
            await self.init_session()
            
            # TRONSCAN API获取TRC20交易
            url = f"{TRONSCAN_API_BASE}/token_trc20/transfers"
            params = {
                'limit': limit,
                'start': 0,
                'sort': '-timestamp',
                'count': 'true',
                'filterTokenValue': 1,
                'tokens': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',  # USDT合约地址
                'toAddress': address
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('token_transfers', [])
                else:
                    logger.error(f"TRONSCAN API请求失败: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"获取USDT交易记录失败: {e}")
            return []
    
    async def check_new_transactions(self) -> List[dict]:
        """检查新的交易"""
        transactions = await self.get_usdt_transactions(USDT_ADDRESS)
        new_transactions = []
        
        for tx in transactions:
            tx_timestamp = tx.get('block_timestamp', 0)
            if tx_timestamp > self.last_check_timestamp:
                new_transactions.append(tx)
        
        if new_transactions:
            # 更新最后检查时间戳
            self.last_check_timestamp = max(tx.get('block_timestamp', 0) for tx in new_transactions)
        
        return new_transactions
    
    def match_order_amount(self, received_amount: float) -> Optional[str]:
        """根据金额匹配订单"""
        for order_id, order_info in pending_orders.items():
            expected_amount = order_info['amount_with_random']
            # 允许小额差异（0.01 USDT）
            if abs(received_amount - expected_amount) <= 0.01:
                return order_id
        return None

# 全局检测器实例
usdt_detector = USDTDetector()

def generate_order_amount_with_random(base_amount: float) -> float:
    """生成带随机小额的订单金额"""
    random_offset = random.uniform(-0.1, 0.1)
    return round(base_amount + random_offset, 2)

async def start_usdt_detection(context: ContextTypes.DEFAULT_TYPE):
    """启动USDT检测任务"""
    global detection_task
    
    if detection_task is None or detection_task.done():
        detection_task = asyncio.create_task(usdt_detection_loop(context))
        logger.info("USDT检测任务已启动")

async def usdt_detection_loop(context: ContextTypes.DEFAULT_TYPE):
    """USDT检测循环"""
    while True:
        try:
            # 检查并清理超时订单
            await clean_expired_orders(context)
            
            # 检查新交易
            if pending_orders:
                new_transactions = await usdt_detector.check_new_transactions()
                
                for tx in new_transactions:
                    await process_transaction(tx, context)
            
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            
        except Exception as e:
            logger.error(f"USDT检测循环错误: {e}")
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

async def process_transaction(transaction: dict, context: ContextTypes.DEFAULT_TYPE):
    """处理单个交易"""
    try:
        # 解析交易信息
        amount_str = transaction.get('quant', '0')
        # USDT有6位小数
        received_amount = float(amount_str) / 1000000
        tx_hash = transaction.get('transaction_id', '')
        from_address = transaction.get('from_address', '')
        
        logger.info(f"检测到USDT交易: {received_amount} USDT, 来自: {from_address}, 交易哈希: {tx_hash}")
        
        # 匹配订单
        order_id = usdt_detector.match_order_amount(received_amount)
        
        if order_id:
            order_info = pending_orders[order_id]
            user_id = order_info['user_id']
            credit_amount = order_info['credit_amount']
            
            # 添加积分
            UserDatabase.add_credits(user_id, credit_amount)
            
            # 发送确认消息
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ 付款确认成功！\n\n"
                         f"📋 订单号：{order_id}\n"
                         f"💰 收到金额：{received_amount:.2f} USDT\n"
                         f"🎯 已添加积分：{credit_amount}\n"
                         f"🔗 交易哈希：{tx_hash[:10]}...\n\n"
                         f"感谢您的购买！积分已到账。",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"发送确认消息失败: {e}")
            
            # 移除已处理的订单
            del pending_orders[order_id]
            logger.info(f"订单 {order_id} 处理完成，用户 {user_id} 获得 {credit_amount} 积分")
            
    except Exception as e:
        logger.error(f"处理交易失败: {e}")

async def clean_expired_orders(context: ContextTypes.DEFAULT_TYPE):
    """清理超时订单"""
    current_time = datetime.now()
    expired_orders = []
    
    for order_id, order_info in pending_orders.items():
        if current_time - order_info['created_at'] > timedelta(minutes=ORDER_TIMEOUT_MINUTES):
            expired_orders.append(order_id)
    
    for order_id in expired_orders:
        order_info = pending_orders[order_id]
        user_id = order_info['user_id']
        
        # 通知用户订单超时
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⏰ 订单超时通知\n\n"
                     f"📋 订单号：{order_id}\n"
                     f"❌ 订单已超时作废（{ORDER_TIMEOUT_MINUTES}分钟）\n\n"
                     f"如需重新购买，请重新下单。",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"发送超时通知失败: {e}")
        
        # 移除超时订单
        del pending_orders[order_id]
        logger.info(f"订单 {order_id} 已超时作废")

# 修改后的购买确认处理函数
async def handle_purchase_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理购买确认 - 集成USDT自动检测"""
    text = update.message.text.strip()
    if text == "确认":
        user_id = update.effective_user.id
        amount = context.user_data.get('purchase_amount', 0)
        price = amount * 0.1
        
        # 生成带随机小额的订单金额
        from usdt_detector import generate_order_amount_with_random, pending_orders, start_usdt_detection
        from datetime import datetime
        
        amount_with_random = generate_order_amount_with_random(price)
        
        # 记录购买订单（使用你现有的UserDatabase）
        order_id = UserDatabase.record_purchase(user_id, amount, price)
        
        # 添加到待处理订单列表
        pending_orders[order_id] = {
            'user_id': user_id,
            'credit_amount': amount,
            'original_amount': price,
            'amount_with_random': amount_with_random,
            'created_at': datetime.now()
        }
        
        # 启动检测任务（如果还没启动）
        await start_usdt_detection(context)
        
        await update.message.reply_text(
            f"📋 购买订单详情：\n"
            f"订单号：{order_id}\n"
            f"积分数量：{amount}\n"
            f"支付金额：{amount_with_random:.2f} USDT\n\n"
            f"💰 请将准确金额 {amount_with_random:.2f} USDT 发送到以下地址：\n\n"
            f"`{USDT_ADDRESS}`\n\n"  # 这个地址需要在usdt_detector.py中配置
            f"⚠️ 重要提醒：\n"
            f"• 请发送准确金额 {amount_with_random:.2f} USDT\n"
            f"• 系统将自动检测并确认付款\n"
            f"• 订单有效期：30分钟\n"
            f"• 超时订单将自动作废\n\n"
            f"🔄 正在监控付款中...\n",
            parse_mode='Markdown'
        )
    elif text == "取消":
        await update.message.reply_text("❌ 已取消购买。")
    else:
        await update.message.reply_text("请回复 确认 或 取消")
        return AWAIT_CONFIRM_PURCHASE
    
    return ConversationHandler.END

# 添加查询订单状态的功能
async def check_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询订单状态"""
    user_id = update.effective_user.id
    user_orders = [order_id for order_id, order_info in pending_orders.items() 
                   if order_info['user_id'] == user_id]
    
    if not user_orders:
        await update.message.reply_text("📋 您当前没有待处理的订单。")
        return
    
    status_text = "📋 您的待处理订单：\n\n"
    for order_id in user_orders:
        order_info = pending_orders[order_id]
        remaining_time = ORDER_TIMEOUT_MINUTES - (datetime.now() - order_info['created_at']).total_seconds() / 60
        
        status_text += f"订单号：{order_id}\n"
        status_text += f"金额：{order_info['amount_with_random']:.2f} USDT\n"
        status_text += f"剩余时间：{max(0, int(remaining_time))}分钟\n"
        status_text += f"状态：等待付款\n\n"
    
    await update.message.reply_text(status_text)

# 应用关闭时的清理函数
async def cleanup_usdt_detector():
    """清理USDT检测器资源"""
    global detection_task
    
    if detection_task and not detection_task.done():
        detection_task.cancel()
        try:
            await detection_task
        except asyncio.CancelledError:
            pass
    
    await usdt_detector.close_session()
    logger.info("USDT检测器已清理")

# 取消操作
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ 操作已取消。")
    return ConversationHandler.END

# 管理员加积分命令
async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 检查管理员权限
    if not is_admin(user_id):
        await update.message.reply_text("❌ 您没有权限执行此操作。")
        return
    
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("用法：/addpoints <user_id> <amount>")
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        
        if UserDatabase.add_points(target_user_id, amount):
            await update.message.reply_text(f"✅ 已为用户 {target_user_id} 添加 {amount} 积分。")
        else:
            await update.message.reply_text("❌ 添加积分失败，请检查用户ID是否正确。")
    except ValueError:
        await update.message.reply_text("参数错误，请输入有效的用户ID和数量。")

# 添加管理员命令
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 只有超级管理员可以添加管理员
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ 只有超级管理员可以添加管理员。")
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("用法：/addadmin <user_id>")
        return

    try:
        target_user_id = int(context.args[0])
        
        if target_user_id in ADMIN_IDS:
            await update.message.reply_text("❌ 该用户已经是配置文件中的管理员。")
            return
        
        if add_admin_to_db(target_user_id, user_id):
            await update.message.reply_text(f"✅ 已将用户 {target_user_id} 添加为管理员。")
        else:
            await update.message.reply_text("❌ 添加管理员失败，请确保用户ID存在。")
    except ValueError:
        await update.message.reply_text("参数错误，请输入有效的用户ID。")

# 移除管理员命令
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 只有超级管理员可以移除管理员
    if not is_super_admin(user_id):
        await update.message.reply_text("❌ 只有超级管理员可以移除管理员。")
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("用法：/removeadmin <user_id>")
        return

    try:
        target_user_id = int(context.args[0])
        
        if target_user_id == SUPER_ADMIN_ID:
            await update.message.reply_text("❌ 不能移除超级管理员。")
            return
        
        if target_user_id in ADMIN_IDS:
            await update.message.reply_text("❌ 不能移除配置文件中的管理员，请修改配置文件。")
            return
        
        if remove_admin_from_db(target_user_id):
            await update.message.reply_text(f"✅ 已将用户 {target_user_id} 从管理员列表中移除。")
        else:
            await update.message.reply_text("❌ 移除管理员失败，该用户可能不是管理员。")
    except ValueError:
        await update.message.reply_text("参数错误，请输入有效的用户ID。")

# 管理员列表命令
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 只有管理员可以查看管理员列表
    if not is_admin(user_id):
        await update.message.reply_text("❌ 您没有权限执行此操作。")
        return
    
    admins = get_admin_list()
    
    if not admins:
        await update.message.reply_text("暂无管理员数据。")
        return
    
    message = "👥 管理员列表：\n\n"
    
    for admin in admins:
        admin_id = admin['user_id']
        source = admin['source']
        
        # 标记超级管理员
        if admin_id == SUPER_ADMIN_ID:
            role = "👑 超级管理员"
        else:
            role = "👤 管理员"
        
        # 获取用户信息
        if source == 'database':
            username = admin.get('username')
            first_name = admin.get('first_name', '未知用户')
            name = f"@{username}" if username else first_name
            added_at = admin.get('added_at', '').strftime('%Y-%m-%d') if admin.get('added_at') else '未知'
            message += f"{role} - {name} (ID: {admin_id})\n"
            message += f"   来源: {'数据库' if source == 'database' else '配置文件'}\n"
            if source == 'database':
                message += f"   添加时间: {added_at}\n"
        else:
            message += f"{role} - ID: {admin_id}\n"
            message += f"   来源: 配置文件\n"
        
        message += "\n"
    
    await update.message.reply_text(message)

# 确认购买订单命令（管理员专用）
async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 检查管理员权限
    if not is_admin(user_id):
        await update.message.reply_text("❌ 您没有权限执行此操作。")
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("用法：/confirm <order_id>")
        return

    try:
        order_id = int(context.args[0])
        
        connection = get_db_connection()
        if connection is None:
            await update.message.reply_text("❌ 数据库连接失败。")
            return
        
        cursor = connection.cursor(dictionary=True)
        
        # 获取订单信息
        cursor.execute("""
            SELECT * FROM purchase_records 
            WHERE id = %s AND status = 'pending'
        """, (order_id,))
        order = cursor.fetchone()
        
        if not order:
            await update.message.reply_text("❌ 未找到待确认的订单。")
            return
        
        # 更新订单状态
        cursor.execute("""
            UPDATE purchase_records 
            SET status = 'completed' 
            WHERE id = %s
        """, (order_id,))
        
        # 给用户添加积分
        if UserDatabase.add_points(order['user_id'], order['points_amount']):
            await update.message.reply_text(
                f"✅ 订单 {order_id} 确认成功！\n"
                f"用户 {order['user_id']} 已获得 {order['points_amount']} 积分。"
            )
        else:
            await update.message.reply_text("❌ 确认订单失败。")
            
        connection.close()
        
    except ValueError:
        await update.message.reply_text("参数错误，请输入有效的订单ID。")
    except Error as e:
        logging.error(f"确认购买订单错误: {e}")
        await update.message.reply_text("❌ 确认订单时发生错误。")

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


# 主函数 - 修改后的版本
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
            AWAIT_CONFIRM_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_purchase_confirmation)],  # 这个函数需要替换
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
    app.add_handler(CommandHandler("check_rank", check_rank))
    app.add_handler(CommandHandler("addpoints", add_points))

    # 🔥 新增：添加USDT检测相关的处理器
    app.add_handler(CommandHandler("order_status", check_order_status))

    # 设置菜单按钮
    app.job_queue.run_once(set_menu_button, 1)

    # 🔥 新增：注册清理函数
    atexit.register(lambda: asyncio.run(cleanup_usdt_detector()))

    print("✅ Bot 正在运行...")
    print("🔄 USDT自动检测已启用...")
    app.run_polling()

if __name__ == '__main__':
    main()