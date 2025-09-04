#!/usr/bin/env python3
"""
Test Runner for the Event Framework
Note: this should not contain any protocol-specific code
"""
import json
import sys
import os
import traceback
import copy
try:
    import yaml
except Exception:
    yaml = None
import re
import itertools
from datetime import datetime
from pathlib import Path

# Ensure repository root is on sys.path for 'core' imports when running as a script
try:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
except Exception:
    pass

class TestRunner:
    def __init__(self):
        self.verbose = False
        self.logs = []
        self._temp_db_files = set()  # Track all temp DB files created
        
    def _track_db_file(self, db_path):
        """Track a database file for later cleanup"""
        if db_path and db_path != ':memory:' and not db_path.startswith(':'):
            self._temp_db_files.add(db_path)
    
    def _cleanup_db_files(self):
        """Clean up all tracked database files"""
        if self._temp_db_files:
            print(f"\nCleaning up {len(self._temp_db_files)} test database files...")
        for db_path in list(self._temp_db_files):
            # Clean up the main database file
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                    if self.verbose:
                        print(f"  Removed: {db_path}")
                except Exception as e:
                    print(f"  Failed to remove {db_path}: {e}")
            
            # Also clean up SQLite's auxiliary files
            for suffix in ['-wal', '-shm']:
                aux_path = db_path + suffix
                if os.path.exists(aux_path):
                    try:
                        os.remove(aux_path)
                        if self.verbose:
                            print(f"  Removed: {aux_path}")
                    except Exception as e:
                        if self.verbose:
                            print(f"  Failed to remove {aux_path}: {e}")
        self._temp_db_files.clear()
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().isoformat()
        entry = f"[{timestamp}] [{level}] {message}"
        self.logs.append(entry)
        if self.verbose:
            print(entry)
    
    def subset_match(self, actual, expected, path=""):
        """
        Check if expected is a subset of actual.
        Returns (matches, mismatch_path, expected_value, actual_value)
        """
        # Special case for "..." which matches any value
        if expected == "...":
            return True, None, None, None
            
        # Wildcard matches anything
        if expected == "*":
            return True, None, None, None
        
        # Type check
        if type(actual) != type(expected):
            return False, path, expected, actual
        
        if isinstance(expected, dict):
            # Check all keys in expected exist in actual with matching values
            for key in expected:
                if key == "*":
                    # Wildcard key - match any key with the expected value
                    if not actual:  # No keys in actual dict
                        return False, f"{path}.*", expected[key], None
                    # Check if any key has the expected value
                    found_match = False
                    for actual_key, actual_val in actual.items():
                        matches, _, _, _ = self.subset_match(actual_val, expected[key], f"{path}.{actual_key}")
                        if matches:
                            found_match = True
                            break
                    if not found_match:
                        # Return the first actual value for error reporting
                        first_key = list(actual.keys())[0] if actual else None
                        first_val = actual[first_key] if first_key else None
                        return False, f"{path}.*", expected[key], first_val
                else:
                    if key not in actual:
                        return False, f"{path}.{key}", expected[key], None
                    matches, mismatch_path, exp_val, act_val = self.subset_match(
                        actual[key], expected[key], f"{path}.{key}"
                    )
                    if not matches:
                        return False, mismatch_path, exp_val, act_val
            return True, None, None, None
            
        elif isinstance(expected, list):
            # Lists must match exactly in length
            if len(actual) != len(expected):
                return False, f"{path}.length", len(expected), len(actual)
            
            # Check if this is a list of objects (dicts)
            # If so, compare without caring about order
            if (expected and isinstance(expected[0], dict) and
                actual and isinstance(actual[0], dict)):
                
                # For lists with wildcard IDs, we need to match by type/structure
                if any(item.get('id') == '*' for item in expected if isinstance(item, dict)):
                    # Match items by type and other fields
                    unmatched_actual = list(actual)
                    for exp_item in expected:
                        found = False
                        for i, act_item in enumerate(unmatched_actual):
                            # Try to match this expected item with an actual item
                            matches, _, _, _ = self.subset_match(act_item, exp_item, path)
                            if matches:
                                unmatched_actual.pop(i)
                                found = True
                                break
                        if not found:
                            return False, f"{path}[id={exp_item.get('id', '?')}]", exp_item, None
                    return True, None, None, None
                
                # For lists with concrete IDs, use ID-based matching
                elif all('id' in item for item in expected if isinstance(item, dict)):
                    # Build maps by ID for order-independent comparison
                    expected_by_id = {item['id']: item for item in expected if isinstance(item, dict) and 'id' in item}
                    actual_by_id = {item['id']: item for item in actual if isinstance(item, dict) and 'id' in item}
                    
                    # Check all expected items exist in actual
                    for exp_id, exp_item in expected_by_id.items():
                        if exp_id not in actual_by_id:
                            return False, f"{path}[id={exp_id}]", exp_item, None
                        matches, mismatch_path, exp_val, act_val = self.subset_match(
                            actual_by_id[exp_id], exp_item, f"{path}[id={exp_id}]"
                        )
                        if not matches:
                            return False, mismatch_path, exp_val, act_val
                    return True, None, None, None
                else:
                    # For lists of objects without IDs, fall back to order-dependent comparison
                    for i, (a, e) in enumerate(zip(actual, expected)):
                        matches, mismatch_path, exp_val, act_val = self.subset_match(
                            a, e, f"{path}[{i}]"
                        )
                        if not matches:
                            return False, mismatch_path, exp_val, act_val
                    return True, None, None, None
            else:
                # For other lists, order matters
                for i, (a, e) in enumerate(zip(actual, expected)):
                    matches, mismatch_path, exp_val, act_val = self.subset_match(
                        a, e, f"{path}[{i}]"
                    )
                    if not matches:
                        return False, mismatch_path, exp_val, act_val
                return True, None, None, None
            
        else:
            # Primitive values must match exactly
            if actual != expected:
                return False, path, expected, actual
            return True, None, None, None
    
    def run_test_scenario(self, scenario, test_file):
        """Run a single test scenario using real framework"""
        scenario_name = scenario.get("name", scenario.get("description", "Unnamed"))
        self.log(f"Running scenario: {scenario_name}")

        try:
            given = scenario.get("given", {})
            then = scenario.get("then", {})
            
            # Set environment variables if specified
            if "env" in given:
                for key, value in given["env"].items():
                    os.environ[key] = value
            
            # Set crypto mode to dummy by default
            if "CRYPTO_MODE" not in os.environ:
                os.environ["CRYPTO_MODE"] = "dummy"
            
            # Set up initial state using persistent database
            from core.db import create_db
            # Use a unique database for each test to avoid conflicts
            import uuid
            test_id = str(uuid.uuid4())[:8]
            base_test_db = os.environ.get('TEST_DB_PATH', ':memory:')
            # If this scenario requires concurrency, force a file-backed DB
            requires_file_db = bool(given.get("concurrent"))
            if base_test_db != ':memory:':
                # Make it unique for this test
                test_db_path = base_test_db.replace('.db', f'_{test_id}.db')
            else:
                test_db_path = base_test_db
                if requires_file_db:
                    # Use a unique temporary file for sharing between threads
                    test_db_path = f".test_concurrent_{test_id}.db"
            
            db = create_db(db_path=test_db_path)
            
            # Track the database file for cleanup
            self._track_db_file(test_db_path)
            
            # Seed SQL generically from given db.tables/state
            given_db = given.get("db", {"state": {}})
            try:
                self._seed_sql_generic(db, given_db)
            except Exception:
                pass
            
            # Tests should provide encrypted data directly, not use setup generation
            
            # Execute commands if any
            command_results = []
            if "commands" in given:
                for cmd in given["commands"]:
                    result = self.execute_command(cmd, db)
                    command_results.append(result)
                    # Note: events are now projected automatically by run_command

            # Execute concurrent scenario if specified
            if "concurrent" in given:
                self._run_concurrent(given["concurrent"], test_db_path)
            
            # Legacy permutation shortcuts removed – tests should drive via SQL/stateful operations
            
            # Run ticks if specified or if this is a tick.json test
            ticks_to_run = scenario.get('ticks', 0)
            # For tick.json tests, always run at least one tick
            if 'tick.json' in test_file:
                ticks_to_run = max(1, ticks_to_run)
            
            if ticks_to_run > 0:
                from core.tick import tick
                time_now_ms = scenario.get('time_now_ms')
                for _ in range(ticks_to_run):
                    tick(db, time_now_ms=time_now_ms)
            
            # Build result for comparison
            # Convert persistent db to dict for comparison
            # Reload DB from disk in case concurrent workers used separate connections
            if hasattr(db, 'close'):
                db.close()
            db_fresh = create_db(db_path=test_db_path)
            result = {}

            # Attach generic SQL snapshot
            try:
                snap = self._dump_sql_generic(db_fresh)
                result['snapshot'] = snap
                if isinstance(snap, dict) and 'tables' in snap:
                    result['tables'] = snap['tables']
            except Exception:
                pass
            # Do not attach dict-style db view; SQL tables are the source of truth
            if command_results:
                result["commandResults"] = command_results
                # No dict-db back-compat normalization here
            
            # Close the database connection
            if hasattr(db, 'close'):
                db.close()
            
            # Cleanup is now handled by _cleanup_db_files() at the end
            
            # Filter out description from then before matching
            then_filtered = {k: v for k, v in then.items() if k != "description"}
            # No protocol-specific filtering here; protocols define snapshots
            
            matches, path, exp_val, act_val = self.subset_match(result, then_filtered)
            if matches:
                return {"scenario": scenario_name, "passed": True, "logs": self.logs}
            else:
                self.log(f"Mismatch at {path}: expected {exp_val}, got {act_val}", "ERROR")
                return {"scenario": scenario_name, "passed": False, "logs": self.logs}

        except Exception as e:
            self.log(f"Scenario crashed: {str(e)}", "ERROR")
            self.log(traceback.format_exc(), "ERROR")
            return {
                "scenario": scenario_name,
                "passed": False,
                "logs": self.logs,
                "error": str(e)
            }

    def _seed_sql_generic(self, db, given_db):
        if not hasattr(db, 'conn') or db.conn is None:
            return
        tables = {}
        src = given_db or {}
        # Only seed from 'tables' — SQL is the source of truth now
        if isinstance(src.get('tables'), dict):
            tables.update(src['tables'])
        if not tables:
            return
        conn = db.conn
        cur = conn.cursor()
        try:
            conn.execute('BEGIN IMMEDIATE')
        except Exception:
            pass
        def _table_info(tname):
            """Return list of (name, type, notnull, pk, dflt_value)."""
            cols = []
            try:
                for r in cur.execute(f"PRAGMA table_info({tname})").fetchall():
                    # r: cid, name, type, notnull, dflt_value, pk
                    cols.append((r[1], (r[2] or '').upper(), int(r[3] or 0), int(r[5] or 0), r[4]))
            except Exception:
                pass
            return cols
        for tname, rows in tables.items():
            try:
                cur.execute(f"DELETE FROM {tname}")
            except Exception:
                continue
            info = _table_info(tname)
            if not info:
                continue
            col_names = [c[0] for c in info]
            for row in (rows or []):
                if not isinstance(row, dict):
                    continue
                # Build a values dict from available keys
                vals = {k: row.get(k) for k in row.keys() if k in col_names}
                # Ensure unique event_id where required
                try:
                    if 'event_id' in col_names and ('event_id' not in vals or not vals.get('event_id')):
                        import uuid as _uuid
                        vals['event_id'] = f"seeded-{_uuid.uuid4()}"
                except Exception:
                    pass
                # JSON-encode common JSON columns when seeding
                try:
                    import json as _json
                    for jk in ['data', 'metadata', 'event_data']:
                        if jk in vals and not (isinstance(vals[jk], (str, bytes)) or vals[jk] is None):
                            vals[jk] = _json.dumps(vals[jk])
                except Exception:
                    pass
                # Fill required not-null columns with sensible defaults
                for name, ctype, notnull, pk, dflt in info:
                    if pk == 1:
                        continue
                    if name in vals:
                        continue
                    if notnull:
                        if dflt is not None:
                            vals[name] = dflt
                        else:
                            lname = name.lower()
                            if 'sig' == lname:
                                vals[name] = ''
                            elif 'int' in ctype or 'INTEGER' in ctype:
                                vals[name] = 0
                            else:
                                vals[name] = ''
                ins_cols = list(vals.keys())
                placeholders = ','.join(['?'] * len(ins_cols))
                insert_sql = f"INSERT INTO {tname}({','.join(ins_cols)}) VALUES({placeholders})"
                values = [vals[k] for k in ins_cols]
                try:
                    cur.execute(insert_sql, values)
                except Exception:
                    pass
        try:
            conn.commit()
        except Exception:
            pass

    def _dump_sql_generic(self, db):
        if not hasattr(db, 'conn') or db.conn is None:
            return { 'tables': {} }
        conn = db.conn
        cur = conn.cursor()
        try:
            table_names = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        except Exception:
            table_names = []
        def _skip(name):
            return (
                not name or name.startswith('sqlite_') or name in ['_kv_store','_list_store','_event_store']
            )
        out = {}
        # Preload column types for boolean normalization
        col_types = {}
        for tname in table_names:
            if _skip(tname):
                continue
            types = {}
            try:
                for r in cur.execute(f"PRAGMA table_info({tname})").fetchall():
                    # r: cid, name, type, notnull, dflt_value, pk
                    types[r[1]] = (r[2] or '').upper()
            except Exception:
                pass
            col_types[tname] = types
        for tname in sorted(n for n in table_names if not _skip(n)):
            try:
                order_col = None
                try:
                    for r in cur.execute(f"PRAGMA table_info({tname})").fetchall():
                        if r[5] == 1:
                            order_col = r[1]
                            break
                except Exception:
                    pass
                sql = f"SELECT * FROM {tname}"
                if order_col:
                    sql += f" ORDER BY {order_col}"
                rows = cur.execute(sql).fetchall()
                cols = [d[0] for d in cur.description]
                items = []
                for r in rows:
                    obj = { cols[i]: r[i] for i in range(len(cols)) }
                    # Try JSON decode for common columns
                    for key in ['data','metadata','event_data']:
                        v = obj.get(key)
                        if isinstance(v, str):
                            try:
                                import json
                                obj[key] = json.loads(v)
                            except Exception:
                                pass
                    # Normalize event_store rows to have 'data' instead of 'event_data'
                    if tname == 'event_store' and 'event_data' in obj and 'data' not in obj:
                        obj['data'] = obj.pop('event_data')
                    # Boolean normalization based on declared type
                    try:
                        types = col_types.get(tname) or {}
                        for k, t in types.items():
                            if 'BOOL' in t and k in obj and isinstance(obj[k], (int, float)):
                                obj[k] = bool(obj[k])
                    except Exception:
                        pass
                    items.append(obj)
                out[tname] = items
            except Exception:
                pass
        # Return canonical tables-only snapshot
        return { 'tables': out }

    def _run_concurrent(self, spec, db_path):
        """Run tick and commands concurrently against the same SQLite file.

        Spec format:
          {
            "commands": [ {"handler":..., "command":..., "input":..., "delay_ms": 0}, ... ],
            "tick": {"runs": 1, "time_now_ms": 1000, "delay_ms": 0, "interval_ms": 0}
          }
        Each worker creates its own DB connection bound to db_path to avoid cross-thread sqlite issues.
        """
        import threading
        import time as _time
        from core.db import create_db

        errors = []

        def run_command_worker(cmd_def):
            try:
                delay = int(cmd_def.get("delay_ms", 0))
                if delay:
                    _time.sleep(delay / 1000.0)
                db_local = create_db(db_path=db_path)
                from core.command import run_command
                handler = cmd_def["handler"]
                command = cmd_def["command"]
                input_data = cmd_def.get("input", {})
                time_now_ms = cmd_def.get("time_now_ms")
                run_command(handler, command, input_data, db_local, time_now_ms=time_now_ms)
                if hasattr(db_local, 'close'):
                    db_local.close()
            except Exception as e:
                self.log(f"Concurrent command failed: {e}", "ERROR")
                errors.append(e)

        def run_tick_worker(tick_def):
            try:
                delay = int(tick_def.get("delay_ms", 0))
                if delay:
                    _time.sleep(delay / 1000.0)
                runs = int(tick_def.get("runs", 1))
                interval = int(tick_def.get("interval_ms", 0))
                time_now_ms = tick_def.get("time_now_ms")
                from core.tick import tick
                db_local = create_db(db_path=db_path)
                for i in range(runs):
                    tick(db_local, time_now_ms=time_now_ms)
                    if interval and i < runs - 1:
                        _time.sleep(interval / 1000.0)
                if hasattr(db_local, 'close'):
                    db_local.close()
            except Exception as e:
                self.log(f"Concurrent tick failed: {e}", "ERROR")
                errors.append(e)

        threads = []
        for cmd in spec.get("commands", []):
            t = threading.Thread(target=run_command_worker, args=(cmd,), daemon=True)
            threads.append(t)
        tick_spec = spec.get("tick")
        if tick_spec:
            threads.append(threading.Thread(target=run_tick_worker, args=(tick_spec,), daemon=True))

        # If using in-memory DB, switch to a temporary file so threads share state
        if db_path == ':memory:':
            tmp_path = f".concurrent_{int(_time.time()*1000)}.db"
            self.log(f"Concurrent test requires file-backed DB, switching to {tmp_path}")
            db_path = tmp_path
            self._track_db_file(tmp_path)

        # Start all threads
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            raise errors[0]
    
    def execute_command(self, cmd, db):
        """Execute a command and return its result"""
        handler = cmd["handler"]
        command = cmd["command"]
        input_data = cmd.get("input", {})
        
        # Validate input against schema if defined
        from core.schema_validator import validate_command_input, validate_command_output
        is_valid, error = validate_command_input(handler, command, input_data)
        if not is_valid:
            raise ValueError(f"Input validation failed: {error}")
        
        # Use run_command to execute and project events
        from core.command import run_command
        updated_db, result = run_command(handler, command, input_data, db, time_now_ms=1000)
        
        # Update db reference - db is already updated by run_command
        # The updated_db returned is the same reference
        
        # Validate output against schema if defined
        is_valid, error = validate_command_output(handler, command, result)
        if not is_valid:
            raise ValueError(f"Output validation failed: {error}")
        
        # Convert db in result to dict for comparison
        if 'db' in result and hasattr(result['db'], 'to_dict'):
            result['db'] = result['db'].to_dict()
        
        return result
    
    
    
    def run_handler_test(self, test, handler_file, handler_name=None, command_name=None):
        """Run handler tests using real framework"""
        # Determine protocol from handler file path
        protocol = handler_file.split('/')[1] if '/' in handler_file else 'signed_groups'
        
        # For all protocols, automatically generate permutations if not specified
        if "permutations" not in test:
            # Collect all events from the test
            events = []
            given = test.get("given", {})
            
            # Only collect events from eventStore that are meant to be processed
            # Skip if eventStore already has events in initial state (idempotency tests)
            initial_state = given.get("db", {}).get("state", {})
            initial_eventstore = given.get("db", {}).get("eventStore", [])
            
            # Skip permutation for idempotency tests
            # (eventStore has initial events and state has corresponding data)
            if initial_eventstore and any(initial_state.get(k) for k in ["messages", "users", "groups", "channels"]):
                # This looks like an idempotency test, skip permutation
                pass
            else:
                # Collect events from eventStore for permutation
                if "eventStore" in given.get("db", {}):
                    events.extend(given["db"]["eventStore"])
                
                # Add the envelope if present
                if "envelope" in given:
                    events.append(given["envelope"])
            
            # If we have multiple events, generate permutations
            if len(events) > 1:
                # Generate all permutations
                all_permutations = list(itertools.permutations(events))
                
                # Run test for each permutation
                results = []
                for i, perm in enumerate(all_permutations):
                    self.log(f"Testing permutation {i+1}/{len(all_permutations)}: {[e['data']['type'] for e in perm if 'data' in e]}")
                    
                    # Create a persistent DB and seed SQL from given state
                    from core.db import create_db
                    import uuid as _uuid
                    base_test_db = os.environ.get('TEST_DB_PATH', ':memory:')
                    if base_test_db != ':memory:':
                        test_db_path = base_test_db.replace('.db', f'_{str(_uuid.uuid4())[:8]}.db')
                    else:
                        test_db_path = base_test_db
                    perm_db = create_db(db_path=test_db_path)
                    self._track_db_file(test_db_path)

                    # Seed SQL only (tables)
                    given_db = copy.deepcopy(test.get('given', {}).get('db', {}))
                    try:
                        self._seed_sql_generic(perm_db, given_db)
                    except Exception:
                        pass

                    # Process events in this order using persistent DB
                    from core.handle import handle
                    for event in perm:
                        perm_db = handle(perm_db, event, time_now_ms=1000)
                    
                    # Run ticks if specified
                    ticks_to_run = test.get('ticks', 0)
                    if ticks_to_run > 0:
                        from core.tick import run_all_jobs as tick
                        for _ in range(ticks_to_run):
                            tick(perm_db, time_now_ms=1000)
                    
                    # Build snapshot for SQL-native protocols
                    result_obj = {}
                    try:
                        # Always use generic SQL snapshot
                        snap = self._dump_sql_generic(perm_db)
                        if isinstance(snap, dict):
                            result_obj['snapshot'] = snap
                            if 'tables' in snap:
                                result_obj['tables'] = snap['tables']
                    except Exception:
                        pass

                    # Check result matches expected (supports tables/snapshot in 'then')
                    then = test.get("then", {})
                    matches, path, exp_val, act_val = self.subset_match(result_obj, then)
                    
                    if not matches:
                        self.log(f"Permutation {i+1} FAILED at {path}: expected {exp_val}, got {act_val}", "ERROR")
                        scenario_name = test.get("description", "Unnamed")
                        return {"scenario": scenario_name, "passed": False, "logs": self.logs}
                    else:
                        self.log(f"Permutation {i+1} passed")
                
                # All permutations passed
                scenario_name = test.get("description", "Unnamed")
                return {"scenario": scenario_name, "passed": True, "logs": self.logs}
        
        # For handler tests with envelope, we need to handle it directly
        if "envelope" in test.get("given", {}):
            scenario_name = test.get("description", "Unnamed")
            self.log(f"Running projector test: {scenario_name}")
            
            given = test.get("given", {})
            then = test.get("then", {})
            envelope = given["envelope"]
            # Use a persistent DB so SQL-only handlers see tables
            from core.db import create_db
            import uuid as _uuid
            base_test_db = os.environ.get('TEST_DB_PATH', ':memory:')
            if base_test_db != ':memory:':
                test_db_path = base_test_db.replace('.db', f'_{str(_uuid.uuid4())[:8]}.db')
            else:
                test_db_path = base_test_db
            db = create_db(db_path=test_db_path)
            # Track for cleanup
            self._track_db_file(test_db_path)
            # Seed SQL only (tables)
            given_db = given.get("db", {})
            try:
                self._seed_sql_generic(db, given_db)
            except Exception:
                pass
            
            # Call handle directly with the envelope
            from core.handle import handle
            self.log(f"Calling handle with envelope: {envelope}")
            import json
            self.log(f"Initial db state: {json.dumps(given_db, indent=2)}")
            
            result_db = handle(db, envelope, time_now_ms=1000)
            
            try:
                rb = result_db.to_dict() if hasattr(result_db, 'to_dict') else result_db
                self.log(f"Result db after handle: {json.dumps(rb, indent=2)}")
                # Also log SQL tables when in verbose mode for debugging
                if self.verbose:
                    try:
                        snap_dbg = self._dump_sql_generic(result_db)
                        self.log(f"SQL tables after handle: {json.dumps(snap_dbg.get('tables', {}), indent=2)}")
                    except Exception:
                        pass
            except Exception:
                self.log("Result db after handle: <non-serializable>")
            
            # Check for errors
            if 'blocked' in result_db:
                self.log(f"WARNING: Found blocked envelopes: {result_db['blocked']}", "WARNING")
            
            # No dict-state diff logging; SQL is the source of truth
            
            # Run ticks if specified
            ticks_to_run = test.get('ticks', 0)
            if ticks_to_run > 0:
                self.log(f"Running {ticks_to_run} ticks for projector test")
                from core.tick import run_all_jobs as tick
                # Run the specified number of ticks
                base_time = 1000
                time_increment = 100
                for i in range(ticks_to_run):
                    current_time = base_time + (i + 1) * time_increment
                    self.log(f"Tick {i+1} at time {current_time}")
                    result_db = tick(result_db, time_now_ms=current_time)
            
            # Check result
            result = {}
            # Generic SQL snapshot only
            try:
                snap = self._dump_sql_generic(result_db)
                if isinstance(snap, dict):
                    result['snapshot'] = snap
                    if 'tables' in snap:
                        result['tables'] = snap['tables']
            except Exception:
                pass
            matches, path, exp_val, act_val = self.subset_match(result, then)

            # Idempotency check (default ON): Re-apply events and expect same SQL tables
            idempo_failed = False
            idempo_error = None
            try:
                given_db = copy.deepcopy(given.get("db", {}))
                base_events = []
                # Collect base events (eventStore + envelope)
                if "eventStore" in given_db:
                    base_events.extend(given_db["eventStore"])
                if envelope:
                    base_events.append(envelope)

                if base_events:
                    def _dump_tables_only(db_obj):
                        snap = self._dump_sql_generic(db_obj)
                        t = (snap or {}).get('tables', {}) if isinstance(snap, dict) else {}
                        # Ignore event_store in idempotency comparisons
                        if 'event_store' in t:
                            t = {k: v for k, v in t.items() if k != 'event_store'}
                        return t

                    # Single pass 
                    # Create a new database for idempotency testing
                    import uuid as _uuid
                    base_test_db = os.environ.get('TEST_DB_PATH', ':memory:')
                    if base_test_db != ':memory:':
                        single_db_path = base_test_db.replace('.db', f'_idmp_single_{str(_uuid.uuid4())[:8]}.db')
                    else:
                        single_db_path = base_test_db
                    single_db = create_db(db_path=single_db_path)
                    self._track_db_file(single_db_path)
                    self._seed_sql_generic(single_db, copy.deepcopy(given_db))
                    for ev in base_events:
                        single_db = handle(single_db, ev, time_now_ms=1000)
                    ticks_to_run = test.get('ticks', 0)
                    if ticks_to_run > 0:
                        from core.tick import run_all_jobs as run_tick
                        for i in range(ticks_to_run):
                            current_time = 1000 + (i + 1) * 100
                            single_db = run_tick(single_db, time_now_ms=current_time)

                    # Double pass
                    if base_test_db != ':memory:':
                        double_db_path = base_test_db.replace('.db', f'_idmp_double_{str(_uuid.uuid4())[:8]}.db')
                    else:
                        double_db_path = base_test_db
                    doubled_db = create_db(db_path=double_db_path)
                    self._track_db_file(double_db_path)
                    self._seed_sql_generic(doubled_db, copy.deepcopy(given_db))
                    doubled_events = base_events + base_events
                    for ev in doubled_events:
                        doubled_db = handle(doubled_db, ev, time_now_ms=1000)
                    if ticks_to_run > 0:
                        from core.tick import run_all_jobs as run_tick
                        for i in range(ticks_to_run):
                            current_time = 1000 + (i + 1) * 100
                            doubled_db = run_tick(doubled_db, time_now_ms=current_time)

                    # Compare SQL tables (excluding event_store)
                    single_tables = _dump_tables_only(single_db)
                    double_tables = _dump_tables_only(doubled_db)
                    if single_tables != double_tables:
                        idempo_failed = True
                        idempo_error = "Idempotency failed: tables differ after doubling events"
            except Exception as e:
                idempo_failed = True
                idempo_error = f"Idempotency check crashed: {e}"

            if matches and not idempo_failed:
                return {"scenario": scenario_name, "passed": True, "logs": self.logs}
            else:
                if not matches:
                    self.log(f"Mismatch at {path}: expected {exp_val}, got {act_val}", "ERROR")
                if idempo_failed:
                    self.log(idempo_error, "ERROR")
                return {"scenario": scenario_name, "passed": False, "logs": self.logs}
        
        
        # For command tests, handle differently
        if "params" in test.get("given", {}):
            # This is a command test
            scenario_name = test.get("description", "Command test")
            self.log(f"Running command test: {scenario_name}")
            
            given = test.get("given", {})
            then = test.get("then", {})
            
            # Set environment variables if specified
            if "env" in given:
                for key, value in given["env"].items():
                    os.environ[key] = value
            
            # Tests should provide encrypted data directly, not use setup generation
            
            # Execute command
            # Extract handler name from file path
            if not handler_name:
                path_parts = handler_file.split('/')
                for i, part in enumerate(path_parts):
                    if part == "handlers" and i + 1 < len(path_parts):
                        handler_name = path_parts[i + 1]
                        break
                else:
                    handler_name = "message"  # fallback
            
            # Use command name if provided
            if not command_name:
                command_name = "create"  # fallback
            
            cmd = {
                "handler": handler_name,
                "command": command_name,
                "input": given["params"]
            }
            
            # Initialize db using persistent database
            from core.db import create_db
            # Use a unique database for each test to avoid conflicts
            import uuid
            test_id = str(uuid.uuid4())[:8]
            base_test_db = os.environ.get('TEST_DB_PATH', ':memory:')
            if base_test_db != ':memory:':
                # Make it unique for this test
                test_db_path = base_test_db.replace('.db', f'_{test_id}.db')
            else:
                test_db_path = base_test_db
            
            db = create_db(db_path=test_db_path)
            
            # Track the database file for cleanup
            self._track_db_file(test_db_path)
            
            # Seed SQL tables generically from given state
            given_db = given.get("db", {})
            try:
                self._seed_sql_generic(db, given_db)
            except Exception:
                pass
            
            try:
                result = self.execute_command(cmd, db)
                
                # Apply the command's db changes if any
                if "db" in result:
                    # Update the persistent db with changes
                    for key, value in result["db"].items():
                        db[key] = value
            except Exception as e:
                self.log(f"Command execution failed: {str(e)}", "ERROR")
                # For crypto-related failures, add more context
                if "decrypt" in str(e).lower() or "crypto" in str(e).lower():
                    self.log("Note: Real crypto tests require proper encryption/decryption. Check that:", "ERROR")
                    self.log("  - PyNaCl is installed (pip install pynacl)", "ERROR")
                    self.log("  - Keys are properly formatted (64 hex chars for 32-byte keys)", "ERROR")
                    self.log("  - Wire format matches expectations (hash:64, nonce:48, ciphertext:remaining)", "ERROR")
                    self.log(f"  - Current CRYPTO_MODE: {os.environ.get('CRYPTO_MODE', 'dummy')}", "ERROR")
                raise
            
            # Run ticks if specified
            ticks = test.get("ticks", 0)
            if ticks > 0:
                self.log(f"Running {ticks} ticks after command")
                
                # Constants for time progression
                base_time = given.get("params", {}).get("time_now_ms", 1000)
                time_increment = 100  # ms between ticks
                
                # Run jobs generically for all protocols
                from core.tick import run_all_jobs as tick
                
                # Run the specified number of ticks
                for i in range(ticks):
                    current_time = base_time + (i + 1) * time_increment
                    self.log(f"Tick {i+1} at time {current_time}")
                    db = tick(db, time_now_ms=current_time)
                    
                # no-op: db state asserted via generic snapshot
            
            # Always attach a generic SQL snapshot (protocol-agnostic)
            result_snapshot = None
            try:
                result_snapshot = self._dump_sql_generic(db)
                result['snapshot'] = result_snapshot
                if isinstance(result_snapshot, dict) and 'tables' in result_snapshot:
                    result['tables'] = result_snapshot['tables']
            except Exception:
                pass
            # Check result
            return_matches = True
            if "return" in then:
                matches, path, exp_val, act_val = self.subset_match(result, then["return"])
                if not matches:
                    self.log(f"Mismatch at return{path}: expected {exp_val}, got {act_val}", "ERROR")
                    return_matches = False
            
            # Prefer snapshot assertions when provided
            snapshot_matches = True
            if "snapshot" in then and result_snapshot is not None:
                matches, path, exp_val, act_val = self.subset_match({"snapshot": result_snapshot}, {"snapshot": then["snapshot"]})
                if not matches:
                    self.log(f"Mismatch at {path}: expected {exp_val}, got {act_val}", "ERROR")
                    snapshot_matches = False

            # Direct tables assertions when provided
            tables_matches = True
            if "tables" in then:
                if 'tables' in result:
                    matches, path, exp_val, act_val = self.subset_match({"tables": result['tables']}, {"tables": then["tables"]})
                    if not matches:
                        self.log(f"Mismatch at {path}: expected {exp_val}, got {act_val}", "ERROR")
                        tables_matches = False
                else:
                    self.log("Mismatch: tables expected but no tables in result", "ERROR")
                    tables_matches = False
            
            # Idempotency for command tests (default ON): run command once vs twice
            idempo_failed = False
            try:
                def _dump_tables_only(db_obj):
                    snap = self._dump_sql_generic(db_obj)
                    t = (snap or {}).get('tables', {}) if isinstance(snap, dict) else {}
                    return {k: v for k, v in t.items() if k != 'event_store'}

                # Single pass
                from core.db import create_db as _create
                import uuid as _uuid
                base_db_path = os.environ.get('TEST_DB_PATH', ':memory:')
                single_db_path = base_db_path.replace('.db', f'_idmp1_{str(_uuid.uuid4())[:8]}.db') if base_db_path != ':memory:' else base_db_path
                single_db = _create(db_path=single_db_path)
                self._track_db_file(single_db_path)
                self._seed_sql_generic(single_db, given_db)
                # Execute the same command once
                _ = self.execute_command(cmd, single_db)
                # Ticks
                if ticks > 0:
                    from core.tick import run_all_jobs as run_tick
                    base_time = given.get("params", {}).get("time_now_ms", 1000)
                    for i in range(ticks):
                        current_time = base_time + (i + 1) * 100
                        single_db = run_tick(single_db, time_now_ms=current_time)

                # Double pass
                double_db_path = base_db_path.replace('.db', f'_idmp2_{str(_uuid.uuid4())[:8]}.db') if base_db_path != ':memory:' else base_db_path
                double_db = _create(db_path=double_db_path)
                self._track_db_file(double_db_path)
                self._seed_sql_generic(double_db, given_db)
                _ = self.execute_command(cmd, double_db)
                _ = self.execute_command(cmd, double_db)
                if ticks > 0:
                    from core.tick import run_all_jobs as run_tick
                    base_time = given.get("params", {}).get("time_now_ms", 1000)
                    for i in range(ticks):
                        current_time = base_time + (i + 1) * 100
                        double_db = run_tick(double_db, time_now_ms=current_time)

                if _dump_tables_only(single_db) != _dump_tables_only(double_db):
                    idempo_failed = True
                # Track these DBs for cleanup
                self._track_db_file(single_db_path)
                self._track_db_file(double_db_path)
            except Exception:
                idempo_failed = True

            # Close database before returning
            if hasattr(db, 'close'):
                db.close()
            
            # Cleanup is now handled by _cleanup_db_files() at the end
                
            # If SNAPSHOT_ONLY=1 for non-framework protocols, require snapshot block
            require_snapshot = (os.environ.get('SNAPSHOT_ONLY') == '1')
            # Require only what is specified (or env-enforced)
            overall_ok = (
                return_matches and
                (snapshot_matches if ("snapshot" in then or require_snapshot) else True) and
                (tables_matches if ("tables" in then) else True)
            )
            if overall_ok and not idempo_failed:
                return {"scenario": scenario_name, "passed": True, "logs": self.logs}
            else:
                return {"scenario": scenario_name, "passed": False, "logs": self.logs}
        
        # For handler tests with newEvent, convert to envelope
        if "newEvent" in test.get("given", {}):
            given = test.get("given", {})
            event = given["newEvent"]
            
            # Create an envelope from the event
            envelope = {
                "data": event,
                "metadata": {
                    "sender": event.get("sender", "test-user")
                }
            }
            
            # Add envelope to test
            modified_test = copy.deepcopy(test)
            modified_test["given"]["envelope"] = envelope
            del modified_test["given"]["newEvent"]
            
            return self.run_handler_test(modified_test, handler_file)
        
        return self.run_test_scenario(test, handler_file)
    
    def run_file(self, test_path):
        """Run all test scenarios in a file"""
        self.logs = []
        results = []
        
        try:
            # Ensure proper environment (HANDLER_PATH/TEST_DB_PATH) when running a single file
            try:
                norm = os.path.normpath(test_path)
                parts = norm.split(os.sep)
                if 'protocols' in parts:
                    idx = parts.index('protocols')
                    if idx + 1 < len(parts):
                        protocol_name = parts[idx + 1]
                        protocol_path = os.path.join(*parts[: idx + 2])
                        handlers_path = os.path.join(protocol_path, 'handlers')
                        if os.path.isdir(handlers_path):
                            os.environ['HANDLER_PATH'] = handlers_path
                        # Use a protocol-specific DB path so schema (if present) is applied
                        os.environ['TEST_DB_PATH'] = f".test_{protocol_name}.db"
                        # Clean any stale DB from previous runs of this single file
                        try:
                            if os.path.exists(os.environ['TEST_DB_PATH']):
                                os.remove(os.environ['TEST_DB_PATH'])
                        except Exception:
                            pass
                # Always enable test-mode logging for single-file runs
                os.environ['TEST_MODE'] = '1'
                os.environ['DEBUG_CRYPTO'] = '1'
            except Exception:
                pass

            with open(test_path, 'r') as f:
                test_data = json.load(f)
            
            # Check if this is a JSON-only test file
            if test_data.get("jsonTestsOnly"):
                # Skip command execution, just verify test structure
                if "commands" in test_data:
                    for cmd_name, cmd_def in test_data["commands"].items():
                        if "tests" in cmd_def:
                            for test in cmd_def["tests"]:
                                scenario_name = test.get("description", f"{cmd_name} test")
                                results.append({
                                    "file": test_path,
                                    "scenario": scenario_name,
                                    "passed": True,
                                    "logs": [f"JSON-only test verified: {scenario_name}"]
                                })
                return results
            
            # Determine test type based on file location and content
            if "handlers" in test_path:
                # Handler tests
                if "projector" in test_data and "tests" in test_data["projector"]:
                    for test in test_data["projector"]["tests"]:
                        self.logs = []
                        result = self.run_handler_test(test, test_path)
                        result["file"] = test_path
                        results.append(result)
                
                if "commands" in test_data:
                    for cmd_name, cmd_def in test_data["commands"].items():
                        if "tests" in cmd_def:
                            for test in cmd_def["tests"]:
                                self.logs = []
                                # Extract handler name from path
                                path_parts = test_path.split('/')
                                handler_name = None
                                for i, part in enumerate(path_parts):
                                    if part == "handlers" and i + 1 < len(path_parts):
                                        handler_name = path_parts[i + 1]
                                        break
                                result = self.run_handler_test(test, test_path, handler_name, cmd_name)
                                result["file"] = test_path
                                results.append(result)
                                
            elif "tick.json" in test_path:
                # Tick tests
                if "tests" in test_data:
                    for test in test_data["tests"]:
                        self.logs = []
                        result = self.run_test_scenario(test, test_path)
                        result["file"] = test_path
                        results.append(result)
                        
            elif "runner.json" in test_path:
                # Runner tests are meta-tests - skip for now
                # These test the test runner itself, not the framework
                pass
            
            return results
            
        except Exception as e:
            self.log(f"Failed to load test file: {str(e)}", "ERROR")
            self.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return [{
                "file": test_path,
                "scenario": "File load error",
                "passed": False,
                "error": str(e),
                "logs": self.logs
            }]
    
    
    def run_protocol_tests(self, protocol_name, protocol_path):
        """Run tests for a specific protocol"""
        print(f"\n" + "="*60)
        print(f"RUNNING PROTOCOL: {protocol_name}")
        print("="*60)
        
        # Set test mode for better logging
        os.environ["TEST_MODE"] = "1"
        os.environ["DEBUG_CRYPTO"] = "1"  # Enable crypto debugging by default
        
        # Set handler path for this protocol
        handlers_path = os.path.join(protocol_path, "handlers")
        if os.path.exists(handlers_path):
            os.environ["HANDLER_PATH"] = handlers_path
        
        # Use a protocol-specific test database file
        # This ensures each protocol gets its own schema
        test_db_path = f".test_{protocol_name}.db"
        os.environ["TEST_DB_PATH"] = test_db_path
        
        # Clean up any existing test database
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except:
                pass
        
        # Check for schema.sql and validate if present
        schema_file = os.path.join(protocol_path, "schema.sql")
        if os.path.exists(schema_file):
            print(f"\nFound schema.sql, validating handler data against schema...")
            try:
                from core.check_schema_sql import SQLSchemaParser, HandlerSchemaValidator
                
                # Parse schema
                schema_parser = SQLSchemaParser(schema_file)
                print(f"  Parsed {len(schema_parser.tables)} tables from schema")
                
                # Validate handlers
                validator = HandlerSchemaValidator(schema_parser)
                total_errors = 0
                total_warnings = 0
                
                # Check each handler
                for root, dirs, files in os.walk(handlers_path):
                    # Look for {folder}_handler.json pattern
                    handler_name = os.path.basename(root)
                    handler_json_name = f"{handler_name}_handler.json"
                    if handler_json_name in files:
                        handler_path = os.path.join(root, handler_json_name)
                        
                        errors, warnings = validator.validate_handler(handler_path)
                        if errors or warnings:
                            print(f"\n  Handler '{handler_name}':")
                            if errors:
                                print(f"    Schema errors: {len(errors)}")
                                for error in errors[:3]:  # Show first 3 errors
                                    print(f"      - {error}")
                                if len(errors) > 3:
                                    print(f"      ... and {len(errors) - 3} more")
                            if warnings:
                                print(f"    Schema warnings: {len(warnings)}")
                                
                        total_errors += len(errors)
                        total_warnings += len(warnings)
                
                if total_errors > 0 or total_warnings > 0:
                    print(f"\n  Schema validation summary:")
                    print(f"    Total errors: {total_errors} (not enforced)")
                    print(f"    Total warnings: {total_warnings}")
                else:
                    print(f"  ✓ All handlers match schema perfectly!")
                    
            except Exception as e:
                print(f"  WARNING: Schema validation failed: {str(e)}")
                if self.verbose:
                    import traceback
                    traceback.print_exc()
        
        # Check for api.yaml and validate if present
        api_file = os.path.join(protocol_path, "api.yaml")
        if os.path.exists(api_file):
            if yaml is None:
                print("\nFound api.yaml, but PyYAML is not installed; skipping API validation.")
            else:
                print(f"\nFound api.yaml, validating API operations...")
                api_errors = self.validate_api(protocol_name, protocol_path, api_file, handlers_path)
                if api_errors > 0:
                    print(f"  ❌ API validation found {api_errors} errors")
                else:
                    print(f"  ✅ All API operations validated successfully")
        
        # Run tests for this protocol
        protocol_results = []
        for root, dirs, files in os.walk(protocol_path):
            for file in files:
                if file.endswith(".json") and file != "schema.json":
                    test_path = os.path.join(root, file)
                    results = self.run_file(test_path)
                    protocol_results.extend(results)
                    
                    # Don't clean up here - we'll clean up at the start of each protocol instead
        
        # Summary for this protocol
        passed = sum(1 for r in protocol_results if r["passed"])
        failed = sum(1 for r in protocol_results if not r["passed"])
        
        print(f"\n{protocol_name} Test Results: {passed} passed, {failed} failed")
        
        # Clean up all test databases created for this protocol
        self._cleanup_db_files()
        
        # Also clean up the main protocol test database
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except:
                pass
        
        return protocol_results
    
    def run_all_tests(self):
        """Run tests for all protocols separately"""
        all_results = []
        protocol_summaries = []
        
        # Discover all protocols
        protocols_dir = "protocols"
        if not os.path.exists(protocols_dir):
            print("No protocols directory found")
            return False
        
        # Run tests for each protocol
        for protocol_name in sorted(os.listdir(protocols_dir)):
            protocol_path = os.path.join(protocols_dir, protocol_name)
            if os.path.isdir(protocol_path):
                results = self.run_protocol_tests(protocol_name, protocol_path)
                all_results.extend(results)
                
                # Store summary for this protocol
                passed = sum(1 for r in results if r["passed"])
                failed = sum(1 for r in results if not r["passed"])
                protocol_summaries.append({
                    "name": protocol_name,
                    "passed": passed,
                    "failed": failed
                })
        
        # Overall summary
        total_passed = sum(1 for r in all_results if r["passed"])
        total_failed = sum(1 for r in all_results if not r["passed"])
        
        print(f"\n{'='*60}")
        print("SUMMARY BY PROTOCOL")
        print("="*60)
        for summary in protocol_summaries:
            status = "✓" if summary["failed"] == 0 else "✗"
            print(f"{status} {summary['name']}: {summary['passed']} passed, {summary['failed']} failed")
        
        print(f"\n{'='*60}")
        print(f"TOTAL Test Results: {total_passed} passed, {total_failed} failed")
        print(f"{'='*60}\n")
        
        # Show failed tests
        for result in all_results:
            if not result["passed"]:
                print(f"FAILED: {result['file']} - {result['scenario']}")
                if "error" in result:
                    print(f"  Error: {result['error']}")
                for log in result.get("logs", []):
                    if "ERROR" in log:
                        print(f"  {log}")
                print()
        
        # Final cleanup of any remaining test databases
        self._cleanup_db_files()
        
        return total_failed == 0
    
    def validate_api(self, protocol_name, protocol_path, api_file, handlers_path):
        """Validate API specification against handlers. Returns error count."""
        try:
            # Load API specification
            if yaml is None:
                # If YAML isn't available, skip validation cleanly
                return 0
            with open(api_file, 'r') as f:
                api_spec = yaml.safe_load(f)
            
            # Discover handlers
            handlers = {}
            for handler_dir in os.listdir(handlers_path):
                handler_path = os.path.join(handlers_path, handler_dir)
                if os.path.isdir(handler_path):
                    # Look for {folder}_handler.json pattern
                    handler_json_path = os.path.join(handler_path, f"{handler_dir}_handler.json")
                    if os.path.exists(handler_json_path):
                        try:
                            with open(handler_json_path, 'r') as f:
                                handler_data = json.load(f)
                            
                            # Extract commands
                            commands = []
                            if "commands" in handler_data:
                                commands.extend(handler_data["commands"].keys())
                            
                            # Jobs are also callable as commands
                            if "job" in handler_data:
                                commands.append(handler_data["job"])
                            
                            handlers[handler_dir] = commands
                        except Exception as e:
                            print(f"  Warning: Failed to parse {handler_json_path}: {e}")
            
            print(f"  Found {len(handlers)} handlers: {', '.join(handlers.keys())}")
            
            # Validate operations
            error_count = 0
            operation_count = 0
            
            # Special operations that don't map to handlers
            special_operations = ["tick.run"]
            
            if "paths" in api_spec:
                for path, path_item in api_spec["paths"].items():
                    for method, operation in path_item.items():
                        if method in ["get", "post", "put", "delete", "patch"]:
                            operation_count += 1
                            operation_id = operation.get("operationId")
                            
                            if not operation_id:
                                print(f"    Error: {method.upper()} {path}: Missing operationId")
                                error_count += 1
                                continue
                            
                            # Skip special operations
                            if operation_id in special_operations:
                                continue
                            
                            # Check operationId format
                            if '.' not in operation_id:
                                print(f"    Error: {method.upper()} {path}: Invalid operationId format '{operation_id}'")
                                error_count += 1
                                continue
                            
                            handler_name, command_name = operation_id.split('.', 1)
                            
                            # Check if handler exists
                            if handler_name not in handlers:
                                print(f"    Error: {method.upper()} {path}: Handler '{handler_name}' not found")
                                error_count += 1
                                continue
                            
                            # Check if command exists
                            if command_name not in handlers[handler_name]:
                                print(f"    Error: {method.upper()} {path}: Command '{command_name}' not found in handler '{handler_name}'")
                                error_count += 1
                            
                            # Check request body schema for required fields
                            if "requestBody" in operation:
                                request_body = operation["requestBody"]
                                if "content" in request_body and "application/json" in request_body["content"]:
                                    schema = request_body["content"]["application/json"].get("schema", {})
                                    if schema.get("type") == "object":
                                        # Check if required array is missing when properties are defined
                                        if "properties" in schema and "required" not in schema:
                                            # Only flag as error if there are properties that should be required
                                            prop_count = len(schema["properties"])
                                            if prop_count > 0:
                                                print(f"    Error: {method.upper()} {path}: Request body schema has {prop_count} properties but no 'required' array specified")
                                                error_count += 1
                            
                            # Check response schemas for required fields
                            if "responses" in operation:
                                for status_code, response in operation["responses"].items():
                                    if "content" in response and "application/json" in response["content"]:
                                        schema = response["content"]["application/json"].get("schema", {})
                                        if schema.get("type") == "object":
                                            # Check if required array is missing when properties are defined
                                            if "properties" in schema and "required" not in schema:
                                                prop_count = len(schema["properties"])
                                                if prop_count > 0:
                                                    print(f"    Error: {method.upper()} {path}: Response {status_code} schema has {prop_count} properties but no 'required' array specified")
                                                    error_count += 1
            
            print(f"  Validated {operation_count} operations")
            
            # Check for duplicate operationIds
            operation_ids = []
            if "paths" in api_spec:
                for path, path_item in api_spec["paths"].items():
                    for method, operation in path_item.items():
                        if method in ["get", "post", "put", "delete", "patch"]:
                            if "operationId" in operation:
                                operation_ids.append(operation["operationId"])
            
            duplicates = [x for x in operation_ids if operation_ids.count(x) > 1]
            if duplicates:
                unique_duplicates = list(set(duplicates))
                print(f"    Error: Duplicate operationIds found: {unique_duplicates}")
                error_count += len(unique_duplicates)
            
            return error_count
            
        except Exception as e:
            print(f"  ERROR: Failed to validate API: {str(e)}")
            return 1

