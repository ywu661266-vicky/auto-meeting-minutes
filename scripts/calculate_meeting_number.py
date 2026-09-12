#!/usr/bin/env python3
"""
计算周例会序号

根据目标日期计算是第几次周例会。

基准日期：2026年8月17日 = 第25次（根据客户真实样本）

使用方法：
    python calculate_meeting_number.py <目标日期>
    
示例：
    python calculate_meeting_number.py 2026-09-07
    输出：2026年09月07日（周一）= 第28次周例会
    
    python calculate_meeting_number.py 2026-09-14
    输出：2026年09月14日（周一）= 第29次周例会
"""

import sys
from datetime import datetime, timedelta


def calculate_meeting_number(target_date):
    """
    计算周例会序号
    
    Args:
        target_date: 目标日期（datetime对象）
    
    Returns:
        序号（int），如果日期在基准日期之前返回 None
    """
    # 基准日期：2026年8月17日 = 第25次
    base_date = datetime(2026, 8, 17)
    base_number = 25
    
    days_diff = (target_date - base_date).days
    
    if days_diff < 0:
        return None
    
    number = base_number + days_diff // 7
    return number


def main():
    if len(sys.argv) < 2:
        print("用法：python calculate_meeting_number.py <目标日期>")
        print("")
        print("日期格式：YYYY-MM-DD 或 YYYY/MM/DD")
        print("")
        print("示例：")
        print("  python calculate_meeting_number.py 2026-09-07")
        print("  python calculate_meeting_number.py 2026/09/14")
        print("")
        print("基准日期：2026年8月17日 = 第25次")
        sys.exit(1)
    
    date_str = sys.argv[1]
    
    try:
        # 解析日期
        if '/' in date_str:
            target_date = datetime.strptime(date_str, '%Y/%m/%d')
        else:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print(f"错误：日期格式不正确 '{date_str}'")
        print("请使用 YYYY-MM-DD 或 YYYY/MM/DD 格式")
        sys.exit(1)
    
    # 计算序号
    number = calculate_meeting_number(target_date)
    
    if number is None:
        print(f"错误：日期 {target_date.strftime('%Y年%m月%d日')} 在基准日期（2026年8月17日）之前")
        print("无法自动计算序号，请手动提供")
        sys.exit(1)
    
    # 获取星期几
    weekdays = ['一', '二', '三', '四', '五', '六', '日']
    weekday = weekdays[target_date.weekday()]
    
    # 输出结果
    print(f"{target_date.strftime('%Y年%m月%d日')}（周{weekday}）= 第{number}次周例会")


if __name__ == "__main__":
    main()
