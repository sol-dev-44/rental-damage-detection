"""Dynamic prompt construction for the damage-detection pipeline.

Uses Jinja2 templates (NOT LangChain) to assemble the system and user
prompts that are sent to Claude.  The template is stored as a string
constant in this module so there are no external template files to manage.

Key sections of the prompt:
  1. Asset context -- type, metadata, identifier.
  2. Retrieval-augmented examples -- past corrections for this asset type
     retrieved via metadata-based filtering (see ``few_shot_engine``).
     These are *retrieval-augmented prompting* examples, not "learned"
     behaviour; Claude has no persistent memory between calls.
  3. Known false-positive patterns for this asset type so the model can
     avoid repeating common mistakes.
  4. Task instructions -- what JSON schema to return.
  5. Accuracy context -- optional stats on historical accuracy for this
     tenant / asset type so the model can self-calibrate.
"""

from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, BaseLoader, StrictUndefined

# ---------------------------------------------------------------------------
# Jinja2 template (stored inline -- no file-system dependency)
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATE = """\
You are a damage-detection AI for rental equipment.  Your task is to compare
"before" (pre-rental) and "after" (post-rental) photos of a piece of
equipment and identify any NEW damage that occurred during the rental period.

## Asset context
- Asset type: {{ asset_type }}
- Asset identifier: {{ asset_identifier }}
{% if asset_metadata %}
- Additional metadata: {{ asset_metadata | tojson }}
{% endif %}

## Instructions
1. Compare each after photo to the before photo(s).
2. Identify ONLY new damage -- do NOT flag pre-existing wear or cosmetic
   features visible in the before photos.
3. For each finding, provide:
   - damage_type (e.g. scratch, dent, crack, tear, discoloration, gouge, chip)
   - location_description (where on the asset the damage is)
   - severity: one of "minor", "moderate", "major", "severe"
   - confidence_score: integer 0-100
   - ai_reasoning: a brief explanation of why this is new damage
   - bounding_box (optional): {"x": int, "y": int, "width": int, "height": int}
     in pixels, referencing the after photo
4. If you see NO new damage, return an empty findings list.
5. Be conservative -- it is better to miss borderline damage than to produce
   false positives.  Only report damage you are confident about (>= 70).

{% if false_positive_patterns %}
## Common false positives to AVOID for {{ asset_type }} assets
These patterns have been flagged by operators as frequent mistakes.  Do NOT
report them unless you are very confident they represent genuine new damage:
{% for pattern in false_positive_patterns %}
- {{ pattern }}
{% endfor %}
{% endif %}

{% if few_shot_examples %}
## Reference examples from past inspections
The following are real corrections made by human operators on similar
{{ asset_type }} assets.  Use them to calibrate your judgements.  These
examples are provided via retrieval-augmented prompting -- they do not
represent persistent learned behaviour.
{% for ex in few_shot_examples %}

### Example {{ loop.index }}
- Original AI damage_type: {{ ex.original_damage_type }}
- Original AI severity: {{ ex.original_severity }}
- Correction type: {{ ex.feedback_type }}
{% if ex.corrected_damage_type %}- Corrected damage_type: {{ ex.corrected_damage_type }}{% endif %}
{% if ex.corrected_severity %}- Corrected severity: {{ ex.corrected_severity }}{% endif %}
{% if ex.operator_notes %}- Operator notes: {{ ex.operator_notes }}{% endif %}
{% endfor %}
{% endif %}

{% if accuracy_context %}
## Historical accuracy context
These stats summarise how well the model has performed for this tenant.
Use them to inform your confidence calibration -- e.g. if past accuracy
for "scratch" on "jetski" is only 60%, be more cautious reporting scratches.
{% for key, value in accuracy_context.items() %}
- {{ key }}: {{ value }}
{% endfor %}
{% endif %}

## Required output format
Return ONLY a JSON object with the following shape (no markdown fences,
no explanatory text outside the JSON):

{
  "findings": [
    {
      "damage_type": "string",
      "location_description": "string",
      "severity": "minor | moderate | major | severe",
      "confidence_score": 0-100,
      "ai_reasoning": "string",
      "bounding_box": {"x": 0, "y": 0, "width": 0, "height": 0} | null
    }
  ]
}
"""

