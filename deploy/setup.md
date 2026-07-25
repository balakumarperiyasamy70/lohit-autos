# Lohit Enterprises LLC — Used Car Dealer — Setup & Deployment

**Business:** Lohit Enterprises LLC — used car dealer, Blytheville, AR
**Domain:** used-cardealer.com
**Stack:** Python + Flask · Gunicorn · Nginx · MySQL/MariaDB · Let's Encrypt

## Server
- **Host:** Bluehost VPS · **IP:** 129.121.85.32 · **OS:** Ubuntu 24.04
- **App directory:** /opt/lohit-autos
- **Port:** 8006 (Gunicorn)
- **Database:** `lohit` (MySQL)
- **GitHub repo:** balakumarperiyasamy70/lohit-autos (create this)

---

## Initial Deployment Steps

### 1. Create GitHub repo & push (from Windows PC)
```powershell
cd C:\Users\SubhaB\OneDrive\Documents\AmericanCDL\SKILLFORGE\WS\lohit-autos
git init
git add .
git commit -m "Initial Lohit Enterprises used car dealer site"
git branch -M main
git remote add origin https://github.com/balakumarperiyasamy70/lohit-autos.git
git push -u origin main
```

### 2. Clone on server
```bash
cd /opt
git clone https://github.com/balakumarperiyasamy70/lohit-autos.git
cd lohit-autos
```

### 3. Python virtual environment
```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 4. Database setup
```sql
CREATE DATABASE lohit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'lohit'@'127.0.0.1' IDENTIFIED BY 'LohitAutos2026!';
GRANT ALL PRIVILEGES ON lohit.* TO 'lohit'@'127.0.0.1';
FLUSH PRIVILEGES;
```

### 5. Run schema (creates tables + sample inventory)
```bash
mysql -u root -p lohit < schema.sql
```

### 6. Set admin password
```bash
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('LohitAdmin2026!'))"
# Copy the hash, then:
mysql -u root -p lohit -e "UPDATE admin_users SET password_hash='<hash>' WHERE username='admin';"
```

### 7. Create .env file
```bash
cp .env.example .env
nano .env
```
Fill in:
- `SECRET_KEY` — `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `DB_PASSWORD` — LohitAutos2026!
- `BUSINESS_PHONE`, `BUSINESS_EMAIL`, `BUSINESS_ADDRESS` — the real dealer details
- `SMTP_PASS` — mailbox password for lead-notification emails (or leave blank to disable)

### 8. Permissions (uploads dir must be writable by gunicorn user)
```bash
chown -R www-data:www-data /opt/lohit-autos
chmod -R 775 /opt/lohit-autos/static/uploads
```

### 9. Systemd service
```bash
cp deploy/lohit-autos.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable lohit-autos
systemctl start lohit-autos
systemctl status lohit-autos
```

### 10. Nginx config
```bash
cp deploy/nginx.conf /etc/nginx/sites-available/used-cardealer.com
ln -s /etc/nginx/sites-available/used-cardealer.com /etc/nginx/sites-enabled/
nginx -t
```

### 11. DNS records (at the registrar for used-cardealer.com)
| Type | Name | Value |
|------|------|-------|
| A | @ | 129.121.85.32 |
| A | www | 129.121.85.32 |

### 12. SSL certificate
```bash
certbot --nginx -d used-cardealer.com -d www.used-cardealer.com
systemctl reload nginx
```

---

## Ongoing Updates (after any code change)

**On Windows PC:**
```powershell
git add .
git commit -m "describe change"
git push
```

**On server:**
```bash
cd /opt/lohit-autos
git pull
systemctl restart lohit-autos
```

---

## Admin Panel
- **URL:** https://used-cardealer.com/admin/login
- **Username:** admin
- **Password:** LohitAdmin2026!  *(change after first login — see step 6 to reset)*

### What the admin can do
- **Vehicles** — add/edit/delete, upload multiple photos, set the main photo, mark Available/Pending/Sold, feature on homepage
- **Leads** — inbox of every inquiry, financing request, trade-in, and contact message; mark New/Contacted/Closed
- **Dashboard** — counts of available/sold vehicles and new leads

## Database Credentials
- Database: `lohit` · User: `lohit` · Host: 127.0.0.1 · Password: LohitAutos2026!

---

## Notes
- **Photos** are uploaded through the admin panel and stored in `static/uploads/` (gitignored — they live only on the server, so `git pull` won't delete them).
- **Sample inventory** (6 vehicles) is seeded by `schema.sql`. Delete or edit these from the admin panel once real inventory is added.
- **Lead emails** forward to `LEAD_NOTIFY_TO` (Balakumar.Periyasamy@gmail.com by default). Requires a working `SMTP_PASS`.
- **No Stripe/online payments** — the site drives phone calls and leads, which suits used-car sales. A deposit/reservation flow can be added later if desired.

## Deployment Log
| Date | Action | Notes |
|------|--------|-------|
| 2026-07-24 | Project built | Flask app, admin panel, 6 sample vehicles |
