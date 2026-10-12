"""Tests for the four blocking handout checks (Batch M, M1)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from checks import (  # noqa: E402
    TextBlock,
    check_claims,
    check_completeness,
    check_contact_gate,
    check_forbidden_words,
    check_hr_lock,
    check_modules_yaml_has_all_catalog_keys,
    flatten_text_blocks,
    is_concept_only,
    load_content,
    run_all_checks,
)


# ---------- real content files: the actual build must be clean ----------

def test_real_content_passes_every_check_with_all_modules_selected():
    content = load_content()
    catalog_keys = {m["key"] for m in content["modules"]["modules"]}
    problems = run_all_checks(
        content=content,
        selected_module_keys=catalog_keys | {"core"},
        confirmed_blocks=["hr_recruitment_ai"],
        contact_data=None,
        catalog_module_keys=catalog_keys,
    )
    assert problems == []


def test_real_content_has_exactly_ten_workflow_modules_plus_core():
    content = load_content()
    assert "core" in content["modules"]
    assert len(content["modules"]["modules"]) == 10


def test_real_claims_register_has_sixteen_or_more_entries_with_evidence():
    content = load_content()
    claims = content["claims"]["claims"]
    assert len(claims) >= 16
    for claim_id, claim in claims.items():
        assert claim.get("evidence", "").strip(), f"{claim_id} has empty evidence"


# ---------- check 1: forbidden words ----------

def test_forbidden_word_without_negation_is_flagged():
    blocks = [TextBlock("test.block", "en", "We guarantee this will work.")]
    problems = check_forbidden_words(blocks)
    assert len(problems) == 1
    assert "guarantee" in problems[0]


def test_forbidden_word_inside_a_negation_is_allowed():
    blocks = [TextBlock("test.block", "en", "This is not a ready-to-send reply.")]
    assert check_forbidden_words(blocks) == []


def test_forbidden_word_nl_without_negation_is_flagged():
    blocks = [TextBlock("test.block", "nl", "Dit systeem werkt volledig automatisch.")]
    problems = check_forbidden_words(blocks)
    assert len(problems) == 2  # "volledig" and "automatisch" both hit


def test_forbidden_word_nl_negated_is_allowed():
    blocks = [TextBlock("test.block", "nl", "Dit is geen kant-en-klaar antwoord.")]
    assert check_forbidden_words(blocks) == []


def test_forbidden_word_substring_inside_a_longer_dutch_word_is_not_a_false_positive():
    # "veilig" is a substring of "beveiligingsmelding" but must not match there.
    blocks = [TextBlock("test.block", "nl", "Beveiligings- of privacymelding: 06-1234567.")]
    assert check_forbidden_words(blocks) == []


def test_forbidden_word_case_insensitive():
    blocks = [TextBlock("test.block", "en", "This is 100% SECURE.")]
    problems = check_forbidden_words(blocks)
    assert len(problems) == 2  # "100%" and "secure"


# ---------- check 2: claim register + absolute-word/number rule ----------

def test_unknown_claim_id_is_flagged():
    blocks = [TextBlock("test.block", "en", "This is backed by evidence.", claims=["C99"])]
    problems = check_claims(blocks, {"claims": {}})
    assert any("unknown claim" in p for p in problems)


def test_claim_with_empty_evidence_is_flagged():
    blocks = [TextBlock("test.block", "en", "This is backed by evidence.", claims=["C1"])]
    problems = check_claims(blocks, {"claims": {"C1": {"text": "x", "evidence": "  "}}})
    assert any("no evidence" in p for p in problems)


def test_absolute_word_without_claim_or_exception_is_flagged():
    blocks = [TextBlock("test.block", "en", "Every request is always logged.")]
    problems = check_claims(blocks, {"claims": {}})
    assert len(problems) == 1
    assert "absolute word" in problems[0]


def test_absolute_word_with_claim_id_is_allowed():
    blocks = [TextBlock("test.block", "en", "Every request is logged.", claims=["C2"])]
    problems = check_claims(blocks, {"claims": {"C2": {"text": "x", "evidence": "y"}}})
    assert problems == []


def test_number_without_claim_or_exception_is_flagged():
    blocks = [TextBlock("test.block", "en", "You can submit up to 20 requests per day.")]
    problems = check_claims(blocks, {"claims": {}})
    assert len(problems) == 1


def test_absolute_word_with_allow_absolute_is_allowed():
    blocks = [TextBlock("test.block", "nl", "Dit is nooit een kant-en-klaar antwoord.", allow_absolute=True)]
    assert check_claims(blocks, {"claims": {}}) == []


def test_sentence_with_neither_absolute_word_nor_number_needs_nothing():
    blocks = [TextBlock("test.block", "en", "A team member reviews the result.")]
    assert check_claims(blocks, {"claims": {}}) == []


# ---------- check 3: completeness ----------

def test_completeness_flags_a_module_without_a_template():
    modules_yaml = {"modules": [{"key": "document_intelligence"}]}
    problems = check_completeness(["document_intelligence", "no_such_module"], modules_yaml)
    assert len(problems) == 1
    assert "no_such_module" in problems[0]


def test_completeness_ignores_core():
    modules_yaml = {"modules": [{"key": "document_intelligence"}]}
    assert check_completeness(["document_intelligence", "core"], modules_yaml) == []


def test_catalog_coverage_flags_a_catalog_module_missing_a_template():
    modules_yaml = {"modules": [{"key": "document_intelligence"}]}
    problems = check_modules_yaml_has_all_catalog_keys(
        modules_yaml, ["core", "document_intelligence", "compliance_monitor"]
    )
    assert any("compliance_monitor" in p and "no template" in p for p in problems)


def test_catalog_coverage_flags_an_orphan_template():
    modules_yaml = {"modules": [{"key": "document_intelligence"}, {"key": "ghost_module"}]}
    problems = check_modules_yaml_has_all_catalog_keys(modules_yaml, ["core", "document_intelligence"])
    assert any("ghost_module" in p for p in problems)


# ---------- check 4: HR lock + contact gate ----------

def test_hr_module_selected_but_not_confirmed_is_blocked():
    problems = check_hr_lock(["hr_recruitment_ai", "core"], confirmed_blocks=[])
    assert len(problems) == 1
    assert "hr_recruitment_ai" in problems[0]


def test_hr_module_selected_and_confirmed_is_allowed():
    problems = check_hr_lock(["hr_recruitment_ai", "core"], confirmed_blocks=["hr_recruitment_ai"])
    assert problems == []


def test_hr_module_not_selected_needs_no_confirmation():
    problems = check_hr_lock(["core", "document_intelligence"], confirmed_blocks=[])
    assert problems == []


def test_missing_contact_json_is_not_a_check_failure_but_forces_concept_mode():
    assert check_contact_gate(None) == []
    assert is_concept_only(None) is True


def test_contact_json_missing_a_field_is_a_check_failure_and_forces_concept_mode():
    contact = {"urgent_phone": "+31 20 1234567", "urgent_hours": "", "security_contact": "security@valqeron.com"}
    problems = check_contact_gate(contact)
    assert len(problems) == 1
    assert "urgent_hours" in problems[0]
    assert is_concept_only(contact) is True


def test_complete_contact_json_passes_and_is_not_concept_mode():
    contact = {
        "urgent_phone": "+31 20 1234567",
        "urgent_hours": "Mon-Fri 09:00-17:00 CET",
        "security_contact": "security@valqeron.com",
    }
    assert check_contact_gate(contact) == []
    assert is_concept_only(contact) is False


# ---------- flatten_text_blocks ----------

def test_flatten_text_blocks_includes_both_languages_for_every_shared_block():
    content = load_content()
    blocks = flatten_text_blocks(content["shared"], content["modules"])
    shared_block_ids = {b.block_id for b in blocks if b.block_id.startswith("shared.")}
    expected = {f"shared.{k}" for k in content["shared"]["blocks"].keys()}
    assert expected.issubset(shared_block_ids)


def test_flatten_text_blocks_includes_all_ten_modules():
    content = load_content()
    blocks = flatten_text_blocks(content["shared"], content["modules"])
    module_ids = {b.block_id.split(".")[1] for b in blocks if b.block_id.startswith("module.") and b.block_id != "module.core"}
    assert len(module_ids) == 10
