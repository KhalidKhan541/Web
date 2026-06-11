import os
import psycopg2
import psycopg2.extras
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS developers (
        id SERIAL PRIMARY KEY,
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        id SERIAL PRIMARY KEY,
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS developer_apis (
        id SERIAL PRIMARY KEY,
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_requests (
        id SERIAL PRIMARY KEY,
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_logs (
        id SERIAL PRIMARY KEY,
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS developer_withdrawals (
        id SERIAL PRIMARY KEY,
        developer_id INTEGER NOT NULL,
        amount_usd REAL NOT NULL,
        easypaisa_number TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP,
        FOREIGN KEY(developer_id) REFERENCES developers(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
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
        id SERIAL PRIMARY KEY,
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
        id SERIAL PRIMARY KEY,
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
        id SERIAL PRIMARY KEY,
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
    import hashlib
    cursor.execute("SELECT id FROM developers LIMIT 1")
    if not cursor.fetchone():
        pwd_hash = hashlib.sha256("devadmin123".encode()).hexdigest()
        cursor.execute(
            """INSERT INTO developers (email, password_hash, name, easypaisa_number, api_commission_rate)
               VALUES (%s, %s, %s, %s, %s)""",
            ("dev@agentapis.com", pwd_hash, "Super Admin", "03001234567", 0.20)
        )

    # Seed default legacy admin
    cursor.execute("SELECT id FROM users WHERE email = '03156543273'")
    if not cursor.fetchone():
        pwd_hash = hashlib.sha256("SWE_Khalid".encode()).hexdigest()
        admin_api_key = "adm_key_super_secret_agent_market"
        cursor.execute(
            "INSERT INTO users (email, password_hash, api_key, balance, is_admin) VALUES (%s, %s, %s, %s, %s)",
            ("03156543273", pwd_hash, admin_api_key, 1000.0, 1)
        )

    conn.commit()
    cursor.close()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# HELPER: convert RealDictRow to plain dict
# ═══════════════════════════════════════════════════════════════

def _fetchone(cursor):
    row = cursor.fetchone()
    return dict(row) if row else None

def _fetchall(cursor):
    return [dict(r) for r in cursor.fetchall()]

# ═══════════════════════════════════════════════════════════════
# DEVELOPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_developer_by_email(email):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM developers WHERE email = %s", (email,))
    dev = _fetchone(cur)
    cur.close(); conn.close()
    return dev

def get_developer_by_id(dev_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM developers WHERE id = %s", (dev_id,))
    dev = _fetchone(cur)
    cur.close(); conn.close()
    return dev

def create_developer(email, password_hash, name, easypaisa_number="03000000000"):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO developers (email, password_hash, name, easypaisa_number) VALUES (%s, %s, %s, %s) RETURNING id",
            (email, password_hash, name, easypaisa_number)
        )
        dev_id = cur.fetchone()[0]
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        dev_id = None
    finally:
        cur.close(); conn.close()
    return dev_id

def update_developer_password(dev_id, new_password_hash):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE developers SET password_hash = %s, updated_at = %s WHERE id = %s",
                (new_password_hash, datetime.now(), dev_id))
    conn.commit(); cur.close(); conn.close()

def update_developer_email(dev_id, new_email):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE developers SET email = %s, updated_at = %s WHERE id = %s",
                    (new_email, datetime.now(), dev_id))
        conn.commit()
        success = True
    except psycopg2.IntegrityError:
        conn.rollback()
        success = False
    finally:
        cur.close(); conn.close()
    return success

def update_developer_easypaisa(dev_id, new_number):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE developers SET easypaisa_number = %s, updated_at = %s WHERE id = %s",
                (new_number, datetime.now(), dev_id))
    conn.commit(); cur.close(); conn.close()

def update_developer_profile(dev_id, name=None, easypaisa_number=None, commission_rate=None):
    conn = get_db_connection()
    cur = conn.cursor()
    updates = []
    params = []
    if name is not None:
        updates.append("name = %s"); params.append(name)
    if easypaisa_number is not None:
        updates.append("easypaisa_number = %s"); params.append(easypaisa_number)
    if commission_rate is not None:
        updates.append("api_commission_rate = %s"); params.append(commission_rate)
    if updates:
        updates.append("updated_at = %s"); params.append(datetime.now())
        params.append(dev_id)
        cur.execute(f"UPDATE developers SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
    cur.close(); conn.close()

# ═══════════════════════════════════════════════════════════════
# AGENT FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def create_agent(developer_id, name, email, api_key):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO agents (developer_id, name, email, api_key) VALUES (%s, %s, %s, %s) RETURNING id",
            (developer_id, name, email, api_key)
        )
        agent_id = cur.fetchone()[0]
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        agent_id = None
    finally:
        cur.close(); conn.close()
    return agent_id

def get_agent_by_api_key(api_key):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM agents WHERE api_key = %s", (api_key,))
    agent = _fetchone(cur)
    cur.close(); conn.close()
    return agent

def get_agent_by_id(agent_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM agents WHERE id = %s", (agent_id,))
    agent = _fetchone(cur)
    cur.close(); conn.close()
    return agent

def get_developer_agents(developer_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM agents WHERE developer_id = %s ORDER BY created_at DESC", (developer_id,))
    agents = _fetchall(cur)
    cur.close(); conn.close()
    return agents

def update_agent_balance(agent_id, amount_usd):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE agents SET balance_usd = balance_usd + %s, total_spent_usd = total_spent_usd + %s WHERE id = %s",
        (amount_usd, abs(amount_usd) if amount_usd < 0 else 0, agent_id)
    )
    conn.commit(); cur.close(); conn.close()

def toggle_agent_status(agent_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE agents SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = %s", (agent_id,))
    conn.commit(); cur.close(); conn.close()

# ═══════════════════════════════════════════════════════════════
# DEVELOPER API CATALOG FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def add_developer_api(developer_id, api_name, category, url, description, price_per_call_usd=0.10):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO developer_apis (developer_id, api_name, category, url, description, price_per_call_usd)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (developer_id, api_name, category, url, description, price_per_call_usd)
        )
        api_id = cur.fetchone()[0]
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.execute(
            """UPDATE developer_apis SET category = %s, url = %s, description = %s, price_per_call_usd = %s
               WHERE developer_id = %s AND api_name = %s""",
            (category, url, description, price_per_call_usd, developer_id, api_name)
        )
        conn.commit()
        api_id = True
    finally:
        cur.close(); conn.close()
    return api_id

def get_developer_apis(developer_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM developer_apis WHERE developer_id = %s AND is_active = 1 ORDER BY category, api_name", (developer_id,))
    apis = _fetchall(cur)
    cur.close(); conn.close()
    return apis

def get_developer_api_by_name(developer_id, api_name):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM developer_apis WHERE developer_id = %s AND api_name = %s", (developer_id, api_name))
    api = _fetchone(cur)
    cur.close(); conn.close()
    return api

def update_developer_api_price(developer_id, api_name, price_usd):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE developer_apis SET price_per_call_usd = %s WHERE developer_id = %s AND api_name = %s",
                (price_usd, developer_id, api_name))
    conn.commit(); cur.close(); conn.close()

def toggle_developer_api(developer_id, api_name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""UPDATE developer_apis SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
                   WHERE developer_id = %s AND api_name = %s""", (developer_id, api_name))
    conn.commit(); cur.close(); conn.close()

def delete_developer_api(developer_id, api_name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM developer_apis WHERE developer_id = %s AND api_name = %s", (developer_id, api_name))
    conn.commit(); cur.close(); conn.close()

# ═══════════════════════════════════════════════════════════════
# PAYMENT REQUEST FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def create_payment_request(agent_id, developer_id, amount_usd, notes=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payment_requests (agent_id, developer_id, amount_usd, notes) VALUES (%s, %s, %s, %s) RETURNING id",
        (agent_id, developer_id, amount_usd, notes)
    )
    req_id = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    return req_id

def get_payment_requests(developer_id, status=None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if status:
        cur.execute(
            """SELECT pr.*, a.name as agent_name, a.email as agent_email
               FROM payment_requests pr JOIN agents a ON pr.agent_id = a.id
               WHERE pr.developer_id = %s AND pr.status = %s ORDER BY pr.requested_at DESC""",
            (developer_id, status)
        )
    else:
        cur.execute(
            """SELECT pr.*, a.name as agent_name, a.email as agent_email
               FROM payment_requests pr JOIN agents a ON pr.agent_id = a.id
               WHERE pr.developer_id = %s ORDER BY pr.requested_at DESC""",
            (developer_id,)
        )
    reqs = _fetchall(cur)
    cur.close(); conn.close()
    return reqs

def get_agent_payment_requests(agent_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT pr.*, d.name as developer_name, d.easypaisa_number as developer_easypaisa
           FROM payment_requests pr JOIN developers d ON pr.developer_id = d.id
           WHERE pr.agent_id = %s ORDER BY pr.requested_at DESC""",
        (agent_id,)
    )
    reqs = _fetchall(cur)
    cur.close(); conn.close()
    return reqs

def approve_payment_request(req_id, easypaisa_txn_id=""):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "UPDATE payment_requests SET status = 'APPROVED', approved_at = %s, easypaisa_txn_id = %s WHERE id = %s",
        (datetime.now(), easypaisa_txn_id, req_id)
    )
    cur.execute("SELECT * FROM payment_requests WHERE id = %s", (req_id,))
    req = _fetchone(cur)
    if req:
        cur.execute("UPDATE agents SET balance_usd = balance_usd + %s WHERE id = %s",
                    (req['amount_usd'], req['agent_id']))
    conn.commit(); cur.close(); conn.close()

def reject_payment_request(req_id, notes=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE payment_requests SET status = 'REJECTED', approved_at = %s, notes = %s WHERE id = %s",
        (datetime.now(), notes, req_id)
    )
    conn.commit(); cur.close(); conn.close()

# ═══════════════════════════════════════════════════════════════
# AGENT USAGE LOGS
# ═══════════════════════════════════════════════════════════════

def add_agent_log(agent_id, developer_id, api_name, status_code, cost_usd, developer_earned_usd):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO agent_logs (agent_id, developer_id, api_name, status_code, cost_usd, developer_earned_usd) VALUES (%s, %s, %s, %s, %s, %s)",
        (agent_id, developer_id, api_name, status_code, cost_usd, developer_earned_usd)
    )
    conn.commit(); cur.close(); conn.close()

def get_developer_logs(developer_id, limit=100):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT al.*, ag.name as agent_name FROM agent_logs al
           JOIN agents ag ON al.agent_id = ag.id
           WHERE al.developer_id = %s ORDER BY al.timestamp DESC LIMIT %s""",
        (developer_id, limit)
    )
    logs = _fetchall(cur)
    cur.close(); conn.close()
    return logs

def get_agent_logs(agent_id, limit=50):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM agent_logs WHERE agent_id = %s ORDER BY timestamp DESC LIMIT %s", (agent_id, limit))
    logs = _fetchall(cur)
    cur.close(); conn.close()
    return logs

def get_developer_earnings(developer_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT COUNT(*) as total_calls, SUM(cost_usd) as total_revenue,
                  SUM(developer_earned_usd) as total_earned, COUNT(DISTINCT agent_id) as active_agents
           FROM agent_logs WHERE developer_id = %s""",
        (developer_id,)
    )
    result = _fetchone(cur)
    cur.close(); conn.close()
    return result or {"total_calls": 0, "total_revenue": 0, "total_earned": 0, "active_agents": 0}

# ═══════════════════════════════════════════════════════════════
# DEVELOPER WITHDRAWAL FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def create_withdrawal_request(developer_id, amount_usd, easypaisa_number):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO developer_withdrawals (developer_id, amount_usd, easypaisa_number) VALUES (%s, %s, %s) RETURNING id",
        (developer_id, amount_usd, easypaisa_number)
    )
    req_id = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    return req_id

