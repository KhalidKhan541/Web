
# First, let me create the updated database.py with new tables for developers, agents, and transactions

database_py = '''import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marketplace.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ─── DEVELOPER SUPER ADMIN TABLE ───
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS developers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        easypaisa_number TEXT DEFAULT '03000000000',
        api_commission_rate REAL DEFAULT 0.20,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # ─── AGENT TABLE (AI Agents belonging to developers) ───
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        developer_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        api_key TEXT UNIQUE NOT NULL,
        email TEXT,
        balance_usd REAL DEFAULT 0.00,
        total_spent_usd REAL DEFAULT 0.00,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(developer_id) REFERENCES developers(id)
    )
    """)
    
    # ─── DEVELOPER API CATALOG (APIs developers choose to offer) ───
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS developer_apis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        developer_id INTEGER NOT NULL,
        api_name TEXT NOT NULL,
        category TEXT NOT NULL,
        url TEXT NOT NULL,
        description TEXT NOT NULL,
        price_per_call_usd REAL DEFAULT 0.10,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(developer_id) REFERENCES developers(id),
        UNIQUE(developer_id, api_name)
    )
    """)
    
    # ─── AGENT PAYMENT REQUESTS (Top-ups agents request from developers) ───
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id INTEGER NOT NULL,
        developer_id INTEGER NOT NULL,
        amount_usd REAL NOT NULL,
        easypaisa_txn_id TEXT,
        status TEXT DEFAULT 'PENDING',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved_at TIMESTAMP,
        notes TEXT,
        FOREIGN KEY(agent_id) REFERENCES agents(id),
        FOREIGN KEY(developer_id) REFERENCES developers(id)
    )
    """)
    
    # ─── AGENT USAGE LOGS (Per-developer, per-agent) ───
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id INTEGER NOT NULL,
        developer_id INTEGER NOT NULL,
        api_name TEXT NOT NULL,
        status_code INTEGER NOT NULL,
        cost_usd REAL NOT NULL,
        developer_earned_usd REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(agent_id) REFERENCES agents(id),
        FOREIGN KEY(developer_id) REFERENCES developers(id)
    )
    """)
    
    # ─── DEVELOPER WITHDRAWALS (Developer cashing out to Easypaisa) ───
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS developer_withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        developer_id INTEGER NOT NULL,
        amount_usd REAL NOT NULL,
        easypaisa_number TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP,
        FOREIGN KEY(developer_id) REFERENCES developers(id)
    )
    """)
    
    # ─── LEGACY TABLES (keep for backward compatibility) ───
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        api_key TEXT UNIQUE NOT NULL,
        balance REAL DEFAULT 10.0,
        is_admin INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS apis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        url TEXT NOT NULL,
        description TEXT NOT NULL,
        price_per_call REAL DEFAULT 0.10,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        order_id TEXT UNIQUE NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'PENDING',
        gateway_tx_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        api_id INTEGER NOT NULL,
        status_code INTEGER NOT NULL,
        cost REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(api_id) REFERENCES apis(id)
    )
    """)
    
    # Seed default developer super admin if none exists
    cursor.execute("SELECT * FROM developers LIMIT 1")
    if not cursor.fetchone():
        import hashlib
        pwd_hash = hashlib.sha256("devadmin123".encode()).hexdigest()
        cursor.execute(
            """INSERT INTO developers (email, password_hash, name, easypaisa_number, api_commission_rate) 
               VALUES (?, ?, ?, ?, ?)""",
            ("dev@agentapis.com", pwd_hash, "Super Admin", "03001234567", 0.20)
        )
    
    # Seed default legacy admin
    cursor.execute("SELECT * FROM users WHERE email = '03156543273'")
    if not cursor.fetchone():
        import hashlib
        pwd_hash = hashlib.sha256("SWE_Khalid".encode()).hexdigest()
        admin_api_key = "adm_key_super_secret_agent_market"
        cursor.execute(
            "INSERT INTO users (email, password_hash, api_key, balance, is_admin) VALUES (?, ?, ?, ?, ?)",
            ("03156543273", pwd_hash, admin_api_key, 1000.0, 1)
        )
    
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# DEVELOPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_developer_by_email(email):
    conn = get_db_connection()
    dev = conn.execute("SELECT * FROM developers WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dev

def get_developer_by_id(dev_id):
    conn = get_db_connection()
    dev = conn.execute("SELECT * FROM developers WHERE id = ?", (dev_id,)).fetchone()
    conn.close()
    return dev

def create_developer(email, password_hash, name, easypaisa_number="03000000000"):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO developers (email, password_hash, name, easypaisa_number) 
               VALUES (?, ?, ?, ?)""",
            (email, password_hash, name, easypaisa_number)
        )
        conn.commit()
        dev_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        dev_id = None
    finally:
        conn.close()
    return dev_id

def update_developer_password(dev_id, new_password_hash):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE developers SET password_hash = ?, updated_at = ? WHERE id = ?",
        (new_password_hash, datetime.now().isoformat(), dev_id)
    )
    conn.commit()
    conn.close()

def update_developer_email(dev_id, new_email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE developers SET email = ?, updated_at = ? WHERE id = ?",
            (new_email, datetime.now().isoformat(), dev_id)
        )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def update_developer_easypaisa(dev_id, new_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE developers SET easypaisa_number = ?, updated_at = ? WHERE id = ?",
        (new_number, datetime.now().isoformat(), dev_id)
    )
    conn.commit()
    conn.close()

def update_developer_profile(dev_id, name=None, easypaisa_number=None, commission_rate=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if easypaisa_number is not None:
        updates.append("easypaisa_number = ?")
        params.append(easypaisa_number)
    if commission_rate is not None:
        updates.append("api_commission_rate = ?")
        params.append(commission_rate)
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(dev_id)
        query = f"UPDATE developers SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# AGENT FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def create_agent(developer_id, name, email, api_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO agents (developer_id, name, email, api_key) VALUES (?, ?, ?, ?)",
            (developer_id, name, email, api_key)
        )
        conn.commit()
        agent_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        agent_id = None
    finally:
        conn.close()
    return agent_id

def get_agent_by_api_key(api_key):
    conn = get_db_connection()
    agent = conn.execute("SELECT * FROM agents WHERE api_key = ?", (api_key,)).fetchone()
    conn.close()
    return agent

def get_agent_by_id(agent_id):
    conn = get_db_connection()
    agent = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    conn.close()
    return agent

def get_developer_agents(developer_id):
    conn = get_db_connection()
    agents = conn.execute(
        "SELECT * FROM agents WHERE developer_id = ? ORDER BY created_at DESC",
        (developer_id,)
    ).fetchall()
    conn.close()
    return [dict(a) for a in agents]

def update_agent_balance(agent_id, amount_usd):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE agents SET balance_usd = balance_usd + ?, total_spent_usd = total_spent_usd + ? WHERE id = ?",
        (amount_usd, abs(amount_usd) if amount_usd < 0 else 0, agent_id)
    )
    conn.commit()
    conn.close()

def toggle_agent_status(agent_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE agents SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (agent_id,)
    )
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# DEVELOPER API CATALOG FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def add_developer_api(developer_id, api_name, category, url, description, price_per_call_usd=0.10):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO developer_apis (developer_id, api_name, category, url, description, price_per_call_usd)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (developer_id, api_name, category, url, description, price_per_call_usd)
        )
        conn.commit()
        api_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # Update existing
        cursor.execute(
            """UPDATE developer_apis SET category = ?, url = ?, description = ?, price_per_call_usd = ?
               WHERE developer_id = ? AND api_name = ?""",
            (category, url, description, price_per_call_usd, developer_id, api_name)
        )
        conn.commit()
        api_id = True
    finally:
        conn.close()
    return api_id

def get_developer_apis(developer_id):
    conn = get_db_connection()
    apis = conn.execute(
        "SELECT * FROM developer_apis WHERE developer_id = ? AND is_active = 1 ORDER BY category, api_name",
        (developer_id,)
    ).fetchall()
    conn.close()
    return [dict(a) for a in apis]

def get_developer_api_by_name(developer_id, api_name):
    conn = get_db_connection()
    api = conn.execute(
        "SELECT * FROM developer_apis WHERE developer_id = ? AND api_name = ?",
        (developer_id, api_name)
    ).fetchone()
    conn.close()
    return api

def update_developer_api_price(developer_id, api_name, price_usd):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE developer_apis SET price_per_call_usd = ? WHERE developer_id = ? AND api_name = ?",
        (price_usd, developer_id, api_name)
    )
    conn.commit()
    conn.close()

def toggle_developer_api(developer_id, api_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE developer_apis SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END 
           WHERE developer_id = ? AND api_name = ?""",
        (developer_id, api_name)
    )
    conn.commit()
    conn.close()

def delete_developer_api(developer_id, api_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM developer_apis WHERE developer_id = ? AND api_name = ?",
        (developer_id, api_name)
    )
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# PAYMENT REQUEST FUNCTIONS (Agent → Developer)
# ═══════════════════════════════════════════════════════════════

def create_payment_request(agent_id, developer_id, amount_usd, notes=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO payment_requests (agent_id, developer_id, amount_usd, notes) 
           VALUES (?, ?, ?, ?)""",
        (agent_id, developer_id, amount_usd, notes)
    )
    conn.commit()
    req_id = cursor.lastrowid
    conn.close()
    return req_id

def get_payment_requests(developer_id, status=None):
    conn = get_db_connection()
    if status:
        reqs = conn.execute(
            """SELECT pr.*, a.name as agent_name, a.email as agent_email 
               FROM payment_requests pr
               JOIN agents a ON pr.agent_id = a.id
               WHERE pr.developer_id = ? AND pr.status = ?
               ORDER BY pr.requested_at DESC""",
            (developer_id, status)
        ).fetchall()
    else:
        reqs = conn.execute(
            """SELECT pr.*, a.name as agent_name, a.email as agent_email 
               FROM payment_requests pr
               JOIN agents a ON pr.agent_id = a.id
               WHERE pr.developer_id = ?
               ORDER BY pr.requested_at DESC""",
            (developer_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in reqs]

def get_agent_payment_requests(agent_id):
    conn = get_db_connection()
    reqs = conn.execute(
        """SELECT pr.*, d.name as developer_name, d.easypaisa_number as developer_easypaisa
           FROM payment_requests pr
           JOIN developers d ON pr.developer_id = d.id
           WHERE pr.agent_id = ?
           ORDER BY pr.requested_at DESC""",
        (agent_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reqs]

def approve_payment_request(req_id, easypaisa_txn_id=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE payment_requests 
           SET status = 'APPROVED', approved_at = ?, easypaisa_txn_id = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), easypaisa_txn_id, req_id)
    )
    # Credit the agent
    req = cursor.execute("SELECT * FROM payment_requests WHERE id = ?", (req_id,)).fetchone()
    if req:
        cursor.execute(
            "UPDATE agents SET balance_usd = balance_usd + ? WHERE id = ?",
            (req['amount_usd'], req['agent_id'])
        )
    conn.commit()
    conn.close()

def reject_payment_request(req_id, notes=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE payment_requests 
           SET status = 'REJECTED', approved_at = ?, notes = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), notes, req_id)
    )
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# AGENT USAGE LOGS
# ═══════════════════════════════════════════════════════════════

def add_agent_log(agent_id, developer_id, api_name, status_code, cost_usd, developer_earned_usd):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO agent_logs (agent_id, developer_id, api_name, status_code, cost_usd, developer_earned_usd)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (agent_id, developer_id, api_name, status_code, cost_usd, developer_earned_usd)
    )
    conn.commit()
    conn.close()

def get_developer_logs(developer_id, limit=100):
    conn = get_db_connection()
    logs = conn.execute(
        """SELECT al.*, ag.name as agent_name 
           FROM agent_logs al
           JOIN agents ag ON al.agent_id = ag.id
           WHERE al.developer_id = ?
           ORDER BY al.timestamp DESC
           LIMIT ?""",
        (developer_id, limit)
    ).fetchall()
    conn.close()
    return [dict(l) for l in logs]

def get_agent_logs(agent_id, limit=50):
    conn = get_db_connection()
    logs = conn.execute(
        """SELECT * FROM agent_logs WHERE agent_id = ? ORDER BY timestamp DESC LIMIT ?""",
        (agent_id, limit)
    ).fetchall()
    conn.close()
    return [dict(l) for l in logs]

def get_developer_earnings(developer_id):
    conn = get_db_connection()
    result = conn.execute(
        """SELECT 
            COUNT(*) as total_calls,
            SUM(cost_usd) as total_revenue,
            SUM(developer_earned_usd) as total_earned,
            COUNT(DISTINCT agent_id) as active_agents
           FROM agent_logs 
           WHERE developer_id = ?""",
        (developer_id,)
    ).fetchone()
    conn.close()
    return dict(result) if result else {"total_calls": 0, "total_revenue": 0, "total_earned": 0, "active_agents": 0}

# ═══════════════════════════════════════════════════════════════
# DEVELOPER WITHDRAWAL FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def create_withdrawal_request(developer_id, amount_usd, easypaisa_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO developer_withdrawals (developer_id, amount_usd, easypaisa_number)
           VALUES (?, ?, ?)""",
        (developer_id, amount_usd, easypaisa_number)
    )
    conn.commit()
    req_id = cursor.lastrowid
    conn.close()
    return req_id

def get_developer_withdrawals(developer_id):
    conn = get_db_connection()
    withdrawals = conn.execute(
        "SELECT * FROM developer_withdrawals WHERE developer_id = ? ORDER BY requested_at DESC",
        (developer_id,)
    ).fetchall()
    conn.close()
    return [dict(w) for w in withdrawals]

# ═══════════════════════════════════════════════════════════════
# LEGACY FUNCTIONS (keep for compatibility)
# ═══════════════════════════════════════════════════════════════

def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user

def get_user_by_api_key(api_key):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE api_key = ?", (api_key,)).fetchone()
    conn.close()
    return user

def create_user(email, pwd_hash, api_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (email, password_hash, api_key) VALUES (?, ?, ?)",
            (email, pwd_hash, api_key)
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        user_id = None
    finally:
        conn.close()
    return user_id

def update_user_balance(user_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_all_apis():
    conn = get_db_connection()
    apis = conn.execute("SELECT * FROM apis WHERE is_active = 1").fetchall()
    conn.close()
    return [dict(a) for a in apis]

def get_api_by_name(name):
    conn = get_db_connection()
    api = conn.execute("SELECT * FROM apis WHERE name = ?", (name,)).fetchone()
    conn.close()
    return api

def add_api(name, category, url, description, price_per_call):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO apis (name, category, url, description, price_per_call) VALUES (?, ?, ?, ?, ?)",
            (name, category, url, description, price_per_call)
        )
        conn.commit()
        api_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        cursor.execute(
            "UPDATE apis SET category = ?, url = ?, description = ? WHERE name = ?",
            (category, url, description, name)
        )
        conn.commit()
        api_id = True
    finally:
        conn.close()
    return api_id

def update_api_price(name, price):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE apis SET price_per_call = ? WHERE name = ?", (price, name))
    conn.commit()
    conn.close()

def create_transaction(user_id, order_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (user_id, order_id, amount, status) VALUES (?, ?, ?, 'PENDING')",
        (user_id, order_id, amount)
    )
    conn.commit()
    conn.close()

def get_transaction_by_order_id(order_id):
    conn = get_db_connection()
    tx = conn.execute("SELECT * FROM transactions WHERE order_id = ?", (order_id,)).fetchone()
    conn.close()
    return tx

def complete_transaction(order_id, gateway_tx_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    tx = cursor.execute("SELECT * FROM transactions WHERE order_id = ?", (order_id,)).fetchone()
    if tx and tx['status'] == 'PENDING':
        cursor.execute(
            "UPDATE transactions SET status = 'PAID', gateway_tx_id = ?, updated_at = ? WHERE order_id = ?",
            (gateway_tx_id, datetime.now().isoformat(), order_id)
        )
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (tx['amount'], tx['user_id']))
        conn.commit()
        success = True
    else:
        success = False
    conn.close()
    return success

def add_usage_log(user_id, api_id, status_code, cost):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (user_id, api_id, status_code, cost) VALUES (?, ?, ?, ?)",
        (user_id, api_id, status_code, cost)
    )
    conn.commit()
    conn.close()

def get_user_logs(user_id, limit=50):
    conn = get_db_connection()
    logs = conn.execute("""
        SELECT l.*, a.name as api_name 
        FROM logs l
        JOIN apis a ON l.api_id = a.id
        WHERE l.user_id = ?
        ORDER BY l.timestamp DESC
        LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(log) for log in logs]

def get_all_logs(limit=100):
    conn = get_db_connection()
    logs = conn.execute("""
        SELECT l.*, a.name as api_name, u.email as user_email
        FROM logs l
        JOIN apis a ON l.api_id = a.id
        JOIN users u ON l.user_id = u.id
        ORDER BY l.timestamp DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(log) for log in logs]
'''

with open('/mnt/agents/output/database.py', 'w') as f:
    f.write(database_py)

print("✅ database.py created successfully")
print(f"Size: {len(database_py)} characters")
