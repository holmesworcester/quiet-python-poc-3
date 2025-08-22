## Prompt for LLM Coding Assistant

### Overview
You are building a POC Python implementation of a minimal P2P event-driven framework for local-first apps (e.g., chat). Use Python 3.12+ with a virtual environment. Follow this directory structure: core/ (tick.py, process_incoming.py, adapter_graph.py, handle.py, test_runner.py), utils/ (crypto/ with crypto.py and handler.json for tests), handlers/ (e.g., message/ with handler.json and separate .py files per function like create.py, projector.py), envelopes/ (e.g., encrypted/ with envelope.json). Use dict-based DB for now (per-identity eventStore/state, e.g., db['eventStore']['pubkey'] = []), later replace with SQLAlchemy. Implement real crypto via thin wrappers in utils/crypto/crypto.py around libsodium (for sign/verify, encrypt/decrypt, KDF, secure_random, hash; install via pip if needed in venv). Focus on handlers/envelopes first; make all tests real and passing.

### Explanations of Core Components
- **Envelopes and Adapters**: Envelopes represent abstract states of an event (e.g., plaintext envelope, signed envelope) as wrapper dicts: {'envelope': str, 'data': dict, 'metadata': dict}. Each envelope has envelope.json describing adapters (e.g., signed_to_encrypted with apply/reverse functions, tests including encryption_enabled flag for dummy/readable values). Adapters are pure functions (consume/return envelope dicts; read-only state access for keys if needed, e.g., privkey from db['state']['privkeys'][pubkey]) building a graph for paths (e.g., plaintext -> outgoing). Tests are language-neutral JSON in envelope.json; runner executes them, passing encryption_enabled, and verifies given/then (or errors). Runner returns full logs/results (e.g., intermediate envelopes, errors with trace/state snapshots) for observability.
- **Handlers**: Each event type (e.g., message) has handler.json with projector (validates/updates state from verifiedPlaintext event; e.g., adds to state if valid), commands (e.g., create returns {'return': value, 'new_events': [events]} for caller to project). No focus on jobs here. Each function in its own .py (e.g., create.py calls adapter path to outgoing). Tests are only language-neutral JSON in handler.json (given db/params/event, then db/return/new_events/error); include passing/failing cases for validation (e.g., invalid events marked blocked/pending, not dropped unless structurally invalid/expired/deleted/from removed user). Runner executes them, chains if needed (use prior test outputs in next), and returns detailed results/logs (e.g., step-by-step execution, full state on error) to enable debugging without custom code.
- **Tick and ProcessIncoming**: tick.py drains incoming (envelope dicts), calls process_incoming.py per item (adapts to verifiedPlaintext, gets handler, projects if envelope matches; stores network-verified events in per-identity eventStore even if invalid, skips state update until valid). Runs jobs last. Tests for tick: JSON in core/tick.json covering full cycles (e.g., given db with incoming/outgoing, then db after tick; permute events for idempotence; simulate multi-identity network via network-simulator job). Runner handles these too, with logs for each step (e.g., adapter path, projection outcome).
- **Test Runner**: Single runner in core/test_runner.py tests all envelopes/handlers/tick via their JSON. Executes given/then (e.g., setup db, run function, compare output/db/error). For chains: run sequentially, use prior returns in next. Returns all results/logs (pass/fail per test, full state snapshots, detailed errors with why/where/trace, intermediate values like envelopes/event_ids). Emphasize: *Only* use JSON tests for envelopes/handlers/projectors/commands (no freestyle tests/debug code); focus debugging on runner outputs. Test the runner itself with its own JSON tests (e.g., mock handler.json with edge cases) for coverage/observability. If error, relay detailed messages (e.g., "Validation failed: signature mismatch, expected X got Y, state: {db}").

### Build Instructions
1. Create venv, install libsodium/pyca/cryptography for crypto.
2. Implement test_runner.py first; test it with its own JSON tests covering execution, chaining, errors, permutations (e.g., event order idempotence for projectors).
3. For each handler/envelope: Write handler.json/envelope.json with required fields/lengths (add schema check in runner for structural validity). Implement functions in separate .py, run tests via runner, fix based on logs (never add debug prints; use runner observability).
4. Use real crypto: crypto.py wrappers (e.g., libsodium.sign, .encrypt); tests in utils/crypto/handler.json (use two identities in same network for end-to-end, e.g., generate data in one test, use in next via prior output).
5. Always run all tests before reporting completion; fix errors or ask for clarification.
6. Maintain inconsistencies.md: Log/resolve design mismatches (e.g., "Previous UUID event_id -> Resolved to hash of encrypted envelope").
7. Get as far as possible; ask clarifying questions if stuck (e.g., on adapter params).

