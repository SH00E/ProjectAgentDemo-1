# -*- coding: utf-8 -*-
import sqlite3

conn = sqlite3.connect('repair_agent/memory_data/cases.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute('SELECT id, case_type, title, device_type FROM cases ORDER BY id')
rows = cursor.fetchall()

print('=== 案例数据库内容 ===')
for row in rows:
    print(f"ID:{row['id']} | 类型:{row['case_type']} | 标题:{row['title']} | 设备:{row['device_type']}")

conn.close()
