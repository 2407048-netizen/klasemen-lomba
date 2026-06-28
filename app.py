from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import shutil
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.secret_key = "rahasia_klasemen_lomba_2025"

# ============================
# DETEKSI ENVIRONMENT
# ============================
IS_VERCEL = os.environ.get('VERCEL') == '1'

if IS_VERCEL:
    DATABASE = '/tmp/database.db'
    UPLOAD_FOLDER = '/tmp/photos'
else:
    DATABASE = "database.db"
    UPLOAD_FOLDER = 'static/photos'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

ADMIN_PASSWORD = "azky031006"

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def setup_vercel_db():
    """Copy database dan foto dari repo ke /tmp saat running di Vercel."""
    if IS_VERCEL:
        src_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
        dst_db = '/tmp/database.db'
        
        if os.path.exists(src_db):
            shutil.copy2(src_db, dst_db)
            print("✅ Database copied to /tmp")
        else:
            print("️ database.db tidak ditemukan di repo, akan dibuat baru")
        
        src_photos = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'photos')
        dst_photos = '/tmp/photos'
        
        if os.path.exists(src_photos):
            if os.path.exists(dst_photos):
                shutil.rmtree(dst_photos)
            shutil.copytree(src_photos, dst_photos)
            print("✅ Photos copied to /tmp")
        else:
            print("⚠️ Folder photos tidak ditemukan di repo")
        
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS peserta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL UNIQUE,
            skor INTEGER NOT NULL DEFAULT 0,
            foto TEXT DEFAULT 'default.png',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("PRAGMA table_info(peserta)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'foto' not in columns:
        cursor.execute("ALTER TABLE peserta ADD COLUMN foto TEXT DEFAULT 'default.png'")
        conn.commit()
    
    peserta_awal = ["Keyla", "Aldi", "Dika", "Athar", "Vira", "Riko", "Liya"]
    for nama in peserta_awal:
        cursor.execute("INSERT OR IGNORE INTO peserta (nama, skor) VALUES (?, 0)", (nama,))
        cursor.execute("UPDATE peserta SET foto = 'default.png' WHERE nama = ? AND foto IS NULL", (nama,))
    
    conn.commit()
    conn.close()
    print("✅ Database berhasil diinisialisasi.")

# ============================
# ROUTES
# ============================

@app.route("/")
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nama, skor, foto,
               RANK() OVER (ORDER BY skor DESC) as peringkat
        FROM peserta
        ORDER BY skor DESC, nama ASC
    """)
    semua_peserta = cursor.fetchall()
    conn.close()

    podium = semua_peserta[:3] if len(semua_peserta) >= 3 else semua_peserta
    sisanya = semua_peserta[3:] if len(semua_peserta) > 3 else []

    total_peserta = len(semua_peserta)
    total_skor = sum(p['skor'] for p in semua_peserta)
    skor_tertinggi = semua_peserta[0]['skor'] if semua_peserta else 0
    rata_rata = round(total_skor / total_peserta, 1) if total_peserta > 0 else 0

    return render_template(
        "index.html",
        podium=podium,
        semua_peserta=semua_peserta,
        sisanya=sisanya,
        total_peserta=total_peserta,
        total_skor=total_skor,
        skor_tertinggi=skor_tertinggi,
        rata_rata=rata_rata
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["logged_in"] = True
            flash("Login berhasil! Selamat datang, Admin.", "success")
            return redirect(url_for("admin"))
        else:
            flash("Password salah! Coba lagi.", "danger")
    return render_template("login.html")

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        flash("Silakan login terlebih dahulu.", "warning")
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nama, skor, foto,
               RANK() OVER (ORDER BY skor DESC) as peringkat
        FROM peserta
        ORDER BY skor DESC, nama ASC
    """)
    peserta = cursor.fetchall()
    conn.close()

    total_peserta = len(peserta)
    total_skor = sum(p['skor'] for p in peserta)
    skor_tertinggi = peserta[0]['skor'] if peserta else 0
    rata_rata = round(total_skor / total_peserta, 1) if total_peserta > 0 else 0

    return render_template(
        "admin.html",
        peserta=peserta,
        total_peserta=total_peserta,
        total_skor=total_skor,
        skor_tertinggi=skor_tertinggi,
        rata_rata=rata_rata
    )

