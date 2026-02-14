"""
FB Grappr Pro — License Server
يشتغل على Railway مجاناً
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify

app = Flask(__name__)

# ── مفتاح سري — غيّره لأي كلام تختاره ──────────────────────────────────────
API_SECRET = os.environ.get("API_SECRET", "mohDev")
DB_PATH    = os.environ.get("DB_PATH", "license.db")


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS licenses (
                serial          TEXT PRIMARY KEY,
                hw_ids          TEXT DEFAULT '[]',
                activations     INTEGER DEFAULT 0,
                max_activations INTEGER DEFAULT 2,
                expiry_date     TEXT,
                status          TEXT DEFAULT 'active',
                plan            TEXT DEFAULT 'basic',
                customer_name   TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
# AUTH MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════════════

def require_secret(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        secret = request.headers.get("X-API-Secret") or request.json.get("secret", "") if request.json else ""
        if secret != API_SECRET:
            return jsonify({"ok": False, "msg": "غير مصرح"}), 403
        return f(*args, **kwargs)
    return decorated


def log_activity(serial, hw_id, action, result):
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO activity_log (serial,hw_id,action,ip,result) VALUES (?,?,?,?,?)",
                (serial, hw_id, action, request.remote_addr, result)
            )
            conn.commit()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS — العميل بيستخدمهم
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/validate", methods=["POST"])
def validate():
    """التحقق من Serial + تسجيل الجهاز"""
    data    = request.json or {}
    serial  = data.get("serial", "").strip().upper()
    hw_id   = data.get("hw_id", "").strip()
    secret  = data.get("secret", "")

    if secret != API_SECRET:
        return jsonify({"ok": False, "msg": "غير مصرح"}), 403

    if not serial or not hw_id:
        return jsonify({"ok": False, "msg": "بيانات ناقصة"})

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM licenses WHERE serial=?", (serial,)
        ).fetchone()

        if not row:
            log_activity(serial, hw_id, "validate", "not_found")
            return jsonify({"ok": False, "msg": "الـ Serial غير موجود!"})

        if row["status"] != "active":
            log_activity(serial, hw_id, "validate", "revoked")
            return jsonify({"ok": False, "msg": "تم إيقاف هذا الـ Serial!"})

        # التحقق من الصلاحية
        if row["expiry_date"]:
            try:
                if datetime.now() > datetime.fromisoformat(row["expiry_date"]):
                    log_activity(serial, hw_id, "validate", "expired")
                    return jsonify({"ok": False, "msg": "انتهت صلاحية الاشتراك!"})
            except ValueError:
                pass

        hw_ids = json.loads(row["hw_ids"] or "[]")

        # الجهاز مسجّل مسبقاً
        if hw_id in hw_ids:
            log_activity(serial, hw_id, "validate", "ok_existing")
            return jsonify({
                "ok":      True,
                "msg":     "مفعّل ✓",
                "plan":    row["plan"],
                "expiry":  row["expiry_date"] or "غير محدد",
                "name":    row["customer_name"] or ""
            })

        # جهاز جديد — تحقق من الحد
        if row["activations"] >= row["max_activations"]:
            log_activity(serial, hw_id, "validate", "max_reached")
            return jsonify({
                "ok":  False,
                "msg": f"تم استخدام الـ Serial على {row['max_activations']} أجهزة بالفعل!"
            })

        # سجّل الجهاز الجديد
        hw_ids.append(hw_id)
        conn.execute(
            "UPDATE licenses SET hw_ids=?, activations=activations+1 WHERE serial=?",
            (json.dumps(hw_ids), serial)
        )
        conn.commit()

        log_activity(serial, hw_id, "validate", "ok_new_device")
        return jsonify({
            "ok":     True,
            "msg":    f"تم التفعيل! ({row['activations']+1}/{row['max_activations']})",
            "plan":   row["plan"],
            "expiry": row["expiry_date"] or "غير محدد",
            "name":   row["customer_name"] or ""
        })


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS — الأدمن بس
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/create", methods=["POST"])
@require_secret
def create_serial():
    """إنشاء Serial جديد"""
    import random
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    serial = ''.join(random.choices(chars, k=5)) + '-' + ''.join(random.choices(chars, k=4))

    data          = request.json or {}
    max_act       = int(data.get("max_activations", 2))
    expiry_days   = int(data.get("expiry_days", 0))
    plan          = data.get("plan", "basic")
    customer_name = data.get("customer_name", "")

    expiry = None
    if expiry_days > 0:
        expiry = (datetime.now() + timedelta(days=expiry_days)).isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO licenses (serial,max_activations,expiry_date,plan,customer_name) VALUES (?,?,?,?,?)",
            (serial, max_act, expiry, plan, customer_name)
        )
        conn.commit()

    return jsonify({
        "ok":     True,
        "serial": serial,
        "plan":   plan,
        "expiry": expiry or "غير محدد",
        "max":    max_act
    })


@app.route("/admin/list", methods=["GET"])
@require_secret
def list_serials():
    """قائمة كل الـ Serials"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT serial,activations,max_activations,expiry_date,status,plan,customer_name,created_at FROM licenses ORDER BY created_at DESC"
        ).fetchall()
    return jsonify({"ok": True, "serials": [dict(r) for r in rows]})


