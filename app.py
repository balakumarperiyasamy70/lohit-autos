import json
import os
import smtplib
import uuid
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps

import pymysql
from dotenv import load_dotenv
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, Response, abort)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret')

SITE_NAME = 'Lohit Enterprises LLC'
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'https://used-cardealer.com')
BUSINESS_PHONE = os.environ.get('BUSINESS_PHONE', '(870) 763-4588')
BUSINESS_PHONE_RAW = ''.join(c for c in BUSINESS_PHONE if c.isdigit())
BUSINESS_EMAIL = os.environ.get('BUSINESS_EMAIL', 'info@used-cardealer.com')
BUSINESS_LOT_ADDRESS = os.environ.get('BUSINESS_ADDRESS', '104 S Porter Dr, Blytheville, AR 72315')
BUSINESS_MAILING_ADDRESS = os.environ.get('BUSINESS_ADDRESS', '357 S Division St, Blytheville, AR 72315')
BUSINESS_HOURS = os.environ.get('BUSINESS_HOURS', 'Open Daily 8:30 AM – 7 PM')

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_CONTENT_MB = 12
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_MB * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Template globals (available in every template) ──────────────────────────────
@app.context_processor
def inject_globals():
    return dict(
        SITE_NAME=SITE_NAME,
        SITE_DOMAIN=SITE_DOMAIN,
        BUSINESS_PHONE=BUSINESS_PHONE,
        BUSINESS_PHONE_RAW=BUSINESS_PHONE_RAW,
        BUSINESS_EMAIL=BUSINESS_EMAIL,
        BUSINESS_ADDRESS=BUSINESS_ADDRESS,
        BUSINESS_HOURS=BUSINESS_HOURS,
        current_year=date.today().year,
    )


# ── reCAPTCHA (optional; skipped if no secret configured) ───────────────────────
RECAPTCHA_SECRET = os.environ.get('RECAPTCHA_SECRET', '')


def verify_recaptcha(token):
    if not RECAPTCHA_SECRET:
        return True  # not configured — allow through
    import urllib.request
    import urllib.parse
    try:
        data = urllib.parse.urlencode({'secret': RECAPTCHA_SECRET, 'response': token}).encode()
        req = urllib.request.urlopen('https://www.google.com/recaptcha/api/siteverify', data, timeout=5)
        result = json.loads(req.read().decode())
        return result.get('success', False)
    except Exception:
        return False


# ── Email ───────────────────────────────────────────────────────────────────────
SMTP_HOST = os.environ.get('SMTP_HOST', 'mail.skillforgeusa.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))
SMTP_USER = os.environ.get('SMTP_USER', 'noreply@skillforgeusa.com')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
LEAD_NOTIFY_TO = os.environ.get('LEAD_NOTIFY_TO', 'Balakumar.Periyasamy@gmail.com')


def send_email(to_addr, subject, html_body):
    if not SMTP_PASS:
        app.logger.warning('SMTP not configured — email skipped')
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'{SITE_NAME} <{SMTP_USER}>'
        msg['Reply-To'] = BUSINESS_EMAIL
        msg['To'] = to_addr
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_addr, msg.as_string())
        return True
    except Exception as e:
        app.logger.error(f'Email error: {e}')
        return False


