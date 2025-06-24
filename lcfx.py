import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns

def analyze_user_retention(df, base_date, target_days):
    """
    分析用户留存情况
    
    参数:
    df: DataFrame，包含'日期'和'游戏ID'列
    base_date: str，基准日期，格式如'2024-05-25'
    target_days: list，要分析的后续天数，如[1, 3, 5, 7, 14, 30]
    
    返回:
    dict: 包含留存分析结果
    """
    # 确保日期列是datetime格式
    df['日期'] = pd.to_datetime(df['日期'])
    base_date = pd.to_datetime(base_date)
    
    # 获取基准日期登录的用户
    base_users = set(df[df['日期'] == base_date]['游戏ID'].unique())
    base_user_count = len(base_users)
    
    print(f"基准日期 {base_date.strftime('%Y-%m-%d')} 登录用户数: {base_user_count}")
    
    if base_user_count == 0:
        print("基准日期没有用户登录")
        return {}
    
    results = {}
    results['base_date'] = base_date.strftime('%Y-%m-%d')
    results['base_user_count'] = base_user_count
    results['retention_data'] = []
    
    # 分析每个目标天数的留存情况
    for days in target_days:
        target_date = base_date + timedelta(days=days)
        
        # 获取目标日期登录的用户
        target_users = set(df[df['日期'] == target_date]['游戏ID'].unique())
        
        # 计算留存用户（既在基准日期登录，又在目标日期登录的用户）
        retained_users = base_users.intersection(target_users)
        retained_count = len(retained_users)
        
        # 计算留存率
        retention_rate = (retained_count / base_user_count) * 100 if base_user_count > 0 else 0
        
        result_item = {
            'target_date': target_date.strftime('%Y-%m-%d'),
            'days_after': days,
            'retained_users': retained_count,
            'retention_rate': round(retention_rate, 2)
        }
        
        results['retention_data'].append(result_item)
        
        print(f"第{days}天后 ({target_date.strftime('%Y-%m-%d')}): "
              f"留存用户数 {retained_count}, 留存率 {retention_rate:.2f}%")
    
    return results

def analyze_all_dates_retention(df, target_days=[1, 3, 5, 7, 14, 30]):
    """
    分析所有日期的用户留存情况
    
    参数:
    df: DataFrame，包含'日期'和'游戏ID'列
    target_days: list，要分析的后续天数列表，如[1, 3, 5, 7, 14, 30]
    
    返回:
    DataFrame: 包含每天的用户数和各时间点的留存情况
    """
    # 确保日期列是datetime格式
    df['日期'] = pd.to_datetime(df['日期'])
    
    # 获取所有唯一日期并排序
    all_dates = sorted(df['日期'].unique())
    
    print(f"数据中共有 {len(all_dates)} 个不同的日期")
    print(f"日期范围: {all_dates[0].strftime('%Y-%m-%d')} 到 {all_dates[-1].strftime('%Y-%m-%d')}")
    
    results = []
    
    for base_date in all_dates:
        # 获取基准日期登录的用户
        base_users = set(df[df['日期'] == base_date]['游戏ID'].unique())
        base_user_count = len(base_users)
        
        # 初始化结果行
        result_row = {
            '基准日期': base_date.strftime('%Y-%m-%d'),
            '基准日期用户数': base_user_count
        }
        
        # 分析每个目标天数的留存情况
        for days in target_days:
            target_date = base_date + timedelta(days=days)
            
            # 检查目标日期是否存在于数据中
            if target_date in all_dates:
                # 获取目标日期登录的用户
                target_users = set(df[df['日期'] == target_date]['游戏ID'].unique())
                
                # 计算留存用户
                retained_users = base_users.intersection(target_users)
                retained_count = len(retained_users)
                retention_rate = (retained_count / base_user_count) * 100 if base_user_count > 0 else 0
                
                result_row[f'D+{days}留存用户数'] = retained_count
                result_row[f'D+{days}留存率(%)'] = round(retention_rate, 2)
            else:
                # 如果目标日期不存在，标记为无数据
                result_row[f'D+{days}留存用户数'] = 'N/A'
                result_row[f'D+{days}留存率(%)'] = 'N/A'
        
        results.append(result_row)
    
    return pd.DataFrame(results)