@app.route("/admin/revoke", methods=["POST"])
@require_secret
def revoke_serial():
    """إيقاف Serial"""
    serial = (request.json or {}).get("serial", "").strip().upper()
    if not serial:
        return jsonify({"ok": False, "msg": "أدخل الـ Serial"})
    with get_db() as conn:
        cur = conn.execute("UPDATE licenses SET status='revoked' WHERE serial=?", (serial,))
        conn.commit()
    return jsonify({"ok": cur.rowcount > 0, "msg": "تم الإيقاف" if cur.rowcount else "Serial غير موجود"})


@app.route("/admin/reactivate", methods=["POST"])
@require_secret
def reactivate_serial():
    """إعادة تفعيل Serial"""
    serial = (request.json or {}).get("serial", "").strip().upper()
    with get_db() as conn:
        cur = conn.execute("UPDATE licenses SET status='active' WHERE serial=?", (serial,))
        conn.commit()
    return jsonify({"ok": cur.rowcount > 0, "msg": "تمت إعادة التفعيل"})


@app.route("/admin/reset_devices", methods=["POST"])
@require_secret
def reset_devices():
    """مسح الأجهزة المسجّلة على Serial معين"""
    serial = (request.json or {}).get("serial", "").strip().upper()
    with get_db() as conn:
        conn.execute("UPDATE licenses SET hw_ids='[]', activations=0 WHERE serial=?", (serial,))
        conn.commit()
    return jsonify({"ok": True, "msg": "تم مسح الأجهزة"})


@app.route("/admin/log", methods=["GET"])
@require_secret
def get_log():
    """سجل النشاط"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    return jsonify({"ok": True, "log": [dict(r) for r in rows]})


@app.route("/admin/stats", methods=["GET"])
@require_secret
def get_stats():
    """إحصائيات سريعة"""
    with get_db() as conn:
        total    = conn.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
        active   = conn.execute("SELECT COUNT(*) FROM licenses WHERE status='active'").fetchone()[0]
        revoked  = conn.execute("SELECT COUNT(*) FROM licenses WHERE status='revoked'").fetchone()[0]
        devices  = conn.execute("SELECT SUM(activations) FROM licenses").fetchone()[0] or 0
        today    = conn.execute(
            "SELECT COUNT(*) FROM activity_log WHERE date(created_at)=date('now')"
        ).fetchone()[0]
    return jsonify({
        "ok": True,
        "total_serials":  total,
        "active_serials": active,
        "revoked":        revoked,
        "total_devices":  devices,
        "requests_today": today
    })


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "FB Grappr Pro License Server", "version": "2.0"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
