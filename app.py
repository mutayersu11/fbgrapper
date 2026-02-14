import os
import json
import sqlite3
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ── CONFIGURATION ──
# سيتم استلام المفتاح السري من إعدادات Railway، أو استخدام القيمة الافتراضية
API_SECRET = os.environ.get("API_SECRET", "fbgrappr_2026")
DB_PATH    = "license.db"

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS licenses (
                serial           TEXT PRIMARY KEY,
                hw_ids          TEXT DEFAULT '[]',
                activations      INTEGER DEFAULT 0,
                max_activations INTEGER DEFAULT 2,
                expiry_date      TEXT,
                status           TEXT DEFAULT 'active',
                plan             TEXT DEFAULT 'basic',
                customer_name    TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                serial     TEXT,
                hw_id      TEXT,
                action     TEXT,
                ip         TEXT,
                result     TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

init_db()

# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════════════
def require_secret(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        secret = request.headers.get("X-API-Secret")
        if not secret and request.is_json:
            secret = request.json.get("secret")
        if secret != API_SECRET:
            return jsonify({"ok": False, "msg": "Unauthorized"}), 403
        return f(*args, **kwargs)
    return decorated

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/stats")
@require_secret
def get_stats():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM licenses WHERE status='active'").fetchone()[0]
        revoked = conn.execute("SELECT COUNT(*) FROM licenses WHERE status='revoked'").fetchone()[0]
        devices = conn.execute("SELECT SUM(activations) FROM licenses").fetchone()[0] or 0
        today = conn.execute("SELECT COUNT(*) FROM activity_log WHERE date(created_at)=date('now')").fetchone()[0]
    return jsonify({
        "ok": True, "total": total, "active": active, "revoked": revoked, "devices": devices, "today": today
    })

@app.route("/admin/list")
@require_secret
def list_serials():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
    return jsonify({"ok": True, "serials": [dict(r) for r in rows]})

@app.route("/admin/create", methods=["POST"])
@require_secret
def create():
    data = request.json
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    serial = ''.join(random.choices(chars, k=5)) + '-' + ''.join(random.choices(chars, k=4))
    expiry_days = int(data.get("expiry_days", 0))
    expiry = (datetime.now() + timedelta(days=expiry_days)).isoformat() if expiry_days > 0 else None
    
    with get_db() as conn:
        conn.execute("INSERT INTO licenses (serial, max_activations, expiry_date, plan, customer_name) VALUES (?,?,?,?,?)",
                    (serial, data.get("max_activations", 2), expiry, data.get("plan", "pro"), data.get("customer_name", "")))
        conn.commit()
    return jsonify({"ok": True, "serial": serial, "expiry": expiry or "♾️"})

@app.route("/api/validate", methods=["POST"])
def validate():
    data = request.json or {}
    serial = data.get("serial", "").strip().upper()
    hw_id = data.get("hw_id", "").strip()
    if data.get("secret") != API_SECRET: return jsonify({"ok": False, "msg": "API Key Error"}), 403
    
    with get_db() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE serial=?", (serial,)).fetchone()
        if not row: return jsonify({"ok": False, "msg": "Invalid Serial"})
        if row["status"] != "active": return jsonify({"ok": False, "msg": "Serial Revoked"})
        
        hw_ids = json.loads(row["hw_ids"])
        if hw_id not in hw_ids:
            if row["activations"] >= row["max_activations"]:
                return jsonify({"ok": False, "msg": "Device Limit Reached"})
            hw_ids.append(hw_id)
            conn.execute("UPDATE licenses SET hw_ids=?, activations=activations+1 WHERE serial=?", (json.dumps(hw_ids), serial))
            conn.commit()
            
    return jsonify({"ok": True, "msg": "Verified", "plan": row["plan"]})

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD HTML (INTEGRATED WITH YOUR URL)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FB Grappr Pro — لوحة التحكم</title>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;700;900&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #080b10; --bg2: #0d1117; --bg3: #161b22; --bg4: #21262d;
  --border: #30363d; --text: #e6edf3; --muted: #8b949e;
  --blue: #388bfd; --blue2: #1f6feb; --green: #3fb950; --red: #f85149;
}
body { font-family: 'Tajawal', sans-serif; background: var(--bg); color: var(--text); margin:0; }
#login-screen { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; background: var(--bg); }
.login-card { width: 400px; background: var(--bg3); border: 1px solid var(--border); border-radius: 20px; padding: 40px; text-align: center; }
input { width: 100%; padding: 12px; margin: 10px 0; background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; color: white; box-sizing: border-box; }
.login-btn { width: 100%; padding: 14px; background: var(--blue2); border: none; border-radius: 10px; color: white; cursor: pointer; font-weight: 700; transition: 0.3s; }
.login-btn:hover { background: var(--blue); }
#app { display: none; padding-right: 260px; }
.sidebar { position: fixed; right: 0; top: 0; bottom: 0; width: 260px; background: var(--bg3); border-left: 1px solid var(--border); padding: 20px; }
.nav-item { padding: 12px; cursor: pointer; border-radius: 8px; margin-bottom: 5px; color: var(--muted); transition: 0.3s; }
.nav-item:hover, .nav-item.active { background: var(--bg4); color: white; }
.main-content { padding: 40px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin-bottom: 30px; }
.stat-card { background: var(--bg3); padding: 20px; border-radius: 15px; border: 1px solid var(--border); text-align: center; }
.stat-value { font-size: 28px; font-weight: 900; color: var(--blue); }
table { width: 100%; border-collapse: collapse; background: var(--bg3); border-radius: 10px; overflow: hidden; margin-top: 20px; }
th, td { padding: 15px; text-align: right; border-bottom: 1px solid var(--border); }
th { background: var(--bg4); color: var(--muted); font-size: 13px; }
.badge { padding: 4px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; }
.badge-active { background: rgba(63, 185, 80, 0.2); color: var(--green); }
</style>
</head>
<body>

<div id="login-screen">
  <div class="login-card">
    <div style="font-size: 50px; margin-bottom: 10px;">⚡</div>
    <h2>FB Grappr Pro</h2>
    <p style="color: var(--muted); font-size: 12px; margin-bottom: 20px;">نظام إدارة التراخيص - 2026</p>
    <input type="password" id="api-secret" placeholder="ادخل المفتاح السري" autofocus>
    <button class="login-btn" onclick="doLogin()">🚀 دخول للنظام</button>
    <div id="err" style="color:var(--red); font-size:12px; margin-top:10px; display:none">❌ المفتاح السري غير صحيح</div>
  </div>
</div>

<div id="app">
  <aside class="sidebar">
    <h3 style="color: var(--blue);">⚡ FB Grappr</h3>
    <hr style="border: 0; border-top: 1px solid var(--border); margin: 20px 0;">
    <div class="nav-item active" onclick="showPage('dashboard')">📊 الرئيسية</div>
    <div class="nav-item" onclick="showPage('create')">✨ إنشاء سيريال</div>
    <div class="nav-item" onclick="location.reload()" style="color: var(--red);">🚪 خروج</div>
  </aside>

  <main class="main-content">
    <div id="page-dashboard" class="page active">
      <div class="stats-grid">
        <div class="stat-card"><div>إجمالي السيريالات</div><div class="stat-value" id="stat-total">0</div></div>
        <div class="stat-card"><div>نشط</div><div class="stat-value" id="stat-active">0</div></div>
        <div class="stat-card"><div>أجهزة مفعلة</div><div class="stat-value" id="stat-devices">0</div></div>
        <div class="stat-card"><div>طلبات اليوم</div><div class="stat-value" id="stat-today">0</div></div>
      </div>
      
      <div style="background: var(--bg3); padding: 20px; border-radius: 15px; border: 1px solid var(--border);">
        <h3 style="margin-top: 0;">🔑 قائمة التراخيص</h3>
        <table>
          <thead><tr><th>العميل</th><th>السيريال</th><th>الأجهزة</th><th>الحالة</th></tr></thead>
          <tbody id="serials-table"></tbody>
        </table>
      </div>
    </div>

    <div id="page-create" class="page" style="display:none">
       <div class="login-card" style="text-align:right; width:100%; max-width: 500px; margin: auto;">
          <h3>✨ توليد ترخيص جديد</h3>
          <label style="font-size: 13px; color: var(--muted);">👤 اسم العميل</label>
          <input type="text" id="new-name" placeholder="مثال: أحمد محمد">
          <label style="font-size: 13px; color: var(--muted);">📅 عدد أيام الصلاحية (0 للابد)</label>
          <input type="number" id="new-days" value="30">
          <button class="login-btn" onclick="createNewSerial()">🛠️ إنشاء السيريال</button>
          <div id="res-box" style="display:none; margin-top:20px; padding:15px; background:var(--bg4); border-radius:10px; text-align:center">
             <div style="font-size: 12px; color: var(--green);">تم الإنشاء بنجاح:</div>
             <h3 id="result-serial" style="color:var(--blue); letter-spacing: 2px;"></h3>
          </div>
       </div>
    </div>
  </main>
</div>

<script>
// الرابط الخاص بك مدمج هنا مباشرة
const SERVER_URL = 'https://fbgrapper-production.up.railway.app';
let API_KEY = 'fbgrappr_2026';

async function doLogin() {
    API_KEY = document.getElementById('api-secret').value;
    try {
        const res = await fetch(`${SERVER_URL}/admin/stats`, { headers: {'X-API-Secret': API_KEY}});
        if(res.ok) {
            document.getElementById('login-screen').style.display = 'none';
            document.getElementById('app').style.display = 'block';
            refreshData();
        } else {
            document.getElementById('err').style.display = 'block';
        }
    } catch(e) {
        alert("خطأ في الاتصال بالسيرفر");
    }
}

async function refreshData() {
    const sRes = await fetch(`${SERVER_URL}/admin/stats`, { headers: {'X-API-Secret': API_KEY}});
    const stats = await sRes.json();
    document.getElementById('stat-total').innerText = stats.total;
    document.getElementById('stat-active').innerText = stats.active;
    document.getElementById('stat-devices').innerText = stats.devices;
    document.getElementById('stat-today').innerText = stats.today;

    const lRes = await fetch(`${SERVER_URL}/admin/list`, { headers: {'X-API-Secret': API_KEY}});
    const list = await lRes.json();
    let rows = '';
    list.serials.forEach(s => {
        rows += `<tr>
            <td>${s.customer_name || 'بدون اسم'}</td>
            <td style="font-family:monospace; color:var(--blue)">${s.serial}</td>
            <td>${s.activations}/${s.max_activations}</td>
            <td><span class="badge badge-active">${s.status}</span></td>
        </tr>`;
    });
    document.getElementById('serials-table').innerHTML = rows || '<tr><td colspan="4" style="text-align:center">لا يوجد سيريالات حالياً</td></tr>';
}

async function createNewSerial() {
    const name = document.getElementById('new-name').value;
    const days = document.getElementById('new-days').value;
    
    const res = await fetch(`${SERVER_URL}/admin/create`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-API-Secret': API_KEY},
        body: JSON.stringify({ customer_name: name, expiry_days: days, plan: 'pro' })
    });
    
    const result = await res.json();
    if(result.ok) {
        document.getElementById('res-box').style.display = 'block';
        document.getElementById('result-serial').innerText = result.serial;
        refreshData();
    }
}

function showPage(p) {
    document.querySelectorAll('.page').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.getElementById('page-' + p).style.display = 'block';
    event.currentTarget.classList.add('active');
}
</script>
</body>
</html>
    """)

if __name__ == "__main__":
    # تشغيل السيرفر على البورت المخصص من Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