def plot_overall_retention_trends(retention_df, target_days=[1, 3, 5, 7, 14, 30]):
    """
    绘制整体留存趋势图
    """
    # 准备数据
    retention_df['基准日期'] = pd.to_datetime(retention_df['基准日期'])
    
    # 创建子图
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('用户留存分析总览', fontsize=16, fontweight='bold')
    
    # 1. 每日登录用户数趋势
    ax1 = axes[0, 0]
    ax1.plot(retention_df['基准日期'], retention_df['基准日期用户数'], 
             marker='o', linewidth=2, markersize=4)
    ax1.set_title('每日登录用户数趋势')
    ax1.set_xlabel('日期')
    ax1.set_ylabel('登录用户数')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. 不同时间点的留存率趋势
    ax2 = axes[0, 1]
    colors = plt.cm.Set3(np.linspace(0, 1, len(target_days)))
    
    for i, days in enumerate(target_days):
        col_name = f'D+{days}留存率(%)'
        if col_name in retention_df.columns:
            # 过滤掉N/A值
            valid_data = retention_df[retention_df[col_name] != 'N/A'].copy()
            if not valid_data.empty:
                valid_data[col_name] = pd.to_numeric(valid_data[col_name])
                ax2.plot(valid_data['基准日期'], valid_data[col_name], 
                        marker='o', linewidth=2, markersize=3, 
                        label=f'D+{days}', color=colors[i])
    
    ax2.set_title('不同时间点留存率趋势')
    ax2.set_xlabel('日期')
    ax2.set_ylabel('留存率 (%)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis='x', rotation=45)
    
    # 3. 平均留存率对比
    ax3 = axes[1, 0]
    avg_retention = []
    day_labels = []
    
    for days in target_days:
        col_name = f'D+{days}留存率(%)'
        if col_name in retention_df.columns:
            valid_values = retention_df[retention_df[col_name] != 'N/A'][col_name]
            if not valid_values.empty:
                valid_values = pd.to_numeric(valid_values)
                avg_retention.append(valid_values.mean())
                day_labels.append(f'D+{days}')
    
    if avg_retention:
        bars = ax3.bar(day_labels, avg_retention, alpha=0.7, color='lightblue')
        ax3.set_title('平均留存率对比')
        ax3.set_xlabel('时间点')
        ax3.set_ylabel('平均留存率 (%)')
        ax3.grid(True, alpha=0.3, axis='y')
        
        # 在柱子上添加数值标签
        for bar, value in zip(bars, avg_retention):
            ax3.annotate(f'{value:.1f}%', 
                        (bar.get_x() + bar.get_width()/2, bar.get_height()),
                        textcoords="offset points", xytext=(0,3), ha='center')
    
    # 4. 留存用户数分布箱线图
    ax4 = axes[1, 1]
    retention_data_for_box = []
    box_labels = []
    
    for days in target_days:
        col_name = f'D+{days}留存用户数'
        if col_name in retention_df.columns:
            valid_values = retention_df[retention_df[col_name] != 'N/A'][col_name]
            if not valid_values.empty:
                valid_values = pd.to_numeric(valid_values)
                retention_data_for_box.append(valid_values.tolist())
                box_labels.append(f'D+{days}')
    
    if retention_data_for_box:
        ax4.boxplot(retention_data_for_box, labels=box_labels)
        ax4.set_title('留存用户数分布')
        ax4.set_xlabel('时间点')
        ax4.set_ylabel('留存用户数')
        ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()

# 示例使用
def example_usage():
    """
    示例用法
    """
    # 创建示例数据
    dates = pd.date_range('2024-05-20', '2024-06-10', freq='D')
    users = range(1, 501)  # 500个用户
    
    data = []
    for date in dates:
        # 模拟每天有不同比例的用户登录
        login_probability = 0.6 + 0.2 * np.sin((date - dates[0]).days / 7)  # 周期性变化
        daily_users = np.random.choice(users, 
                                     size=int(len(users) * login_probability), 
                                     replace=False)
        for user in daily_users:
            data.append({'日期': date, '游戏ID': user})
    
    df = pd.DataFrame(data)
    print("示例数据预览:")
    print(df.head(10))
    print(f"\n数据形状: {df.shape}")
    
    # 分析特定日期的留存情况
    print("\n" + "="*50)
    print("分析2024-05-25的用户留存情况")
    print("="*50)
    
    retention_results = analyze_user_retention(
        df, 
        base_date='2024-05-25', 
        target_days=[1, 3, 5, 7, 14]
    )
    
    # 绘制留存曲线
    plot_retention_curve(retention_results)
    
    # 分析所有日期的留存情况
    print("\n" + "="*50)
    print("分析所有日期的用户留存情况")
    print("="*50)
    
    # 分析多个时间点的留存
    target_days = [1, 3, 5, 7, 14, 30]
    all_retention_df = analyze_all_dates_retention(df, target_days)
    print("\n留存分析结果:")
    print(all_retention_df.head(10))
    
    # 绘制整体留存趋势
    plot_overall_retention_trends(all_retention_df, target_days)
    
    # 生成摘要报告
    get_retention_summary(all_retention_df, target_days)
    
    return df, all_retention_df

# 如果你有真实的Excel文件，使用以下函数读取
def load_and_analyze_excel(file_path, target_days=[1, 3, 5, 7, 14, 30]):
    """
    从Excel文件加载数据并进行完整的留存分析
    
    参数:
    file_path: str, Excel文件路径
    target_days: list, 要分析的天数列表，默认[1, 3, 5, 7, 14, 30]
    
    返回:
    tuple: (原始数据DataFrame, 留存分析结果DataFrame)
    """
    try:
        # 读取Excel文件
        df = pd.read_excel(file_path)
        print(f"成功读取Excel文件，数据形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        print("\n数据预览:")
        print(df.head())
        
        # 检查必要的列是否存在
        required_columns = ['日期', '游戏ID']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"警告: 缺少必要的列: {missing_columns}")
            print("请确保Excel文件包含'日期'和'游戏ID'列")
            return None, None
        
        # 进行全面的留存分析
        print("\n开始进行留存分析...")
        retention_df = analyze_all_dates_retention(df, target_days)
        
        print("\n留存分析结果预览:")
        print(retention_df.head(10))
        
        # 显示统计摘要
        print(f"\n统计摘要:")
        print(f"- 分析日期数: {len(retention_df)}")
        print(f"- 用户总数: {df['游戏ID'].nunique()}")
        print(f"- 登录记录总数: {len(df)}")
        print(f"- 平均每日登录用户数: {retention_df['基准日期用户数'].mean():.1f}")
        
        # 绘制图表
        plot_overall_retention_trends(retention_df, target_days)
        
        # 保存结果到Excel文件
        output_file = file_path.replace('.xlsx', '_留存分析结果.xlsx').replace('.xls', '_留存分析结果.xlsx')
        retention_df.to_excel(output_file, index=False)
        print(f"\n分析结果已保存到: {output_file}")
        
        return df, retention_df
        
    except Exception as e:
        print(f"处理Excel文件时出错: {e}")
        return None, None

def get_retention_summary(retention_df, target_days=[1, 3, 5, 7, 14, 30]):
    """
    生成留存分析摘要报告
    """
    print("="*60)
    print("用户留存分析摘要报告")
    print("="*60)
    
    # 基础统计
    total_days = len(retention_df)
    avg_daily_users = retention_df['基准日期用户数'].mean()
    max_daily_users = retention_df['基准日期用户数'].max()
    max_day = retention_df.loc[retention_df['基准日期用户数'].idxmax(), '基准日期']
    
    print(f"分析期间: {retention_df['基准日期'].min()} 到 {retention_df['基准日期'].max()}")
    print(f"总分析天数: {total_days}天")
    print(f"平均每日登录用户数: {avg_daily_users:.1f}人")
    print(f"单日最高登录用户数: {max_daily_users}人 ({max_day})")
    
    print(f"\n各时间点平均留存情况:")
    print("-" * 40)
    
    for days in target_days:
        retention_col = f'D+{days}留存率(%)'
        user_col = f'D+{days}留存用户数'
        
        if retention_col in retention_df.columns:
            # 过滤有效数据
            valid_data = retention_df[retention_df[retention_col] != 'N/A']
            if not valid_data.empty:
                valid_retention = pd.to_numeric(valid_data[retention_col])
                valid_users = pd.to_numeric(valid_data[user_col])
                
                avg_rate = valid_retention.mean()
                avg_users = valid_users.mean()
                data_points = len(valid_data)
                
                print(f"D+{days:2d}: 平均留存率 {avg_rate:5.1f}%, 平均留存用户 {avg_users:6.1f}人 (有效数据点: {data_points})")
    
    print(f"\n" + "="*60)

if __name__ == "__main__":
    # 运行示例
    # df, all_retention_df = example_usage()
    
    # 如果你有真实的Excel文件，使用下面的代码
    df, retention_df = load_and_analyze_excel('/Users/yunqian/Documents/git/telegram_bot/0624.xlsx', [1, 3, 5, 7, 14, 30])
    # 如果分析成功，显示摘要报告
    if retention_df is not None:
      get_retention_summary(retention_df)