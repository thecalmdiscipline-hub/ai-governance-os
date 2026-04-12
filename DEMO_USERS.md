# Local demo users

## Tenant 1
Username: dennis_admin
Password: Admin123!
Role: admin
Organization: org_id=1

## Tenant 2
Username: customer2_admin
Password: Customer123!
Role: admin
Organization: Customer 2

## Reset commands
Default admin:
./scripts/reset_local_admin.sh

Customer 2:
./scripts/create_local_customer_2.sh

Full clean reset:
./scripts/reset_local_portal_state.sh

## Start local demo
./scripts/start_local_portal.sh

## Smoke checks
Default tenant:
./scripts/smoke_local_portal_minimal.sh

Customer 2:
./scripts/smoke_customer2_portal.sh

Multi-tenant:
./scripts/smoke_multi_tenant.sh

## Prepare ready-to-show demo data
Run:
./scripts/prepare_demo_state.sh

Result:
- tenant 1 has demo document + workflow
- tenant 2 has separate demo document + workflow
- isolation can be shown immediately
