import logging
from mysql.connector import connect, Error
from datetime import datetime
from typing import Optional, Dict, Any

# 你应该在同目录或utils中有此函数
from db_connection import get_db_connection  # 确保你有这个函数

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