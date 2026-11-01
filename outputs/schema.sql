-- YottaFlex churn and retention database schema
-- Generated from the project data model.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS retention_outcomes;
DROP TABLE IF EXISTS churn_outcomes;
DROP TABLE IF EXISTS campaign_contacts;
DROP TABLE IF EXISTS eligibility_rules;
DROP TABLE IF EXISTS offers;
DROP TABLE IF EXISTS support_cases;
DROP TABLE IF EXISTS billing_events;
DROP TABLE IF EXISTS usage_snapshots;
DROP TABLE IF EXISTS subscription_history;
DROP TABLE IF EXISTS subscriptions;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (customer_id TEXT PRIMARY KEY,
        signup_date TEXT,
        region TEXT,
        segment TEXT,
        acquisition_channel TEXT,
        seasonal_user INTEGER);
CREATE TABLE subscriptions (subscription_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        plan TEXT,
        monthly_fee REAL,
        status TEXT,
        start_date TEXT,
        end_date TEXT);
CREATE TABLE subscription_history (history_id TEXT PRIMARY KEY,
        subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
        event_type TEXT NOT NULL,
        previous_plan TEXT,
        new_plan TEXT,
        previous_fee REAL,
        new_fee REAL,
        previous_status TEXT,
        new_status TEXT,
        effective_date TEXT NOT NULL);
CREATE TABLE usage_snapshots (snapshot_id TEXT PRIMARY KEY,
        subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
        month TEXT,
        data_gb REAL,
        sessions INTEGER,
        active_days INTEGER);
CREATE TABLE billing_events (billing_event_id TEXT PRIMARY KEY,
        subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
        event_date TEXT,
        event_type TEXT,
        amount REAL,
        status TEXT);
CREATE TABLE support_cases (support_case_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        opened_at TEXT,
        category TEXT,
        priority TEXT,
        status TEXT,
        resolution_hours REAL);
CREATE TABLE offers (offer_id TEXT PRIMARY KEY,
        offer_type TEXT,
        discount_pct REAL,
        duration_months INTEGER,
        estimated_cost REAL,
        active INTEGER);
CREATE TABLE eligibility_rules (rule_id TEXT PRIMARY KEY,
        min_risk_score INTEGER,
        max_cost_margin_pct REAL,
        active_only INTEGER,
        cooldown_days INTEGER);
CREATE TABLE campaign_contacts (contact_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        offer_id TEXT NOT NULL REFERENCES offers(offer_id),
        group_name TEXT,
        contact_date TEXT,
        eligibility_status TEXT,
        risk_score_at_contact INTEGER,
        estimated_cost REAL,
        campaign_id TEXT,
        rule_id TEXT,
        minimum_required_risk_score INTEGER,
        monthly_margin REAL,
        maximum_allowed_offer_cost REAL,
        max_cost_margin_pct REAL,
        decision_reasons TEXT);
CREATE TABLE churn_outcomes (churn_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        prediction_date TEXT,
        horizon_end TEXT,
        churned INTEGER,
        churn_type TEXT,
        churn_date TEXT,
        baseline_churn_propensity REAL);
CREATE TABLE retention_outcomes (retention_id TEXT PRIMARY KEY,
        contact_id TEXT NOT NULL REFERENCES campaign_contacts(contact_id),
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        retained INTEGER,
        realized_offer_cost REAL,
        outcome_date TEXT,
        offer_responded INTEGER);
