"""
PII-anonimiseringslaag — AVG/GDPR-compliance vóór elke externe LLM-call.

Achtergrond (zie CLAUDE.md §5, risico "Geen AVG-anonimisering vóór LLM-calls",
ernst: Kritiek): elke workflow die tekst naar OpenAI stuurt (een derde partij,
sub-verwerker buiten de EU) moet persoonsgegevens van natuurlijke personen
eerst detecteren en verwijderen/vervangen. Deze module is die laag.

Gebruik (per workflow-implementatie):

    from app.core.pii_anonymizer import anonymize_text, PIIAnonymizerUnavailable

    try:
        user_message = anonymize_text(user_message, workflow="sales_lead_qualification")
    except PIIAnonymizerUnavailable as exc:
        return {..., "status": "degraded", "degraded_reason": str(exc)}

BELANGRIJK — fail closed, nooit fail open:
    Als de anonimisering zelf niet kan draaien (Presidio/spaCy niet
    geïnstalleerd, modellen ontbreken, onverwachte fout), gooit
    anonymize_text() een PIIAnonymizerUnavailable-exception. De aanroepende
    workflow MOET die opvangen door het bestaande "degraded"-antwoordpad te
    nemen (hetzelfde patroon als de bestaande "OPENAI_API_KEY ontbreekt"-tak
    in elke workflow) — NOOIT de exception negeren en alsnog de
    ongeanonimiseerde tekst naar OpenAI sturen. Dat zou precies het lek zijn
    dat deze laag moet voorkomen.

Ontwerpkeuzes:
  - Presidio (Microsoft, open source, self-hosted — geen data verlaat de
    eigen infrastructuur voor de detectiestap zelf) met spaCy NLP-modellen
    voor zowel Nederlands (nl_core_news_lg) als Engels (en_core_web_lg),
    omdat Valqeron's klantdata een mix van beide talen bevat.
  - Patroon-/regex-gebaseerde herkenners (EMAIL_ADDRESS, PHONE_NUMBER,
    IBAN_CODE, CREDIT_CARD, NL_BSN, IP_ADDRESS) draaien altijd met BEIDE
    taalmodellen — die zijn taal-onafhankelijk (regex + checksums) en dat
    verhoogt de recall bij gemengde/onzekere taal zonder risico.
  - NER-afhankelijke entiteiten (PERSON, LOCATION) draaien daarentegen
    ALLEEN met het taalmodel van de gedetecteerde dominante taal (via
    `langdetect`, met een confidence-drempel — zie
    `_detect_confident_language()`). Reden: het Engelse spaCy-model op
    zuiver Nederlandse tekst loslaten (en vice versa) bleek bij verificatie
    stelselmatig hoogst-stellige (score 0.85) maar volledig onjuiste
    PERSON-hits op te leveren — bijv. "Dit" en "tien procent" werden door
    het Engelse model op Nederlandse tekst als PERSON herkend. Alleen bij
    een onzekere/dubbelzinnige taaldetectie (korte tekst, gemengde taal,
    lage confidence) vallen we terug op BEIDE modellen voor PERSON/LOCATION
    — de veilige kant op (kans op over-redactie in het randgeval, nooit op
    gemiste PII).
  - Standaard entiteitenset (alle workflows behalve invoice_processing):
    PERSON, EMAIL_ADDRESS, PHONE_NUMBER, IBAN_CODE, CREDIT_CARD, IP_ADDRESS,
    NL_BSN, LOCATION.
  - invoice_processing gebruikt een aangepaste, kleinere set (zie
    ENTITY_SETS["invoice_processing"] hieronder): die workflow moet
    vendor.name en vendor.address juist WEL uit de factuurtekst kunnen
    extraheren (dat zijn bedrijfsgegevens, geen persoonsgegevens van een
    natuurlijk persoon, en het staat letterlijk in het output-schema) — dus
    PERSON en LOCATION worden daar bewust NIET geanonimiseerd. Sterke
    individuele identifiers (e-mail, telefoon, IBAN, creditcard, BSN,
    IP-adres) worden daar wél verwijderd, voor het geval een contactpersoon
    van de leverancier toevallig in de factuurtekst voorkomt.
  - Organisatienamen (ORG) worden nooit geanonimiseerd — bedrijfsnamen zijn
    voor B2B-gebruik functioneel noodzakelijk en zijn doorgaans geen
    persoonsgegeven.
  - Custom recognizer voor het Nederlandse BSN (burgerservicenummer) met de
    officiële 11-proef als validator, zodat willekeurige 8-9-cijferige
    reeksen niet massaal als BSN worden gemarkeerd (lage false-positive rate).
  - Custom NL_PHONE-recognizer (toegevoegd 2026-09-18, zelfde ontwerp als
    NL_BSN hierboven): Presidio's ingebouwde PHONE_NUMBER-recognizer bleek
    bij productieverificatie het veelgebruikte Nederlandse mobiele formaat
    "06-12345678" niet betrouwbaar te detecteren met de (Python-3.9-gedwongen
    oudere) spaCy-modellen. NL_PHONE is een aanvullende, taal-onafhankelijke
    patroon-recognizer specifiek voor NL-mobiele nummers (06-.../+31 6.../
    0031 6...), met een structuurvalidator (geen checksum bestaat voor
    telefoonnummers zoals bij BSN — de validator controleert dat het
    genormaliseerde nummer op de juiste lengte/prefix uitkomt en geen
    triviale, herhaalde-cijferreeks is). Draait naast, niet in plaats van,
    de generieke PHONE_NUMBER-recognizer — beide staan in de entiteitenset,
    delen dezelfde "<TELEFOONNUMMER>"-placeholder.
  - Vervanging is een simpele "<TYPE>"-placeholder (bijv. "<PERSOON>"), geen
    per-waarde-nummering — voldoende voor de workflows hier, die de
    geanonimiseerde tekst alleen als LLM-input gebruiken en de originele
    (niet-geanonimiseerde) structured fields apart en direct uit de eigen
    payload teruggeven aan de gebruiker (nooit via de LLM-response) — zie de
    per-workflow docstrings voor de bevestiging per workflow.

Zie tests/test_pii_anonymizer.py voor de verwachte input/output-contracten.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PIIAnonymizerUnavailable(RuntimeError):
    """De anonimiseringslaag kon niet initialiseren of niet draaien.

    Aanroepers MOETEN dit behandelen als een harde stop vóór elke externe
    LLM-call — nooit terugvallen op het versturen van de ruwe tekst.
    """


# Standaard entiteitenset — alle workflows behalve de expliciete overrides
# hieronder.
_DEFAULT_ENTITIES: List[str] = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "NL_PHONE",
    "IBAN_CODE",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "NL_BSN",
    "LOCATION",
]

# Per-workflow overrides. Alleen invoice_processing wijkt af: die workflow
# extraheert vendor.name / vendor.address rechtstreeks uit de factuurtekst
# via de LLM (geen andere bron beschikbaar — zie de workflow-docstring), dus
# PERSON en LOCATION blijven daar bewust ongemoeid. Sterke individuele
# identifiers worden wel verwijderd.
ENTITY_SETS: Dict[str, List[str]] = {
    "invoice_processing": [
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "NL_PHONE",
        "IBAN_CODE",
        "CREDIT_CARD",
        "IP_ADDRESS",
        "NL_BSN",
    ],
}

_REPLACEMENTS: Dict[str, str] = {
    "PERSON": "<PERSOON>",
    "EMAIL_ADDRESS": "<E-MAILADRES>",
    "PHONE_NUMBER": "<TELEFOONNUMMER>",
    "NL_PHONE": "<TELEFOONNUMMER>",
    "IBAN_CODE": "<REKENINGNUMMER>",
    "CREDIT_CARD": "<CREDITCARDNUMMER>",
    "IP_ADDRESS": "<IP-ADRES>",
    "NL_BSN": "<BSN>",
    "LOCATION": "<LOCATIE>",
}

_SCORE_THRESHOLD = float(os.getenv("PII_ANALYZER_SCORE_THRESHOLD", "0.45"))
_LANGUAGES = ("nl", "en")

# Entiteitstypen die uitsluitend via spaCy's NER-pijplijn worden gedetecteerd
# (geen regex/pattern-recognizer). Alleen déze typen zijn gevoelig voor het
# "verkeerde taalmodel"-probleem hierboven — de overige typen in
# _DEFAULT_ENTITIES/ENTITY_SETS zijn regex-/checksum-gebaseerd en dus
# taal-onafhankelijk veilig om met beide modellen te draaien.
_NER_ENTITY_TYPES = frozenset({"PERSON", "LOCATION"})

# Drempel voor `langdetect`'s kansschatting (0.0-1.0) om een taal "zeker
# genoeg" te vinden om NER-detectie te beperken tot dat ene taalmodel. Onder
# deze drempel (of bij een taal buiten _LANGUAGES, of bij een detectiefout op
# erg korte tekst) draaien we voor de zekerheid beide modellen — zie
# `_detect_confident_language()`.
_LANG_DETECTION_CONFIDENCE_THRESHOLD = 0.90

_init_lock = threading.Lock()
_analyzer = None  # type: ignore[var-annotated]
_anonymizer_engine = None  # type: ignore[var-annotated]
_init_error: Optional[str] = None


def _is_valid_nl_bsn(digits: str) -> bool:
    """Officiële 11-proef voor het Nederlandse burgerservicenummer.

    Een reeks van 8 of 9 cijfers is alleen een geldig BSN als de gewogen som
    (gewichten 9..2 voor de eerste 8 cijfers, gewicht -1 voor het laatste
    cijfer) deelbaar is door 11. Dit voorkomt dat elk willekeurig 9-cijferig
    getal (bijv. een factuurnummer) als BSN wordt aangemerkt.
    """
    if not digits.isdigit() or len(digits) not in (8, 9):
        return False
    padded = digits.zfill(9)
    total = sum(int(d) * w for d, w in zip(padded[:8], range(9, 1, -1)))
    total += int(padded[8]) * -1
    return total != 0 and total % 11 == 0


def _build_nl_bsn_recognizer():
    from presidio_analyzer import Pattern, PatternRecognizer

    class NLBSNRecognizer(PatternRecognizer):
        def validate_result(self, pattern_text: str) -> Optional[bool]:
            digits = re.sub(r"\D", "", pattern_text)
            return _is_valid_nl_bsn(digits)

    pattern = Pattern(name="nl_bsn_digits", regex=r"\b\d{8,9}\b", score=0.3)
    return NLBSNRecognizer(
        supported_entity="NL_BSN",
        patterns=[pattern],
        supported_language="nl",
        context=["bsn", "burgerservicenummer", "sofinummer", "sofi-nummer"],
        name="NL_BSN_recognizer",
    )


def _is_valid_nl_phone(digits: str) -> bool:
    """Structuurcontrole voor een Nederlands mobiel telefoonnummer.

    Geen checksum bestaat voor telefoonnummers (in tegenstelling tot BSN's
    11-proef), dus deze validator controleert in plaats daarvan structuur:
    na normalisatie van een eventueel landcode-prefix (+31/0031) moet het
    resultaat exact 10 cijfers zijn en beginnen met "06" (het Nederlandse
    mobiele-trunkprefix), en mag niet louter uit één herhaald cijfer bestaan
    (bijv. "0600000000" — een veelvoorkomende placeholder-/testwaarde, geen
    echt nummer). Dit voorkomt dat willekeurige 10-cijferige reeksen (bijv.
    een IBAN-rekeningnummer) massaal als telefoonnummer worden gemarkeerd.
    """
    if digits.startswith("0031"):
        digits = "0" + digits[4:]
    elif digits.startswith("31") and len(digits) == 11:
        digits = "0" + digits[2:]
    if len(digits) != 10 or not digits.startswith("06"):
        return False
    if len(set(digits[2:])) == 1:
        return False
    return True


def _build_nl_phone_recognizer():
    from presidio_analyzer import Pattern, PatternRecognizer

    class NLPhoneRecognizer(PatternRecognizer):
        def validate_result(self, pattern_text: str) -> Optional[bool]:
            digits = re.sub(r"\D", "", pattern_text)
            return _is_valid_nl_phone(digits)

    # Matches the Dutch national mobile format (06-XXXXXXXX, with optional
    # dash/space separators or none at all) and the international form
    # (+31 6 XXXXXXXX / 0031 6 XXXXXXXX). The leading \b is only applied to
    # the "06" branch — a \b right before "+" never matches (neither side is
    # a word character), so the +31/0031 branches rely on the literal digit
    # prefix itself to anchor the match instead.
    pattern = Pattern(
        name="nl_phone_mobile",
        regex=r"(?:\+31[-\s]?6|0031[-\s]?6|\b06)(?:[-\s]?\d){8}\b",
        score=0.4,
    )
    return NLPhoneRecognizer(
        supported_entity="NL_PHONE",
        patterns=[pattern],
        supported_language="nl",
        context=["telefoon", "tel", "bel", "mobiel", "nummer"],
        name="NL_PHONE_recognizer",
    )


def _init_analyzer():
    """Bouwt de Presidio AnalyzerEngine met NL+EN spaCy-modellen.

    Wordt precies één keer uitgevoerd (thread-safe, lazy) — pas bij de
    eerste echte aanroep, zodat imports die deze module alleen importeren
    (of tests die 'm mocken) geen zware spaCy-modellen hoeven te laden.
    """
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [
            {"lang_code": "nl", "model_name": "nl_core_news_lg"},
            {"lang_code": "en", "model_name": "en_core_web_lg"},
        ],
    }
    provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
    nlp_engine = provider.create_engine()

    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=list(_LANGUAGES))
    analyzer.registry.add_recognizer(_build_nl_bsn_recognizer())
    analyzer.registry.add_recognizer(_build_nl_phone_recognizer())
    return analyzer


def _get_engines():
    """Retourneert (analyzer, anonymizer_engine), lazy geïnitialiseerd.

    Gooit PIIAnonymizerUnavailable als initialisatie faalt — en onthoudt die
    fout zodat volgende aanroepen niet telkens opnieuw een dure, langzaam
    falende import proberen.
    """
    global _analyzer, _anonymizer_engine, _init_error

    if _analyzer is not None and _anonymizer_engine is not None:
        return _analyzer, _anonymizer_engine
    if _init_error is not None:
        raise PIIAnonymizerUnavailable(_init_error)

    with _init_lock:
        if _analyzer is not None and _anonymizer_engine is not None:
            return _analyzer, _anonymizer_engine
        if _init_error is not None:
            raise PIIAnonymizerUnavailable(_init_error)

        try:
            from presidio_anonymizer import AnonymizerEngine

            analyzer = _init_analyzer()
            anonymizer_engine = AnonymizerEngine()
        except Exception as exc:  # noqa: BLE001 — moet nooit de caller crashen
            _init_error = (
                "PII-anonimisering kon niet worden geïnitialiseerd (Presidio/spaCy "
                f"ontbreekt of faalt): {type(exc).__name__}: {exc}. Controleer of "
                "presidio-analyzer, presidio-anonymizer, spacy en de nl_core_news_lg "
                "/ en_core_web_lg modellen geïnstalleerd zijn (zie requirements.txt)."
            )
            logger.error("pii_anonymizer: init mislukt: %s", _init_error, exc_info=True)
            raise PIIAnonymizerUnavailable(_init_error) from exc

        _analyzer, _anonymizer_engine = analyzer, anonymizer_engine
        logger.info("pii_anonymizer: Presidio-analyzer geïnitialiseerd (nl + en)")
        return _analyzer, _anonymizer_engine


def _detect_confident_language(text: str) -> Optional[str]:
    """Detecteert de dominante taal van `text`, maar alleen als dat met
    voldoende zekerheid kan.

    Gebruikt `langdetect` (deterministisch gemaakt via een vaste seed — de
    onderliggende Naive Bayes-detector is anders niet-deterministisch tussen
    aanroepen). Retourneert de taalcode ("nl"/"en") als:
      - detectie lukt (geen te korte/lege tekst of andere detectiefout),
      - de meest waarschijnlijke taal een van de ondersteunde talen is, EN
      - de kans daarvoor minstens _LANG_DETECTION_CONFIDENCE_THRESHOLD is.

    Retourneert None in alle andere gevallen (onzeker) — de aanroeper valt
    dan terug op het draaien van BEIDE taalmodellen voor de NER-afhankelijke
    entiteiten, de veilige kant op.
    """
    try:
        from langdetect import detect_langs
        from langdetect.lang_detect_exception import LangDetectException
        from langdetect.detector_factory import DetectorFactory

        # Zonder vaste seed is langdetect's Naive Bayes-sampling niet
        # deterministisch (kan per aanroep licht wisselen) — dat willen we
        # niet voor een compliance-kritieke beslissing zoals deze.
        DetectorFactory.seed = 0
    except Exception:  # noqa: BLE001 — langdetect ontbreekt of faalt te laden
        return None

    try:
        candidates = detect_langs(text)
    except LangDetectException:
        return None
    except Exception:  # noqa: BLE001
        return None

    if not candidates:
        return None

    top = candidates[0]
    if top.lang not in _LANGUAGES or top.prob < _LANG_DETECTION_CONFIDENCE_THRESHOLD:
        return None
    return top.lang


def _resolve_overlaps(results: List[Any]) -> List[Any]:
    """Lost overlappende spans op tussen de NL- en EN-analyse.

    Grofmazige greedy interval-selectie: hoogste score wint, daarna vroegste
    startpositie. Nodig omdat we twee aparte analyze()-aanroepen (nl + en)
    samenvoegen — binnen één taal lost Presidio dit zelf al op, maar niet
    tussen twee losse aanroepen.
    """
    ordered = sorted(results, key=lambda r: (-r.score, r.start))
    selected: List[Any] = []
    occupied: List[tuple] = []
    for r in ordered:
        if any(not (r.end <= s or r.start >= e) for s, e in occupied):
            continue
        selected.append(r)
        occupied.append((r.start, r.end))
    return sorted(selected, key=lambda r: r.start)


def anonymize_text(text: str, workflow: Optional[str] = None) -> str:
    """Anonimiseert persoonsgegevens in `text` vóór verzending naar OpenAI.

    Args:
        text: de ruwe tekst die anders 1-op-1 als LLM-input zou dienen.
        workflow: workflow-key (bijv. "sales_lead_qualification"), gebruikt
            om de juiste entiteitenset te kiezen (zie ENTITY_SETS hierboven).
            Onbekende/None -> standaard volledige set.

    Returns:
        De tekst met gedetecteerde persoonsgegevens vervangen door
        "<TYPE>"-placeholders. Lege/blanco input wordt ongewijzigd
        teruggegeven (niets te anonimiseren, geen reden om te falen).

    Raises:
        PIIAnonymizerUnavailable: als de anonimisering zelf niet kon
            draaien. Dit MOET door de aanroeper worden opgevangen door het
            bestaande "degraded"-antwoordpad van de workflow te nemen.
    """
    if not text or not text.strip():
        return text

    analyzer, anonymizer_engine = _get_engines()
    entities = ENTITY_SETS.get(workflow or "", _DEFAULT_ENTITIES)

    # Splits in taal-onafhankelijke (regex/checksum) en NER-afhankelijke
    # entiteitstypen — zie de uitleg bij _NER_ENTITY_TYPES hierboven. Alleen
    # voor de NER-afhankelijke set beperken we tot het taalmodel van de
    # gedetecteerde dominante taal (als die met voldoende zekerheid bekend
    # is); de patroon-gebaseerde set draait altijd met beide modellen.
    pattern_entities = [e for e in entities if e not in _NER_ENTITY_TYPES]
    ner_entities = [e for e in entities if e in _NER_ENTITY_TYPES]

    confident_language = _detect_confident_language(text) if ner_entities else None
    ner_languages = {confident_language} if confident_language else set(_LANGUAGES)

    all_results: List[Any] = []
    for language in _LANGUAGES:
        language_entities = list(pattern_entities)
        if language in ner_languages:
            language_entities.extend(ner_entities)
        if not language_entities:
            continue
        try:
            all_results.extend(
                analyzer.analyze(
                    text=text,
                    language=language,
                    entities=language_entities,
                    score_threshold=_SCORE_THRESHOLD,
                )
            )
        except Exception as exc:  # noqa: BLE001
            raise PIIAnonymizerUnavailable(
                f"PII-analyse ({language}) mislukt: {type(exc).__name__}: {exc}"
            ) from exc

    if not all_results:
        return text

    resolved = _resolve_overlaps(all_results)

    from presidio_anonymizer.entities import OperatorConfig

    operators = {
        entity_type: OperatorConfig("replace", {"new_value": placeholder})
        for entity_type, placeholder in _REPLACEMENTS.items()
    }
    operators["DEFAULT"] = OperatorConfig("replace", {"new_value": "<PERSOONSGEGEVEN>"})

    try:
        anonymized = anonymizer_engine.anonymize(
            text=text,
            analyzer_results=resolved,
            operators=operators,
        )
    except Exception as exc:  # noqa: BLE001
        raise PIIAnonymizerUnavailable(
            f"PII-anonimisering mislukt: {type(exc).__name__}: {exc}"
        ) from exc

    logger.info(
        "pii_anonymizer: workflow=%s — %d entiteit(en) geanonimiseerd (%s)",
        workflow or "default",
        len(resolved),
        ", ".join(sorted({r.entity_type for r in resolved})),
    )

    return anonymized.text
