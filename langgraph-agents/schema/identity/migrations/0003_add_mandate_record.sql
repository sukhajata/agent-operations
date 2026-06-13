-- Migration: Add MandateRecord document type
-- Stores exploratory agent mandates in ArcadeDB instead of YAML config

CREATE DOCUMENT TYPE IF NOT EXISTS MandateRecord;
CREATE PROPERTY IF NOT EXISTS MandateRecord.mandate_id STRING;
CREATE PROPERTY IF NOT EXISTS MandateRecord.name STRING;
CREATE PROPERTY IF NOT EXISTS MandateRecord.domain STRING;
CREATE PROPERTY IF NOT EXISTS MandateRecord.agent_type STRING;
CREATE PROPERTY IF NOT EXISTS MandateRecord.focus_id STRING;
CREATE PROPERTY IF NOT EXISTS MandateRecord.polling_interval_minutes INTEGER;
CREATE PROPERTY IF NOT EXISTS MandateRecord.signal_threshold FLOAT;
CREATE PROPERTY IF NOT EXISTS MandateRecord.active BOOLEAN;

CREATE INDEX IF NOT EXISTS MandateRecord.active ON MandateRecord (active) NOTUNIQUE;
