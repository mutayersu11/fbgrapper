"""
FB Grappr Pro SaaS v2.0.0
"""
import sys, os, sqlite3, hashlib, threading, time, re, urllib.parse, uuid, json, subprocess
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
from datetime import datetime, timedelta

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

try:
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_WDM = True
except ImportError:
    HAS_WDM = False

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QTextEdit, QLabel, QLineEdit, QProgressBar,
    QDialog, QFormLayout, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox, QFrame,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor

APP_NAME    = "FB Grappr Pro SaaS"
APP_VERSION = "2.0.0"
APP_DB      = "fb_pro.db"

# ← غيّر الرابط ده برابط السيرفر بتاعك على Railway
SERVER_URL  = "https://YOUR-APP.railway.app"
API_SECRET  = "fbgrappr_secret_2024"
SCREEN_RECORDERS = {'obs64.exe','obs32.exe','xsplit.exe','bandicam.exe','sharex.exe','camtasia.exe'}
EG_PHONE_REGEX   = r'(?:\+?20|0)?1[0-2,5][0-9]{8}'

DARK_BASE = """
QWidget{background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',sans-serif;font-size:13px;}
QLabel{color:#c9d1d9;}
QLineEdit,QTextEdit,QSpinBox,QComboBox{background:#161b22;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;padding:10px 14px;font-size:13px;}
QLineEdit:focus,QTextEdit:focus,QSpinBox:focus{border-color:#388bfd;}
QLineEdit:disabled{background:#0d1117;color:#484f58;}
QPushButton{background:#21262d;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;padding:10px 20px;font-size:13px;font-weight:600;min-height:36px;}
QPushButton:hover{background:#30363d;border-color:#8b949e;}
QPushButton:pressed{background:#161b22;}
QPushButton:disabled{background:#161b22;color:#484f58;border-color:#21262d;}
QPushButton#primary{background:#1f6feb;border-color:#388bfd;color:white;}
QPushButton#primary:hover{background:#388bfd;}
QPushButton#success{background:#238636;border-color:#2ea043;color:white;}
QPushButton#success:hover{background:#2ea043;}
QPushButton#danger{background:#b62324;border-color:#da3633;color:white;}
QPushButton#danger:hover{background:#da3633;}
QTableWidget{background:#161b22;border:1px solid #30363d;border-radius:8px;gridline-color:#21262d;alternate-background-color:#0d1117;}
QTableWidget::item{padding:10px 14px;border:none;}
QTableWidget::item:selected{background:#1f6feb;color:white;}
QHeaderView::section{background:#21262d;color:#8b949e;padding:10px 14px;border:none;border-bottom:1px solid #30363d;font-weight:600;font-size:12px;}
QTabWidget::pane{border:1px solid #30363d;border-radius:8px;background:#161b22;margin-top:-1px;}
QTabBar::tab{background:transparent;color:#8b949e;padding:10px 20px;border-bottom:2px solid transparent;font-weight:600;}
QTabBar::tab:selected{color:#c9d1d9;border-bottom:2px solid #388bfd;}
QTabBar::tab:hover{color:#c9d1d9;background:#161b22;}
QProgressBar{border:none;border-radius:6px;background:#21262d;text-align:center;color:white;font-weight:600;font-size:12px;min-height:20px;}
QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1f6feb,stop:1 #388bfd);border-radius:6px;}
QScrollBar:vertical{background:#161b22;width:8px;border-radius:4px;}
QScrollBar::handle:vertical{background:#30363d;border-radius:4px;min-height:30px;}
QScrollBar::handle:vertical:hover{background:#484f58;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
QFrame#card{background:#161b22;border:1px solid #30363d;border-radius:12px;}
"""
DIALOG_EXTRA = "QDialog{background:#0d1117;}"


def get_chrome_driver():
    opts = Options()
    opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--window-size=1920,1080')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    if HAS_WDM:
        try:
            svc = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=svc, options=opts)
        except Exception:
            pass

    try:
        base = os.path.dirname(sys.executable if getattr(sys,'frozen',False) else __file__)
        drv  = os.path.join(base, 'chromedriver.exe')
        if os.path.isfile(drv):
            return webdriver.Chrome(service=Service(drv), options=opts)
    except Exception:
        pass

    try:
        return webdriver.Chrome(options=opts)
    except Exception as e:
        raise RuntimeError(
            f"تعذّر تشغيل ChromeDriver.\n\nالخطأ: {e}\n\n"
            "الحل: حمّل chromedriver.exe المناسب لنسخة Chrome\n"
            "من: https://chromedriver.chromium.org/downloads\n"
            "وحطّه في نفس مجلد البرنامج."
        )


