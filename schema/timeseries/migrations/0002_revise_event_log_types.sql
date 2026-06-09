-- Migration: Revise Event Log Types (simplified — no prior migrations applied)
-- Drops old types and creates clean schema for AgentSignal, AgentAction, AgentCheckpoint, CommitmentTransition

-- Drop old types
DROP TYPE IF EXISTS AgentSignal;
DROP TYPE IF EXISTS AgentAction;
DROP TYPE IF EXISTS AgentFinding;
DROP TYPE IF EXISTS AgentCheckpoint;
DROP TYPE IF EXISTS ObjectiveTransition;
DROP TYPE IF EXISTS CommitmentTransition;

-- AgentSignal: observations (stage='observation') and findings (stage='finding')
CREATE TYPE IF NOT EXISTS AgentSignal EXTENDS TimeSeries RETENTION 7 DAYS;
-- Tags (indexed partition keys)
CREATE PROPERTY IF NOT EXISTS AgentSignal.agent_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.mtp_version STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.focus_id STRING;
-- Fields
CREATE PROPERTY IF NOT EXISTS AgentSignal.event_type STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.ts DATETIME;
CREATE PROPERTY IF NOT EXISTS AgentSignal.claim STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.domain STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS AgentSignal.reasoning STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.sources EMBEDDED;
CREATE PROPERTY IF NOT EXISTS AgentSignal.stage STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.novelty_flag BOOLEAN;

-- AgentAction: tool executions, operations, and worker lifecycle events
CREATE TYPE IF NOT EXISTS AgentAction EXTENDS TimeSeries RETENTION 30 DAYS;
-- Tags
CREATE PROPERTY IF NOT EXISTS AgentAction.agent_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentAction.mtp_version STRING;
CREATE PROPERTY IF NOT EXISTS AgentAction.commitment_id STRING;
-- Fields
CREATE PROPERTY IF NOT EXISTS AgentAction.event_type STRING;
CREATE PROPERTY IF NOT EXISTS AgentAction.ts DATETIME;
CREATE PROPERTY IF NOT EXISTS AgentAction.payload EMBEDDED;

-- AgentCheckpoint: agent decision boundaries
CREATE TYPE IF NOT EXISTS AgentCheckpoint EXTENDS TimeSeries RETENTION 180 DAYS;
-- Tags
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.agent_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.mtp_version STRING;
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.commitment_id STRING;
-- Fields
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.event_type STRING;
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.ts DATETIME;
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.payload EMBEDDED;

-- CommitmentTransition: commitment lifecycle state changes
CREATE TYPE IF NOT EXISTS CommitmentTransition EXTENDS TimeSeries RETENTION 0 DAYS;
-- Tags
CREATE PROPERTY IF NOT EXISTS CommitmentTransition.agent_id STRING;
CREATE PROPERTY IF NOT EXISTS CommitmentTransition.mtp_version STRING;
CREATE PROPERTY IF NOT EXISTS CommitmentTransition.commitment_id STRING;
-- Fields
CREATE PROPERTY IF NOT EXISTS CommitmentTransition.event_type STRING;
CREATE PROPERTY IF NOT EXISTS CommitmentTransition.ts DATETIME;
CREATE PROPERTY IF NOT EXISTS CommitmentTransition.payload EMBEDDED;
