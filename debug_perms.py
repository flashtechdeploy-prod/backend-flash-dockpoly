import sqlite3
import os

db_path = r"C:/Users/ahmed/Desktop/newfolder/erp/flash_erp.db"

if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- Detailed User Permissions ---")
    users = cursor.execute("SELECT id, username, is_superuser FROM users").fetchall()
    for u in users:
        print(f"\nUser: {u['username']} (ID: {u['id']}, Super: {u['is_superuser']})")
        
        # Get roles for this user
        roles = cursor.execute("""
            SELECT r.id, r.name 
            FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?
        """, (u['id'],)).fetchall()
        
        for r in roles:
            print(f"  Role: {r['name']} (ID: {r['id']})")
            
            # Get permissions for this role
            perms = cursor.execute("""
                SELECT p.key 
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = ?
            """, (r['id'],)).fetchall()
            
            p_keys = [p['key'] for p in perms]
            print(f"    Permissions: {', '.join(p_keys)}")
            
    conn.close()
