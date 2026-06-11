-- Migration: Add FocusRecord and CommitmentRecord (simplified — no prior migrations applied)
-- Drops ObjectiveRecord, creates FocusRecord and CommitmentRecord with revised schemas

DROP TYPE IF EXISTS ObjectiveRecord;

-- FocusRecord: targeted exploration focus for colony workers
-- FocusRecord: targeted exploration focus for colony workers
CREATE DOCUMENT TYPE IF NOT EXISTS FocusRecord;
CREATE PROPERTY IF NOT EXISTS FocusRecord.focus_id STRING;
CREATE PROPERTY IF NOT EXISTS FocusRecord.domain STRING;
CREATE PROPERTY IF NOT EXISTS FocusRecord.description STRING;
CREATE PROPERTY IF NOT EXISTS FocusRecord.status STRING;
CREATE PROPERTY IF NOT EXISTS FocusRecord.created_at DATETIME;
CREATE PROPERTY IF NOT EXISTS FocusRecord.priority_signal FLOAT;
CREATE PROPERTY IF NOT EXISTS FocusRecord.checkpoint EMBEDDED;
CREATE PROPERTY IF NOT EXISTS FocusRecord.assigned_agent_id STRING;
CREATE INDEX IF NOT EXISTS FocusRecord.focus_id ON FocusRecord (focus_id) UNIQUE;
CREATE INDEX IF NOT EXISTS FocusRecord.status ON FocusRecord (status) NOTUNIQUE;

-- CommitmentRecord: commitment to deliver a specific outcome
CREATE DOCUMENT TYPE IF NOT EXISTS CommitmentRecord;
CREATE PROPERTY IF NOT EXISTS CommitmentRecord.commitment_id STRING;
CREATE PROPERTY IF NOT EXISTS CommitmentRecord.status STRING;
CREATE PROPERTY IF NOT EXISTS CommitmentRecord.created_at DATETIME;
CREATE PROPERTY IF NOT EXISTS CommitmentRecord.domain STRING;
CREATE PROPERTY IF NOT EXISTS CommitmentRecord.priority_signal FLOAT;
CREATE PROPERTY IF NOT EXISTS CommitmentRecord.checkpoint EMBEDDED;
CREATE PROPERTY IF NOT EXISTS CommitmentRecord.assigned_agent_id STRING;
CREATE PROPERTY IF NOT EXISTS CommitmentRecord.implementation_state STRING;
CREATE INDEX IF NOT EXISTS CommitmentRecord.commitment_id ON CommitmentRecord (commitment_id) UNIQUE;
CREATE INDEX IF NOT EXISTS CommitmentRecord.status ON CommitmentRecord (status) NOTUNIQUE;
