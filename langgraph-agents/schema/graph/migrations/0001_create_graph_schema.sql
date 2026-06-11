-- Migration: Create Knowledge Graph Schema
-- Creates vertex types for the six knowledge graph node types and edge types
-- for relationships between them.

-- ProductStructure: Structural discoveries about the product
CREATE TYPE IF NOT EXISTS ProductStructure EXTENDS Vertex;
CREATE PROPERTY IF NOT EXISTS ProductStructure.node_id STRING;
CREATE PROPERTY IF NOT EXISTS ProductStructure.node_type STRING;
CREATE PROPERTY IF NOT EXISTS ProductStructure.confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS ProductStructure.initial_confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS ProductStructure.decay_rate FLOAT;
CREATE PROPERTY IF NOT EXISTS ProductStructure.last_reinforced DATETIME;
CREATE PROPERTY IF NOT EXISTS ProductStructure.revalidation_required BOOLEAN;

-- DecisionRecord: Architectural and design decisions
CREATE TYPE IF NOT EXISTS DecisionRecord EXTENDS Vertex;
CREATE PROPERTY IF NOT EXISTS DecisionRecord.node_id STRING;
CREATE PROPERTY IF NOT EXISTS DecisionRecord.node_type STRING;
CREATE PROPERTY IF NOT EXISTS DecisionRecord.confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS DecisionRecord.initial_confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS DecisionRecord.decay_rate FLOAT;
CREATE PROPERTY IF NOT EXISTS DecisionRecord.last_reinforced DATETIME;
CREATE PROPERTY IF NOT EXISTS DecisionRecord.revalidation_required BOOLEAN;

-- InvestigationFinding: Findings from investigations
CREATE TYPE IF NOT EXISTS InvestigationFinding EXTENDS Vertex;
CREATE PROPERTY IF NOT EXISTS InvestigationFinding.node_id STRING;
CREATE PROPERTY IF NOT EXISTS InvestigationFinding.node_type STRING;
CREATE PROPERTY IF NOT EXISTS InvestigationFinding.confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS InvestigationFinding.initial_confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS InvestigationFinding.decay_rate FLOAT;
CREATE PROPERTY IF NOT EXISTS InvestigationFinding.last_reinforced DATETIME;
CREATE PROPERTY IF NOT EXISTS InvestigationFinding.revalidation_required BOOLEAN;

-- CompetitorCapability: Observed competitor capabilities
CREATE TYPE IF NOT EXISTS CompetitorCapability EXTENDS Vertex;
CREATE PROPERTY IF NOT EXISTS CompetitorCapability.node_id STRING;
CREATE PROPERTY IF NOT EXISTS CompetitorCapability.node_type STRING;
CREATE PROPERTY IF NOT EXISTS CompetitorCapability.confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS CompetitorCapability.initial_confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS CompetitorCapability.decay_rate FLOAT;
CREATE PROPERTY IF NOT EXISTS CompetitorCapability.last_reinforced DATETIME;
CREATE PROPERTY IF NOT EXISTS CompetitorCapability.revalidation_required BOOLEAN;

-- CustomerTheme: Aggregated customer themes
CREATE TYPE IF NOT EXISTS CustomerTheme EXTENDS Vertex;
CREATE PROPERTY IF NOT EXISTS CustomerTheme.node_id STRING;
CREATE PROPERTY IF NOT EXISTS CustomerTheme.node_type STRING;
CREATE PROPERTY IF NOT EXISTS CustomerTheme.confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS CustomerTheme.initial_confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS CustomerTheme.decay_rate FLOAT;
CREATE PROPERTY IF NOT EXISTS CustomerTheme.last_reinforced DATETIME;
CREATE PROPERTY IF NOT EXISTS CustomerTheme.revalidation_required BOOLEAN;

-- CustomerSignal: Individual customer signals
CREATE TYPE IF NOT EXISTS CustomerSignal EXTENDS Vertex;
CREATE PROPERTY IF NOT EXISTS CustomerSignal.node_id STRING;
CREATE PROPERTY IF NOT EXISTS CustomerSignal.node_type STRING;
CREATE PROPERTY IF NOT EXISTS CustomerSignal.confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS CustomerSignal.initial_confidence FLOAT;
CREATE PROPERTY IF NOT EXISTS CustomerSignal.decay_rate FLOAT;
CREATE PROPERTY IF NOT EXISTS CustomerSignal.last_reinforced DATETIME;
CREATE PROPERTY IF NOT EXISTS CustomerSignal.revalidation_required BOOLEAN;

-- Edge types

-- DEPENDS_ON: ProductStructure -> ProductStructure
CREATE TYPE IF NOT EXISTS DEPENDS_ON EXTENDS Edge;

-- DECIDED_BY: DecisionRecord -> ProductStructure
CREATE TYPE IF NOT EXISTS DECIDED_BY EXTENDS Edge;

-- INVESTIGATED: InvestigationFinding -> ProductStructure or DecisionRecord
CREATE TYPE IF NOT EXISTS INVESTIGATED EXTENDS Edge;

-- OBSERVED: CompetitorCapability -> ProductStructure
CREATE TYPE IF NOT EXISTS OBSERVED EXTENDS Edge;

-- REPORTED_BY: CustomerTheme -> CustomerSignal
CREATE TYPE IF NOT EXISTS REPORTED_BY EXTENDS Edge;

-- NEGATIVE_KNOWLEDGE: InvestigationFinding -> InvestigationFinding (with reason)
CREATE TYPE IF NOT EXISTS NEGATIVE_KNOWLEDGE EXTENDS Edge;
CREATE PROPERTY IF NOT EXISTS NEGATIVE_KNOWLEDGE.reason STRING;
