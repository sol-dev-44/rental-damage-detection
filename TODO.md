# DockGuard MVP Checklist

**Goal:** MVP up and running by end of weekend (March 22, 2026)

---

## SHORT TERM — "Make it work" (Wed-Thu)

### 1. Bootstrap & Auth (Do First)
- [ ] Create seed script to bootstrap first tenant + admin user in Supabase
- [ ] Build Login page component (`frontend/src/pages/LoginPage.tsx`)
- [ ] Add auth guards / ProtectedRoute wrapper to App.tsx
- [ ] Wire up `useAuthStore` (Zustand) — it exists but isn't connected to routing
- [ ] Add logout endpoint (`POST /auth/logout`) — frontend expects it, backend doesn't have it
- [ ] Handle 401 responses in API client → redirect to login

### 2. Fix Backend-Frontend Mismatches (Critical)
- [ ] Fix API endpoint paths in `frontend/src/lib/api.ts`:
  - Photos delete: frontend uses `/inspections/{id}/photos/{id}`, backend is `/photos/{id}`
  - Feedback: frontend uses `POST /feedback`, backend is `POST /findings/{id}/feedback`
  - Detection: frontend uses `/detection/analyze`, backend is `/inspections/{id}/detect`
- [ ] Reconcile data schema mismatches:
  - Asset: frontend expects `registration_number`, `manufacturer`, `model`, `year` — backend has `identifier`, `metadata_`, `asset_type`
  - Inspection: frontend expects `session_id`, `inspector_name` — backend has `rental_session_id`, `inspector_id`
  - RentalSession: frontend expects `customer_name/email/phone`, `checkout_time` — backend has `renter_name`, `renter_contact`, `started_at`
- [ ] Add missing `GET /inspections` list endpoint (backend has create/get/update but no list)

### 3. Wire Up the AI Pipeline
- [ ] Connect detection worker to actual Claude vision API (currently a placeholder in `inspections.py` `_run_detection()`)
- [ ] Implement detection status tracking (frontend polls `/detection/status/{jobId}` but no endpoint exists)
- [ ] Test end-to-end: upload photos → trigger detection → get findings

### 4. Photo Upload (R2 Storage)
- [ ] Set up Cloudflare R2 bucket + API credentials
- [ ] Add R2 credentials to `.env`
- [ ] Wire up `storage_service.upload_photo()` in photo upload route (currently commented out as TODO)
- [ ] Verify photo download works in detection pipeline

---

## MID TERM — "Make it real" (Fri-Sun → MVP by Sunday)

### 5. Complete the Core Pages
- [ ] FleetOverview (dashboard) — currently placeholder, wire to real asset/inspection data
- [ ] DamageHistory — wire to real findings data with filters
- [ ] RentalSessions page — wire to real session data
- [ ] AccuracyDashboard — wire to real metrics endpoints
- [ ] InspectionFlow — fix hardcoded "Current User" (line 81), use auth store

### 6. End-to-End User Flow
- [ ] User logs in → sees dashboard with fleet overview
- [ ] User creates an asset (jet ski / boat) with details
- [ ] User starts a rental session (customer info, asset selection)
- [ ] User creates pre-rental inspection → takes/uploads photos
- [ ] Customer returns equipment
- [ ] User creates post-rental inspection → takes/uploads photos
- [ ] User triggers AI detection → Claude compares before/after
- [ ] User reviews AI findings (approve/reject/modify)
- [ ] User feedback stored for few-shot learning improvement

### 7. Polish & Edge Cases
- [ ] Error states — show meaningful messages when API calls fail
- [ ] Loading states — spinners/skeletons while data loads
- [ ] Empty states — "No assets yet" / "No inspections" messaging
- [ ] Mobile responsiveness — rental operators will use tablets/phones on the dock
- [ ] Photo capture from device camera (not just file upload)

### 8. Deployment Prep
- [ ] Create backend Dockerfile
- [ ] Create frontend Dockerfile
- [ ] Verify docker-compose works end-to-end
- [ ] Set up production environment variables
- [ ] CORS: restrict `allow_origins` from wildcard `*` to actual frontend domain

---

## KNOWN BUGS TO FIX

- [ ] `pyproject.toml` had wrong build-backend (`hatchling.backends` → `hatchling.build`) — FIXED
- [ ] `pyproject.toml` missing `email-validator` dep — FIXED (added `pydantic[email]`)
- [ ] `config.py` env_file path was `.env` but file lives at project root — FIXED (`../.env`)
- [ ] CORS set to `allow_credentials=True` with `allow_origins=["*"]` — not valid per spec, needs fixing for production
- [ ] Frontend test setup exists (`test-setup.ts`) but no actual test files

---

## NOT FOR MVP (Backlog)

- [ ] Public tenant registration (self-serve signup for new rental businesses)
- [ ] Password reset flow
- [ ] User management UI (admin invites operators)
- [ ] Repair cost lookup management UI
- [ ] Email notifications (damage detected, inspection complete)
- [ ] Reporting / export (PDF damage reports for insurance)
- [ ] Offline mode (service worker for dock environments with spotty wifi)
- [ ] Multi-photo comparison (more than 2 photos per inspection)
- [ ] CI/CD pipeline fixes (frontend tests, Docker build steps)
- [ ] Monitoring / error tracking (Sentry or similar)
