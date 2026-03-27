# FinSight

FinSight is a production-grade, self-healing personal finance intelligence system built for the Indian digital transaction ecosystem. It runs as a persistent Android-level service — capturing financial signals simultaneously from SMS messages and UPI app push notifications — deduplicating them at the device level through a cryptographic fingerprinting protocol before any data ever leaves the phone, classifying and extracting structured transactions through a hybrid ML pipeline, and continuously improving itself through a reinforcement learning loop driven entirely by real user behaviour. The AI insights layer is powered exclusively by **Groq Llama 3.3 70B**. No other third-party API is used.

The system operates at Truecaller-equivalent Android process priority, survives application closure and device reboots, and resolves all three fundamental sync scenarios — first install, re-install with existing data, and real-time new signal arrival — through a deterministic state machine that guarantees zero duplicate transactions across every condition.

---

## Table of Contents

1. [The Problem Space](#the-problem-space)
2. [System Design Philosophy](#system-design-philosophy)
3. [Full System Architecture](#full-system-architecture)
4. [Layer 1 — Android Data Acquisition Layer](#layer-1--android-data-acquisition-layer)
5. [Layer 2 — On-Device Intelligence Layer](#layer-2--on-device-intelligence-layer)
6. [Layer 3 — SyncOrchestrator — The Three Conditions](#layer-3--syncorchestrator--the-three-conditions)
   - [SyncCheckpoint — The Source of Truth](#synccheckpoint--the-source-of-truth)
   - [Condition 1: First Install, Empty Database](#condition-1-first-install-empty-database)
   - [Condition 2: Re-install, Database Has Data](#condition-2-re-install-database-has-data)
   - [Condition 3: New Real-Time Signal Arrives](#condition-3-new-real-time-signal-arrives)
   - [Sync State Machine](#sync-state-machine)
   - [Collision Resolution Matrix](#collision-resolution-matrix)
7. [Layer 4 — Encrypted Transport Layer](#layer-4--encrypted-transport-layer)
8. [Layer 5 — Backend Processing Pipeline](#layer-5--backend-processing-pipeline)
9. [Layer 6 — Backend Deduplication Gate](#layer-6--backend-deduplication-gate)
10. [Layer 7 — Subscription Intelligence Engine](#layer-7--subscription-intelligence-engine)
11. [Layer 8 — Reinforcement Learning System](#layer-8--reinforcement-learning-system)
12. [Layer 9 — AI Insights Layer (Groq)](#layer-9--ai-insights-layer-groq)
13. [Layer 10 — Storage Architecture](#layer-10--storage-architecture)
14. [Flutter Application Layer](#flutter-application-layer)
15. [Machine Learning Methodology](#machine-learning-methodology)
16. [Production Deployment Architecture](#production-deployment-architecture)
17. [Project Structure](#project-structure)
18. [Running the Project](#running-the-project)
19. [Research Contribution Summary](#research-contribution-summary)

---

## The Problem Space

Modern Indian digital finance produces transactional signals through two independent channels simultaneously:

**Channel A — SMS**: Banks send structured SMS alerts for every UPI credit, debit, NEFT, IMPS, and card transaction. These arrive reliably for bank-issued confirmations but may be delayed by network conditions, suppressed by DND settings, or never arrive for certain UPI flows.

**Channel B — UPI App Notifications**: Apps like PhonePe, Google Pay, Paytm, BHIM, Amazon Pay, Cred, Fi, and Jupiter send rich push notifications at the exact moment of transaction — often before the bank SMS arrives, and sometimes when the SMS never arrives at all.

Beyond the dual-channel problem, any persistent personal finance system must correctly handle three lifecycle scenarios:

- A user installs the app for the first time. Their phone has years of historical financial SMS. None of it is in the database yet.
- A user re-installs the app or logs in on a new device. The database already contains their complete history. Their device has all that same SMS plus some new ones. Syncing naively creates thousands of duplicate transactions.
- The system is running normally and a new SMS or notification arrives. It must be processed without conflicting with any previously stored record.

FinSight solves all three through a deterministic SyncOrchestrator that governs exactly what gets synced, when, and how.

---

## System Design Philosophy

**The sync layer is not an afterthought.** Most personal finance apps treat sync as a simple batch upload. FinSight treats sync as a stateful, resumable, conflict-aware protocol with three distinct operating modes and a persistent checkpoint that survives app kills, device reboots, and network failures.

**Fingerprint before transmit.** No transaction data is sent to the backend until a cryptographic fingerprint has been computed and checked against both the local ledger and the backend deduplication gate. Duplicates are eliminated on the device, not by the database.

**Idempotent by design.** Every sync operation is fully idempotent. Running the same sync twice produces the same database state as running it once. This is guaranteed at three independent layers: local SQLite fingerprint ledger, Redis Bloom Filter on the backend, and PostgreSQL unique constraint on the fingerprint column.

**No third-party API lock-in except Groq.** All ML models run in-house. All storage is owned infrastructure. All SMS and notification processing is on-device. Groq is the single external dependency, used only where a 70B-scale model is genuinely needed.

**Persistent by design.** The system starts on boot, runs as a foreground service, survives application closure, and resumes all in-progress sync operations after interruption — exactly from the last committed checkpoint.

---

## Full System Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                      ANDROID DEVICE (Physical Hardware)                     ║
║                                                                              ║
║  ┌───────────────────────┐   ┌────────────────────────────────────────────┐ ║
║  │  SmsBroadcastReceiver │   │     FinSightNotificationListener           │ ║
║  │  android.provider     │   │     android.service.notification           │ ║
║  │  .telephony.SMS_RCV   │   │     PhonePe, GPay, Paytm, BHIM,           │ ║
║  │  (static, boot-safe)  │   │     Cred, Fi, Jupiter, Amazon Pay          │ ║
║  └──────────┬────────────┘   └───────────────────────┬────────────────────┘ ║
║             │  raw SMS PDU                           │  notification bundle  ║
║             └─────────────────┬─────────────────────┘                       ║
║                               ▼                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │               FinSightForegroundService  (START_STICKY)                │ ║
║  │                                                                        │ ║
║  │  ┌────────────────────┐   ┌──────────────────────────────────────────┐ │ ║
║  │  │  SignalQueue        │   │         SyncOrchestrator                 │ │ ║
║  │  │  LinkedBlocking     │──▶│  Mode: BACKFILL | CATCHUP | REALTIME    │ │ ║
║  │  │  Queue (cap=500)   │   │  ┌────────────────────────────────────┐  │ │ ║
║  │  └────────────────────┘   │  │  SyncCheckpoint (local + remote)   │  │ │ ║
║  │                           │  └────────────────────────────────────┘  │ │ ║
║  │                           └──────────────────┬───────────────────────┘ │ ║
║  │                                              │                          │ ║
║  │  ┌───────────────────────────────────────────▼───────────────────────┐ │ ║
║  │  │              On-Device Intelligence Pipeline                       │ │ ║
║  │  │  ┌─────────────────────┐  ┌──────────────────────────────────┐   │ │ ║
║  │  │  │ FingerprintEngine   │  │  CrossSourceDeduplicator         │   │ │ ║
║  │  │  │ SHA-256 canonical   │  │  15-min merge window             │   │ │ ║
║  │  │  └─────────────────────┘  └──────────────────────────────────┘   │ │ ║
║  │  │  ┌─────────────────────┐  ┌──────────────────────────────────┐   │ │ ║
║  │  │  │ TFLite Classifier   │  │  LocalSQLiteBuffer (WAL + AES)   │   │ │ ║
║  │  │  │ 48-feature INT8     │  │  Fingerprint ledger + sync queue │   │ │ ║
║  │  │  └─────────────────────┘  └──────────────────────────────────┘   │ │ ║
║  │  └───────────────────────────────────────────────────────────────────┘ │ ║
║  └──────────────────────────────────────────┬─────────────────────────────┘ ║
║                                             │  AES-256-GCM + TLS 1.3        ║
╚═════════════════════════════════════════════╪═════════════════════════════════╝
                                              │
                               ┌──────────────▼──────────────┐
                               │      Transport Layer          │
                               │  Retry · Backoff · Compress  │
                               └──────────────┬──────────────┘
                                              │
╔═════════════════════════════════════════════╪═════════════════════════════════╗
║                        FASTAPI BACKEND                                       ║
║                                             │                                ║
║  ┌──────────────────────────────────────────▼─────────────────────────────┐  ║
║  │                    Backend Deduplication Gate                            │  ║
║  │     Redis Bloom Filter (per-user) → PostgreSQL UNIQUE(fingerprint)       │  ║
║  └──────────────────────────────────────────┬──────────────────────────────┘  ║
║                                             │                                ║
║  ┌──────────────────────────────────────────▼─────────────────────────────┐  ║
║  │                    Hybrid ML Pipeline                                    │  ║
║  │    Preprocess → WeakLabel → Classify → Extract → Fraud → Analytics      │  ║
║  └──────┬──────────────────────┬────────────────────┬──────────────────────┘  ║
║         │                      │                     │                        ║
║  ┌──────▼──────┐  ┌────────────▼────────┐  ┌────────▼────────────────────┐  ║
║  │ Subscription│  │ Reinforcement        │  │ AI Insights                 │  ║
║  │ Intelligence│  │ Learning System      │  │ Groq Llama 3.3 70B          │  ║
║  │ Engine      │  │ LinUCB + RLHF-lite   │  │ SSE Streaming               │  ║
║  └─────────────┘  └─────────────────────┘  └─────────────────────────────┘  ║
║                                                                               ║
║  ┌──────────────────────────────────────────────────────────────────────┐    ║
║  │  Storage: Supabase PostgreSQL · Redis (Bloom + Cache) · SQLite (device)│  ║
║  └──────────────────────────────────────────────────────────────────────┘    ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## Layer 1 — Android Data Acquisition Layer

### 1.1 SmsBroadcastReceiver

Registered **statically** in `AndroidManifest.xml` with `android.provider.telephony.SMS_RECEIVED`. Static registration means the receiver fires even when the application process is completely killed — Android wakes the process specifically to deliver the broadcast. The receiver does no inline processing. It immediately enqueues the raw `SmsMessage` PDU into `SignalQueue` tagged with `source: SMS` and returns within milliseconds.

```xml
<receiver android:name=".SmsBroadcastReceiver"
          android:exported="true"
          android:permission="android.permission.BROADCAST_SMS">
    <intent-filter android:priority="999">
        <action android:name="android.provider.telephony.SMS_RECEIVED"/>
    </intent-filter>
</receiver>
```

### 1.2 FinSightNotificationListener

Extends Android's `NotificationListenerService` — a system-bound service that receives every notification posted on the device. Once granted via **Settings → Notification Access**, this service cannot be killed by battery optimizers because it is bound to the system's `NotificationManager` process, not the app process.

A curated package-name allowlist filters only financial app notifications:

```
com.phonepe.app               → PhonePe
com.google.android.apps.nbu.paisa.user → Google Pay
net.one97.paytm               → Paytm
in.org.npci.upiapp            → BHIM
com.amazon.mShop.android.shopping → Amazon Pay
com.dreamplug.androidapp      → Cred
com.fi.money                  → Fi Money
com.jupiter                   → Jupiter
com.slice.app                 → Slice
com.mobikwik_new              → MobiKwik
in.freecharge.android         → Freecharge
```

For each matching notification: title, body, timestamp (nanosecond precision), package name, group key, and extras bundle are extracted and enqueued as `Signal{source: NOTIFICATION}`. `onListenerDisconnected()` calls `requestRebind()` to auto-reconnect if the system severs the binding.

### 1.3 FinSightForegroundService

The central coordinator. Runs at `IMPORTANCE_FOREGROUND` (priority=100), the highest priority available to a third-party application — the same level as Truecaller, WhatsApp, and Google Maps Navigation. Declared `START_STICKY`: Android automatically restarts it if killed. Holds `PARTIAL_WAKE_LOCK` during active processing windows. Carries a persistent non-intrusive foreground notification required by Android to maintain this priority tier.

`DeviceBootReceiver` listens for `BOOT_COMPLETED` and `QUICKBOOT_POWERON` (HTC/Huawei) to restart the service after any device reboot.

### 1.4 SignalQueue

In-memory `LinkedBlockingQueue` (capacity=500). Both `SmsBroadcastReceiver` and `FinSightNotificationListener` enqueue signals here. A dedicated `SignalProcessorThread` consumes from the queue and routes signals to the `SyncOrchestrator`. If the queue fills during a burst, overflow signals are written directly to the local SQLite buffer with status `PENDING_PROCESSING` — zero signal loss under any load condition.

---

## Layer 2 — On-Device Intelligence Layer

### 2.1 Transaction Fingerprint Engine

A fingerprint is a deterministic, canonical identifier for the economic substance of a transaction. Two signals from different sources (SMS and notification) representing the same financial event will always produce the same fingerprint. This is the foundation of the entire deduplication system.

**Fingerprint computation:**

```
Step 1: Amount normalization
  raw_amount  = extract_amount(signal.text)
  norm_amount = Decimal(raw_amount).quantize(Decimal("0.01"))
  // ₹649, ₹649.0, ₹649.00 → "649.00" (identical string always)

Step 2: Merchant normalization
  raw_merchant   = extract_merchant(signal.text or notification.body)
  canon_merchant = MerchantNormalizer.quick_normalize(raw_merchant)
  // "NETFLIX.COM", "Netflix India", "NETFLIX*8734" → "netflix"
  // Uses: curated alias dict (200+ merchants) + lowercase + strip noise tokens

Step 3: Time bucket (15-minute window)
  time_bucket = floor(signal.timestamp_ms / 900_000)
  // Any two signals within the same 15-min block share this value
  // Window chosen because:
  //   UPI notifications arrive in 0–30 seconds of transaction
  //   Bank SMS arrive in 0–10 minutes in normal network conditions
  //   15 minutes safely covers both without over-merging distinct transactions

Step 4: Direction
  direction = classify_direction(signal.text)  // "credit" or "debit"

Step 5: Final fingerprint
  fingerprint = SHA-256(
    f"{norm_amount}|{canon_merchant}|{time_bucket}|{direction}"
  )
```

**Critical property — historical SMS fingerprinting**: The fingerprint algorithm uses `signal.timestamp_ms` which, for historical SMS read from ContentResolver, is set to `SMS.date` (the original message timestamp stored by the Android SMS system). This means a fingerprint computed during a historical backfill in Condition 1 is **identical** to the fingerprint that would have been computed in real time when that SMS originally arrived. This property is what makes the three-zone strategy in Condition 2 work correctly.

### 2.2 CrossSourceDeduplicator

Maintains a `FingerprintLedger` in local SQLite. The state machine for each incoming signal:

```
Signal arrives → fingerprint computed

  CASE A: No ledger entry exists
    → Create PENDING entry {sources_seen: [source], window_end: now + 15min}
    → Schedule dedup timer for 15 minutes

  CASE B: PENDING entry exists, DIFFERENT source, within window
    → Same transaction captured from both SMS and notification
    → Merge payloads (best fields from each source — see merge strategy)
    → Update entry: {sources_seen: [SMS, NOTIFICATION], status: MERGED}
    → Commit immediately as single merged record
    → Cancel dedup timer

  CASE C: PENDING entry exists, SAME source, within window
    → Same channel sent two signals (unusual — should not happen in normal operation)
    → Increment occurrence_count
    → If count == 2: suffix fingerprint with ":2", treat as distinct transaction
    → Commit both as separate records

  CASE D: COMMITTED or SYNCED entry exists (any source)
    → Already processed. DISCARD the incoming signal. Done.

  CASE E: Window expired (15 min), only one source seen
    → Status: COMMITTED
    → Forward single-source record to sync queue
```

**Payload merge strategy** (when both SMS and notification captured the same event):

| Field | Preferred Source | Reason |
|---|---|---|
| Amount | SMS | Bank SMS amounts are authoritative and verified |
| Merchant display name | Notification | UPI apps have cleaner, user-facing merchant names |
| Timestamp | Notification | Posted at exact moment of transaction |
| Bank name | SMS | Notification may omit bank context |
| UPI / reference number | SMS | Bank SMS includes full reference IDs |
| Account last 4 digits | SMS | Bank confirms account identity |
| Transaction direction | Both (verified) | Must agree; mismatch → CONFLICT_ANOMALY flag |

**Conflict escalation**: If SMS says "credit" and notification says "debit" for the same fingerprint, the record is flagged `CONFLICT_ANOMALY`, forwarded with both raw payloads attached, and reviewed by the fraud detector on the backend rather than auto-merged.

### 2.3 TFLite Quick Classifier

A quantized INT8 TFLite model distilled from the backend's full XGBoost + RF ensemble. Input: 48-feature engineered vector. Inference time: under 3ms on mid-range Android hardware.

```
Confidence >= 0.90 → classify on-device, backend skips ML (uses device result)
Confidence 0.65–0.90 → classify on-device, backend re-runs full ML to confirm
Confidence < 0.65 → mark UNCERTAIN, backend runs full ML pipeline
```

Filtering effect: OTPs, promotional SMS, and spam (~65–70% of all SMS) are filtered and classified on-device. They are stored locally with their classification but not forwarded to the backend ML pipeline, dramatically reducing backend processing load and sync payload size.

Updated TFLite models are delivered via `/api/v1/model/update` and hot-swapped without an app release.

### 2.4 LocalSQLiteBuffer (WAL + AES-256)

All processed signals waiting for backend sync are stored in a WAL-mode SQLite database. WAL mode allows concurrent reads (Flutter UI thread) and writes (service processing thread) without blocking. Encrypted with SQLCipher using a per-device key stored in Android Keystore.

```sql
CREATE TABLE fingerprint_ledger (
    fingerprint      TEXT PRIMARY KEY,
    first_seen_ms    INTEGER NOT NULL,
    sources_seen     TEXT NOT NULL,     -- JSON: ["SMS"], ["NOTIFICATION"], ["SMS","NOTIFICATION"]
    dedup_status     TEXT NOT NULL,     -- PENDING | MERGED | COMMITTED | CONFLICT | SYNCED
    occurrence_count INTEGER DEFAULT 1,
    dedup_window_ms  INTEGER NOT NULL,  -- first_seen_ms + 900000
    merged_payload   TEXT              -- JSON, null if single-source
);

CREATE TABLE sync_queue (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint      TEXT UNIQUE NOT NULL,
    payload_json     TEXT NOT NULL,     -- AES-256-GCM encrypted
    ondevice_class   TEXT,
    ondevice_conf    REAL,
    sync_status      TEXT DEFAULT 'PENDING', -- PENDING|SYNCING|SYNCED|FAILED
    created_at_ms    INTEGER NOT NULL,
    sync_attempts    INTEGER DEFAULT 0,
    last_attempt_ms  INTEGER,
    batch_id         TEXT
);

CREATE TABLE sync_checkpoint (
    key              TEXT PRIMARY KEY,
    value            TEXT NOT NULL,
    updated_at_ms    INTEGER NOT NULL
);
```

---

## Layer 3 — SyncOrchestrator — The Three Conditions

The `SyncOrchestrator` governs what SMS data gets processed and synced, in what order, under what conditions, and how conflicts with existing database records are resolved. It selects its operating mode deterministically based on the device's sync state at login time and transitions between modes as the system matures.

---

### SyncCheckpoint — The Source of Truth

The `SyncCheckpoint` is a bidirectional record persisted on both the device (SQLite `sync_checkpoint` table) and the backend (Supabase `user_sync_state` table). It is the single authoritative answer to: *"What has this user already synced?"*

**Checkpoint fields:**

```
SyncCheckpoint {
  user_id:                    UUID
  sync_mode:                  UNINITIALIZED | BACKFILL | CATCHUP | REALTIME
  backfill_completed_at:      TIMESTAMP | null   // null = backfill never finished
  last_synced_sms_date:       TIMESTAMP | null   // timestamp of newest SMS confirmed synced
  oldest_sms_date_on_device:  TIMESTAMP | null   // oldest SMS at time of backfill
  total_sms_synced:           INTEGER
  total_fingerprints:         INTEGER
  device_id:                  UUID
  schema_version:             INTEGER
  updated_at:                 TIMESTAMP
}
```

The checkpoint is written to **both** local SQLite and Supabase at the end of every sync batch. On app startup, the orchestrator:

1. Reads the local checkpoint (fastest — no network required)
2. Fetches the remote checkpoint from Supabase
3. Takes the **more recent** of the two (by `updated_at`)

**Why bidirectional?**
- Device replaced → local checkpoint is missing, remote is intact → remote wins → Condition 2 activates correctly
- App killed mid-batch before remote write → local is newer → local wins → correct resume point
- Supabase temporarily unavailable at startup → local checkpoint still enables correct mode selection

**Conflict resolution**: If local and remote `updated_at` are identical but values differ (extremely rare), remote (Supabase) wins. The backend is the authoritative record of what has been committed to the database.

---

### Condition 1: First Install, Empty Database

**Triggers when**: `sync_checkpoint.sync_mode == UNINITIALIZED` AND Supabase `user_sync_state` returns null (no prior record for this `user_id`).

This is the cleanest condition. The database is empty. Every SMS on the device is new. The risk is volume: a user's phone may contain 3–5 years of SMS including thousands of financial messages.

```
CONDITION 1 — HISTORICAL BACKFILL MODE
═══════════════════════════════════════

STEP 1: SET MODE
  → checkpoint.sync_mode = BACKFILL
  → Checkpoint written to local SQLite + Supabase

STEP 2: INVENTORY ALL SMS
  → Read ALL SMS from ContentResolver
      URI: content://sms/inbox
      Projection: [_id, address, date, body]
      Sort: date DESC (newest first — show user recent data quickly)
  → Total count recorded: e.g., 8,420 SMS across 4 years

STEP 3: ON-DEVICE PRE-FILTER
  → For each SMS in inventory:
      → TFLite quick-classify (3ms per SMS)
      → If class ∈ {OTP, PROMOTIONAL, PERSONAL, SPAM} with confidence ≥ 0.85:
          → Mark SKIP. Store classification locally. Do not process further.
      → If class ∈ {FINANCIAL_TRANSACTION, FINANCIAL_ALERT}:
          → Mark PROCESS
  → Estimated throughput: ~15–25% pass filter (1,200–2,100 of 8,420)
  → Total pre-filter time: ~25 seconds for 8,420 SMS

STEP 4: FINGERPRINT ALL CANDIDATES
  → For each SMS marked PROCESS:
      → Use SMS.date as timestamp (original receive time, not current time)
      → Compute fingerprint via FingerprintEngine
      → Write to fingerprint_ledger with status HISTORICAL
      → No 15-minute dedup window applies (historical SMS cannot have a
        live notification pair — notifications are ephemeral, not stored)
      → Group into batches of 200

STEP 5: SYNC IN BATCHES (newest first)
  → For each batch of 200 fingerprinted candidates:
      → Encrypt and compress payload
      → POST /api/v1/sync/batch?mode=backfill
      → Backend runs full ML pipeline on each record
      → Backend dedup gate (Bloom Filter check):
          → DB is empty, Bloom Filter is empty
          → All fingerprints flagged ABSENT → all records inserted
      → Backend responds: {acknowledged: [...fingerprints], model_version: "..."}
      → Device marks acknowledged fingerprints as SYNCED in fingerprint_ledger
      → Checkpoint updated after every batch:
            last_synced_sms_date = oldest SMS date in this batch
            total_sms_synced    += batch_size
      → Checkpoint written to local SQLite AND Supabase immediately after each batch

  → Inter-batch delay: 500ms (prevents backend saturation)
  → Connectivity gate: batches only sent on WiFi or mobile signal ≥ -90 dBm

STEP 6: BACKFILL COMPLETE
  → All financial SMS on device processed
  → checkpoint.backfill_completed_at = NOW()
  → checkpoint.sync_mode = REALTIME
  → Final checkpoint written to local SQLite AND Supabase

STEP 7: TRANSITION
  → SyncOrchestrator switches to Condition 3 (REALTIME mode)
  → All future signals handled as new real-time events
```

**Interruption and resumption**: If the app is killed or the device reboots during backfill, the checkpoint contains `last_synced_sms_date`. On restart, the orchestrator:
1. Detects mode is still `BACKFILL` (backfill_completed_at is null)
2. Reads SMS from ContentResolver filtered to `date < last_synced_sms_date` (older than already processed)
3. Resumes processing from exactly that point

No SMS is processed twice because fingerprints already `SYNCED` in the local ledger are skipped at the fingerprinting step.

**Progress UI**: The Flutter app shows a non-blocking progress banner during backfill: "Setting up FinSight · Scanning 3 years of transactions · 1,240 / 1,847 processed". The app is fully usable during backfill. The banner is dismissible and the backfill continues in the background service.

---

### Condition 2: Re-install, Database Has Data

**Triggers when**: `sync_checkpoint.sync_mode == UNINITIALIZED` (local SQLite wiped by re-install) BUT Supabase `user_sync_state` returns a non-null record with `backfill_completed_at != null`.

This is the most complex condition. The database has the user's complete transaction history. The device has all that same historical SMS plus new SMS that arrived after the last login. Syncing all SMS naively creates massive duplicates. Sending only SMS newer than the checkpoint might miss SMS that arrived between re-installs but were not captured due to connectivity failures during the original session.

**The solution is CATCHUP MODE with a three-zone time partitioning strategy:**

```
CONDITION 2 — CATCHUP MODE
═══════════════════════════

STEP 1: RESTORE CHECKPOINT FROM SUPABASE
  → Local checkpoint is missing (re-install wiped local SQLite)
  → Remote checkpoint loaded from Supabase:
        last_synced_sms_date = e.g., 2025-11-15T14:32:00Z
  → checkpoint.sync_mode = CATCHUP
  → Checkpoint written to local SQLite (restoring local state)

STEP 2: DEFINE THREE TIME ZONES

  Full device SMS timeline:
  ──────────────────────────────────────────────────────────────────▶ time
  │◄──────── ZONE A ────────────►│◄─── ZONE B ───►│◄─── ZONE C ───►│
  │  Definitely in DB.           │  Uncertain.     │  Definitely    │
  │  Skip entirely.              │  Check each     │  new. Sync     │
  │  No network calls.           │  fingerprint    │  all.          │
  │                              │  against backend│                │
  oldest SMS                (last_synced        last_synced      now
  on device                  - 7 days)          _sms_date

  ZONE A: date < (last_synced_sms_date - 7 days)
  ZONE B: (last_synced_sms_date - 7 days) ≤ date ≤ last_synced_sms_date
  ZONE C: date > last_synced_sms_date

  Why 7 days overlap in Zone B?
  → Covers SMS that arrived just before the previous app session ended
    but was never successfully synced (connectivity failure, interrupted batch)
  → Covers SMS timestamp drift: some OEM SMS apps store dates with
    offsets up to 72 hours from the actual arrival time
  → Covers any SMS where the backend batch was sent but the acknowledgment
    was lost before the device could mark records as SYNCED
  → 7 days is conservative enough to catch all realistic edge cases while
    keeping Zone B small enough to avoid unnecessary processing load

STEP 3: PROCESS ZONE A — SKIP ENTIRELY
  → All SMS with date < (last_synced_sms_date - 7 days)
  → Zero processing. Zero fingerprint computation. Zero network calls.
  → These are guaranteed to be in the database.
  → This zone may contain thousands of SMS — skipping it entirely is
    the primary optimization that makes Condition 2 tractable.

STEP 4: PROCESS ZONE B — PER-FINGERPRINT CHECK
  → Read all SMS from ContentResolver where:
        date >= (last_synced_sms_date - 7 days)
        AND date <= last_synced_sms_date
  → Apply TFLite pre-filter (same as Condition 1 Step 3)
  → For each candidate SMS:
        → Compute fingerprint (using SMS.date as timestamp)
  → Collect all Zone B fingerprints into batches of 500
  → POST /api/v1/dedup/check (batch fingerprint lookup — does NOT sync data)
        Body: { "fingerprints": ["fp1", "fp2", ...] }
        Response: { "present": ["fp1", ...], "absent": ["fp3", ...] }
  → PRESENT fingerprints → already in DB → mark locally as SYNCED → skip
  → ABSENT fingerprints → not in DB (genuine sync gap) → add to sync queue

  Expected outcome:
    95–99% of Zone B fingerprints will be PRESENT (already synced from before)
    1–5% will be ABSENT (genuine gaps — connectivity failures, etc.)
    Only the ABSENT ones proceed to actual data sync

STEP 5: PROCESS ZONE C — SYNC ALL
  → Read all SMS where date > last_synced_sms_date
  → These cannot be in the database (they arrived after the last session)
  → Apply TFLite pre-filter → fingerprint → batch → sync
  → Same pipeline as Condition 1 Step 5
  → Backend dedup gate still runs (safety net) but finds 0 duplicates

STEP 6: SYNC ZONE B ABSENT + ZONE C RECORDS
  → Batch all records from Steps 4 and 5 together
  → POST /api/v1/sync/batch?mode=catchup
  → Backend runs full ML pipeline
  → Backend dedup gate verifies (double safety net)
  → Acknowledgments received → device marks SYNCED
  → Checkpoint updated per batch

STEP 7: UPDATE CHECKPOINT
  → sync_mode = REALTIME
  → last_synced_sms_date = timestamp of newest SMS just synced
  → backfill_completed_at unchanged (preserved from original install)
  → Checkpoint written to local SQLite AND Supabase

STEP 8: TRANSITION TO REALTIME MODE
```

**Re-install on a different device**: The same logic applies. The remote checkpoint contains `last_synced_sms_date` from the old device. The new device's SMS history (which may be different — some SMS from old SIM may not be present) is analyzed using the three-zone strategy. SMS messages that exist on the new device and were synced from the old device produce the same fingerprints (same content, same timestamps) and will be found PRESENT in the backend Bloom Filter.

**Why not check all fingerprints against the backend instead of using zones?**
Zone A may contain thousands of SMS spanning years of history. Sending thousands of fingerprint-check API calls — even batched at 500 per request — is wasteful when the checkpoint already guarantees that everything before `last_synced_sms_date - 7 days` was committed. The three-zone strategy eliminates 90%+ of unnecessary network calls by using the checkpoint as a logical shortcut.

---

### Condition 3: New Real-Time Signal Arrives

**Triggers when**: `sync_checkpoint.sync_mode == REALTIME` AND a new signal arrives via `SmsBroadcastReceiver` or `FinSightNotificationListener`.

This is the steady-state operating condition. The database contains a complete, deduplicated transaction history. The orchestrator handles only net-new signals.

```
CONDITION 3 — REALTIME MODE
═════════════════════════════

A new signal arrives (SMS or Notification):

STEP 1: ENQUEUE
  → Signal enqueued into SignalQueue by BroadcastReceiver or NotificationListener
  → Tagged: source, received_at_ms, raw_payload

STEP 2: FINGERPRINT
  → SignalProcessorThread dequeues signal
  → FingerprintEngine computes fingerprint
  → timestamp = signal.received_at_ms (real-time — NOT historical date)

STEP 3: LOCAL DEDUP CHECK (sub-millisecond SQLite lookup)
  → Query fingerprint_ledger WHERE fingerprint = ?
  
  → NOT FOUND → no prior record → proceed to Step 4
  
  → FOUND, status = PENDING → same transaction, different source arriving
      → CrossSourceDeduplicator: merge with existing PENDING entry
      → Update sources_seen: ["SMS","NOTIFICATION"] or reverse
      → Merge payloads using merge strategy (Layer 2.2)
      → Status → MERGED → commit merged record immediately
      → Cancel the 15-minute dedup timer
      → Proceed directly to Step 6 (skip Steps 4–5, classification already done)
  
  → FOUND, status = COMMITTED | MERGED | SYNCED
      → Already processed successfully
      → DISCARD this signal. Done.

STEP 4: TFLite QUICK CLASSIFY
  → If confidence ≥ 0.85 and class ∈ {OTP, PROMOTIONAL, PERSONAL, SPAM}:
      → Write to fingerprint_ledger as CLASSIFIED_SKIP
      → Do not add to sync queue. Done. (most signals end here)
  
  → If class ∈ {FINANCIAL_TRANSACTION, FINANCIAL_ALERT}:
      → Write to fingerprint_ledger as PENDING
      → Write to sync_queue as PENDING
      → Proceed

STEP 5: DEDUP WINDOW (15-minute wait)
  → Record sits in PENDING state for up to 15 minutes
  → If second signal arrives from the other source within window:
      → Step 3 CASE handles the merge → MERGED → immediate sync
  → If no second signal within window:
      → Timer fires → status → COMMITTED → proceed to sync

STEP 6: SYNC TO BACKEND
  → SyncCoordinator batches COMMITTED/MERGED records
      (up to 10 records, or 30-second interval — whichever comes first)
  → POST /api/v1/sync/batch?mode=realtime
  → Backend dedup gate (Redis Bloom Filter check):
      → Expected: 0 duplicates (local check at Step 3 eliminated them)
      → If Bloom Filter says PRESENT (false positive at 0.001% rate):
          → Log as BLOOM_FALSE_POSITIVE
          → Skip insert (PostgreSQL ON CONFLICT DO NOTHING would also catch it)
          → Still include in acknowledgment response (device marks SYNCED)
  → Backend acknowledges fingerprints in response
  → Device marks SYNCED in both fingerprint_ledger and sync_queue
  → Checkpoint: last_synced_sms_date updated to latest

STEP 7: CAN A NEW REALTIME SMS CONFLICT WITH EXISTING DB DATA?

  Answer: NO — by construction.

  Case A: Same transaction, SMS + Notification
    → CrossSourceDeduplicator merges them at Step 3.
    → Only ONE record reaches the backend. No conflict.

  Case B: New transaction, same merchant and amount as an old one
    → The time_bucket component of the fingerprint differs.
    → Old transaction: time_bucket = floor(old_timestamp / 900000)
    → New transaction: time_bucket = floor(now / 900000)
    → Different fingerprints. Both records stored. Correct behaviour —
      they are legitimately different transactions.

  Case C: Two transactions to same merchant, same amount, same 15-minute window
    → This can only happen with two real distinct payments (extremely rare).
    → CrossSourceDeduplicator occurrence_count logic suffixes the second
      fingerprint with ":2". Both records stored with distinct fingerprints.

  Case D: Historical SMS arriving after a re-install that slipped through Condition 2
    → Impossible if Condition 2 Zone B check ran correctly.
    → Defense-in-depth: Backend Bloom Filter would catch it anyway (0.001% FP rate).
    → PostgreSQL UNIQUE constraint catches it even if Bloom Filter has a false negative.
    → Triple-layer defense means this is mathematically unachievable in practice.
```

---

### Sync State Machine

```
                         ┌─────────────────┐
                         │  UNINITIALIZED   │  App installed, user authenticated
                         └────────┬────────┘
                                  │
           ┌──────────────────────┴──────────────────────┐
           │  Remote checkpoint = null                   │  Remote checkpoint exists
           │  (true first install)                       │  (re-install / new device)
           ▼                                             ▼
    ┌────────────┐                               ┌─────────────┐
    │  BACKFILL  │                               │   CATCHUP   │
    │ Condition 1│                               │ Condition 2 │
    │            │                               │             │
    │ Read ALL   │                               │ Zone A skip │
    │ device SMS │                               │ Zone B check│
    │ Filter     │                               │ Zone C sync │
    │ Fingerprint│                               │             │
    │ Batch sync │                               │             │
    └─────┬──────┘                               └──────┬──────┘
          │  backfill_completed_at set                  │  catchup complete
          │  checkpoint written                         │  checkpoint updated
          └──────────────────────┬──────────────────────┘
                                 │
                                 ▼
                          ┌────────────┐
                          │  REALTIME  │◄──────────────────────────────────────┐
                          │ Condition 3│  Steady state.                        │
                          │            │  All new SMS and notifications        │
                          │ New signal │  processed here permanently.          │
                          │ arrives    │                                       │
                          └─────┬──────┘                                       │
                                │  fingerprint → local dedup → TFLite         │
                                │  → 15min window → sync → acknowledge        │
                                └──────────────────────────────────────────────┘

SPECIAL TRANSITIONS:
  BACKFILL interrupted → restart → resume from checkpoint.last_synced_sms_date
  CATCHUP  interrupted → restart → resume Zone B/C from checkpoint
  REALTIME → app reinstalled → UNINITIALIZED → remote checkpoint → CATCHUP
  REALTIME → user logs out → new login same device → remote checkpoint intact
             → backfill_completed_at non-null → skip to REALTIME directly
  REALTIME → user logs out → new login different device → same as re-install
```

---

### Collision Resolution Matrix

A complete reference for every scenario where a transaction fingerprint might appear more than once:

| Scenario | Detection Layer | Resolution |
|---|---|---|
| SMS + Notification for same transaction (real time) | Local `CrossSourceDeduplicator` (Step 3) | Payloads merged, single record committed |
| SMS + Notification for same transaction (historical) | Not possible — notifications are ephemeral | N/A |
| Same batch sent twice (connectivity failure mid-response) | Backend Redis Bloom Filter | Second batch skipped, acknowledged |
| Re-install, Zone A SMS (definitely already synced) | Checkpoint time zone logic | Skipped before fingerprinting |
| Re-install, Zone B SMS already in DB | `/dedup/check` Bloom Filter lookup | Marked PRESENT → skipped |
| Re-install, Zone B SMS NOT in DB (genuine gap) | `/dedup/check` Bloom Filter lookup | Marked ABSENT → synced |
| Two legitimate payments, same merchant, same amount, different day | Different time bucket → different fingerprint | Both stored correctly as separate records |
| Two legitimate payments, same merchant, same amount, same 15-min window | `occurrence_count` check in CrossSourceDeduplicator | Second fingerprint suffixed ":2" → both stored |
| Historical backfill SMS that are already in DB (shouldn't happen in Condition 1) | Backend Bloom Filter + PostgreSQL UNIQUE | Caught and skipped |
| SMS direction = credit, notification direction = debit (same fingerprint) | `CONFLICT_ANOMALY` flag | Both raw payloads stored, fraud detector escalates |
| Backend Bloom Filter false positive (0.001% rate) | PostgreSQL `ON CONFLICT DO NOTHING` | Insert skipped, fingerprint acknowledged — no duplicate |

---

## Layer 4 — Encrypted Transport Layer

### Security

- **TLS 1.3** with certificate pinning (SHA-256 of backend leaf certificate)
- **AES-256-GCM** for payload encryption with HKDF-derived per-session keys
- **gzip** compression before encryption (~65% payload size reduction for SMS batches)

### Sync Endpoints

```
POST /api/v1/sync/batch?mode=backfill|catchup|realtime
  Encrypted batch up to 200 signals
  Returns: {batch_id, acknowledged, rejected, model_version}

POST /api/v1/dedup/check
  Batch fingerprint lookup against Bloom Filter (Condition 2 Zone B only)
  Body: {fingerprints: [...]}
  Returns: {present: [...], absent: [...]}

GET  /api/v1/sync/checkpoint
  Fetch remote SyncCheckpoint (called on app startup)

PUT  /api/v1/sync/checkpoint
  Write updated checkpoint after each successful sync batch
```

### Retry Strategy

```
Attempt 1: immediate
Attempt 2: 30s ± 10s jitter
Attempt 3: 2min ± 30s jitter
Attempt 4: 10min ± 1min jitter
Attempt 5: 30min ± 5min jitter
Attempt 6+: 6h (circuit-open state, only retried on next connectivity probe)
```

Records are never removed from the local sync queue until the backend returns them in the `acknowledged` list. Acknowledgment handling is idempotent — receiving the same acknowledgment twice is safe.

---

## Layer 5 — Backend Processing Pipeline

### Mode-Aware Request Routing

```python
if mode == "backfill":
    # DB is empty for this user. Bloom Filter is empty.
    # Run full pipeline on every record. No pre-check needed.
    process_full_pipeline(signals)

elif mode == "catchup":
    # Device already checked Zone B fingerprints via /dedup/check.
    # Backend runs Bloom Filter as second safety net, then full pipeline.
    check_bloom_then_process(signals)

elif mode == "realtime":
    # Steady state. Bloom Filter embedded in dedup gate.
    # Device pre-filtered OTPs/promos, so most signals are financial.
    process_full_pipeline(signals)
```

### Hybrid ML Pipeline

**Stage 1 — Rule-based labeler (confidence ≥ 0.80 → direct output)**

Classifies into: `financial_transaction`, `financial_alert`, `otp`, `promotional`, `personal`, `spam`. Uses domain rules for Indian banking SMS: sender patterns (bank shortcodes vs phone numbers), amount regex patterns, payment rail indicators (UPI, NEFT, IMPS, RTGS), OTP markers, promotional language, phishing signals.

**Stage 2 — Ensemble ML (confidence < 0.80)**

- TF-IDF vectorization (5000 features, 1–3 gram)
- 48-dimension engineered feature vector appended
- XGBoost (600 estimators, max_depth=7) + Random Forest (300 estimators, min_samples_leaf=2)
- Soft-voting: `final_score = 0.55 × XGBoost + 0.45 × RF`

**Stage 3 — RL Policy Correction**

LinUCB contextual bandit applies per-user category preference adjustments (see Layer 8).

**Stage 4 — On-device result reconciliation**

If the device sent `ondevice_conf ≥ 0.90`, the backend uses that classification and logs `source: ONDEVICE`. If UNCERTAIN, the backend's full pipeline result takes precedence.

### Transaction Field Extractor

Converts classified `financial_transaction` signals into structured objects: amount, direction, canonical merchant, bank, payment method, UPI reference, account last 4, transaction date, balance after, source channel (sms/notification/merged/dataset).

### Fraud and Anomaly Screening

Phishing and spam pattern matching: lottery scams, fake KYC alerts, suspicious shortlinks, OTP theft, fake bank sender impersonation.

Statistical anomaly scoring:
```python
anomaly_score = sigmoid(
    0.35 × normalize(z_amount) +
    0.25 × normalize(debit_burst_in_1h) +
    0.25 × merchant_novelty +
    0.15 × time_of_day_rarity
)
```
Score > 0.85 → push notification alert to user.

### Analytics Engine

Net flow, category breakdown, payment method distribution, top merchants, cash flow forecast (7d/30d exponential smoothing). Computed asynchronously. Cached in Redis with 5-minute TTL, invalidated on new transaction commit.

---

## Layer 6 — Backend Deduplication Gate

### Redis Bloom Filter (Level 1)

```
Key:      "dedup:{user_id}"
Capacity: 10,000,000 fingerprints per user
FP rate:  0.001%
Memory:   ~2.4 MB per user
Lookup:   O(1), sub-millisecond
```

Every incoming fingerprint is checked here before any database operation. PRESENT → skip. ABSENT → proceed to Level 2.

Used also by the `/dedup/check` endpoint (Condition 2 Zone B) to let the device pre-screen fingerprints before sending full payloads.

### PostgreSQL UNIQUE Constraint (Level 2)

```sql
ALTER TABLE transactions ADD CONSTRAINT uq_fingerprint UNIQUE (fingerprint);
```

The deterministic final guard. Catches Bloom Filter false positives (0.001% rate) via `ON CONFLICT DO NOTHING`. If this constraint fires, the insert is skipped, the fingerprint is added to the Bloom Filter, and the backend still acknowledges the fingerprint so the device marks it SYNCED.

**Why two levels?**
At scale, preventing even a PostgreSQL index lookup on already-present fingerprints saves significant per-request latency. The Bloom Filter eliminates the database read entirely for known-committed records. Level 2 only activates for the 0.001% of false positives — in practice, almost never.

**Bloom Filter persistence**: Rebuilt from the transactions table on backend startup. Until rebuilt, duplicate protection falls back entirely to the PostgreSQL constraint. Once rebuilt, it reflects the full committed history.

---

## Layer 7 — Subscription Intelligence Engine

### Architecture

```
Committed transactions
        │
        ▼
┌──────────────────────┐
│ Merchant Normalizer  │  all-MiniLM-L6-v2 (semantic embedding dedup)
│ NLP + fuzzy dedup    │  + rapidfuzz token-sort-ratio ≥ 85
│                      │  + 200+ Indian merchant alias dictionary
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Periodicity Detector │  ACF (7/14/28-31/90/365 day lag peaks)
│                      │  + FFT (dominant frequency ≥ 3σ above noise)
│ score = 0.40×ACF     │  + Lomb-Scargle (sparse histories < 8 points)
│       + 0.35×FFT     │
│       + 0.25×LS      │  Confirmed if score ≥ 0.60 AND occurrences ≥ 2
└──────────┬───────────┘  Variable bills flagged if amount CV > 0.15
           ▼
┌──────────────────────┐
│ HDBSCAN Clusterer    │  6D: [merchant_pca[0:3], periodicity_score,
│ min_cluster_size=2   │       avg_amount_log, dominant_period_days]
│ min_samples=1        │  Surfaces duplicate subscriptions
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Category Classifier  │  Groq Llama 3.3 70B zero-shot → JSON output
│                      │  Entertainment, Utilities, SaaS, Health,
│                      │  Finance, Food, Shopping, Other
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Savings Computer     │  monthly_cost, annual_cost, usage_score,
│ + Priority Ranker    │  waste_score = (1−usage_score) × annual_cost
└──────────┬───────────┘  ranked by waste_score DESC
           ▼
┌──────────────────────┐
│ Cancel & Save Engine │  Groq Llama 3.3 70B structured JSON output:
│                      │  recommendation, rationale, alternatives,
│                      │  estimated_12m_saving, action_priority
└──────────────────────┘
```

### Dataset Ingestion Mode (Hackathon / Demo)

```
POST /api/v1/dataset/ingest
```

Accepts JSON array or CSV file of structured bank transactions. Runs the full Subscription Intelligence Engine. Returns detected subscriptions, category breakdown, total monthly cost, and Cancel & Save recommendations. No mobile app or SMS permissions required.

```json
[{
  "transaction_id": "TXN_001",
  "date": "2025-01-15",
  "description": "NETFLIX SUBSCRIPTION",
  "amount": 649.00,
  "type": "debit",
  "category": null
}]
```

---

## Layer 8 — Reinforcement Learning System

### Three Adaptive Policies

**Category Policy — LinUCB Contextual Bandit**

State: 48-feature transaction vector. Actions: 8 category labels. Per-user `(A, b)` parameter matrices updated online after every reward event. Cold-start uses global priors; diverges as user data accumulates. Converges to >92% user-preference alignment after 20–30 explicit corrections.

**Subscription Policy — Gradient Threshold Learning**

Adapts per-user thresholds: `periodicity_score_threshold` (default 0.60), `min_occurrence_count` (default 2), `amount_cv_threshold` (default 0.15). Updated via gradient step after explicit subscription feedback.

**Recommendation Policy — ε-greedy Bandit**

Learns per-user weights for: `waste_score`, `category_preference`, `subscription_age`, `amount_magnitude`. Updated after each recommendation interaction (acted on vs dismissed).

### Reward Signals

| User Action | Reward |
|---|---|
| Views transaction, no correction | +0.3 |
| Corrects category A → B | −1.0 (A), +1.0 (B) |
| Acts on Cancel & Save recommendation | +1.0 |
| Dismisses recommendation | −0.5 |
| Adds transaction manually (capture miss) | −0.5 |
| Thumbs up/down on AI chat | ±0.5 |

### Model Versioning and Rollback

Every policy update creates a versioned record in `rl_policy_versions`. Consistently negative rewards after an update trigger automatic rollback to the previous version.

### Continuous Retraining

- Trigger: 200 new transactions since last training
- Check interval: 5 minutes
- User corrections override rule-assigned labels in training data
- After retraining: model distilled to INT8 TFLite → pushed to all user devices

**Current training results**: 3,005 SMS · CV accuracy 99.93% · CV std 0.08% · weighted F1 1.00 · trained 2026-02-15.

---

## Layer 9 — AI Insights Layer (Groq)

**Groq Llama 3.3 70B Versatile** is the sole external API dependency.

**Financial Chat Assistant**: Streaming SSE chat. System prompt injects user's financial profile (income estimate, debits, savings rate, category breakdown, subscription summary, recent anomalies). Optional web augmentation fetches from authoritative Indian sources (RBI, government portals) when query references current events.

**Subscription Recommender**: Non-streaming JSON mode. Returns structured `Cancel & Save` objects for top-N subscriptions by waste score within ~2 seconds.

**Semantic Cache**: Near-identical queries served from Redis without hitting Groq (cosine similarity > 0.95 threshold). Cache TTL: 30 minutes.

**Circuit Breaker**: 3 failures in 60 seconds → circuit OPEN. Chat returns graceful offline message. Recommendations served from pre-computed cache. Probe after 60 seconds.

---

## Layer 10 — Storage Architecture

### On-Device (SQLite WAL + AES-256)

SQLCipher-encrypted WAL-mode SQLite. Key from Android Keystore. Tables: `fingerprint_ledger`, `sync_queue`, `sync_checkpoint`, `classified_signals`.

### Backend (Supabase PostgreSQL)

```sql
CREATE TABLE transactions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES auth.users NOT NULL,
    fingerprint      TEXT NOT NULL,
    amount           NUMERIC(12,2) NOT NULL,
    direction        TEXT NOT NULL CHECK (direction IN ('credit','debit')),
    merchant         TEXT NOT NULL,
    merchant_raw     TEXT,
    bank             TEXT,
    payment_method   TEXT,
    upi_ref          TEXT,
    account_last4    TEXT,
    transaction_date TIMESTAMPTZ NOT NULL,
    balance_after    NUMERIC(12,2),
    source           TEXT NOT NULL CHECK (source IN ('sms','notification','merged','dataset')),
    category         TEXT NOT NULL,
    category_confidence FLOAT,
    rl_adjusted      BOOLEAN DEFAULT FALSE,
    fraud_score      FLOAT DEFAULT 0.0,
    anomaly_score    FLOAT DEFAULT 0.0,
    is_subscription  BOOLEAN DEFAULT FALSE,
    sync_mode        TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_fingerprint UNIQUE (fingerprint)
);

CREATE INDEX idx_txn_user_date      ON transactions (user_id, transaction_date DESC);
CREATE INDEX idx_txn_user_merchant  ON transactions (user_id, merchant);
CREATE INDEX idx_txn_user_category  ON transactions (user_id, category);
CREATE INDEX idx_txn_fingerprint    ON transactions (fingerprint);

CREATE TABLE user_sync_state (
    user_id                    UUID PRIMARY KEY REFERENCES auth.users,
    sync_mode                  TEXT NOT NULL DEFAULT 'UNINITIALIZED',
    backfill_completed_at      TIMESTAMPTZ,
    last_synced_sms_date       TIMESTAMPTZ,
    oldest_sms_date_on_device  TIMESTAMPTZ,
    total_sms_synced           INTEGER DEFAULT 0,
    total_fingerprints         INTEGER DEFAULT 0,
    device_id                  UUID,
    schema_version             INTEGER DEFAULT 1,
    updated_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE subscriptions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES auth.users NOT NULL,
    merchant         TEXT NOT NULL,
    category         TEXT NOT NULL,
    avg_monthly_cost NUMERIC(10,2) NOT NULL,
    periodicity_days INTEGER NOT NULL,
    periodicity_score FLOAT NOT NULL,
    first_seen       TIMESTAMPTZ NOT NULL,
    last_seen        TIMESTAMPTZ NOT NULL,
    occurrence_count INTEGER NOT NULL,
    waste_score      FLOAT,
    recommendation   TEXT,
    is_active        BOOLEAN DEFAULT TRUE,
    user_action      TEXT,
    action_at        TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE rl_policy_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES auth.users NOT NULL,
    policy_type     TEXT NOT NULL,
    parameters      JSONB NOT NULL,
    training_reward FLOAT,
    n_updates       INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE feedback_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users NOT NULL,
    event_type  TEXT NOT NULL,
    target_id   UUID,
    old_value   TEXT,
    new_value   TEXT,
    reward      FLOAT,
    processed   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE chat_history (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID REFERENCES auth.users NOT NULL,
    role       TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

All tables have Row-Level Security policies ensuring users can only access their own rows.

### Redis

Per-user Bloom Filters (dedup gate), analytics cache (5-min TTL), Groq semantic cache (30-min TTL), API rate limit counters, RL reward buffer queue.

---

## Flutter Application Layer

### Permission Onboarding (First Launch)

Step-by-step guided flow, one permission per screen:

1. **SMS Permission** (`READ_SMS`, `RECEIVE_SMS`) — "Read your bank SMS to track transactions automatically."
2. **Notification Access** — Guided to Settings → Notification Access → FinSight toggle. "Capture UPI payments that don't send an SMS."
3. **Battery Optimization Exemption** — Guided to Settings → Battery → FinSight → No restrictions. "Keep FinSight running when the app is closed."

All three required for full dual-channel capture. Each screen explains exactly what is and is not done with the permission.

### Screen Inventory

**Dashboard**: Monthly net flow, spending velocity gauge, recent transactions, subscription cost ticker, anomaly alert cards.

**Transactions**: Paginated list with search, time filters, category filter, source badge (SMS / Notification / Merged / Dataset), inline category correction (feeds RL), sync status and progress banner during backfill/catchup.

**Analytics**: Spending trend (bar), category breakdown (donut), income vs expense (line), payment method distribution (pie), cash flow forecast (area), top merchants table.

**Subscriptions**: Total monthly recurring cost hero card, category tiles, individual subscription cards with next expected date and cancel-savings amount, Groq Cancel & Save recommendation panel with Cancel / Keep / Remind Later actions (each feeds RL reward).

**AI Chat**: Streaming Groq chat with financial context summary panel.

**Profile**: Subscription summary, system status (service running, last sync time, transactions today, ML model version, current sync mode and progress).

### Platform Channel Bridge

`MethodChannel`: Flutter → Android commands (start service, force sync, get status). `EventChannel`: Android → Flutter streaming events (sync progress, new transaction arrival, anomaly detected). `flutter_background_service` package manages the Dart isolate bridging Flutter and the Android service lifecycle.

---

## Machine Learning Methodology

### Pipeline Summary

```
Input: SMS text / Notification body / Merged payload
    │
    ▼ Preprocessing
    │  → Text normalization (lowercase, expand abbreviations, normalize amounts)
    │  → 48 engineered features (text metrics, amount, direction, payment rail,
    │    bank signals, fraud signals, source signals, temporal, user context)
    │  → TF-IDF (5000 features, 1-3 gram)
    │
    ├─ Rule-based labeler (confidence ≥ 0.80) → direct output
    │
    └─ Ensemble ML (confidence < 0.80)
         ├─ XGBoost (600 estimators, max_depth=7)
         ├─ Random Forest (300 estimators, min_samples_leaf=2)
         └─ Soft vote: 0.55 × XGB + 0.45 × RF
              │
              └─ LinUCB RL policy correction → final classification
```

### Weak Supervision Bootstrap

The rule-based labeler generates initial training labels using domain knowledge about Indian banking SMS. This bootstraps a labeled dataset without manual annotation — a documented weak-supervision approach. Pseudo-labels from domain rules train the statistical classifier. User corrections progressively replace pseudo-labels with ground truth in subsequent retraining cycles.

### Training Results

| Metric | Value |
|---|---|
| SMS in latest training run | 3,005 |
| Cross-validation accuracy | 99.93% |
| CV standard deviation | 0.08% |
| Weighted F1-score | 1.00 |
| Training date | 2026-02-15 |

Class distribution: `financial_alert` 328, `financial_transaction` 789, `otp` 52, `personal` 155, `promotional` 1,679, `spam` 2.

*Research note: Results should be presented as strong internal project results, not claims of real-world generalization. The `spam` class has very low support. Honest framing of weak-supervision uncertainty strengthens a research paper's credibility.*

---

## Production Deployment Architecture

```
Flutter App       → Google Play Store (APK/AAB)
FastAPI Backend   → Docker + Gunicorn + 4× Uvicorn workers → Render / Railway / Fly.io
Supabase          → Managed PostgreSQL + Auth + Storage
Redis             → Upstash serverless (no infrastructure management)
Groq              → API only (no GPU provisioning required)
```

All endpoints use `async def` with `asyncpg` connection pooling. All Groq streaming uses `async for`. The backend scales horizontally by adding Uvicorn worker replicas behind a load balancer.

### Environment Variables

```env
# Groq (sole external API)
GROQ_API_KEY=gsk_...

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/finsight

# Redis
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your_jwt_secret_min_32_chars
CERTIFICATE_PIN_SHA256=sha256/...

# Sync
BACKFILL_BATCH_SIZE=200
BACKFILL_BATCH_DELAY_MS=500
CATCHUP_OVERLAP_DAYS=7
DEDUP_WINDOW_MS=900000

# ML
RETRAIN_THRESHOLD=200
RETRAIN_CHECK_INTERVAL_SEC=300
TFLITE_MODEL_VERSION=2026.03.15
ONDEVICE_CONFIDENCE_THRESHOLD=0.90

# RL
RL_BANDIT_ALPHA=0.5
RL_LEARNING_RATE=0.01
RL_MIN_UPDATES_BEFORE_SWITCH=10

# App
ENVIRONMENT=production
LOG_LEVEL=info
```

---

## Project Structure

```text
FinSight/
├── README.md
│
├── ML_Model/                                      # FastAPI Backend
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── gunicorn.conf.py
│   ├── Dockerfile
│   │
│   ├── api/
│   │   ├── auth.py
│   │   ├── sync.py                                # Batch sync (all three modes)
│   │   ├── dedup.py                               # /dedup/check (Condition 2 Zone B)
│   │   ├── checkpoint.py                          # SyncCheckpoint GET/PUT
│   │   ├── transactions.py
│   │   ├── analytics.py
│   │   ├── subscriptions.py
│   │   ├── ai_chat.py
│   │   ├── dataset.py                             # CSV/JSON ingestion
│   │   └── model_update.py                        # TFLite delivery
│   │
│   ├── sync/
│   │   ├── orchestrator.py                        # Mode selection and routing
│   │   ├── checkpoint_manager.py                  # Bidirectional checkpoint R/W
│   │   ├── dedup_gate.py                          # Bloom Filter + PG unique
│   │   ├── batch_processor.py                     # Per-mode batch handling
│   │   └── zone_partitioner.py                    # Condition 2 three-zone logic
│   │
│   ├── pipeline/
│   │   ├── preprocessor.py
│   │   ├── labeler.py
│   │   ├── classifier.py
│   │   ├── extractor.py
│   │   ├── fraud_detector.py
│   │   └── analytics_engine.py
│   │
│   ├── subscription/
│   │   ├── normalizer.py
│   │   ├── periodicity.py
│   │   ├── clusterer.py
│   │   ├── categorizer.py
│   │   ├── savings.py
│   │   ├── recommender.py
│   │   └── dataset_ingestor.py
│   │
│   ├── rl/
│   │   ├── bandit.py
│   │   ├── reward_collector.py
│   │   ├── policy_manager.py
│   │   ├── feedback_processor.py
│   │   └── subscription_policy.py
│   │
│   ├── groq_client.py
│   ├── web_augmentor.py
│   ├── train.py
│   ├── auto_trainer.py
│   ├── tflite_converter.py
│   │
│   ├── data/
│   │   └── dummy_transactions.json
│   └── models/
│       ├── vectorizer.joblib
│       ├── classifier.joblib
│       ├── label_encoder.joblib
│       ├── training_metrics.json
│       └── finsight_classifier.tflite
│
├── finsight/                                      # Flutter Application
│   ├── android/app/src/main/
│   │   ├── AndroidManifest.xml
│   │   └── kotlin/com/finsight/
│   │       ├── SmsBroadcastReceiver.kt
│   │       ├── FinSightNotificationListener.kt
│   │       ├── FinSightForegroundService.kt
│   │       ├── DeviceBootReceiver.kt
│   │       ├── SignalQueue.kt
│   │       ├── SyncOrchestrator.kt                # Three-condition state machine
│   │       ├── SyncCheckpoint.kt                  # Bidirectional checkpoint
│   │       ├── TransactionFingerprintEngine.kt
│   │       ├── CrossSourceDeduplicator.kt
│   │       ├── TFLiteQuickClassifier.kt
│   │       ├── LocalSQLiteBuffer.kt
│   │       ├── SyncCoordinator.kt
│   │       └── MainActivity.kt
│   │
│   └── lib/
│       ├── screens/
│       │   ├── auth_screen.dart
│       │   ├── permission_setup_screen.dart
│       │   ├── dashboard_screen.dart
│       │   ├── transactions_screen.dart
│       │   ├── analytics_screen.dart
│       │   ├── subscriptions_screen.dart
│       │   ├── ai_chat_screen.dart
│       │   └── profile_screen.dart
│       ├── services/
│       │   ├── platform_channel_service.dart
│       │   ├── sync_service.dart
│       │   ├── subscription_service.dart
│       │   ├── feedback_service.dart
│       │   └── auth_service.dart
│       ├── models/
│       │   ├── transaction_model.dart
│       │   ├── subscription_model.dart
│       │   └── recommendation_model.dart
│       └── core/
│           ├── constants.dart
│           └── theme.dart
│
└── supabase/
    ├── migrations/
    └── config.toml
```

---

## Running the Project

### Backend

```bash
cd ML_Model
pip install -r requirements.txt
cp .env.example .env
# Configure: GROQ_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, DATABASE_URL, REDIS_URL

uvicorn main:app --host 0.0.0.0 --port 8080 --reload    # development
gunicorn main:app -c gunicorn.conf.py                   # production
```

### Train and Convert ML Model

```bash
cd ML_Model
python train.py               # Train XGBoost + RF ensemble
python tflite_converter.py    # Distill to INT8 TFLite for on-device deployment
```

### Hackathon / Demo Mode

```bash
# Via API (backend must be running, no mobile device needed)
curl -X POST http://localhost:8080/api/v1/dataset/ingest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d @data/dummy_transactions.json

# Standalone (no auth required)
python -m subscription.dataset_ingestor --file data/dummy_transactions.json --demo
```

### Flutter App

```bash
cd finsight
flutter pub get
flutter run                         # development
flutter build apk --release         # production APK
```

Update `finsight/lib/core/constants.dart` with your backend URL before running on a physical device. On first launch, complete the three-step permission setup — the app will not reach its home screen until all three permissions are granted.

---

## Research Contribution Summary

FinSight can be positioned in a final-year project or research paper as:

- **A dual-channel financial signal acquisition system** capturing SMS and UPI push notifications simultaneously, deduplicating them via SHA-256 fingerprinting with a 15-minute temporal merge window and a deterministic payload merge strategy that selects the authoritative field from each source
- **A three-condition sync protocol** with deterministic mode selection (Backfill / Catchup / Realtime), a bidirectional SyncCheckpoint that persists through re-installs and device replacements, a three-zone time partitioning strategy for re-install scenarios (eliminating 90%+ of redundant network calls), and triple-layer collision prevention (local SQLite ledger, Redis Bloom Filter at 0.001% FP rate, PostgreSQL unique constraint)
- **A hybrid weakly-supervised ML pipeline** for Indian financial SMS combining domain rule labeling, XGBoost + Random Forest soft-voting ensemble, on-device INT8 TFLite inference, and LinUCB contextual bandit personalization
- **A multi-method subscription detection engine** combining ACF, FFT, and Lomb-Scargle periodicity analysis with HDBSCAN density clustering over a 6-dimensional merchant feature space
- **A reinforcement learning personalization layer** using three independent policy networks that adapt classification, subscription detection thresholds, and recommendation ranking from implicit and explicit user feedback without manual retraining
- **A Groq Llama 3.3 70B powered financial AI** delivering structured Cancel & Save recommendations and streaming personalized financial chat with zero other external API dependencies
- **A production Android persistent service architecture** at Truecaller-equivalent process priority with boot persistence, WAL-mode AES-encrypted local buffering, and AES-256-GCM + TLS 1.3 transport security

---

## Conclusion

FinSight is not a budgeting app. It is a persistent, self-improving financial signal processing system that operates at the Android system level, captures every financial event from every channel simultaneously, resolves the complete application lifecycle — first install, re-install, and real-time steady state — through a deterministic sync protocol that enforces zero duplicate transactions at three independent enforcement layers, classifies and extracts structured transaction knowledge through a hybrid ML pipeline, detects recurring subscription drain through advanced time-series and clustering analysis, learns from every user interaction through a reinforcement learning feedback loop, and surfaces actionable financial intelligence through an AI layer powered exclusively by Groq Llama 3.3 70B. From the first SMS scan on a fresh install to the ten-thousandth real-time transaction years later, the system operates with the same architectural guarantees at every step.