@app.route("/admin/upload_foto/<int:peserta_id>", methods=["POST"])
def upload_foto(peserta_id):
    if not session.get("logged_in"):
        flash("Akses ditolak!", "danger")
        return redirect(url_for("login"))
    
    if 'foto' not in request.files:
        flash("Tidak ada file yang dipilih", "danger")
        return redirect(url_for("admin"))
    
    file = request.files['foto']
    
    if file.filename == '':
        flash("Tidak ada file yang dipilih", "danger")
        return redirect(url_for("admin"))
    
    if file and allowed_file(file.filename):
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT foto, nama FROM peserta WHERE id = ?", (peserta_id,))
        peserta = cursor.fetchone()
        
        if peserta and peserta['foto'] != 'default.png':
            old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], peserta['foto'])
            if os.path.exists(old_filepath):
                os.remove(old_filepath)
        
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        new_filename = f"peserta_{peserta_id}.{ext}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        file.save(filepath)
        
        cursor.execute("UPDATE peserta SET foto = ? WHERE id = ?", (new_filename, peserta_id))
        conn.commit()
        conn.close()
        
        flash(f"Foto {peserta['nama']} berhasil diupload!", "success")
        return redirect(url_for("admin"))
    else:
        flash("Format file tidak didukung.", "warning")
        return redirect(url_for("admin"))

@app.route("/admin/hapus_foto/<int:peserta_id>", methods=["POST"])
def hapus_foto(peserta_id):
    if not session.get("logged_in"):
        flash("Akses ditolak!", "danger")
        return redirect(url_for("login"))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT foto, nama FROM peserta WHERE id = ?", (peserta_id,))
    peserta = cursor.fetchone()
    
    if peserta and peserta['foto'] != 'default.png':
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], peserta['foto'])
        if os.path.exists(filepath):
            os.remove(filepath)
    
    cursor.execute("UPDATE peserta SET foto = 'default.png' WHERE id = ?", (peserta_id,))
    conn.commit()
    conn.close()
    
    flash(f"Foto {peserta['nama']} berhasil dihapus", "info")
    return redirect(url_for("admin"))

@app.route("/admin/update/<int:peserta_id>", methods=["POST"])
def update_skor(peserta_id):
    if not session.get("logged_in"):
        flash("Akses ditolak.", "danger")
        return redirect(url_for("login"))
    skor_baru = request.form.get("skor", 0)
    try:
        skor_baru = int(skor_baru)
    except ValueError:
        flash("Skor harus berupa angka!", "danger")
        return redirect(url_for("admin"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE peserta SET skor = ? WHERE id = ?", (skor_baru, peserta_id))
    conn.commit()
    conn.close()
    flash("Skor berhasil diperbarui!", "success")
    return redirect(url_for("admin"))

@app.route("/admin/update_all", methods=["POST"])
def update_all_skor():
    if not session.get("logged_in"):
        flash("Akses ditolak.", "danger")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()
    for key in request.form:
        if key.startswith("skor_"):
            peserta_id = key.replace("skor_", "")
            try:
                skor_baru = int(request.form[key])
                cursor.execute("UPDATE peserta SET skor = ? WHERE id = ?", (skor_baru, peserta_id))
            except ValueError:
                continue
    conn.commit()
    conn.close()
    flash("Semua skor berhasil diperbarui!", "success")
    return redirect(url_for("admin"))

@app.route("/admin/reset", methods=["POST"])
def reset_skor():
    if not session.get("logged_in"):
        flash("Akses ditolak.", "danger")
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE peserta SET skor = 0")
    conn.commit()
    conn.close()
    flash("Semua skor telah direset ke 0!", "info")
    return redirect(url_for("admin"))

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    flash("Anda telah logout.", "info")
    return redirect(url_for("index"))

# ============================
# KONFIGURASI & JALANKAN
# ============================

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
else:
    setup_vercel_db()
    init_db()