# Deploying EstateIQ to a Hostinger VPS

Target stack: Ubuntu VPS, gunicorn behind Nginx, SQLite3 (no external database server).

## 1. Server prep

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip nginx git

sudo adduser --disabled-password --gecos "" estateiq
sudo usermod -aG www-data estateiq
```

## 2. Get the code and install dependencies

```bash
sudo su - estateiq
git clone <your-repo-url> EstateIQ
cd EstateIQ

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Configure environment

```bash
cp .env.example .env
nano .env
```

Set at minimum:

```
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

## 4. Run the ML pipeline and set up the database

```bash
export DJANGO_SETTINGS_MODULE=estateiq.settings.prod

# Place a raw dataset at ml_pipeline/data/raw/properties_raw.csv first (see
# ml_pipeline/data/raw/SOURCE.md), then:
python ml_pipeline/run_pipeline.py --step all

python manage.py migrate
python manage.py import_properties
python manage.py sync_model_metrics
python manage.py geocode_locations
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

## 5. File permissions (SQLite3)

SQLite needs the database file and its directory writable by the user gunicorn runs as, since
SQLite's rollback journal / WAL files are written alongside `db.sqlite3`:

```bash
chmod 664 db.sqlite3
chmod 775 .
sudo chown estateiq:www-data db.sqlite3
```

## 6. gunicorn as a systemd service

```bash
exit  # back to your sudo-capable user

sudo cp /home/estateiq/EstateIQ/deploy/estateiq.service /etc/systemd/system/estateiq.service
sudo systemctl daemon-reload
sudo systemctl enable estateiq
sudo systemctl start estateiq
sudo systemctl status estateiq
```

## 7. Nginx

```bash
sudo cp /home/estateiq/EstateIQ/deploy/nginx.conf /etc/nginx/sites-available/estateiq
sudo ln -s /etc/nginx/sites-available/estateiq /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Edit `/etc/nginx/sites-available/estateiq` first and replace `your-domain.com` and the
`/home/estateiq` paths with your actual values.

## 8. HTTPS (recommended)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Certbot edits the Nginx config in place to add the `listen 443 ssl` block and an http->https
redirect, and installs a renewal timer automatically.

## 9. SQLite backups

A simple daily backup cron line (as the `estateiq` user, `crontab -e`):

```
0 2 * * * sqlite3 /home/estateiq/EstateIQ/db.sqlite3 ".backup /home/estateiq/backups/db-$(date +\%Y\%m\%d).sqlite3" && find /home/estateiq/backups -name 'db-*.sqlite3' -mtime +14 -delete
```

Uses SQLite's own `.backup` command (safe to run against a live database, unlike `cp`) and
prunes backups older than 14 days. Create `/home/estateiq/backups` first.

## 10. Redeploying after code changes

```bash
sudo su - estateiq
cd EstateIQ
source venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
exit

sudo systemctl restart estateiq
```

## 11. Retraining the model in production

Either use the staff-only `/predictor/retrain/` page (runs the pipeline as a background
subprocess and syncs metrics automatically), or run it manually:

```bash
sudo su - estateiq
cd EstateIQ && source venv/bin/activate
python ml_pipeline/run_pipeline.py --step all
python manage.py sync_model_metrics
```

The running gunicorn workers pick up the new `best_model.joblib` automatically the next time
`PredictionEngine` is asked to predict after a retrain triggered through the web UI (it calls
`PredictionEngine.reset()`). After a manual CLI retrain, restart the service instead:
`sudo systemctl restart estateiq`.
