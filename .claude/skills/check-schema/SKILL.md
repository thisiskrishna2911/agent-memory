---
name: check-schema
description: Probe a provider gateway with curl and diff the actual wire format against the SDK's expected schema — surfaces query-vs-body, default-model, and field-name mismatches.
---

# Check Provider Schema

For the provider named in the request (or the one currently being modified):

1. **Locate the plugin** under `videosdk-plugins/videosdk-plugins-<provider>/` and extract:
   - Default model ID
   - Endpoint URL(s)
   - Request payload shape — body fields, headers, query string params
   - Expected response shape
2. **Construct a minimal valid `curl -v`** that mirrors what the SDK sends. Use `${PROVIDER}_API_KEY` from env; do not bake secrets into the command.
3. **Run it** (or hand the user the exact command if it requires their environment) and capture:
   - Request line and headers
   - Request body (with `--data` echoed back)
   - Response status, headers, body
4. **Diff the actual wire format against what the SDK encodes:**
   - Are required params on the body, or accidentally on the query string?
   - Does the default model ID exist for this account / API version?
   - Are field names canonical (`sarvamai` not `sarvam`)?
   - Does the response shape match what the SDK parses?
5. **Report mismatches** with `file:line` references into the plugin source.

Do not propose a fix until the user has reviewed the diff. This is the same loop you'd run before claiming a regression is "fixed" — wire format truth first, theory second.
