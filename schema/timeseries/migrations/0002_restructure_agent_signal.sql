-- Migration: Restructure AgentSignal type
-- Drops payload/objective_id; adds claim, domain, reasoning, sources, focus_id
-- focus_id replaces objective_id for exploratory agent signals

-- Drop old fields
DROP PROPERTY IF EXISTS AgentSignal.objective_id;
DROP PROPERTY IF EXISTS AgentSignal.payload;

-- Add new fields
CREATE PROPERTY IF NOT EXISTS AgentSignal.claim STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.domain STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.reasoning STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.sources EMBEDDED;
CREATE PROPERTY IF NOT EXISTS AgentSignal.focus_id STRING;
