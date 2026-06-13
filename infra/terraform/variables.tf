variable "aws_region" {
  description = "AWS region"
  default     = "us-east-1"
}
variable "openrouter_api_key" {
  description = "OpenRouter API key for agent LLM calls"
  type        = string
  sensitive   = true
}
variable "langfuse_public_key" {
  description = "Langfuse public key for tracing"
  type        = string
  sensitive   = true
}
variable "langfuse_secret_key" {
  description = "Langfuse secret key for tracing"
  type        = string
  sensitive   = true
}
variable "langfuse_host" {
  description = "Langfuse host URL"
  type        = string
  default     = "https://cloud.langfuse.com"
}
variable "arcadedb_secret_name" {
  description = "Secrets Manager secret name for ArcadeDB password"
  default     = "agent-ops/arcadedb"
}
variable "postgres_secret_name" {
  description = "Secrets Manager secret name for PostgreSQL password"
  default     = "agent-ops/postgres"
}