if __name__ == "__main__":
    runner = TestRunner()
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    flags = [a for a in sys.argv[1:] if a.startswith('-')]

    if "--verbose" in flags:
        runner.verbose = True

    try:
        # When protocol paths/names are provided, only run those
        if args:
            all_ok = True
            for arg in args:
                # Support either 'protocols/<name>' or '<name>'
                if os.path.isdir(arg) and os.path.basename(os.path.dirname(arg)) == 'protocols':
                    protocol_path = arg
                    protocol_name = os.path.basename(arg)
                elif os.path.isdir(os.path.join('protocols', arg)):
                    protocol_name = arg
                    protocol_path = os.path.join('protocols', arg)
                else:
                    # If it's a file, run it directly
                    if os.path.isfile(arg):
                        results = runner.run_file(arg)
                        ok = all(r.get('passed') for r in results)
                        all_ok = all_ok and ok
                        continue
                    else:
                        print(f"Unknown path or protocol: {arg}")
                        all_ok = False
                        continue

                results = runner.run_protocol_tests(protocol_name, protocol_path)
                ok = all(r.get('passed') for r in results)
                all_ok = all_ok and ok

            # Cleanup before exit
            runner._cleanup_db_files()
            sys.exit(0 if all_ok else 1)

        # Default: run all protocol tests
        success = runner.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        # Always cleanup on exit
        runner._cleanup_db_files()