class AntiPiracy:
    _hw: str = ""

    @staticmethod
    def get_hardware_id() -> str:
        if AntiPiracy._hw:
            return AntiPiracy._hw
        try:
            parts = []
            try:
                out = subprocess.check_output("wmic cpu get ProcessorId", shell=True, stderr=subprocess.DEVNULL).decode(errors='ignore')
                lines = [l.strip() for l in out.splitlines() if l.strip() and l.strip() != 'ProcessorId']
                parts.append(lines[0] if lines else 'cpu_default')
            except Exception:
                parts.append('cpu_default')
            mac = ':'.join(f'{(uuid.getnode()>>i)&0xff:02x}' for i in range(0,48,8))
            parts.append(mac)
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
                guid,_ = winreg.QueryValueEx(key,"MachineGuid")
                parts.append(str(guid))
            except Exception:
                parts.append('guid_default')
            AntiPiracy._hw = hashlib.sha256('_'.join(parts).encode()).hexdigest()[:16].upper()
            return AntiPiracy._hw
        except Exception:
            return "HWID_DEFAULT_00"

    @staticmethod
    def is_screen_recording() -> bool:
        try:
            import psutil
            for p in psutil.process_iter(['name']):
                if (p.info.get('name') or '').lower() in SCREEN_RECORDERS:
                    return True
        except Exception:
            pass
        return False


class LicenseManager:
    """التحقق من الـ Serial أونلاين عبر السيرفر"""

    def _post(self, endpoint, data):
        if not HAS_REQUESTS:
            return {"ok": False, "msg": "مكتبة requests غير مثبتة!"}
        try:
            resp = requests.post(
                f"{SERVER_URL}{endpoint}",
                json={**data, "secret": API_SECRET},
                timeout=10
            )
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"ok": False, "msg": "لا يوجد اتصال بالإنترنت!"}
        except requests.exceptions.Timeout:
            return {"ok": False, "msg": "انتهت مهلة الاتصال بالسيرفر!"}
        except Exception as e:
            return {"ok": False, "msg": f"خطأ: {e}"}

    def _get(self, endpoint):
        if not HAS_REQUESTS:
            return {"ok": False, "msg": "مكتبة requests غير مثبتة!"}
        try:
            resp = requests.get(
                f"{SERVER_URL}{endpoint}",
                headers={"X-API-Secret": API_SECRET},
                timeout=10
            )
            return resp.json()
        except Exception as e:
            return {"ok": False, "msg": str(e)}

    def validate_serial(self, serial):
        """تحقق سريع من الصيغة فقط (بدون اتصال)"""
        s = re.sub(r"[^A-Za-z0-9\-]", "", serial.strip().upper())
        if len(s) != 10 or s[5] != "-":
            return False, "تنسيق غير صحيح (XXXXX-XXXX)"
        return True, "صالح"

    def activate_serial(self, serial):
        """التحقق الحقيقي عبر السيرفر"""
        s = re.sub(r"[^A-Za-z0-9\-]", "", serial.strip().upper())
        hw = AntiPiracy.get_hardware_id()
        result = self._post("/api/validate", {"serial": s, "hw_id": hw})
        return result.get("ok", False), result.get("msg", "خطأ غير معروف")

    # Admin functions
    def create_license(self, serial, max_act=2, expiry_days=0, customer_name=""):
        result = self._post("/admin/create", {
            "max_activations": max_act,
            "expiry_days": expiry_days,
            "customer_name": customer_name
        })
        return result.get("ok", False), result.get("serial", ""), result.get("msg", "")

    def get_all_licenses(self):
        result = self._get("/admin/list")
        if not result.get("ok"):
            return []
        rows = []
        for r in result.get("serials", []):
            rows.append((
                r.get("serial",""),
                json.dumps([]),
                r.get("activations",0),
                r.get("max_activations",2),
                r.get("expiry_date",""),
                r.get("status",""),
            ))
        return rows

    def revoke_serial(self, serial):
        result = self._post("/admin/revoke", {"serial": serial})
        return result.get("ok", False)

    def reset_devices(self, serial):
        result = self._post("/admin/reset_devices", {"serial": serial})
        return result.get("ok", False)

    def get_stats(self):
        return self._get("/admin/stats")