def notify_new_lead(lead_type, name, phone, email, extra_rows):
    """Send an internal notification email when a new lead comes in."""
    rows = ''.join(
        f'<tr><td style="padding:6px 12px 6px 0;color:#666;">{k}</td>'
        f'<td style="padding:6px 0;"><strong>{v}</strong></td></tr>'
        for k, v in extra_rows if v
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
        <h2 style="color:#1B3A6B;">New {lead_type.title()} Lead — {SITE_NAME}</h2>
        <table style="width:100%;border-collapse:collapse;margin:1rem 0;">
            <tr><td style="padding:6px 12px 6px 0;color:#666;">Name</td><td style="padding:6px 0;"><strong>{name}</strong></td></tr>
            <tr><td style="padding:6px 12px 6px 0;color:#666;">Phone</td><td style="padding:6px 0;"><strong>{phone or '-'}</strong></td></tr>
            <tr><td style="padding:6px 12px 6px 0;color:#666;">Email</td><td style="padding:6px 0;"><strong>{email or '-'}</strong></td></tr>
            {rows}
        </table>
        <p style="color:#888;font-size:0.85rem;">View and manage all leads in the admin panel.</p>
    </div>
    """
    send_email(LEAD_NOTIFY_TO, f'New {lead_type} lead: {name}', html)


# ── Database ──────────────────────────────────────────────────────────────────────
def get_db():
    return pymysql.connect(
        host=os.environ.get('DB_HOST', '127.0.0.1'),
        user=os.environ.get('DB_USER', 'lohit'),
        password=os.environ.get('DB_PASSWORD', ''),
        database=os.environ.get('DB_NAME', 'lohit'),
        cursorclass=pymysql.cursors.DictCursor
    )


# ── Helpers ───────────────────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def save_upload(file_storage):
    """Save an uploaded image with a unique name; return the stored filename or None."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    fname = f'{uuid.uuid4().hex}.{ext}'
    file_storage.save(os.path.join(UPLOAD_FOLDER, fname))
    return fname


def vehicle_title(v):
    parts = [str(v['year']), v['make'], v['model']]
    if v.get('trim'):
        parts.append(v['trim'])
    return ' '.join(parts)


app.jinja_env.globals.update(vehicle_title=vehicle_title)


# ── Public Routes ─────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM vehicles
            WHERE status='available' AND featured=1
            ORDER BY created_at DESC LIMIT 6
        """)
        featured = cur.fetchall()
        if len(featured) < 6:
            cur.execute("""
                SELECT * FROM vehicles WHERE status='available'
                ORDER BY created_at DESC LIMIT 6
            """)
            featured = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS c FROM vehicles WHERE status='available'")
        inventory_count = cur.fetchone()['c']
    db.close()
    return render_template('index.html', featured=featured, inventory_count=inventory_count)


@app.route('/inventory')
def inventory():
    q = request.args.get('q', '').strip()
    make = request.args.get('make', '').strip()
    body = request.args.get('body', '').strip()
    price_max = request.args.get('price_max', '').strip()
    sort = request.args.get('sort', 'newest')

    where = ["status='available'"]
    params = []
    if q:
        where.append("(make LIKE %s OR model LIKE %s OR trim LIKE %s OR CAST(year AS CHAR) LIKE %s)")
        like = f'%{q}%'
        params += [like, like, like, like]
    if make:
        where.append("make=%s")
        params.append(make)
    if body:
        where.append("body_type=%s")
        params.append(body)
    if price_max and price_max.isdigit():
        where.append("price <= %s")
        params.append(int(price_max))

    order = {
        'newest': 'created_at DESC',
        'price_low': 'price ASC',
        'price_high': 'price DESC',
        'mileage_low': 'mileage ASC',
        'year_new': 'year DESC',
    }.get(sort, 'created_at DESC')

    db = get_db()
    with db.cursor() as cur:
        cur.execute(f"SELECT * FROM vehicles WHERE {' AND '.join(where)} ORDER BY {order}", params)
        vehicles = cur.fetchall()
        cur.execute("SELECT DISTINCT make FROM vehicles WHERE status='available' ORDER BY make")
        makes = [r['make'] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT body_type FROM vehicles WHERE status='available' AND body_type IS NOT NULL AND body_type<>'' ORDER BY body_type")
        bodies = [r['body_type'] for r in cur.fetchall()]
    db.close()

    return render_template('inventory.html', vehicles=vehicles, makes=makes, bodies=bodies,
                           q=q, sel_make=make, sel_body=body, price_max=price_max, sort=sort)


@app.route('/vehicle/<int:vehicle_id>')
def vehicle(vehicle_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM vehicles WHERE id=%s", (vehicle_id,))
        v = cur.fetchone()
        if not v:
            db.close()
            abort(404)
        cur.execute("SELECT * FROM vehicle_images WHERE vehicle_id=%s ORDER BY sort_order, id", (vehicle_id,))
        images = cur.fetchall()
        cur.execute("""
            SELECT * FROM vehicles
            WHERE status='available' AND id<>%s
            ORDER BY (make=%s) DESC, created_at DESC LIMIT 3
        """, (vehicle_id, v['make']))
        similar = cur.fetchall()
    db.close()
    return render_template('vehicle.html', v=v, images=images, similar=similar)


@app.route('/inquiry', methods=['POST'])
def inquiry():
    vehicle_id = request.form.get('vehicle_id') or None
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()

    if not name or not (email or phone):
        flash('Please provide your name and a phone number or email.', 'error')
        return redirect(request.referrer or url_for('inventory'))

    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO leads (lead_type, vehicle_id, name, email, phone, message)
            VALUES ('inquiry', %s, %s, %s, %s, %s)
        """, (vehicle_id, name, email, phone, message))
        db.commit()
        veh_desc = '-'
        if vehicle_id:
            cur.execute("SELECT year, make, model, trim, stock_number FROM vehicles WHERE id=%s", (vehicle_id,))
            vrow = cur.fetchone()
            if vrow:
                veh_desc = f"{vrow['year']} {vrow['make']} {vrow['model']} (Stock {vrow['stock_number']})"
    db.close()

    notify_new_lead('inquiry', name, phone, email,
                    [('Vehicle', veh_desc), ('Message', message)])
    return redirect(url_for('thankyou', kind='inquiry'))


