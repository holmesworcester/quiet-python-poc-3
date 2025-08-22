# Framework Tests Protocol

This protocol contains the test suite for the core framework functionality. It validates the behavior of the framework components including:

- **Core Components**: tick, greedy_decrypt, handle, and test_runner
- **Handlers**: message, missing_key, and unknown event handlers
- **Cryptographic Functions**: sign/verify, encrypt/decrypt, hash, seal/unseal, KDF

## Structure

- `runner.json` - Tests for the test runner itself
- `tick.json` - Tests for the main event loop
- `handlers/` - Tests for each handler type:
  - `message/` - Message handling and creation
  - `test_crypto/` - Cryptographic function tests

## Running Tests

The test runner automatically discovers and runs all tests in this protocol when executed.

## Test Format

Tests are written in JSON format with:
- `given`: Initial state/input
- `then`: Expected output/state
- `description`: Human-readable test description

Tests validate both successful operations and error cases to ensure robust framework behavior.