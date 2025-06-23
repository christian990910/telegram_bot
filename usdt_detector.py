"""
USDT自动检测模块
用于监控TRC20 USDT交易并自动为用户添加积分
"""

import asyncio
import aiohttp
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# ==================== 配置参数 ====================
USDT_ADDRESS = "TSsNMAvZrEdJMxdV6rkT4Sb4c7C1uJvmaY"  # 🔥 替换为你的实际TRC20地址
TRONSCAN_API_BASE = "https://apilist.tronscanapi.com/api"
ORDER_TIMEOUT_MINUTES = 30  # 订单超时时间（分钟）
CHECK_INTERVAL_SECONDS = 30  # 检查间隔（秒）

# ==================== 全局变量 ====================
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
            
            async with self.session.get(url, params=params, timeout=10) as response:
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

# ==================== 全局检测器实例 ====================
usdt_detector = USDTDetector()

# ==================== 辅助函数 ====================
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
            
            # 🔥 这里需要导入你的UserDatabase类
            from database import UserDatabase  # 根据你的实际导入路径调整
            
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

# ==================== 用户接口函数 ====================
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
        status_text += f"支付金额：{order_info['amount_with_random']:.2f} USDT\n"
        status_text += f"获得积分：{order_info['credit_amount']}\n"
        status_text += f"剩余时间：{max(0, int(remaining_time))}分钟\n"
        status_text += f"状态：等待付款\n\n"
    
    status_text += f"💰 付款地址：`{USDT_ADDRESS}`\n"
    status_text += f"⚠️ 请发送准确金额到上述地址"
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

# ==================== 清理函数 ====================
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