@app.route('/financing', methods=['GET', 'POST'])
def financing():
    if request.method == 'POST':
        if not verify_recaptcha(request.form.get('g-recaptcha-response', '')):
            flash('CAPTCHA verification failed. Please try again.', 'error')
            return redirect(url_for('financing'))
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        employment_status = request.form.get('employment_status', '').strip()
        monthly_income = request.form.get('monthly_income') or None
        credit_estimate = request.form.get('credit_estimate', '').strip()
        down_payment = request.form.get('down_payment') or None
        message = request.form.get('message', '').strip()

        if not name or not phone:
            flash('Please provide your name and phone number.', 'error')
            return redirect(url_for('financing'))

        db = get_db()
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO leads (lead_type, name, email, phone, employment_status,
                    monthly_income, credit_estimate, down_payment, message)
                VALUES ('financing', %s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, email, phone, employment_status, monthly_income,
                  credit_estimate, down_payment, message))
            db.commit()
        db.close()

        notify_new_lead('financing', name, phone, email, [
            ('Employment', employment_status),
            ('Monthly income', f'${monthly_income}' if monthly_income else ''),
            ('Credit estimate', credit_estimate),
            ('Down payment', f'${down_payment}' if down_payment else ''),
            ('Notes', message),
        ])
        return redirect(url_for('thankyou', kind='financing'))

    return render_template('financing.html')


