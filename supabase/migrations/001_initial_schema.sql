-- FinSight Initial Database Schema
-- Run against Supabase PostgreSQL

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ════════════════════════════════════════
-- 1. Transactions Table
-- ════════════════════════════════════════
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
    direction TEXT NOT NULL CHECK (direction IN ('credit', 'debit')),
    merchant TEXT NOT NULL DEFAULT 'Unknown',
    merchant_raw TEXT,
    bank TEXT,
    payment_method TEXT,
    upi_ref TEXT,
    account_last4 TEXT,
    transaction_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    balance_after NUMERIC(15, 2),
    source TEXT NOT NULL DEFAULT 'sms' CHECK (source IN ('sms', 'notification', 'merged', 'dataset')),
    category TEXT NOT NULL DEFAULT 'uncategorized',
    category_confidence NUMERIC(5, 4) DEFAULT 0.0,
    rl_adjusted BOOLEAN DEFAULT FALSE,
    fraud_score NUMERIC(5, 4) DEFAULT 0.0,
    anomaly_score NUMERIC(5, 4) DEFAULT 0.0,
    is_subscription BOOLEAN DEFAULT FALSE,
    sync_mode TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_fingerprint ON transactions(fingerprint);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant ON transactions(user_id, merchant);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(user_id, category);

-- ════════════════════════════════════════
-- 2. User Sync State (SyncCheckpoint)
-- ════════════════════════════════════════
CREATE TABLE IF NOT EXISTS user_sync_state (
    user_id TEXT PRIMARY KEY,
    sync_mode TEXT NOT NULL DEFAULT 'UNINITIALIZED'
        CHECK (sync_mode IN ('UNINITIALIZED', 'BACKFILL', 'CATCHUP', 'REALTIME')),
    backfill_completed_at TIMESTAMPTZ,
    last_synced_sms_date TIMESTAMPTZ,
    oldest_sms_date_on_device TIMESTAMPTZ,
    total_sms_synced INTEGER DEFAULT 0,
    total_fingerprints INTEGER DEFAULT 0,
    device_id UUID,
    schema_version INTEGER DEFAULT 1,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ════════════════════════════════════════
-- 3. Subscriptions
-- ════════════════════════════════════════
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    merchant TEXT NOT NULL,
    category TEXT DEFAULT 'Other',
    avg_monthly_cost NUMERIC(12, 2) DEFAULT 0,
    periodicity_days INTEGER DEFAULT 30,
    periodicity_score NUMERIC(5, 4) DEFAULT 0.0,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    occurrence_count INTEGER DEFAULT 0,
    waste_score NUMERIC(12, 2) DEFAULT 0.0,
    recommendation TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    user_action TEXT,
    action_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, merchant)
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions(user_id, is_active);

-- ════════════════════════════════════════
-- 4. Feedback Events (RL Reward Signals)
-- ════════════════════════════════════════
CREATE TABLE IF NOT EXISTS feedback_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    target_id UUID,
    old_value TEXT,
    new_value TEXT,
    reward NUMERIC(5, 2) DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_events(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_events(event_type);

-- ════════════════════════════════════════
-- 5. RL Policies (Bandit State)
-- ════════════════════════════════════════
CREATE TABLE IF NOT EXISTS rl_policies (
    user_id TEXT NOT NULL,
    arm_type TEXT NOT NULL DEFAULT 'category',
    bandit_state JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, arm_type)
);

-- ════════════════════════════════════════
-- 6. Chat History
-- ════════════════════════════════════════
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_history(user_id, created_at DESC);

-- ════════════════════════════════════════
-- 7. Row Level Security (RLS)
-- ════════════════════════════════════════
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sync_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE rl_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;

-- Users can only access their own data
CREATE POLICY transactions_user_policy ON transactions
    FOR ALL USING (user_id = current_setting('request.jwt.claim.sub', true));

CREATE POLICY sync_state_user_policy ON user_sync_state
    FOR ALL USING (user_id = current_setting('request.jwt.claim.sub', true));

CREATE POLICY subscriptions_user_policy ON subscriptions
    FOR ALL USING (user_id = current_setting('request.jwt.claim.sub', true));

CREATE POLICY feedback_user_policy ON feedback_events
    FOR ALL USING (user_id = current_setting('request.jwt.claim.sub', true));

CREATE POLICY rl_policies_user_policy ON rl_policies
    FOR ALL USING (user_id = current_setting('request.jwt.claim.sub', true));

CREATE POLICY chat_user_policy ON chat_history
    FOR ALL USING (user_id = current_setting('request.jwt.claim.sub', true));

-- Service role bypass (for backend API)
CREATE POLICY transactions_service_policy ON transactions
    FOR ALL USING (current_setting('role', true) = 'service_role');

CREATE POLICY sync_state_service_policy ON user_sync_state
    FOR ALL USING (current_setting('role', true) = 'service_role');

CREATE POLICY subscriptions_service_policy ON subscriptions
    FOR ALL USING (current_setting('role', true) = 'service_role');

CREATE POLICY feedback_service_policy ON feedback_events
    FOR ALL USING (current_setting('role', true) = 'service_role');

CREATE POLICY rl_policies_service_policy ON rl_policies
    FOR ALL USING (current_setting('role', true) = 'service_role');

CREATE POLICY chat_service_policy ON chat_history
    FOR ALL USING (current_setting('role', true) = 'service_role');
