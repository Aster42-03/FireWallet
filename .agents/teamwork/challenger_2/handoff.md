# Handoff Report (challenger_2)

## 1. Observation
- **Test File**: `tests/api/test_adversarial_empirical_challenger.py`
- **Execution Command**: `backend/.venv/bin/pytest tests/api/test_adversarial_empirical_challenger.py -v`
- **Verbatim Failure**:
  ```
  FAILED tests/api/test_adversarial_empirical_challenger.py::test_adversarial_batch_payout_with_mock_token_returns_503
  AssertionError: CRITICAL VULNERABILITY: Batch payout executed under mock token conditions! Expected HTTP 503, got 200: {"status":"completed","executed_count":1,"failed_count":0,"total_amount_minor":120000,"results":[{"item_id":"2f44cee0-5b21-4e2d-be6e-92b92dd9c1e6","title":"Apartment Rent","status":"paid","paypal_payout_id":"PAYOUT-MOCK-batch_2f","error_message":null}],"remaining_isolated_balance_minor":0,"message":"Batch payout of 1 item(s) ($1,200.00) completed via PayPal Sandbox."}
  assert 200 == 503
  ```
- **Code Observation**:
  In `backend/app/api/v1/bills.py` lines 314-329:
  ```python
  # 5. Live PayPal Sandbox Requirement
  is_live = False
  if hasattr(paypal_client, "has_live_credentials"):
      try:
          res_live = paypal_client.has_live_credentials()
          if asyncio.iscoroutine(res_live):
              is_live = await res_live
          else:
              is_live = bool(res_live)
      except Exception:
          is_live = False

  if not is_live:
      raise HTTPException(
          status_code=503,
          detail="Live PayPal Sandbox connection required for batch payout execution. Network offline or credentials unconfigured."
      )
  ```
  `bills.py` only invokes `paypal_client.has_live_credentials()`, which checks if `client_id` is set. It never verifies `await paypal_client.get_access_token() != "mock_sandbox_access_token"`.

## 2. Logic Chain
1. `PROJECT.md` line 82 defines the contract: `"- Live PayPal Sandbox Requirement: token != 'mock_sandbox_access_token' verified; if mock, return 503 Service Unavailable."`
2. `ORIGINAL_REQUEST.md` line 20 states: `"Require live PayPal Sandbox credentials for batch payout execution and fail cleanly if offline or credentials are missing."`
3. `DISPATCH.md` line 12 instructs: `"- Live PayPal Sandbox guard: execute batch payouts under mock token conditions and confirm HTTP 503 is returned cleanly with zero payments made."`
4. In `backend/app/services/paypal_client.py` lines 124-129, when network connectivity to PayPal fails in sandbox environment, `get_access_token()` sets `self._access_token = "mock_sandbox_access_token"`.
5. In `backend/app/api/v1/bills.py` lines 314-329, `execute_batch` only checks `has_live_credentials()`. If credentials are configured in `.env`, `has_live_credentials()` returns `True` even when the access token is `"mock_sandbox_access_token"`.
6. `execute_batch` then proceeds to step 7 and calls `paypal_client.create_payout(...)`.
7. `create_payout(...)` checks `token == "mock_sandbox_access_token"` and returns a simulated success response (`PAYOUT-MOCK-...`).
8. `execute_batch` marks the batch payment item as `status = "paid"`, writes a debit entry to `LedgerEntry` (`amount = -abs(item.amount_minor)`), and returns HTTP 200 OK.
9. Therefore, batch payouts execute under mock token conditions instead of failing cleanly with HTTP 503, and real ledger reserves are deducted for unmade payouts.

## 3. Caveats
- `tests/integration/test_testcontainers_postgres.py` was skipped during pytest execution because local Docker daemon was not active. This is expected and standard for in-memory SQLite development verification.
- All other 3 challenge domains (Quick Intent canonical classification, Bills allocation zero-sum boundaries, and Emergency friction vs partner approval) passed 100% of adversarial tests without any defects.

## 4. Conclusion
**Verdict**: **`REQUEST_CHANGES`**  
The batch dispatcher implementation violates the Live PayPal Sandbox requirement by allowing mock access tokens to execute simulated payouts and debit ledger funds instead of rejecting with HTTP 503.

**Required Fix**:
In `backend/app/api/v1/bills.py` step 5, verify that `await paypal_client.get_access_token() != "mock_sandbox_access_token"`:
```python
    if is_live:
        try:
            token = await paypal_client.get_access_token()
            if not token or token == "mock_sandbox_access_token":
                is_live = False
        except Exception:
            is_live = False
```

## 5. Verification Method
Run:
```bash
backend/.venv/bin/pytest tests/api/test_adversarial_empirical_challenger.py -k "test_adversarial_batch_payout_with_mock_token_returns_503" -v
```
- Invalidation Condition: The test expects HTTP 503; currently it fails with assertion error receiving HTTP 200. Once the token guard is added, this test will pass.