@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if request.method == 'POST':
        if not verify_recaptcha(request.form.get('g-recaptcha-response', '')):
            flash('CAPTCHA verification failed. Please try again.', 'error')
            return redirect(url_for('sell'))
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        trade_year = request.form.get('trade_year') or None
        trade_make = request.form.get('trade_make', '').strip()
        trade_model = request.form.get('trade_model', '').strip()
        trade_mileage = request.form.get('trade_mileage') or None
        trade_condition = request.form.get('trade_condition', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not phone:
            flash('Please provide your name and phone number.', 'error')
            return redirect(url_for('sell'))

        db = get_db()
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO leads (lead_type, name, email, phone, trade_year, trade_make,
                    trade_model, trade_mileage, trade_condition, message)
                VALUES ('tradein', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, email, phone, trade_year, trade_make, trade_model,
                  trade_mileage, trade_condition, message))
            db.commit()
        db.close()

        notify_new_lead('trade-in', name, phone, email, [
            ('Vehicle', f'{trade_year or ""} {trade_make} {trade_model}'.strip()),
            ('Mileage', trade_mileage),
            ('Condition', trade_condition),
            ('Notes', message),
        ])
        return redirect(url_for('thankyou', kind='tradein'))

    return render_template('sell.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        if not verify_recaptcha(request.form.get('g-recaptcha-response', '')):
            flash('CAPTCHA verification failed. Please try again.', 'error')
            return redirect(url_for('contact'))
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not (email or phone) or not message:
            flash('Please fill in your name, contact info, and message.', 'error')
            return redirect(url_for('contact'))

        db = get_db()
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO leads (lead_type, name, email, phone, message)
                VALUES ('contact', %s, %s, %s, %s)
            """, (name, email, phone, message))
            db.commit()
        db.close()

        notify_new_lead('contact', name, phone, email, [('Message', message)])
        return redirect(url_for('thankyou', kind='contact'))

    return render_template('contact.html')


@app.route('/thank-you')
def thankyou():
    kind = request.args.get('kind', 'inquiry')
    return render_template('thankyou.html', kind=kind)


# ── Admin Routes ──────────────────────────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT * FROM admin_users WHERE username=%s", (username,))
            user = cur.fetchone()
        db.close()
        if user and check_password_hash(user['password_hash'], password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM vehicles WHERE status='available'")
        available = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) AS c FROM vehicles WHERE status='sold'")
        sold = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) AS c FROM leads WHERE status='new'")
        new_leads = cur.fetchone()['c']
        cur.execute("""
            SELECT l.*, v.year AS v_year, v.make AS v_make, v.model AS v_model
            FROM leads l LEFT JOIN vehicles v ON l.vehicle_id=v.id
            ORDER BY l.created_at DESC LIMIT 8
        """)
        recent_leads = cur.fetchall()
    db.close()
    return render_template('admin/dashboard.html', available=available, sold=sold,
                           new_leads=new_leads, recent_leads=recent_leads)


@app.route('/admin/vehicles')
@admin_required
def admin_vehicles():
    status = request.args.get('status', 'all')
    db = get_db()
    with db.cursor() as cur:
        if status == 'all':
            cur.execute("SELECT * FROM vehicles ORDER BY created_at DESC")
        else:
            cur.execute("SELECT * FROM vehicles WHERE status=%s ORDER BY created_at DESC", (status,))
        vehicles = cur.fetchall()
    db.close()
    return render_template('admin/vehicles.html', vehicles=vehicles, status=status)


def _vehicle_form_data():
    f = request.form
    def num(key):
        val = f.get(key, '').strip()
        return val if val else None
    return dict(
        stock_number=f.get('stock_number', '').strip(),
        vin=f.get('vin', '').strip(),
        year=num('year'),
        make=f.get('make', '').strip(),
        model=f.get('model', '').strip(),
        trim=f.get('trim', '').strip(),
        body_type=f.get('body_type', '').strip(),
        mileage=num('mileage') or 0,
        price=num('price') or 0,
        exterior_color=f.get('exterior_color', '').strip(),
        interior_color=f.get('interior_color', '').strip(),
        transmission=f.get('transmission', '').strip(),
        drivetrain=f.get('drivetrain', '').strip(),
        fuel_type=f.get('fuel_type', '').strip(),
        engine=f.get('engine', '').strip(),
        doors=num('doors'),
        cylinders=f.get('cylinders', '').strip(),
        mpg_city=num('mpg_city'),
        mpg_highway=num('mpg_highway'),
        description=f.get('description', '').strip(),
        featured=1 if f.get('featured') else 0,
        status=f.get('status', 'available'),
    )


@app.route('/admin/vehicles/new', methods=['GET', 'POST'])
@admin_required
def admin_vehicle_new():
    if request.method == 'POST':
        d = _vehicle_form_data()
        if not d['stock_number'] or not d['year'] or not d['make'] or not d['model']:
            flash('Stock #, year, make, and model are required.', 'error')
            return render_template('admin/vehicle_form.html', v=d, images=[], mode='new')
        db = get_db()
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO vehicles (stock_number, vin, year, make, model, trim, body_type,
                    mileage, price, exterior_color, interior_color, transmission, drivetrain,
                    fuel_type, engine, doors, cylinders, mpg_city, mpg_highway, description,
                    featured, status)
                VALUES (%(stock_number)s, %(vin)s, %(year)s, %(make)s, %(model)s, %(trim)s,
                    %(body_type)s, %(mileage)s, %(price)s, %(exterior_color)s, %(interior_color)s,
                    %(transmission)s, %(drivetrain)s, %(fuel_type)s, %(engine)s, %(doors)s,
                    %(cylinders)s, %(mpg_city)s, %(mpg_highway)s, %(description)s, %(featured)s,
                    %(status)s)
            """, d)
            new_id = cur.lastrowid
            db.commit()
            # Handle image uploads
            _save_vehicle_images(cur, db, new_id, first_is_main=True)
        db.close()
        flash('Vehicle added.', 'success')
        return redirect(url_for('admin_vehicles'))
    blank = dict(status='available', featured=0)
    return render_template('admin/vehicle_form.html', v=blank, images=[], mode='new')


