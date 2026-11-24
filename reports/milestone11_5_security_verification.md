# Milestone 11.5 — Security, Credential Isolation & Portal Rotation Verification

**Governing specification:** PRD v3.0  
**Current primary database:** DLM1 (`/tmp/delhi_dlm1.db`)  
**Current system status:** `DEGRADE`  
**Previous milestone:** M11.4 — `QUALITY_AUDIT_PASSED_WITH_LIMITATIONS`  
**Evaluation date:** 2026-11-21  

---

## 1. Executive Summary

Following the detection and redaction in Milestone 11.4 of a literal API key in documentation (`reports/milestone11_3_post_cutover_validation.md`), this audit conducted an exhaustive repository-wide verification of credential isolation, version-control protection, and the official portal rotation procedure.

### Primary Audit Findings
1. **Repository Hygiene:** Exactly **0 credential leaks** exist across all documentation, source code, test files, runtime logs, frontend production bundles, and git-tracked files.
2. **Environment File Protection:** `.env` and `backend/.env` are strictly excluded under `.gitignore` (lines 36–40).
3. **Template Hygiene:** `.env.example` contains exclusively non-sensitive placeholder strings (`DELHI_TRANSPORTSTACK_API_KEY=your_delhi_transportstack_api_key_here`).
4. **Portal Rotation Status:** The key currently configured in `.env` is fully functional and authenticated (evidenced by HTTP 200 responses across all three 5-minute temporal snapshots). Because rotating the developer key requires interactive authentication on the external web portal (`https://delhi.transportstack.in`), this action requires direct operator action. Detailed step-by-step rotation instructions are provided below.

---

## 2. Exhaustive Secret Surface Audit

### Table 1: Security Inspection Scope & Leak Detection Results

| Target Surface | Files / Scope Scanned | Leak Check Methodology | Result | Status |
|:---|:---|:---|:---:|:---:|
| **Git Tracked Files** | All version-controlled files | Secret pattern search across index | 0 matches | **SECURE** |
| **Documentation & Reports** | `reports/*.md` | Recursive string matching | 0 matches | **SECURE** |
| **Backend Source & Config** | `backend/app/**`, `backend/core/**` | String search across Python files | 0 matches | **SECURE** |
| **Backend Test Suite** | `backend/tests/**` | Fixture and test body inspection | 0 matches | **SECURE** |
| **Frontend Source & Bundles** | `frontend/src/**`, `frontend/dist/**` | Client-side bundle inspection | 0 matches | **SECURE** |
| **Automation & Scripts** | `scripts/*.py` | Script parameter inspection | 0 matches | **SECURE** |
| **Process Daemon Logs** | Background Uvicorn logs | Log file content search | 0 matches | **SECURE** |
| **API Endpoints** | `/api/v1/health`, `/api/v1/live/status` | Live response payload inspection | 0 matches | **SECURE** |
| **Environment Exclusion** | `.gitignore` | Verifying lines 36–40 | Verified active | **SECURE** |

---

## 3. Operator Instructions for Official Portal Key Rotation

Because rotating API credentials on the Delhi Transport Stack requires authenticated operator access to the web dashboard, the operator must complete the rotation on the portal using the following exact procedure:

### Step-by-Step Operator Rotation Procedure
1. **Access Portal:** Navigate to the official Delhi Transport Stack developer portal:
   [https://delhi.transportstack.in](https://delhi.transportstack.in)
2. **Authenticate:** Log into your developer account using your registered credentials.
3. **Generate Replacement Key:**
   - In the API Management dashboard, navigate to **API Keys**.
   - Click **Generate New Key** (or **Rotate Key**).
   - Copy the newly issued API key to a secure password manager.
4. **Update Local Configuration:**
   - Open `.env` and `backend/.env` in your local workspace.
   - Replace the value of `DELHI_TRANSPORTSTACK_API_KEY`:
     ```bash
     DELHI_TRANSPORTSTACK_API_KEY=<insert_new_key_here>
     ```
   - Ensure no extra spaces or quotation marks are added.
5. **Revoke Previous Key:**
   - Return to the portal dashboard.
   - Locate the previous API key that was previously exposed in local documentation.
   - Click **Revoke** / **Delete** to permanently invalidate the old token.
6. **Restart Backend Daemons:**
   - Restart the backend daemon to reload environment variables:
     ```bash
     pkill -f "uvicorn backend.app.main:app"
     DB_PATH=/tmp/delhi_dlm1.db uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
     ```
7. **Verify New Key Functionality:**
   - Run the validation test:
     ```bash
     pytest backend/tests/test_milestone10_gtfs_rt.py::test_m10_live_feed_real_key_if_configured -v
     ```

---

## 4. Security Verification Verdict

| Criterion | Requirement | Result |
|:---|:---:|:---:|
| Credentials in version-controlled / tracked files | Strictly 0 | **0 (PASSED)** |
| Credentials in API response bodies | Strictly 0 | **0 (PASSED)** |
| Credentials in process stdout / stderr logs | Strictly 0 | **0 (PASSED)** |
| Credentials in client-side frontend code | Strictly 0 | **0 (PASSED)** |
| Active unredacted leaks in workspace | Strictly 0 | **0 (PASSED)** |
| Portal key rotation procedure provided | Exact steps documented | **COMPLETED** |