# ---------------------------------------------------------------------------
# Jinja2 environment (reused across calls -- thread-safe for rendering)
# ---------------------------------------------------------------------------

_ENV = Environment(
    loader=BaseLoader(),
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
)

_compiled_system_template = _ENV.from_string(_SYSTEM_TEMPLATE)

# ---------------------------------------------------------------------------
# Known false-positive patterns per asset type
# ---------------------------------------------------------------------------

_FALSE_POSITIVE_PATTERNS: dict[str, list[str]] = {
    "jetski": [
        "Water spots or salt residue that look like discoloration",
        "Reflection or glare on wet surfaces that resemble scratches",
        "Rubber dock bumper marks that are temporary and wipe off",
        "Factory seam lines mistaken for cracks",
        "Suction cup marks from tow setup",
    ],
    "boat": [
        "Waterline staining that varies with tide or docking conditions",
        "Fender marks that are temporary contact impressions",
        "Sun-bleached gelcoat that is pre-existing wear, not new damage",
        "Barnacle attachment points visible in after photos taken at haul-out",
        "Rope scuff marks from normal docking operations",
    ],
    "parasail": [
        "Creasing in fabric from folding/packing that is not a tear",
        "Sand or salt deposits on canopy surface",
        "Colour variation due to different lighting conditions between photos",
    ],
    "other": [],
}


# ---------------------------------------------------------------------------
# Public builder function
# ---------------------------------------------------------------------------

def build_damage_detection_prompt(
    *,
    asset_type: str,
    asset_identifier: str,
    asset_metadata: dict[str, Any] | None = None,
    few_shot_examples: list[dict[str, Any]] | None = None,
    accuracy_context: dict[str, Any] | None = None,
) -> str:
    """Render the system prompt for a damage-detection Claude request.

    Parameters
    ----------
    asset_type:
        One of the ``AssetType`` enum values (e.g. ``"jetski"``).
    asset_identifier:
        Human-readable identifier for the asset (hull number, registration, etc.).
    asset_metadata:
        Optional dict of extra metadata from ``assets.metadata``.
    few_shot_examples:
        Past corrections retrieved by ``few_shot_engine.get_similar_cases``.
        Each dict should contain keys like ``original_damage_type``,
        ``original_severity``, ``feedback_type``, ``corrected_damage_type``,
        ``corrected_severity``, ``operator_notes``.
    accuracy_context:
        Historical accuracy stats (keyed by descriptive labels) produced by
        ``metrics_tracker``.  Example:
        ``{"scratch accuracy on jetski": "62%", "overall precision": "78%"}``.

    Returns
    -------
    str
        The rendered system prompt.
    """
    false_positive_patterns = _FALSE_POSITIVE_PATTERNS.get(asset_type, [])

    rendered = _compiled_system_template.render(
        asset_type=asset_type,
        asset_identifier=asset_identifier,
        asset_metadata=asset_metadata,
        few_shot_examples=few_shot_examples or [],
        false_positive_patterns=false_positive_patterns,
        accuracy_context=accuracy_context,
    )

    return rendered


# ---------------------------------------------------------------------------
# User-message builder (separate from system prompt)
# ---------------------------------------------------------------------------

def build_user_message(
    num_before: int,
    num_after: int,
) -> str:
    """Return the plain-text user message that accompanies the images.

    The actual image content blocks are assembled by the Claude client;
    this helper provides the textual instruction that sits alongside them.
    """
    parts: list[str] = []
    if num_before > 0:
        parts.append(
            f"I have attached {num_before} BEFORE (pre-rental) photo(s) "
            f"and {num_after} AFTER (post-rental) photo(s)."
        )
    else:
        parts.append(
            f"I have attached {num_after} AFTER (post-rental) photo(s). "
            "No before photos are available -- evaluate the after photos "
            "for visible damage on their own."
        )
    parts.append(
        "Please analyse them for new damage and return your findings "
        "as JSON per the instructions."
    )
    return " ".join(parts)
