-- Migration: Create Event Log TimeSeries Types
-- Creates the five TimeSeries types for the Agent Operations event log
-- Each type has appropriate retention policy, tags (indexed partition keys), and fields (data payload)

-- AgentSignal: Exploratory agent observations (7-day retention)
CREATE TYPE IF NOT EXISTS AgentSignal EXTENDS TimeSeries RETENTION 7 DAYS;
-- Tags (indexed for efficient filtering)
CREATE PROPERTY IF NOT EXISTS AgentSignal.agent_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.objective_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.mtp_version STRING;
-- Fields (data payload)
CREATE PROPERTY IF NOT EXISTS AgentSignal.event_type STRING;
CREATE PROPERTY IF NOT EXISTS AgentSignal.ts DATETIME;
CREATE PROPERTY IF NOT EXISTS AgentSignal.payload EMBEDDED;
CREATE PROPERTY IF NOT EXISTS AgentSignal.confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS AgentSignal.novelty_flag BOOLEAN;

-- AgentAction: Agent tool executions and operations (30-day retention)
CREATE TYPE IF NOT EXISTS AgentAction EXTENDS TimeSeries RETENTION 30 DAYS;
-- Tags (indexed for efficient filtering)
CREATE PROPERTY IF NOT EXISTS AgentAction.agent_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentAction.objective_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentAction.mtp_version STRING;
-- Fields (data payload)
CREATE PROPERTY IF NOT EXISTS AgentAction.event_type STRING;
CREATE PROPERTY IF NOT EXISTS AgentAction.ts DATETIME;
CREATE PROPERTY IF NOT EXISTS AgentAction.payload EMBEDDED;

-- AgentFinding: Verification and objective agent conclusions (90-day retention)
CREATE TYPE IF NOT EXISTS AgentFinding EXTENDS TimeSeries RETENTION 90 DAYS;
-- Tags (indexed for efficient filtering)
CREATE PROPERTY IF NOT EXISTS AgentFinding.agent_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentFinding.objective_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentFinding.mtp_version STRING;
-- Fields (data payload)
CREATE PROPERTY IF NOT EXISTS AgentFinding.event_type STRING;
CREATE PROPERTY IF NOT EXISTS AgentFinding.ts DATETIME;
CREATE PROPERTY IF NOT EXISTS AgentFinding.payload EMBEDDED;
CREATE PROPERTY IF NOT EXISTS AgentFinding.confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS AgentFinding.novelty_flag BOOLEAN;

-- AgentCheckpoint: Objective agent decision boundaries (180-day retention)
CREATE TYPE IF NOT EXISTS AgentCheckpoint EXTENDS TimeSeries RETENTION 180 DAYS;
-- Tags (indexed for efficient filtering)
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.agent_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.objective_id STRING;
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.mtp_version STRING;
-- Fields (data payload)
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.event_type STRING;
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.ts DATETIME;
CREATE PROPERTY IF NOT EXISTS AgentCheckpoint.payload EMBEDDED;

-- ObjectiveTransition: Objective lifecycle state changes (indefinite retention)
CREATE TYPE IF NOT EXISTS ObjectiveTransition EXTENDS TimeSeries RETENTION 0 DAYS;
-- Tags (indexed for efficient filtering)
CREATE PROPERTY IF NOT EXISTS ObjectiveTransition.agent_id STRING;
CREATE PROPERTY IF NOT EXISTS ObjectiveTransition.objective_id STRING;
CREATE PROPERTY IF NOT EXISTS ObjectiveTransition.mtp_version STRING;
-- Fields (data payload)
CREATE PROPERTY IF NOT EXISTS ObjectiveTransition.event_type STRING;
CREATE PROPERTY IF NOT EXISTS ObjectiveTransition.ts DATETIME;
CREATE PROPERTY IF NOT EXISTS ObjectiveTransition.payload EMBEDDED;
