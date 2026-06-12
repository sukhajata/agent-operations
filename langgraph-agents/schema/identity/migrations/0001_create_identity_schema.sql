-- Migration: Create Identity Store Schema
-- Creates document types for MTP documents, ACAP definitions, and
-- objective records in ArcadeDB.

-- MTPDocument: Massive Transformative Purpose documents
CREATE DOCUMENT TYPE IF NOT EXISTS MTPDocument;
CREATE PROPERTY IF NOT EXISTS MTPDocument.mtp_id STRING;
CREATE PROPERTY IF NOT EXISTS MTPDocument.version STRING;
CREATE PROPERTY IF NOT EXISTS MTPDocument.purpose STRING;
CREATE PROPERTY IF NOT EXISTS MTPDocument.constraints LIST STRING;
CREATE PROPERTY IF NOT EXISTS MTPDocument.intent_description STRING;
CREATE PROPERTY IF NOT EXISTS MTPDocument.created_at DATETIME;
CREATE PROPERTY IF NOT EXISTS MTPDocument.created_by STRING;

-- Index on version for fast MTP version lookups
CREATE INDEX IF NOT EXISTS MTPDocument.version ON MTPDocument (version) UNIQUE;

-- ACAPDefinition: Access Control and Action Policy definitions
CREATE DOCUMENT TYPE IF NOT EXISTS ACAPDefinition;
CREATE PROPERTY IF NOT EXISTS ACAPDefinition.acap_id STRING;
CREATE PROPERTY IF NOT EXISTS ACAPDefinition.agent_type STRING;
CREATE PROPERTY IF NOT EXISTS ACAPDefinition.permitted_tools LIST STRING;
CREATE PROPERTY IF NOT EXISTS ACAPDefinition.permitted_mcp_connections LIST STRING;
CREATE PROPERTY IF NOT EXISTS ACAPDefinition.permitted_event_types LIST STRING;
CREATE PROPERTY IF NOT EXISTS ACAPDefinition.forbidden_targets LIST STRING;
CREATE PROPERTY IF NOT EXISTS ACAPDefinition.resource_ceiling EMBEDDED;

-- Index on agent_type for fast ACAP lookups
CREATE INDEX IF NOT EXISTS ACAPDefinition.agent_type ON ACAPDefinition (agent_type) UNIQUE;

-- ObjectiveRecord: Objective lifecycle registry
CREATE DOCUMENT TYPE IF NOT EXISTS ObjectiveRecord;
CREATE PROPERTY IF NOT EXISTS ObjectiveRecord.objective_id STRING;
CREATE PROPERTY IF NOT EXISTS ObjectiveRecord.status STRING;
CREATE PROPERTY IF NOT EXISTS ObjectiveRecord.created_at DATETIME;
CREATE PROPERTY IF NOT EXISTS ObjectiveRecord.domain STRING;
CREATE PROPERTY IF NOT EXISTS ObjectiveRecord.priority_signal FLOAT;
CREATE PROPERTY IF NOT EXISTS ObjectiveRecord.checkpoint EMBEDDED;
CREATE PROPERTY IF NOT EXISTS ObjectiveRecord.assigned_agent_id STRING;
CREATE PROPERTY IF NOT EXISTS ObjectiveRecord.implementation_status STRING;
CREATE PROPERTY IF NOT EXISTS ObjectiveRecord.implementation_state STRING;

-- Index on status for fast objective state queries
CREATE INDEX IF NOT EXISTS ObjectiveRecord.status ON ObjectiveRecord (status) NOTUNIQUE;

-- Index on implementation_status for approval queue queries
CREATE INDEX IF NOT EXISTS ObjectiveRecord.implementation_status ON ObjectiveRecord (implementation_status) NOTUNIQUE;
