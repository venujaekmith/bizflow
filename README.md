# BizFlow

BizFlow is a multi-business Django platform for operating independent business applications under one central platform.

Each business has:

- Its own business identity and URL slug.
- Its own users and memberships.
- Its own enabled business application.
- Its own isolated SQLite file or PostgreSQL database when provisioning is enabled.
- Its own application models, migrations, dashboards, and business rules.

## Current applications

| Application | Example domain models |
|---|---|
| `salonNEXT` | Customers, services, appointments, POS sales |
| `pharmacyB` | Medicines, prescriptions |
| `graceryshopA` | Products, sales |

The central platform provides authentication, business membership, business routing, platform administration, provisioning, subscriptions, and audit records.

## Project structure

```text
bizflow/
├── manage.py
├── bizflow/
│   ├── settings.py
│   └── urls.py
├── bizflow_admin/
│   ├── models.py
│   ├── provisioning.py
│   ├── billing.py
│   ├── platform_views.py
│   └── platform_urls.py
├── business_runtime/
│   ├── database.py
│   └── registry.py
├── salonNEXT/
├── pharmacyB/
├── graceryshopA/
├── templates/
├── PHASE_TRACKER.txt
└── README.md
```

## Requirements

- Python 3.14 or a compatible supported Python version.
- Django 5.2.
- `psycopg` for PostgreSQL mode.
- PostgreSQL 16 or newer for production-grade isolated databases.
- Docker is optional but useful for local PostgreSQL.

The project virtual environment is located one directory above this project in the current workspace:

```bash
../.venv/bin/python
```

## Local development mode

SQLite is the default development database. It supports:

- Authentication.
- Platform dashboard.
- Business registration and membership management.
- Business routing and access control.
- Dashboard demo metrics.
- Automated tests.

Start the application:

```bash
cd bizflow
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser
../.venv/bin/python manage.py runserver
```

Open:

- Login: <http://127.0.0.1:8000/login/>
- Django admin: <http://127.0.0.1:8000/admin/>
- Platform dashboard: <http://127.0.0.1:8000/platform/>

SQLite mode provisions one database file per business under `BIZFLOW_BUSINESS_DATABASE_DIR`
(default: `bizflow/business_databases`). This is suitable for local development and
small single-server deployments. Keep the directory out of version control and back
it up with the business data.

To choose a different directory:

```bash
export BIZFLOW_BUSINESS_DATABASE_DIR=/var/lib/bizflow/business_databases
```

## PostgreSQL mode

Set the platform database environment variables before running Django:

```bash
export BIZFLOW_DB_ENGINE=postgresql
export BIZFLOW_DB_NAME=bizflow_core
export BIZFLOW_DB_USER=bizflow
export BIZFLOW_DB_PASSWORD='replace-this-secret'
export BIZFLOW_DB_HOST=127.0.0.1
export BIZFLOW_DB_PORT=5432
```

The PostgreSQL role used by BizFlow must be allowed to create databases. In production, use a dedicated restricted provisioning role rather than a superuser.

PostgreSQL remains the recommended backend for production deployments requiring
concurrency, multi-server operation, managed backups, and high availability.

Apply platform migrations:

```bash
cd bizflow
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser
../.venv/bin/python manage.py runserver
```

## Business provisioning

1. Sign in as a staff user.
2. Open `/platform/`.
3. Select **Create business**.
4. Enter the business name and slug.
5. Select the business application:
   - `salonNEXT`
   - `pharmacyB`
   - `graceryshopA`
6. Create the business.
7. Open the business list.
8. Select **Provision**.

Provisioning:

1. Creates a database named `bizflow_business_<business_uuid>`.
2. Stores non-secret database metadata in the central database.
3. Applies only the selected business application's migrations.
4. Creates the initial business-owner membership.
5. Marks the business active only after all steps succeed.

Provisioning is idempotent and records attempts and individual steps. A failed operation marks the business as failed and can be retried after the cause is fixed.

## Business URLs

The central login flow resolves active memberships:

- One active membership: direct dashboard redirect.
- Multiple memberships: business selector.
- No active membership: access message.
- Unauthorized business URL: `403`.
- Suspended or inactive business: blocked.

Examples:

```text
/business/salonNEXT/
/business/pharmacyB/
/business/graceryshopA/
```

SalonNEXT operational URLs are mounted below:

```text
/business/<slug>/salon/
/business/<slug>/salon/customers/
/business/<slug>/salon/services/
/business/<slug>/salon/appointments/
/business/<slug>/salon/pos/
/business/<slug>/salon/sales/
```

## Database isolation

Central platform models remain in the platform database:

- Users.
- Businesses.
- Memberships.
- Invitations.
- Subscriptions.
- Audit logs.
- Provisioning metadata.

Business application models are migrated into the selected business database. The database router prevents business application migrations from being applied to the platform database and routes business model queries through the active business database context.

Application code must use:

```python
from business_runtime.database import business_database_context

with business_database_context(business):
    records = Customer.objects.all()
```

Never accept a database alias or database credentials from request input.

## Subscription access

Subscription plans support monthly and annual intervals. Payment records do not store card details. Cancelled and expired subscriptions are blocked by business-resolution middleware.

The current billing service uses a manual provider abstraction. A payment gateway can be integrated behind the provider interface later.

## Testing

Run the complete test suite:

```bash
../.venv/bin/python manage.py test
```

Run checks:

```bash
../.venv/bin/python manage.py check
```

Verify migration files:

```bash
../.venv/bin/python manage.py makemigrations --check --dry-run
```

## Common issues

### Provisioning fails in SQLite mode

Confirm that `BIZFLOW_BUSINESS_DATABASE_DIR` is writable. Each business needs a registered
application, and provisioning must be run after the central migrations are applied.

### Provisioning fails while creating the database

Verify that the configured PostgreSQL role has `CREATEDB` permission and that the host and port are reachable.

### A business is active but has no business tables

The business must have a registered application before provisioning. Create businesses through the platform dashboard and select an application.

### Business data is missing

Confirm that the request is executing inside `business_database_context(business)` and that the business database status is `READY`.

## Security notes

- Do not commit `DJANGO_SECRET_KEY` or database passwords.
- Use HTTPS and secure cookies in production.
- Use a dedicated PostgreSQL provisioning role.
- Do not expose database metadata or credentials to business users.
- Keep tenant membership checks on every protected request.
- Use POST and CSRF protection for state-changing operations.
- Review audit logs for administrative actions.

## Project status

See [PHASE_TRACKER.txt](./PHASE_TRACKER.txt) for completed phases, validation results, limitations, and the next planned phase.
