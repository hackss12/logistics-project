# Mohan Logistics Digital LR Book

A Flask mobile web application and CustomTkinter desktop client for recording Lorry Receipts, storing them in MySQL, and generating selectable A4 landscape PDF copies.

## What is implemented

- Shared MySQL storage via SQLAlchemy, normalized receipt/party/charge/payment/particular/audit tables.
- Globally increasing, MySQL auto-increment-backed LR sequence; the number format is `ML/YYYY/MM/000001`, with the date portion taken from the receipt date. A committed sequence reservation is not reused if a later receipt save fails.
- Decimal-based server-side freight/tax/payment calculations and validation.
- Password-hashed users, roles, CSRF protection for web forms, login-required routes, and an interactive first-admin command.
- Responsive web receipt creation, dashboard, search/filter, date/party/vehicle/payment reports with CSV and Excel export, PDF previews/downloads, cancellation, company settings, user management, and audit history. The web app can be installed on supported phones and tablets as a PWA; it requires an online connection and does not cache private receipt data.
- CustomTkinter sign-in, receipt creation, recent receipt lookup, details, and PDF opening.
- Combined PDF for the five paper-color copies, separate PDF output per copy, and a distinct white consignor-copy action.

The supplied LR reference photographs could not be inspected in this session, so the PDF remains a structured, vector-based reconstruction from the written field list rather than a verified match to the photographed form. The user-supplied logo is included at `static/images/mohan_logistics_logo.png`; the source is a small grayscale raster, rotated to a horizontal wordmark for the header. Each PDF copy now includes visible copy-specific accent color in its banner, section headings, border, and footer. The additional white consignor copy currently uses the same reconstructed field layout as the other forms. Compare against the original book before operational printing.

The current implementation issues receipts immediately. Draft editing, editing issued records with change-reason history, and the complete multi-screen desktop feature set are not included yet.

## Requirements

- Windows 10/11
- Python 3.12 recommended
- MySQL 8.x (MySQL Workbench can be used to create the schema/user)

MySQL is the primary store. SQLite is not used by the application.

## First-time setup (Windows)

1. Install Python 3.12 and MySQL Server 8.x. MySQL Workbench is optional but useful for running the SQL below.
2. In Workbench, connect to the local MySQL server and run:

   ```sql
   CREATE DATABASE mohan_logistics_lr
     CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'lr_app'@'localhost' IDENTIFIED BY 'use-a-unique-long-password';
   GRANT ALL PRIVILEGES ON mohan_logistics_lr.* TO 'lr_app'@'localhost';
   ```

   Choose a unique password locally. Do not put database credentials in source control or share them in chat. The application does not need a publicly reachable MySQL port.
3. Open PowerShell in this project folder and create/activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies and create your local settings:

   ```powershell
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

   Edit `.env`: set a long random `SECRET_KEY`, update `DATABASE_URL` with the MySQL username/password, and set `TAX_RATE` only if an applicable tax rate has been confirmed. Keep `.env` private; it is intended to be excluded from source control.
5. Create the tables and first administrator:

   ```powershell
   flask --app app init-db
   flask --app app create-admin
   ```

   The command prompts for the administrator username and password without echoing the password. Passwords must be at least 12 characters. In this already-initialized workspace, the schema and initial administrator have been created; find the one-time login in `.first_admin_credentials.txt`, sign in, change it at **Password**, then delete that credentials file.
6. Start the responsive web application for local development:

   ```powershell
   flask --app app run --host 127.0.0.1 --port 5000
   ```

   Open `http://127.0.0.1:5000` in a browser on the same computer. This local development address is not accessible from other devices. Do not enable Flask debug mode on a network-accessible host.
7. Start the desktop client in a second activated terminal:

   ```powershell
   python desktop_app.py
   ```

   Sign in with an application user. The desktop client reads and writes the same configured MySQL database as the web app.

## Creating more users

For a fresh database, create the first administrator with `flask --app app create-admin`. Add operator or viewer users with `flask --app app create-user`. The commands prompt for a username and hidden password; do not use a publicly known/default password.

## Office network and remote deployment

For office-network access only, run the web server bound to the server's private LAN interface (for example `0.0.0.0`) and allow inbound web traffic only from the office network in Windows Firewall. Employees can open `http://<server-lan-ip>:5000` in a browser; use HTTPS for PWA installation on mobile devices. Keep MySQL bound to localhost/private interfaces and firewall it from client devices.

For access outside the office, deploy behind a production WSGI server and an HTTPS reverse proxy or managed HTTPS hosting service. Use a private database endpoint, strong unique credentials, secure backups, and firewall rules. Do not expose MySQL port 3306 to the public internet. The built-in Flask development server is not a production server; remote use is not ready until this deployment is completed and secured.

