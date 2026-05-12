from pathlib import Path
import re

ROUTERS_DIR = Path("app/workflows/routers")
MODULE_ACCESS = Path("app/services/module_access.py")
OUT = Path("WORKFLOW_VALIDATION_MATRIX.md")

router_files = sorted(
    p for p in ROUTERS_DIR.glob("*.py")
    if p.name not in {"__init__.py", "all.py"}
)

workflow_keys = [p.stem for p in router_files]

module_text = MODULE_ACCESS.read_text()

module_entries = []
for block in re.findall(r"\{[^{}]*\"name\":\s*\"([^\"]+)\"[^{}]*\"key\":\s*\"([^\"]+)\"[^{}]*\"type\":\s*\"([^\"]+)\"([^{}]*)\}", module_text, re.S):
    name, key, typ, rest = block
    workflow_key_match = re.search(r'"workflow_key":\s*"([^"]+)"', rest)
    workflow_key = workflow_key_match.group(1) if workflow_key_match else ""
    module_entries.append(
        {
            "name": name,
            "key": key,
            "type": typ,
            "workflow_key": workflow_key,
        }
    )

workflow_to_module = {
    m["workflow_key"]: m for m in module_entries if m["workflow_key"]
}

frontend_results_map = {
    "customer_support",
    "document_knowledge",
    "compliance_monitoring",
    "sales_lead_qualification",
    "invoice_processing",
    "hr_recruitment",
    "marketing_automation",
    "meeting_agenda_assistant",
    "quote_contract_generator",
    "business_intelligence",
}

ready_count = 0

lines = []
lines.append("# Workflow Validation Matrix")
lines.append("")
lines.append("| Workflow key | Router exists | Module catalog | Results mapped | Status | Next action |")
lines.append("|---|---:|---:|---:|---|---|")

for workflow in workflow_keys:
    router_exists = "Yes"
    module_exists = "Yes" if workflow in workflow_to_module else "No"
    results_mapped = "Yes" if workflow in frontend_results_map else "No"

    if module_exists == "Yes" and results_mapped == "Yes":
        status = "Product-visible"
        next_action = "Validate live input/output"
        ready_count += 1
    elif module_exists == "Yes":
        status = "Backend-visible only"
        next_action = "Add results mapping"
    else:
        status = "Not in catalog"
        next_action = "Add module catalog entry"

    lines.append(
        f"| `{workflow}` | {router_exists} | {module_exists} | {results_mapped} | {status} | {next_action} |"
    )

lines.append("")
lines.append(f"## Summary")
lines.append("")
lines.append(f"- Total workflow routers: {len(workflow_keys)}")
lines.append(f"- Product-visible workflows: {ready_count}")
lines.append(f"- Remaining workflows needing catalog/results work: {len(workflow_keys) - ready_count}")
lines.append("")
lines.append("## Validation order")
lines.append("")
for workflow in workflow_keys:
    lines.append(f"1. `{workflow}`")

OUT.write_text("\n".join(lines) + "\n")
print(f"WRITTEN {OUT}")