def get_developer_withdrawals(developer_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM developer_withdrawals WHERE developer_id = %s ORDER BY requested_at DESC", (developer_id,))
    withdrawals = _fetchall(cur)
    cur.close(); conn.close()
    return withdrawals

# ═══════════════════════════════════════════════════════════════
# LEGACY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_user_by_email(email):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = _fetchone(cur)
    cur.close(); conn.close()
    return user

def get_user_by_api_key(api_key):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE api_key = %s", (api_key,))
    user = _fetchone(cur)
    cur.close(); conn.close()
    return user

def create_user(email, pwd_hash, api_key):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (email, password_hash, api_key) VALUES (%s, %s, %s) RETURNING id",
            (email, pwd_hash, api_key)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        user_id = None
    finally:
        cur.close(); conn.close()
    return user_id

def update_user_balance(user_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
    conn.commit(); cur.close(); conn.close()

def get_all_apis():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM apis WHERE is_active = 1")
    apis = _fetchall(cur)
    cur.close(); conn.close()
    return apis

def get_api_by_name(name):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM apis WHERE name = %s", (name,))
    api = _fetchone(cur)
    cur.close(); conn.close()
    return api

def add_api(name, category, url, description, price_per_call):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO apis (name, category, url, description, price_per_call) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (name, category, url, description, price_per_call)
        )
        api_id = cur.fetchone()[0]
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.execute("UPDATE apis SET category = %s, url = %s, description = %s WHERE name = %s",
                    (category, url, description, name))
        conn.commit()
        api_id = True
    finally:
        cur.close(); conn.close()
    return api_id

def update_api_price(name, price):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE apis SET price_per_call = %s WHERE name = %s", (price, name))
    conn.commit(); cur.close(); conn.close()

def create_transaction(user_id, order_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO transactions (user_id, order_id, amount, status) VALUES (%s, %s, %s, 'PENDING')",
        (user_id, order_id, amount)
    )
    conn.commit(); cur.close(); conn.close()

def get_transaction_by_order_id(order_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM transactions WHERE order_id = %s", (order_id,))
    tx = _fetchone(cur)
    cur.close(); conn.close()
    return tx

def complete_transaction(order_id, gateway_tx_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM transactions WHERE order_id = %s", (order_id,))
    tx = _fetchone(cur)
    if tx and tx['status'] == 'PENDING':
        cur.execute(
            "UPDATE transactions SET status = 'PAID', gateway_tx_id = %s, updated_at = %s WHERE order_id = %s",
            (gateway_tx_id, datetime.now(), order_id)
        )
        cur.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (tx['amount'], tx['user_id']))
        conn.commit()
        success = True
    else:
        success = False
    cur.close(); conn.close()
    return success

def add_usage_log(user_id, api_id, status_code, cost):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO logs (user_id, api_id, status_code, cost) VALUES (%s, %s, %s, %s)",
        (user_id, api_id, status_code, cost)
    )
    conn.commit(); cur.close(); conn.close()

def get_user_logs(user_id, limit=50):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT l.*, a.name as api_name FROM logs l JOIN apis a ON l.api_id = a.id
           WHERE l.user_id = %s ORDER BY l.timestamp DESC LIMIT %s""",
        (user_id, limit)
    )
    logs = _fetchall(cur)
    cur.close(); conn.close()
    return logs

def get_all_logs(limit=100):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT l.*, a.name as api_name, u.email as user_email
           FROM logs l JOIN apis a ON l.api_id = a.id JOIN users u ON l.user_id = u.id
           ORDER BY l.timestamp DESC LIMIT %s""",
        (limit,)
    )
    logs = _fetchall(cur)
    cur.close(); conn.close()
    return logs