@app.route('/admin/vehicles/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_vehicle_edit(vehicle_id):
    db = get_db()
    if request.method == 'POST':
        d = _vehicle_form_data()
        d['id'] = vehicle_id
        with db.cursor() as cur:
            cur.execute("""
                UPDATE vehicles SET stock_number=%(stock_number)s, vin=%(vin)s, year=%(year)s,
                    make=%(make)s, model=%(model)s, trim=%(trim)s, body_type=%(body_type)s,
                    mileage=%(mileage)s, price=%(price)s, exterior_color=%(exterior_color)s,
                    interior_color=%(interior_color)s, transmission=%(transmission)s,
                    drivetrain=%(drivetrain)s, fuel_type=%(fuel_type)s, engine=%(engine)s,
                    doors=%(doors)s, cylinders=%(cylinders)s, mpg_city=%(mpg_city)s,
                    mpg_highway=%(mpg_highway)s, description=%(description)s, featured=%(featured)s,
                    status=%(status)s
                WHERE id=%(id)s
            """, d)
            db.commit()
            cur.execute("SELECT main_image FROM vehicles WHERE id=%s", (vehicle_id,))
            has_main = cur.fetchone()['main_image']
            _save_vehicle_images(cur, db, vehicle_id, first_is_main=not has_main)
        db.close()
        flash('Vehicle updated.', 'success')
        return redirect(url_for('admin_vehicles'))

    with db.cursor() as cur:
        cur.execute("SELECT * FROM vehicles WHERE id=%s", (vehicle_id,))
        v = cur.fetchone()
        if not v:
            db.close()
            abort(404)
        cur.execute("SELECT * FROM vehicle_images WHERE vehicle_id=%s ORDER BY sort_order, id", (vehicle_id,))
        images = cur.fetchall()
    db.close()
    return render_template('admin/vehicle_form.html', v=v, images=images, mode='edit')


def _save_vehicle_images(cur, db, vehicle_id, first_is_main=False):
    files = request.files.getlist('images')
    saved_any = False
    for i, fs in enumerate(files):
        fname = save_upload(fs)
        if fname:
            cur.execute("INSERT INTO vehicle_images (vehicle_id, filename, sort_order) VALUES (%s,%s,%s)",
                        (vehicle_id, fname, i))
            if first_is_main and not saved_any:
                cur.execute("UPDATE vehicles SET main_image=%s WHERE id=%s", (fname, vehicle_id))
            saved_any = True
    if saved_any:
        db.commit()


@app.route('/admin/vehicles/<int:vehicle_id>/set-main/<int:image_id>', methods=['POST'])
@admin_required
def admin_set_main_image(vehicle_id, image_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT filename FROM vehicle_images WHERE id=%s AND vehicle_id=%s", (image_id, vehicle_id))
        img = cur.fetchone()
        if img:
            cur.execute("UPDATE vehicles SET main_image=%s WHERE id=%s", (img['filename'], vehicle_id))
            db.commit()
    db.close()
    return redirect(url_for('admin_vehicle_edit', vehicle_id=vehicle_id))


@app.route('/admin/vehicles/<int:vehicle_id>/delete-image/<int:image_id>', methods=['POST'])
@admin_required
def admin_delete_image(vehicle_id, image_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT filename FROM vehicle_images WHERE id=%s AND vehicle_id=%s", (image_id, vehicle_id))
        img = cur.fetchone()
        if img:
            cur.execute("DELETE FROM vehicle_images WHERE id=%s", (image_id,))
            cur.execute("UPDATE vehicles SET main_image=NULL WHERE id=%s AND main_image=%s",
                        (vehicle_id, img['filename']))
            db.commit()
            try:
                os.remove(os.path.join(UPLOAD_FOLDER, img['filename']))
            except OSError:
                pass
    db.close()
    return redirect(url_for('admin_vehicle_edit', vehicle_id=vehicle_id))


@app.route('/admin/vehicles/<int:vehicle_id>/status', methods=['POST'])
@admin_required
def admin_vehicle_status(vehicle_id):
    new_status = request.form.get('status', 'available')
    if new_status not in ('available', 'pending', 'sold'):
        new_status = 'available'
    db = get_db()
    with db.cursor() as cur:
        cur.execute("UPDATE vehicles SET status=%s WHERE id=%s", (new_status, vehicle_id))
        db.commit()
    db.close()
    flash(f'Vehicle marked {new_status}.', 'success')
    return redirect(url_for('admin_vehicles'))


@app.route('/admin/vehicles/<int:vehicle_id>/delete', methods=['POST'])
@admin_required
def admin_vehicle_delete(vehicle_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT filename FROM vehicle_images WHERE vehicle_id=%s", (vehicle_id,))
        imgs = cur.fetchall()
        cur.execute("DELETE FROM vehicles WHERE id=%s", (vehicle_id,))
        db.commit()
    db.close()
    for img in imgs:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, img['filename']))
        except OSError:
            pass
    flash('Vehicle deleted.', 'success')
    return redirect(url_for('admin_vehicles'))


@app.route('/admin/leads')
@admin_required
def admin_leads():
    lead_type = request.args.get('type', 'all')
    db = get_db()
    with db.cursor() as cur:
        if lead_type == 'all':
            cur.execute("""
                SELECT l.*, v.year AS v_year, v.make AS v_make, v.model AS v_model, v.stock_number AS v_stock
                FROM leads l LEFT JOIN vehicles v ON l.vehicle_id=v.id
                ORDER BY l.created_at DESC
            """)
        else:
            cur.execute("""
                SELECT l.*, v.year AS v_year, v.make AS v_make, v.model AS v_model, v.stock_number AS v_stock
                FROM leads l LEFT JOIN vehicles v ON l.vehicle_id=v.id
                WHERE l.lead_type=%s ORDER BY l.created_at DESC
            """, (lead_type,))
        leads = cur.fetchall()
    db.close()
    return render_template('admin/leads.html', leads=leads, lead_type=lead_type)


@app.route('/admin/leads/<int:lead_id>/status', methods=['POST'])
@admin_required
def admin_lead_status(lead_id):
    new_status = request.form.get('status', 'contacted')
    if new_status not in ('new', 'contacted', 'closed'):
        new_status = 'contacted'
    db = get_db()
    with db.cursor() as cur:
        cur.execute("UPDATE leads SET status=%s WHERE id=%s", (new_status, lead_id))
        db.commit()
    db.close()
    return redirect(url_for('admin_leads', type=request.args.get('type', 'all')))


# ── SEO ───────────────────────────────────────────────────────────────────────────
@app.route('/sitemap.xml')
def sitemap():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM vehicles WHERE status='available'")
        ids = [r['id'] for r in cur.fetchall()]
    db.close()
    urls = [
        ('/', '1.0', 'daily'),
        ('/inventory', '0.9', 'daily'),
        ('/financing', '0.7', 'monthly'),
        ('/sell', '0.7', 'monthly'),
        ('/contact', '0.6', 'monthly'),
    ]
    parts = [f'  <url><loc>{SITE_DOMAIN}{p}</loc><priority>{pr}</priority><changefreq>{cf}</changefreq></url>'
             for p, pr, cf in urls]
    parts += [f'  <url><loc>{SITE_DOMAIN}/vehicle/{i}</loc><priority>0.8</priority><changefreq>weekly</changefreq></url>'
              for i in ids]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + '\n'.join(parts) + '\n</urlset>')
    return Response(xml, mimetype='application/xml')


@app.route('/robots.txt')
def robots():
    txt = (f"User-agent: *\nAllow: /\nDisallow: /admin\n"
           f"Sitemap: {SITE_DOMAIN}/sitemap.xml")
    return Response(txt, mimetype='text/plain')


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run(debug=True, port=8006)
