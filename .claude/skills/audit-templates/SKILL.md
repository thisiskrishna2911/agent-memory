---
name: audit-templates
description: Validate no-code agent JSON templates against the pipeline factory by actually instantiating each one — not just JSON-schema lint.
---

# Audit Agent Templates

For each no-code agent JSON template (typically under `templates/` or wherever the no-code configs live):

1. **Extract the authoritative schema.** Parse the pipeline factory and config classes (`Pipeline`, `turnDetection`, `vad`, `noiseCancellation`, plugin configs) to determine the exact field names and value shapes the runtime expects.
2. **Validate by instantiation.** For each template, try to instantiate it through the pipeline factory in a subprocess dry-run. JSON-schema lint is not enough — only real instantiation catches wrong field shapes.
3. **Report mismatches** with the file path, the failing field, and the expected vs. actual shape.
4. **Flag non-canonical keys** (e.g., a template referencing both `sarvam` and `sarvamai` when `sarvamai` is the canonical name).
5. **Output a summary table:** which templates pass, which fail, and the proposed fix per failure.

Do **not** auto-apply fixes. Wait for explicit confirmation, then apply one file per response to avoid output token blowups on large template sets.