### Deploy to Vercel

The GitHub repository is configured for Vercel's Python/Flask runtime. Import `hackss12/logistics-project` from the Vercel dashboard (or use the project link provided by Vercel). Vercel installs application packages from `requirements.txt` and builds static files from `static/` into `public/` using `vercel_build.py`.

Before the first deployment, configure these in **Vercel Project → Settings → Environment Variables** for Production (and Preview if needed):

- `SECRET_KEY`: a long, unique random value.
- `DATABASE_URL`: SQLAlchemy URL for a managed MySQL 8 database reachable from Vercel, for example `mysql+pymysql://USER:PASSWORD@PUBLIC_DB_HOST:3306/DB_NAME?charset=utf8mb4`. URL-encode special characters in the username or password.
- `SESSION_COOKIE_SECURE`: `1`.
- `TAX_RATE`: only if a confirmed rate applies.

Do not use the development database host `localhost` or expose an office computer's MySQL port to the internet. Use the database provider's secure external connection endpoint and network controls. Keep these values private; never commit them or send them in chat.

After setting environment variables, redeploy. Initialize the schema and create the first administrator against the hosted database from a trusted local machine with the same `DATABASE_URL` and `SECRET_KEY` set in its environment:

```powershell
flask --app app init-db
flask --app app create-admin
```

The deployed site will not work until a reachable database is configured and initialized. The desktop client is not hosted on Vercel; only the browser app is deployed. Vercel Functions are not a replacement for durable database storage, so keep MySQL on a managed database and maintain backups.

### Install on phones and tablets

The browser app includes a PWA manifest and can be added to a device's home screen. Serve it over HTTPS (or use `localhost` for development); mobile browsers do not allow service workers on a plain HTTP LAN address. Keep the web server and database reachable: the installed app is an online client, not an offline copy.

- **Android:** Open the HTTPS app address in Chrome, then choose **Install app** or **Add to Home screen** from the browser menu.
- **iPhone/iPad:** Open the HTTPS app address in Safari, tap **Share**, then **Add to Home Screen**.

An HTTPS deployment also allows users to open the same app URL from laptops and desktops. Use a trusted certificate and secure deployment as described above; do not expose the Flask development server directly to the internet.

## PDF copies

From a saved LR, use **Preview all copies** or **Download combined PDF** for the five copies in order: Consignor (pink), Consignee (white), Driver (yellow), Record (green), and Extra (blue). Select an individual copy to preview/print or download it from the PDF route. The separate White Consignor Copy has its own action. The PDF page background stays white so that paper color can come from the physical stock.

The logo placeholder should be replaced only with the approved company logo. The layout and the additional white consignor design need comparison against the original paper forms before production printing.

## Schema and backups

- `database/models.py` is the canonical SQLAlchemy schema.
- `database/schema.sql` contains the MySQL table definitions for Workbench/manual review.
- Back up using MySQL Workbench's **Data Export** or:

  ```powershell
  mysqldump -u lr_app -p mohan_logistics_lr > .\mohan_logistics_lr-backup.sql
  ```

- Restore into a selected database with:

  ```powershell
  mysql -u lr_app -p mohan_logistics_lr < .\mohan_logistics_lr-backup.sql
  ```

Protect and test backups; store them separately from the application machine.

## Tests

The current tests cover decimal calculations, receipt persistence/particulars, PDF generation, and sequence formatting across month/year boundaries:

```powershell
python -m unittest discover -s tests -v
```

The MySQL-specific test verifies parallel sequence reservations. Run it only against a disposable database whose name ends in `_test`:

```powershell
$env:TEST_DATABASE_URL = "mysql+pymysql://lr_test:your-test-password@127.0.0.1:3306/mohan_logistics_lr_test?charset=utf8mb4"
python -m unittest tests.test_mysql_sequence_concurrency -v
```

That integration test drops and recreates tables in the configured database. Never point it at the production LR database.

## Common setup issues

- **Can't connect to MySQL:** Confirm MySQL Server is running; check the host, port, database name, user grants and URL encoding for special password characters in `DATABASE_URL`.
- **Unknown database:** Create `mohan_logistics_lr` in Workbench, then run `flask --app app init-db`.
- **Access denied:** Grant the configured application user access to this database; avoid using the MySQL root account for routine application traffic.
- **CSRF failure:** Ensure browser cookies are enabled and reload the form after its session expires.
- **PDF layout / logo:** The included form is not an image-background PDF. Replace the logo placeholder and verify exact original wording/position against a clear scan before printing official copies.
