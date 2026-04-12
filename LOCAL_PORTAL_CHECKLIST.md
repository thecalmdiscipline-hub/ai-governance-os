# Local portal checklist

## Start
Run:
./scripts/start_local_portal.sh

Check:
- backend health returns healthy
- browser opens on localhost:5173
- login page or portal opens correctly

## Login
Use:
- username: dennis_admin
- password: Admin123!

Check:
- dashboard opens
- no "load failed"
- no blank page

## Documents
Check:
- documents tab opens
- upload works
- preview works
- delete works

## Runs
Check:
- runs tab opens
- workflow run list loads
- run detail loads
- run again works for supported workflows
- delete run works

## Audit
Check:
- audit tab opens
- audit list loads
- filters work
- copy details works

## API smoke test
Run:
./scripts/smoke_local_portal_minimal.sh

Expected:
- health ok
- login ok
- upload ok
- workflow run ok
- workflow card ok
- audit ok
- delete ok

## Backend tests
Run:
pytest -q

Expected:
- all tests pass

## Frontend build
Run:
cd /Users/dennisschetters/ai-governance-frontend
npm run build

Expected:
- build succeeds

## Export current local status
Run:
./scripts/export_local_status.sh

Expected files:
- status_export/health.json
- status_export/documents.json
- status_export/workflows_dashboard.json
- status_export/workflows_history.json
- status_export/audit.json

## Stop
Run:
./scripts/stop_local_portal.sh

## Recover admin login
Run:
./scripts/reset_local_admin.sh

Expected:
- local admin exists
- password reset to Admin123!
- login works again

## Reset local portal state
Run:
./scripts/reset_local_portal_state.sh

Expected:
- admin login reset
- documents cleaned
- workflow runs cleaned
- audit logs cleaned

## Customer 2 tenant check
Run:
./scripts/create_local_customer_2.sh
./scripts/smoke_customer2_portal.sh

Expected:
- customer2 can log in
- customer2 can upload own document
- customer2 can run own workflow
- customer2 sees only own data
- cleanup succeeds

## Customer 2 status export
Run:
./scripts/export_customer2_status.sh

Expected files:
- status_export_customer2/token_length.txt
- status_export_customer2/documents.json
- status_export_customer2/workflows_dashboard.json
- status_export_customer2/workflows_history.json
- status_export_customer2/audit.json

## Full multi-tenant smoke
Run:
./scripts/smoke_multi_tenant.sh

Expected:
- local admin tenant works
- customer2 tenant works
- both smoke flows complete
- both export flows complete

## Demo users
See:
DEMO_USERS.md

## Open customer2 demo
Run:
./scripts/open_customer2_portal.sh

Expected:
- browser opens
- customer2 can log in with own tenant account