class FBProDatabase:
    def __init__(self, path=APP_DB):
        self._lock = threading.Lock()
        self.conn  = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('PRAGMA journal_mode=WAL')
        with self._lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS users(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,role TEXT DEFAULT 'user',
                    credits INTEGER DEFAULT 5000,serial TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS leads(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,
                    phone TEXT NOT NULL,keyword TEXT,location TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id,phone),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
            """)
            self.conn.executemany(
                "INSERT OR IGNORE INTO users(username,password_hash,role,credits) VALUES(?,?,?,?)",
                [('admin','ProAdmin2024!','admin',999999),('user','User123Pro!','user',5000)]
            )
            self.conn.commit()

    def verify_user(self, u, p):
        with self._lock:
            row = self.conn.execute("SELECT id,role,credits,serial FROM users WHERE username=? AND password_hash=?",(u,p)).fetchone()
        return {"id":row[0],"role":row[1],"credits":row[2],"serial":row[3]} if row else None

    def get_user_stats(self, uid):
        with self._lock:
            row = self.conn.execute("""
                SELECT COALESCE(u.credits,0),COUNT(l.id) FROM users u
                LEFT JOIN leads l ON u.id=l.user_id WHERE u.id=? GROUP BY u.id""",(uid,)).fetchone()
        return row or (0,0)

    def save_leads(self, uid, phones, kw, loc):
        added = 0
        with self._lock:
            cur = self.conn.cursor()
            for ph in phones:
                try:
                    cur.execute("INSERT INTO leads(user_id,phone,keyword,location) VALUES(?,?,?,?)",(uid,ph,kw,loc))
                    added += 1
                except sqlite3.IntegrityError:
                    pass
            self.conn.commit()
        return added

    def get_user_leads(self, uid, limit=50000):
        with self._lock:
            return self.conn.execute("SELECT phone,scraped_at FROM leads WHERE user_id=? ORDER BY scraped_at DESC LIMIT ?",(uid,limit)).fetchall()

    def get_all_users(self):
        with self._lock:
            return self.conn.execute("SELECT id,username,role,credits,created_at FROM users").fetchall()

    def close(self): self.conn.close()


class ScraperThread(QThread):
    progress        = pyqtSignal(int)
    log             = pyqtSignal(str)
    finished_signal = pyqtSignal(list)
    error_signal    = pyqtSignal(str)

    def __init__(self, keywords, locations, max_phones=1000):
        super().__init__()
        self.keywords=keywords; self.locations=locations
        self.max_phones=max_phones; self.driver=None; self._stop=False

    def stop(self): self._stop=True

    def run(self):
        if not HAS_SELENIUM:
            self.error_signal.emit("مكتبة selenium غير مثبتة.\nشغّل: pip install selenium webdriver-manager")
            return
        phones = set()
        try:
            self.log.emit("⏳ جاري تشغيل المتصفح...")
            self.driver = get_chrome_driver()
            self.log.emit("✅ تم تشغيل المتصفح")
            total = len(self.keywords)*len(self.locations); done=0
            for kw in self.keywords:
                if self._stop: break
                for loc in self.locations:
                    if self._stop: break
                    self.log.emit(f"🔍 البحث: «{kw}» في «{loc}»")
                    url = f"https://www.facebook.com/search/top?q={urllib.parse.quote(kw+' '+loc)}"
                    try:
                        self.driver.get(url); time.sleep(3)
                        for _ in range(3):
                            self.driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
                            time.sleep(1.5)
                        for art in self.driver.find_elements(By.CSS_SELECTOR,'[role="article"]')[:30]:
                            try: phones.update(re.findall(EG_PHONE_REGEX, art.text))
                            except Exception: pass
                    except Exception as e:
                        self.log.emit(f"⚠️ {e}")
                    done+=1; self.progress.emit(int(done/total*100))
                    self.log.emit(f"📊 تم جمع {len(phones)} رقم")
                    if len(phones)>=self.max_phones:
                        self.log.emit("✅ تم الوصول للحد الأقصى."); break
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            if self.driver:
                try: self.driver.quit()
                except Exception: pass
        self.finished_signal.emit(list(phones))


def mkbtn(text, obj=""):
    b=QPushButton(text)
    if obj: b.setObjectName(obj)
    return b

def mkcard():
    f=QFrame(); f.setObjectName("card"); return f


class StatCard(QFrame):
    def __init__(self, icon, label, value):
        super().__init__(); self.setObjectName("card"); self.setFixedHeight(88)
        ly=QHBoxLayout(self); ly.setContentsMargins(20,14,20,14)
        il=QLabel(icon); il.setFont(QFont("Segoe UI Emoji",22)); il.setFixedWidth(44); ly.addWidget(il)
        col=QVBoxLayout(); col.setSpacing(2)
        self.vl=QLabel(value); self.vl.setFont(QFont("Segoe UI",17,QFont.Weight.Bold)); self.vl.setStyleSheet("color:#c9d1d9;")
        ll=QLabel(label); ll.setStyleSheet("color:#8b949e;font-size:11px;")
        col.addWidget(self.vl); col.addWidget(ll); ly.addLayout(col)
    def set_value(self,v): self.vl.setText(v)


class BaseDialog(QDialog):
    def __init__(self, parent=None, title=APP_NAME, w=480, h=420):
        super().__init__(parent); self.setWindowTitle(title); self.setFixedSize(w,h)
        self.setStyleSheet(DARK_BASE+DIALOG_EXTRA)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint,False)


class SerialActivationDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent,"تفعيل الترخيص",520,380)
        self.lm=LicenseManager(); self._build()

    def _build(self):
        ly=QVBoxLayout(self); ly.setSpacing(14); ly.setContentsMargins(40,34,40,34)
        h=QLabel("🔐  تفعيل الترخيص الرقمي"); h.setFont(QFont("Segoe UI",19,QFont.Weight.Bold))
        h.setAlignment(Qt.AlignmentFlag.AlignCenter); h.setStyleSheet("color:#388bfd;"); ly.addWidget(h)
        s=QLabel("أدخل كود التفعيل لفتح جميع الميزات"); s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet("color:#8b949e;font-size:12px;"); ly.addWidget(s)
        hw=AntiPiracy.get_hardware_id()
        hwl=QLabel(f"🖥  معرف جهازك:  {hw}")
        hwl.setStyleSheet("font-family:Consolas,monospace;font-size:12px;color:#3fb950;padding:10px 16px;background:#161b22;border:1px solid #30363d;border-radius:8px;")
        hwl.setAlignment(Qt.AlignmentFlag.AlignCenter); ly.addWidget(hwl)
        self.inp=QLineEdit(); self.inp.setPlaceholderText("XXXXX-XXXX")
        self.inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.inp.setFont(QFont("Consolas",16,QFont.Weight.Bold)); self.inp.setMaxLength(10)
        self.inp.textChanged.connect(self._chg); ly.addWidget(self.inp)
        self.stl=QLabel("⏳  أدخل الـ Serial للتحقق")
        self.stl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stl.setStyleSheet("color:#8b949e;font-size:13px;padding:10px;background:#161b22;border-radius:8px;")
        ly.addWidget(self.stl)
        row=QHBoxLayout()
        self.ab=mkbtn("✅  تفعيل","primary"); self.ab.setEnabled(False); self.ab.clicked.connect(self._act); row.addWidget(self.ab)
        sk=mkbtn("تجاوز (تجربة مجانية)"); sk.clicked.connect(self.accept); row.addWidget(sk)
        ly.addLayout(row)

    def _chg(self, text):
        raw=re.sub(r'[^A-Za-z0-9]','',text.upper())
        fmt=(raw[:5]+'-'+raw[5:9]) if len(raw)>5 else raw
        if fmt!=text:
            self.inp.blockSignals(True); self.inp.setText(fmt); self.inp.blockSignals(False)
        ok,msg=self.lm.validate_serial(fmt)
        if len(fmt)<10:
            self.stl.setText("⏳  أدخل الـ Serial للتحقق")
            self.stl.setStyleSheet("color:#8b949e;font-size:13px;padding:10px;background:#161b22;border-radius:8px;")
            self.ab.setEnabled(False)
        elif ok:
            self.stl.setText("✅  صالح – جاهز للتفعيل")
            self.stl.setStyleSheet("color:#3fb950;font-size:13px;padding:10px;background:#161b22;border-radius:8px;")
            self.ab.setEnabled(True)
        else:
            self.stl.setText(f"❌  {msg}")
            self.stl.setStyleSheet("color:#f85149;font-size:13px;padding:10px;background:#161b22;border-radius:8px;")
            self.ab.setEnabled(False)

    def _act(self):
        ok,msg=self.lm.activate_serial(self.inp.text().strip().upper())
        if ok: QMessageBox.information(self,"✅ تفعيل ناجح",f"🎉 {msg}"); self.accept()
        else: QMessageBox.critical(self,"❌ فشل",msg)


class LoginDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent,APP_NAME,420,360)
        self.db=FBProDatabase(); self.user_data=None; self._build()

    def _build(self):
        ly=QVBoxLayout(self); ly.setSpacing(12); ly.setContentsMargins(44,36,44,36)
        logo=QLabel("⚡"); logo.setFont(QFont("Segoe UI Emoji",34)); logo.setAlignment(Qt.AlignmentFlag.AlignCenter); ly.addWidget(logo)
        t=QLabel(APP_NAME); t.setFont(QFont("Segoe UI",17,QFont.Weight.Bold))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter); t.setStyleSheet("color:#388bfd;"); ly.addWidget(t)
        v=QLabel(f"v{APP_VERSION}  •  منصة جمع الأرقام المتقدمة")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter); v.setStyleSheet("color:#484f58;font-size:11px;margin-bottom:6px;"); ly.addWidget(v)
        self.ui=QLineEdit(); self.ui.setPlaceholderText("اسم المستخدم"); ly.addWidget(self.ui)
        self.pi=QLineEdit(); self.pi.setPlaceholderText("كلمة السر")
        self.pi.setEchoMode(QLineEdit.EchoMode.Password)
        self.pi.returnPressed.connect(self._login); ly.addWidget(self.pi)
        b=mkbtn("🚀  تسجيل الدخول","primary"); b.clicked.connect(self._login); ly.addWidget(b)
        sb=mkbtn("🔑  تفعيل Serial","success"); sb.clicked.connect(lambda: SerialActivationDialog(self).exec()); ly.addWidget(sb)

    def _login(self):
        u=self.ui.text().strip(); p=self.pi.text()
        if not u or not p: QMessageBox.warning(self,"تنبيه","أدخل اسم المستخدم وكلمة السر."); return
        self.user_data=self.db.verify_user(u,p)
        if self.user_data: self.accept()
        else: QMessageBox.critical(self,"❌ خطأ","بيانات الدخول غير صحيحة!"); self.pi.clear(); self.pi.setFocus()


class AntiPiracyWarningDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent,"تحذير",500,320)
        self.setWindowFlags(Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(self.styleSheet()+"QDialog{background:#b62324;}QLabel{color:white;}")
        ly=QVBoxLayout(self); ly.setContentsMargins(48,36,48,36); ly.setSpacing(14)
        il=QLabel("🚨"); il.setFont(QFont("Segoe UI Emoji",48)); il.setAlignment(Qt.AlignmentFlag.AlignCenter); ly.addWidget(il)
        t=QLabel("تحذير أمني!"); t.setFont(QFont("Segoe UI",22,QFont.Weight.Bold)); t.setAlignment(Qt.AlignmentFlag.AlignCenter); ly.addWidget(t)
        m=QLabel("تم اكتشاف برنامج تصوير شاشة!\nالبرنامج محمي بتقنية Anti-Piracy.\nسيُغلق تلقائياً خلال 5 ثوانٍ...")
        m.setWordWrap(True); m.setAlignment(Qt.AlignmentFlag.AlignCenter); m.setStyleSheet("font-size:14px;"); ly.addWidget(m)
        QTimer.singleShot(5000,self.accept)


class ScrapingTab(QWidget):
    def __init__(self, uid, db, on_done):
        super().__init__(); self.uid=uid; self.db=db; self.on_done=on_done; self.scraper=None; self._build()

    def _build(self):
        ly=QVBoxLayout(self); ly.setSpacing(14); ly.setContentsMargins(24,18,24,18)
        card=mkcard(); cl=QVBoxLayout(card); cl.setContentsMargins(20,16,20,16); cl.setSpacing(12)
        t=QLabel("⚙️  إعدادات البحث"); t.setFont(QFont("Segoe UI",13,QFont.Weight.Bold)); t.setStyleSheet("color:#388bfd;"); cl.addWidget(t)
        form=QFormLayout(); form.setSpacing(10); form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.kw=QLineEdit(); self.kw.setPlaceholderText("مثال: نجار, سباك, كهربائي"); form.addRow("🏷  الكلمات:",self.kw)
        self.loc=QLineEdit(); self.loc.setPlaceholderText("مثال: القاهرة, الجيزة"); self.loc.setText("القاهرة, الجيزة"); form.addRow("📍  المناطق:",self.loc)
        self.mx=QSpinBox(); self.mx.setRange(100,10000); self.mx.setValue(1000); self.mx.setSingleStep(100); self.mx.setSuffix(" رقم"); form.addRow("🎯  الحد الأقصى:",self.mx)
        cl.addLayout(form); ly.addWidget(card)
        self.pb=QProgressBar(); self.pb.setValue(0); ly.addWidget(self.pb)
        self.log=QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(150)
        self.log.setFont(QFont("Consolas",10)); self.log.setPlaceholderText("سجل العمليات..."); ly.addWidget(self.log)
        row=QHBoxLayout()
        self.sb=mkbtn("🚀  بدء البحث","primary"); self.sb.clicked.connect(self._start); row.addWidget(self.sb)
        self.stb=mkbtn("⏹  إيقاف"); self.stb.clicked.connect(self._stop); self.stb.setEnabled(False); row.addWidget(self.stb)
        self.eb=mkbtn("📊  تصدير Excel","success"); self.eb.clicked.connect(self._export); self.eb.setEnabled(False); row.addWidget(self.eb)
        ly.addLayout(row); ly.addStretch()

    def _lg(self, msg):
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}]  {msg}")

    def _start(self):
        kws=[k.strip() for k in self.kw.text().split(',') if k.strip()]
        locs=[l.strip() for l in self.loc.text().split(',') if l.strip()]
        if not kws: QMessageBox.warning(self,"تنبيه","أدخل كلمة بحث واحدة على الأقل."); return
        if not locs: QMessageBox.warning(self,"تنبيه","أدخل منطقة واحدة على الأقل."); return
        if not HAS_SELENIUM: QMessageBox.critical(self,"خطأ","مكتبة selenium غير مثبتة!\npip install selenium webdriver-manager"); return
        self.log.clear(); self.pb.setValue(0); self.sb.setEnabled(False); self.stb.setEnabled(True); self.eb.setEnabled(False)
        self._kw=self.kw.text(); self._loc=self.loc.text()
        self.scraper=ScraperThread(kws,locs,self.mx.value())
        self.scraper.progress.connect(self.pb.setValue)
        self.scraper.log.connect(self._lg)
        self.scraper.finished_signal.connect(self._done)
        self.scraper.error_signal.connect(self._err)
        self.scraper.start()

    def _stop(self):
        if self.scraper and self.scraper.isRunning(): self.scraper.stop(); self._lg("⏹ تم طلب الإيقاف...")
        self.sb.setEnabled(True); self.stb.setEnabled(False)

    def _done(self, phones):
        added=self.db.save_leads(self.uid,phones,self._kw,self._loc)
        self._lg(f"✅ اكتمل:  {len(phones)} رقم  |  {added} جديد")
        self.pb.setValue(100); self.sb.setEnabled(True); self.stb.setEnabled(False); self.eb.setEnabled(bool(phones)); self.on_done()

    def _err(self, msg):
        self._lg(f"❌ {msg}"); QMessageBox.critical(self,"خطأ",msg); self.sb.setEnabled(True); self.stb.setEnabled(False)

    def _export(self):
        if not HAS_PANDAS: QMessageBox.critical(self,"خطأ","pip install pandas openpyxl"); return
        leads=self.db.get_user_leads(self.uid)
        if not leads: QMessageBox.information(self,"تنبيه","لا توجد أرقام."); return
        df=pd.DataFrame(leads,columns=['رقم الهاتف','تاريخ الجمع'])
        fn=f"fb_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        try:
            df.to_excel(fn,index=False,engine='openpyxl')
            QMessageBox.information(self,"✅ تم",f"تم حفظ {len(leads)} رقم في:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self,"خطأ",str(e))


class LeadsTab(QWidget):
    def __init__(self, uid, db):
        super().__init__(); self.uid=uid; self.db=db; self._build(); self.refresh()

    def _build(self):
        ly=QVBoxLayout(self); ly.setSpacing(12); ly.setContentsMargins(24,18,24,18)
        row=QHBoxLayout()
        t=QLabel("📋  سجل الأرقام المجموعة"); t.setFont(QFont("Segoe UI",13,QFont.Weight.Bold)); t.setStyleSheet("color:#388bfd;"); row.addWidget(t)
        row.addStretch(); rb=mkbtn("🔄  تحديث"); rb.setFixedWidth(100); rb.clicked.connect(self.refresh); row.addWidget(rb); ly.addLayout(row)
        self.tbl=QTableWidget(0,3)
        self.tbl.setHorizontalHeaderLabels(["📱  رقم الهاتف","📅  تاريخ الجمع","#"])
        self.tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setAlternatingRowColors(True); self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); ly.addWidget(self.tbl)

    def refresh(self):
        leads=self.db.get_user_leads(self.uid); self.tbl.setRowCount(len(leads))
        for i,(ph,ts) in enumerate(leads):
            self.tbl.setItem(i,0,QTableWidgetItem(ph)); self.tbl.setItem(i,1,QTableWidgetItem(str(ts)[:19]))
            n=QTableWidgetItem(str(i+1)); n.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.tbl.setItem(i,2,n)


class AdminTab(QWidget):
    def __init__(self, db):
        super().__init__(); self.db=db; self.lm=LicenseManager(); self._build()

    def _build(self):
        ly=QVBoxLayout(self); ly.setSpacing(14); ly.setContentsMargins(24,18,24,18)
        tabs=QTabWidget()
        sw=QWidget(); sl=QVBoxLayout(sw); sl.setSpacing(10); sl.setContentsMargins(0,14,0,0)
        sr=QHBoxLayout(); gb=mkbtn("🎫  إنشاء Serial جديد","success"); gb.clicked.connect(self._gen); sr.addWidget(gb)
        sr.addStretch(); rf=mkbtn("🔄  تحديث"); rf.clicked.connect(self._load_s); sr.addWidget(rf); sl.addLayout(sr)
        self.st=QTableWidget(0,6)
        self.st.setHorizontalHeaderLabels(["Serial","الأجهزة","التفعيلات","الحد","الصلاحية","الحالة"])
        self.st.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for i in range(1,6): self.st.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
        self.st.setAlternatingRowColors(True); self.st.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); sl.addWidget(self.st)
        tabs.addTab(sw,"🔑  الـ Serials")
        uw=QWidget(); ul=QVBoxLayout(uw); ul.setSpacing(10); ul.setContentsMargins(0,14,0,0)
        ur=QHBoxLayout(); ur.addStretch(); ru=mkbtn("🔄  تحديث"); ru.clicked.connect(self._load_u); ur.addWidget(ru); ul.addLayout(ur)
        self.ut=QTableWidget(0,5)
        self.ut.setHorizontalHeaderLabels(["#","المستخدم","الصلاحية","الاعتمادات","الإنشاء"])
        self.ut.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        for i in [0,2,3,4]: self.ut.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
        self.ut.setAlternatingRowColors(True); self.ut.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); ul.addWidget(self.ut)
        tabs.addTab(uw,"👥  المستخدمون"); ly.addWidget(tabs)
        self._load_s(); self._load_u()

    def _gen(self):
        s=self.lm.generate_serial()
        if self.lm.create_license(s,2):
            QMessageBox.information(self,"✅ Serial جديد",f"تم إنشاء الـ Serial:\n\n🔑  {s}\n\n(حد 2 أجهزة)"); self._load_s()
        else:
            QMessageBox.warning(self,"تنبيه","فشل الإنشاء.")

    def _load_s(self):
        rows=self.lm.get_all_licenses(); self.st.setRowCount(len(rows))
        for i,(serial,hw,act,mx,exp,status) in enumerate(rows):
            self.st.setItem(i,0,QTableWidgetItem(serial))
            self.st.setItem(i,1,QTableWidgetItem(str(len(json.loads(hw or '[]')))))
            self.st.setItem(i,2,QTableWidgetItem(str(act)))
            self.st.setItem(i,3,QTableWidgetItem(str(mx)))
            self.st.setItem(i,4,QTableWidgetItem(exp or 'غير محدد'))
            si=QTableWidgetItem(status); si.setForeground(QColor('#3fb950') if status=='active' else QColor('#f85149')); self.st.setItem(i,5,si)

    def _load_u(self):
        rows=self.db.get_all_users(); self.ut.setRowCount(len(rows))
        for i,(uid,un,role,cred,cr) in enumerate(rows):
            self.ut.setItem(i,0,QTableWidgetItem(str(uid))); self.ut.setItem(i,1,QTableWidgetItem(un))
            ri=QTableWidgetItem(role); ri.setForeground(QColor('#388bfd') if role=='admin' else QColor('#8b949e')); self.ut.setItem(i,2,ri)
            self.ut.setItem(i,3,QTableWidgetItem(f"{cred:,}")); self.ut.setItem(i,4,QTableWidgetItem(str(cr)[:19]))


class ProDashboard(QWidget):
    def __init__(self, user_data):
        super().__init__()
        self.uid=user_data["id"]; self.role=user_data["role"]; self.credits=user_data["credits"]
        self.db=FBProDatabase(); self._build(); self._refresh()

    def _build(self):
        self.setStyleSheet(DARK_BASE)
        root=QVBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0,0,0,0)
        tb=QFrame(); tb.setFixedHeight(62); tb.setStyleSheet("QFrame{background:#161b22;border-bottom:1px solid #30363d;}")
        tl=QHBoxLayout(tb); tl.setContentsMargins(28,0,28,0)
        br=QLabel(f"⚡  {APP_NAME}"); br.setFont(QFont("Segoe UI",15,QFont.Weight.Bold)); br.setStyleSheet("color:#388bfd;border:none;"); tl.addWidget(br)
        tl.addStretch()
        self.cc=QLabel(f"💳  {self.credits:,} اعتماد")
        self.cc.setStyleSheet("color:#3fb950;font-size:13px;font-weight:600;padding:6px 16px;background:#0d1117;border:1px solid #238636;border-radius:20px;")
        tl.addWidget(self.cc)
        rc=QLabel("👑 مدير" if self.role=='admin' else "👤 مستخدم")
        rc.setStyleSheet("color:#8b949e;font-size:12px;padding:6px 14px;background:#21262d;border-radius:20px;border:none;"); tl.addWidget(rc)
        root.addWidget(tb)
        sr=QHBoxLayout(); sr.setSpacing(12); sr.setContentsMargins(24,14,24,8)
        self.sc=StatCard("💳","الاعتمادات",f"{self.credits:,}")
        self.sl=StatCard("📱","إجمالي الأرقام","0")
        self.ss=StatCard("🟢","حالة النظام","نشط ✓")
        self.sv=StatCard("🚀","الإصدار",f"v{APP_VERSION}")
        for c in (self.sc,self.sl,self.ss,self.sv): sr.addWidget(c)
        sw=QWidget(); sw.setLayout(sr); root.addWidget(sw)
        wr=QWidget(); wr.setStyleSheet("background:#0d1117;"); wl=QVBoxLayout(wr); wl.setContentsMargins(24,6,24,24)
        self.tabs=QTabWidget()
        self.scraping_tab=ScrapingTab(self.uid,self.db,self._refresh)
        self.leads_tab=LeadsTab(self.uid,self.db)
        self.tabs.addTab(self.scraping_tab,"🔍  البحث والجمع")
        self.tabs.addTab(self.leads_tab,"📱  الأرقام")
        if self.role=='admin':
            self.admin_tab=AdminTab(self.db); self.tabs.addTab(self.admin_tab,"⚙️  لوحة التحكم")
        wl.addWidget(self.tabs); root.addWidget(wr)

    def _refresh(self):
        cred,leads=self.db.get_user_stats(self.uid)
        self.cc.setText(f"💳  {cred:,} اعتماد")
        self.sc.set_value(f"{cred:,}"); self.sl.set_value(f"{leads:,}")
        self.leads_tab.refresh()


class FBProSaaS(QMainWindow):
    def __init__(self):
        super().__init__()
        self._tim=QTimer(self); self._tim.timeout.connect(self._sec); self._run()

    def _run(self):
        dlg=LoginDialog()
        if dlg.exec()!=QDialog.DialogCode.Accepted or not dlg.user_data: sys.exit(0)
        try:
            self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
            self.setMinimumSize(1200,800); self.resize(1400,900); self.setStyleSheet(DARK_BASE)
            self.dashboard=ProDashboard(dlg.user_data)
            self.setCentralWidget(self.dashboard)
            self.show()
            self._tim.start(10000)
        except Exception as e:
            import traceback
            QMessageBox.critical(None,"خطأ في التشغيل",
                f"حدث خطأ:\n\n{traceback.format_exc()}\n\nيرجى التواصل مع الدعم الفني.")
            sys.exit(1)

    def _sec(self):
        if AntiPiracy.is_screen_recording():
            self._tim.stop(); AntiPiracyWarningDialog(self).exec(); self.close()

    def closeEvent(self, e):
        self._tim.stop()
        if hasattr(self,'dashboard'): self.dashboard.db.close()
        e.accept()


def global_exception_handler(exc_type, exc_val, exc_tb):
    import traceback
    msg = ''.join(traceback.format_exception(exc_type, exc_val, exc_tb))
    try:
        app = QApplication.instance()
        if app:
            QMessageBox.critical(None, "خطأ غير متوقع", f"حدث خطأ:\n\n{msg}")
    except Exception:
        pass
    sys.exit(1)

if __name__=="__main__":
    sys.excepthook = global_exception_handler
    app=QApplication(sys.argv)
    app.setApplicationName(APP_NAME); app.setApplicationVersion(APP_VERSION)
    app.setFont(QFont("Segoe UI",10))
    FBProSaaS(); sys.exit(app.exec())
