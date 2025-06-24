
import pandas as pd

# 读取登录记录 Excel 文件
df = pd.read_excel('/Users/yunqian/Documents/git/telegram_bot/0624.xlsx')  # 请将文件名替换为实际路径
df.columns = ['日期', '用户ID']
df['日期'] = pd.to_datetime(df['日期'])

# 构建日期 -> 用户集合的映射
login_dict = df.groupby('日期')['用户ID'].apply(set).to_dict()

# 设置留存天数
max_days = 7
records = []

# 留存计算
for start_date in sorted(login_dict.keys()):
    base_users = login_dict[start_date]
    row = {'起始日期': start_date, '登录用户数': len(base_users)}

    for n in range(1, max_days + 1):
        check_date = start_date + pd.Timedelta(days=n)
        if check_date in login_dict:
            retained_users = base_users & login_dict[check_date]
            row[f'第{n}天留存'] = len(retained_users)
        else:
            row[f'第{n}天留存'] = 0
    records.append(row)

# 保存为 Excel 文件
retention_df = pd.DataFrame(records)
retention_df.to_excel('用户留存分析.xlsx', index=False)
print("用户留存分析已保存为 '用户留存分析.xlsx'")