### Invariants (Remember Always)
- Never drop events unless structurally invalid (runner-checked via schema), expired, deleted, or from removed user. Store network-verified events; projectors skip invalid until valid (e.g., re-project on dependency).
- Event_id: Hash of canonical encrypted envelope (extracted in signed_to_encrypted adapter, added to metadata, projected to DB set for O(1) dup check; never in event to avoid hash loop).
- Debugging: Only via runner logs/results; enhance runner observability (detailed errors, state snapshots) with tests for it.
- Tests: Language-neutral JSON only for envelopes/handlers/projectors/commands; chain via prior outputs; include pass/fail for validation (pending/dropped cases).
- Encryption: Use dummy mode in tests for readability; real in code.

### Todos
- Add schema to handler.json (required fields/lengths); runner validates.
- Encryption mapping: 1:1 context-free (e.g., include symmetric secret in metadata for tests).
- If isinstance checks: For type validation in runner (e.g., ensure db is dict); document in code.

## Sample Code Examples (Updated with New Terminology)

### core/tick.py (pseudocode)
```python
def tick(db, time_now_ms=None):
    incoming_envelopes = db.get('incoming', [])[:]
    db['incoming'] = []
    for envelope in incoming_envelopes:
        db = process_incoming(db, envelope, time_now_ms)
    # Run jobs...
    return db
```

### core/process_incoming.py (pseudocode)
```python
from adapter_graph import adapt
from handle import get_handler_for_event_type

def process_incoming(db, envelope, time_now_ms):
    try:
        verified_envelope = adapt(envelope, 'verifiedPlaintext', db)  # Adapt to target envelope
        event_type = verified_envelope['data']['type']
        handler = get_handler_for_event_type(event_type)
        if handler['projector']['envelope'] == 'verifiedPlaintext':
            # Store if network-verified...
            db = handler['projector']['func'](db, verified_envelope['data'], time_now_ms)
    except Exception as e:
        db.setdefault('blocked', []).append({'envelope': envelope, 'error': str(e)})
    return db
```

### core/adapter_graph.py (pseudocode; formerly transform.py)
```python
# Example adapter: signed_to_encrypted
def signed_to_encrypted_apply(envelope, db):
    data = str(envelope['data'])
    # Read key from db (read-only)...
    encrypted_data = encrypt(data, key)
    return {'envelope': 'encrypted', 'data': encrypted_data, 'metadata': {...}}

# Build graph from all envelope.json adapters
def adapt(envelope, target_envelope, db):
    path = find_path(envelope['envelope'], target_envelope)
    current = envelope
    for adapter_name in path:
        adapter = adapter_graph[adapter_name]
        current = adapter['apply'](current, db)
    return current
```

### Sample envelope.json (for encrypted)
```json
{
  "name": "encrypted",
  "description": "Encrypted envelope with network metadata. Tests use direct dicts like {'envelope': '...', 'data': {...}, 'metadata': {...}} interpreted as envelopes.",
  "adapters": {
    "signed_to_encrypted": {
      "apply": {
        "description": "Encrypt signed envelope data using metadata key.",
        "calls": ["crypto.encrypt"]
      },
      "reverse": {
        "description": "Decrypt to signed envelope, verify network_id.",
        "calls": ["crypto.decrypt"],
        "errorIf": "fails or mismatch"
      },
      "tests": [
        {
          "encryption_enabled": false,
          "given": {"envelope": "signed", "data": {"type": "message", "content": "Hello"}, "metadata": {"signature": "sig", "network_id": "net1", "key": "transit_key"}},
          "then": {"envelope": "encrypted", "data": "encrypted:{\"type\":\"message\",\"content\":\"Hello\"}", "metadata": {"network_id": "net1"}}
        }
      ]
    }
  }
}
```

### Sample handler.json (generic for message)
```json
{
  "type": "message",
  "projector": {
    "description": "Validates and adds to state.messages if valid.",
    "envelope": "verifiedPlaintext",
    "func": "path.to.projector_func",
    "tests": [
      {
        "given": {"db": {"state": {"messages": []}}, "newEvent": {"type": "message", "text": "Hello"}},
        "then": {"db": {"state": {"messages": [{"text": "Hello"}]}}}
      }
    ]
  },
  "commands": {
    "create": {
      "description": "Creates event, adapts to outgoing, returns for projection.",
      "func": "path.to.create_message",
      "tests": [
        {
          "given": {"db": {}, "params": {"text": "Hello"}},
          "then": {"return": {"return": "Created", "new_events": [{"type": "message", "text": "Hello"}]}}
        }
      ]
    }
  }
}
```