import sqlite3
import os

db_path = r"C:/Users/ahmed/Desktop/newfolder/erp/flash_erp.db"

if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- Users ---")
    users = cursor.execute("SELECT id, username, email, is_active, is_superuser FROM users").fetchall()
    for u in users:
        u_dict = dict(u)
        print(u_dict)
        
        # Check roles
        # Assuming table names based on common patterns: user_roles_link, roles, permissions?
        # Let's list tables first to be sure
    
    print("\n--- Tables ---")
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for t in tables:
        print(t['name'])
        
    conn.close()
