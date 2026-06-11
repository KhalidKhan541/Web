from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import re
import hashlib
import secrets
import requests as http_requests
from datetime import datetime
from dotenv import load_dotenv
import database

load_dotenv()

app = FastAPI(title="AI Agent API Marketplace — Developer Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════

class DeveloperAuth(BaseModel):
    email: str
    password: str

class DeveloperRegister(BaseModel):
    email: str
    password: str
    name: str
    easypaisa_number: str = "03000000000"

class DeveloperUpdateProfile(BaseModel):
    name: str = None
    easypaisa_number: str = None
    api_commission_rate: float = None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class ChangeEmail(BaseModel):
    new_email: str
    password: str

class AgentCreate(BaseModel):
    name: str
    email: str = ""

class AgentTopup(BaseModel):
    agent_id: int
    amount_usd: float

class PaymentRequestCreate(BaseModel):
    amount_usd: float
    notes: str = ""

class PaymentRequestAction(BaseModel):
    request_id: int
    action: str  # APPROVE or REJECT
    easypaisa_txn_id: str = ""
    notes: str = ""

class DeveloperApiCreate(BaseModel):
    api_name: str
    category: str
    url: str
    description: str
    price_per_call_usd: float = 0.10

class DeveloperApiPriceUpdate(BaseModel):
    api_name: str
    price_usd: float

class WithdrawalRequest(BaseModel):
    amount_usd: float

class LegacyUserAuth(BaseModel):
    email: str
    password: str

class LegacyPriceUpdate(BaseModel):
    name: str
    price: float

class LegacyCheckoutRequest(BaseModel):
    amount: float
    user_id: int

class LegacyMockSignRequest(BaseModel):
    orderId: str
    amount: float

# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_api_key() -> str:
    return "agent_" + secrets.token_hex(16)

def parse_readme_apis():
    readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
    if not os.path.exists(readme_path):
        return []
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    apis = []
    sections = re.split(r'\n### ', content)
    for section in sections[1:]:
        lines = section.split('\\n')
        category = lines[0].strip()
        if any(kw in category.lower() for kw in ["index", "guide", "license", "how to", "contributing", "contact"]):
            continue
        table_lines = [l.strip() for l in lines[1:] if l.strip().startswith('|') and '|' in l]
        for line in table_lines:
            if ':---' in line or '---:' in line:
                continue
            if 'Description' in line and 'Auth' in line:
                continue
            parts = [p.strip() for p in line.split('|')]
            if parts and parts[0] == '':
                parts = parts[1:]
            if parts and parts[-1] == '':
                parts = parts[:-1]
            if len(parts) >= 2:
                api_col = parts[0]
                description = parts[1]
                match = re.match(r'\[([^\]]+)\]\(([^)]+)\)', api_col)
                if match:
                    name = match.group(1).strip()
                    url = match.group(2).strip()
                    auth_val = parts[2].lower() if len(parts) > 2 else "no"
                    if "apikey" in auth_val or "oauth" in auth_val:
                        price = 0.25
                    elif "no" in auth_val or "none" in auth_val:
                        price = 0.02
                    else:
                        price = 0.05
                    apis.append({"name": name, "category": category, "url": url,
                                 "description": description, "price_per_call": price})
    return apis

# ═══════════════════════════════════════════════════════════════
# Startup
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
def startup_event():
    database.init_db()
    # Seed global APIs if empty
    apis = database.get_all_apis()
    if len(apis) == 0:
        print("Seeding global API catalog from README.md...")
        parsed = parse_readme_apis()
        for api in parsed:
            database.add_api(api["name"], api["category"], api["url"],
                             api["description"], api["price_per_call"])
        print(f"Seeded {len(parsed)} global APIs.")
    else:
        print(f"Global catalog ready with {len(apis)} APIs.")

# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "AgentAPIs Developer Edition is running", "version": "2.0.0"}

# ═══════════════════════════════════════════════════════════════
# DEVELOPER AUTHENTICATION
# ═══════════════════════════════════════════════════════════════

@app.post("/api/developer/register")
def developer_register(data: DeveloperRegister):
    pwd_hash = hash_password(data.password)
    dev_id = database.create_developer(data.email, pwd_hash, data.name, data.easypaisa_number)
    if not dev_id:
        raise HTTPException(status_code=400, detail="Developer with this email already exists")
    dev = database.get_developer_by_id(dev_id)
    return {
        "status": "success",
        "developer_id": dev_id,
        "email": dev["email"],
        "name": dev["name"],
        "easypaisa_number": dev["easypaisa_number"],
        "message": "Developer account created successfully!"
    }

@app.post("/api/developer/login")
def developer_login(data: DeveloperAuth):
    pwd_hash = hash_password(data.password)
    dev = database.get_developer_by_email(data.email)
    if not dev or dev["password_hash"] != pwd_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not dev["is_active"]:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return {
        "status": "success",
        "developer_id": dev["id"],
        "email": dev["email"],
        "name": dev["name"],
        "easypaisa_number": dev["easypaisa_number"],
        "api_commission_rate": dev["api_commission_rate"],
        "message": f"Welcome back, {dev['name']}!"
    }

@app.get("/api/developer/profile")
def developer_profile(developer_id: int):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    earnings = database.get_developer_earnings(developer_id)
    return {
        "developer": {
            "id": dev["id"],
            "email": dev["email"],
            "name": dev["name"],
            "easypaisa_number": dev["easypaisa_number"],
            "api_commission_rate": dev["api_commission_rate"],
            "is_active": dev["is_active"],
            "created_at": dev["created_at"]
        },
        "earnings": earnings
    }

@app.post("/api/developer/change-password")
def developer_change_password(developer_id: int, data: ChangePassword):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    current_hash = hash_password(data.current_password)
    if dev["password_hash"] != current_hash:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    new_hash = hash_password(data.new_password)
    database.update_developer_password(developer_id, new_hash)
    return {"status": "success", "message": "Password updated successfully"}

@app.post("/api/developer/change-email")
def developer_change_email(developer_id: int, data: ChangeEmail):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    pwd_hash = hash_password(data.password)
    if dev["password_hash"] != pwd_hash:
        raise HTTPException(status_code=401, detail="Password is incorrect")
    success = database.update_developer_email(developer_id, data.new_email)
    if not success:
        raise HTTPException(status_code=400, detail="Email already in use")
    return {"status": "success", "message": "Email updated successfully", "new_email": data.new_email}

@app.post("/api/developer/change-easypaisa")
def developer_change_easypaisa(developer_id: int, new_number: str):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    if not re.match(r'^03\\d{9}$', new_number):
        raise HTTPException(status_code=400, detail="Invalid Easypaisa number format. Use format: 03XXXXXXXXX")
    database.update_developer_easypaisa(developer_id, new_number)
    return {"status": "success", "message": "Easypaisa number updated", "new_number": new_number}

@app.post("/api/developer/update-profile")
def developer_update_profile(developer_id: int, data: DeveloperUpdateProfile):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    database.update_developer_profile(
        developer_id,
        name=data.name,
        easypaisa_number=data.easypaisa_number,
        commission_rate=data.api_commission_rate
    )
    return {"status": "success", "message": "Profile updated successfully"}

# ═══════════════════════════════════════════════════════════════
# AGENT MANAGEMENT (Developer controls their AI agents)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/developer/agents")
def create_agent(developer_id: int, data: AgentCreate):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    api_key = generate_api_key()
    agent_id = database.create_agent(developer_id, data.name, data.email, api_key)
    if not agent_id:
        raise HTTPException(status_code=400, detail="Failed to create agent")
    return {
        "status": "success",
        "agent_id": agent_id,
        "api_key": api_key,
        "message": f"Agent '{data.name}' created successfully"
    }

@app.get("/api/developer/agents")
def list_agents(developer_id: int):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    agents = database.get_developer_agents(developer_id)
    return {"agents": agents}

@app.post("/api/developer/agents/{agent_id}/topup")
def topup_agent(developer_id: int, agent_id: int, data: AgentTopup):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    agent = database.get_agent_by_id(agent_id)
    if not agent or agent["developer_id"] != developer_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    if data.amount_usd <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    database.update_agent_balance(agent_id, data.amount_usd)
    return {
        "status": "success",
        "message": f"Credited {data.amount_usd:.2f} USD to agent '{agent['name']}'",
        "new_balance": agent["balance_usd"] + data.amount_usd
    }

@app.post("/api/developer/agents/{agent_id}/toggle")
def toggle_agent(developer_id: int, agent_id: int):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    agent = database.get_agent_by_id(agent_id)
    if not agent or agent["developer_id"] != developer_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    database.toggle_agent_status(agent_id)
    return {"status": "success", "message": "Agent status toggled"}

# ═══════════════════════════════════════════════════════════════
# PAYMENT REQUESTS (Agent → Developer via Easypaisa)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/agent/payment-request")
def agent_create_payment_request(request: Request, data: PaymentRequestCreate):
    """Agent requests a top-up from their developer"""
    api_key = request.headers.get("X-Agent-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-Agent-API-Key header")
    agent = database.get_agent_by_api_key(api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    if data.amount_usd <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    dev = database.get_developer_by_id(agent["developer_id"])
    req_id = database.create_payment_request(
        agent["id"], agent["developer_id"], data.amount_usd, data.notes
    )
    return {
        "status": "success",
        "request_id": req_id,
        "developer_easypaisa": dev["easypaisa_number"],
        "amount_usd": data.amount_usd,
        "message": f"Payment request created. Send {data.amount_usd:.2f} USD to developer's Easypaisa: {dev['easypaisa_number']}"
    }

@app.get("/api/agent/payment-requests")
def agent_list_payment_requests(request: Request):
    """Agent views their payment request history"""
    api_key = request.headers.get("X-Agent-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-Agent-API-Key header")
    agent = database.get_agent_by_api_key(api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    reqs = database.get_agent_payment_requests(agent["id"])
    return {"requests": reqs}

@app.get("/api/developer/payment-requests")
def developer_list_payment_requests(developer_id: int, status: str = None):
    """Developer views all payment requests from their agents"""
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    reqs = database.get_payment_requests(developer_id, status)
    return {"requests": reqs}

@app.post("/api/developer/payment-requests/action")
def developer_payment_action(developer_id: int, data: PaymentRequestAction):
    """Developer approves or rejects a payment request"""
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    
    if data.action.upper() == "APPROVE":
        database.approve_payment_request(data.request_id, data.easypaisa_txn_id)
        return {"status": "success", "message": "Payment request approved and agent balance credited"}
    elif data.action.upper() == "REJECT":
        database.reject_payment_request(data.request_id, data.notes)
        return {"status": "success", "message": "Payment request rejected"}
    else:
        raise HTTPException(status_code=400, detail="Action must be APPROVE or REJECT")

# ═══════════════════════════════════════════════════════════════
# DEVELOPER API CATALOG MANAGER
# ═══════════════════════════════════════════════════════════════

@app.post("/api/developer/apis")
def developer_add_api(developer_id: int, data: DeveloperApiCreate):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    api_id = database.add_developer_api(
        developer_id, data.api_name, data.category, data.url,
        data.description, data.price_per_call_usd
    )
    return {
        "status": "success",
        "api_id": api_id,
        "message": f"API '{data.api_name}' added to your catalog"
    }

@app.get("/api/developer/apis")
def developer_list_apis(developer_id: int):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    apis = database.get_developer_apis(developer_id)
    return {"apis": apis}

@app.post("/api/developer/apis/price")
def developer_update_api_price(developer_id: int, data: DeveloperApiPriceUpdate):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    database.update_developer_api_price(developer_id, data.api_name, data.price_usd)
    return {"status": "success", "message": f"Updated '{data.api_name}' price to {data.price_usd:.2f} USD/call"}

@app.post("/api/developer/apis/{api_name}/toggle")
def developer_toggle_api(developer_id: int, api_name: str):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    database.toggle_developer_api(developer_id, api_name)
    return {"status": "success", "message": f"API '{api_name}' toggled"}

@app.delete("/api/developer/apis/{api_name}")
def developer_delete_api(developer_id: int, api_name: str):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    database.delete_developer_api(developer_id, api_name)
    return {"status": "success", "message": f"API '{api_name}' removed from catalog"}

# ═══════════════════════════════════════════════════════════════
# AGENT PROXY API (USD-based, per-developer catalog)
# ═══════════════════════════════════════════════════════════════

@app.api_route("/api/proxy/{api_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_api(api_name: str, request: Request):
    """Main proxy endpoint for AI agents — USD pricing, developer catalog"""
    api_key = request.headers.get("X-Agent-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-Agent-API-Key header")
    
    agent = database.get_agent_by_api_key(api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    if not agent["is_active"]:
        raise HTTPException(status_code=403, detail="Agent account is deactivated")
    
    developer_id = agent["developer_id"]
    
    # Look up API in developer's catalog
    api = database.get_developer_api_by_name(developer_id, api_name)
    if not api:
        raise HTTPException(status_code=404, detail=f"API '{api_name}' not found in developer catalog")
    
    if not api["is_active"]:
        raise HTTPException(status_code=403, detail="This API is currently disabled by the developer")
    
    cost_usd = float(api["price_per_call_usd"])
    if float(agent["balance_usd"]) < cost_usd:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient balance. Cost: {cost_usd:.2f} USD. Balance: {agent['balance_usd']:.2f} USD. Request a top-up from your developer."
        )
    
    target_url = api["url"]
    params = dict(request.query_params)
    forward_headers = {k: v for k, v in request.headers.items()
                       if k.lower() not in ["host", "x-agent-api-key", "authorization", "content-length"]}
    body = await request.body()
    
    status_code = 200
    response_content = ""
    response_headers = {}
    
    try:
        r = http_requests.request(
            method=request.method, url=target_url,
            headers=forward_headers, params=params,
            data=body or None, timeout=10.0
        )
        status_code = r.status_code
        response_content = r.text
        response_headers = dict(r.headers)
    except Exception as e:
        response_content = (
            f'{{"status":"success","proxy":"offline-fallback",'
            f'"api":"{api_name}","message":"Target API unreachable; mock response returned.",'
            f'"cost":"{cost_usd:.2f} USD"}}'
        )
        response_headers = {"Content-Type": "application/json"}
    
    # Calculate developer earnings (commission)
    dev = database.get_developer_by_id(developer_id)
    commission_rate = float(dev["api_commission_rate"]) if dev else 0.20
    developer_earned = cost_usd * commission_rate
    
    # Deduct from agent balance
    database.update_agent_balance(agent["id"], -cost_usd)
    
    # Log the usage
    database.add_agent_log(agent["id"], developer_id, api_name, status_code, cost_usd, developer_earned)
    
    safe_headers = {k: v for k, v in response_headers.items()
                    if k.lower() not in ["content-encoding", "content-length", "transfer-encoding", "server"]}
    safe_headers["X-Proxy-Cost"] = f"{cost_usd:.2f} USD"
    safe_headers["X-Agent-Remaining-Balance"] = f"{float(agent['balance_usd']) - cost_usd:.2f} USD"
    safe_headers["X-Developer-Earned"] = f"{developer_earned:.2f} USD"
    
    return Response(
        content=response_content,
        status_code=status_code,
        headers=safe_headers,
        media_type=safe_headers.get("Content-Type", "application/json")
    )

# ═══════════════════════════════════════════════════════════════
# DEVELOPER DASHBOARD & ANALYTICS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/developer/dashboard")
def developer_dashboard(developer_id: int):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    
    agents = database.get_developer_agents(developer_id)
    apis = database.get_developer_apis(developer_id)
    earnings = database.get_developer_earnings(developer_id)
    recent_logs = database.get_developer_logs(developer_id, limit=20)
    pending_payments = database.get_payment_requests(developer_id, status="PENDING")
    
    return {
        "developer": {
            "id": dev["id"],
            "name": dev["name"],
            "email": dev["email"],
            "easypaisa_number": dev["easypaisa_number"],
            "commission_rate": dev["api_commission_rate"]
        },
        "stats": {
            "total_agents": len(agents),
            "active_agents": sum(1 for a in agents if a["is_active"]),
            "total_apis": len(apis),
            "active_apis": sum(1 for a in apis if a["is_active"]),
            "total_calls": earnings["total_calls"] or 0,
            "total_revenue_usd": earnings["total_revenue"] or 0,
            "total_earned_usd": earnings["total_earned"] or 0,
            "pending_payment_requests": len(pending_payments)
        },
        "agents": agents,
        "apis": apis,
        "recent_logs": recent_logs,
        "pending_payments": pending_payments
    }

@app.get("/api/developer/logs")
def developer_logs(developer_id: int, limit: int = 100):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    logs = database.get_developer_logs(developer_id, limit)
    return {"logs": logs}

@app.get("/api/developer/earnings")
def developer_earnings(developer_id: int):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    earnings = database.get_developer_earnings(developer_id)
    return earnings

# ═══════════════════════════════════════════════════════════════
# AGENT DASHBOARD (Agent self-service)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/agent/dashboard")
def agent_dashboard(request: Request):
    api_key = request.headers.get("X-Agent-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-Agent-API-Key header")
    agent = database.get_agent_by_api_key(api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    dev = database.get_developer_by_id(agent["developer_id"])
    logs = database.get_agent_logs(agent["id"], limit=50)
    payment_reqs = database.get_agent_payment_requests(agent["id"])
    
    return {
        "agent": {
            "id": agent["id"],
            "name": agent["name"],
            "email": agent["email"],
            "balance_usd": agent["balance_usd"],
            "total_spent_usd": agent["total_spent_usd"],
            "is_active": agent["is_active"]
        },
        "developer": {
            "name": dev["name"],
            "easypaisa_number": dev["easypaisa_number"]
        },
        "recent_logs": logs,
        "payment_requests": payment_reqs
    }

@app.get("/api/agent/apis")
def agent_list_available_apis(request: Request):
    """Agent sees APIs available from their developer"""
    api_key = request.headers.get("X-Agent-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-Agent-API-Key header")
    agent = database.get_agent_by_api_key(api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    apis = database.get_developer_apis(agent["developer_id"])
    return {"apis": apis}

# ═══════════════════════════════════════════════════════════════
# WITHDRAWALS (Developer → Easypaisa)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/developer/withdraw")
def developer_withdraw(developer_id: int, data: WithdrawalRequest):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    if data.amount_usd <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    earnings = database.get_developer_earnings(developer_id)
    available = earnings["total_earned"] or 0
    
    # Check pending withdrawals
    pending = database.get_developer_withdrawals(developer_id)
    pending_total = sum(w["amount_usd"] for w in pending if w["status"] == "PENDING")
    
    if data.amount_usd > (available - pending_total):
        raise HTTPException(status_code=400, detail="Insufficient earnings for withdrawal")
    
    req_id = database.create_withdrawal_request(developer_id, data.amount_usd, dev["easypaisa_number"])
    return {
        "status": "success",
        "request_id": req_id,
        "amount_usd": data.amount_usd,
        "easypaisa_number": dev["easypaisa_number"],
        "message": f"Withdrawal request for {data.amount_usd:.2f} USD submitted. You will receive funds at {dev['easypaisa_number']}"
    }

@app.get("/api/developer/withdrawals")
def developer_list_withdrawals(developer_id: int):
    dev = database.get_developer_by_id(developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    withdrawals = database.get_developer_withdrawals(developer_id)
    return {"withdrawals": withdrawals}

# ═══════════════════════════════════════════════════════════════
# GLOBAL API CATALOG (for reference/seed)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/apis")
def get_global_apis():
    return database.get_all_apis()

# ═══════════════════════════════════════════════════════════════
# LEGACY ENDPOINTS (backward compatibility)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/register")
def legacy_register(user: LegacyUserAuth):
    pwd_hash = hash_password(user.password)
    api_key = "agent_" + hashlib.md5(user.email.encode()).hexdigest() + "_" + secrets.token_hex(8)
    user_id = database.create_user(user.email, pwd_hash, api_key)
    if not user_id:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    return {
        "status": "success", "user_id": user_id, "email": user.email,
        "api_key": api_key, "balance": 10.0, "is_admin": 1,
        "message": "Registered! Account pre-loaded with 10.00 USD free credit."
    }

@app.post("/api/login")
def legacy_login(user: LegacyUserAuth):
    pwd_hash = hash_password(user.password)
    db_user = database.get_user_by_email(user.email)
    if not db_user or db_user["password_hash"] != pwd_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "status": "success", "user_id": db_user["id"], "email": db_user["email"],
        "api_key": db_user["api_key"], "balance": db_user["balance"],
        "is_admin": db_user["is_admin"],
        "message": f"Welcome back, {db_user['email']}!"
    }

@app.get("/api/user/info")
def legacy_user_info(user_id: int):
    import psycopg2.extras
    conn = database.get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, email, api_key, balance, is_admin FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close(); conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logs = database.get_user_logs(user_id, limit=20)
    return {"user": dict(user), "logs": logs}

@app.post("/api/apis/price")
def legacy_update_price(data: LegacyPriceUpdate, request: Request):
    api = database.get_api_by_name(data.name)
    if not api:
        raise HTTPException(status_code=404, detail="API not found")
    database.update_api_price(data.name, data.price)
    return {"status": "success", "message": f"Updated '{data.name}' price to {data.price:.2f} USD/call"}

@app.get("/api/admin/logs")
def legacy_get_admin_logs(user_id: int):
    return database.get_all_logs(limit=200)

# ═══════════════════════════════════════════════════════════════
# EASYPAYSA PAYMENT GATEWAY (Legacy + New)
# ═══════════════════════════════════════════════════════════════

HASH_KEY = os.getenv("EASYPAISA_HASH_KEY", "PK_EASYPAISA_SECURE_HASH_KEY_98765")
STORE_ID = os.getenv("EASYPAISA_STORE_ID", "12345")
SANDBOX_MODE = os.getenv("EASYPAISA_SANDBOX_MODE", "True").lower() == "true"

def build_secure_hash(params: dict, hash_key: str) -> str:
    sorted_keys = sorted(params.keys())
    kv_pairs = [f"{k}={params[k]}" for k in sorted_keys]
    concatenated = "&".join(kv_pairs) + f"&hashKey={hash_key}"
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()

@app.post("/api/payment/checkout")
def legacy_init_checkout(req: LegacyCheckoutRequest):
    order_id = "EP_" + secrets.token_hex(4).upper() + "_" + str(int(secrets.token_hex(2), 16))
    database.create_transaction(req.user_id, order_id, req.amount)
    
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    postback_url = f"{base_url}/callback"
    
    params = {
        "amount": f"{req.amount:.2f}",
        "orderId": order_id,
        "postBackURL": postback_url,
        "storeId": STORE_ID,
        "transactionType": "InitialRequest"
    }
    secure_hash = build_secure_hash(params, HASH_KEY)
    params["secureHash"] = secure_hash

    if SANDBOX_MODE:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        redirect_url = f"/easypaisa-mock?{qs}"
    else:
        redirect_url = "https://easypaisa.com.pk/merchant/checkout?" + "&".join(
            f"{k}={v}" for k, v in params.items()
        )

    return {"status": "success", "redirect_url": redirect_url, "params": params}

@app.post("/api/payment/mock-sign")
def legacy_mock_sign(req: LegacyMockSignRequest):
    transaction_id = "EP_TX_" + secrets.token_hex(6).upper()
    params = {
        "amount": f"{req.amount:.2f}",
        "orderId": req.orderId,
        "responseCode": "0000",
        "responseMessage": "Success",
        "transactionId": transaction_id,
    }
    params["secureHash"] = build_secure_hash(
        {k: v for k, v in params.items() if k != "secureHash"}, HASH_KEY
    )
    return params

@app.post("/callback")
async def legacy_callback(request: Request):
    try:
        body = await request.json()
    except Exception:
        form_data = await request.form()
        body = dict(form_data)

    order_id = body.get("orderId")
    transaction_id = body.get("transactionId", "TX_" + secrets.token_hex(6).upper())
    response_code = body.get("responseCode")
    response_message = body.get("responseMessage", "")
    amount_str = body.get("amount")
    received_hash = body.get("secureHash")

    if not order_id or not response_code or not received_hash:
        raise HTTPException(status_code=400, detail="Missing required callback parameters")

    verification_params = {
        "amount": amount_str, "orderId": order_id,
        "responseCode": response_code, "responseMessage": response_message,
        "transactionId": transaction_id,
    }
    calculated_hash = build_secure_hash(verification_params, HASH_KEY)

    if calculated_hash != received_hash:
        raise HTTPException(status_code=401, detail="Signature verification failed")

    if response_code == "0000":
        success = database.complete_transaction(order_id, transaction_id)
        if success:
            return {"status": "success", "message": "Transaction credited successfully"}
        return {"status": "ignored", "message": "Transaction already processed"}
    else:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE transactions SET status='FAILED', updated_at=%s WHERE order_id=%s",
            (datetime.now(), order_id)
        )
        conn.commit()
        cur.close(); conn.close()
        return {"status": "failed", "message": "Transaction failed status recorded"}

# ═══════════════════════════════════════════════════════════════
# STATIC FILES SERVING
# ═══════════════════════════════════════════════════════════════

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)

@app.get("/easypaisa-mock", response_class=HTMLResponse)
def serve_easypaisa_mock():
    path = os.path.join(static_dir, "easypaisa_mock.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Easypaisa mock portal not found</h3>"

@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def serve_index():
    path = os.path.join(static_dir, "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Frontend not found</h3>"

@app.get("/styles.css")
def serve_css():
    path = os.path.join(static_dir, "styles.css")
    with open(path) as f:
        return Response(content=f.read(), media_type="text/css")

@app.get("/app.js")
def serve_js():
    path = os.path.join(static_dir, "app.js")
    with open(path) as f:
        return Response(content=f.read(), media_type="application/javascript")

