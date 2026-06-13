# ── Secrets from AWS Secrets Manager ────────────────────────────────────
data "aws_secretsmanager_secret_version" "arcadedb" {
  secret_id = var.arcadedb_secret_name
}

data "aws_secretsmanager_secret_version" "postgres" {
  secret_id = var.postgres_secret_name
}

locals {
  arcadedb_password = jsondecode(data.aws_secretsmanager_secret_version.arcadedb.secret_string)["password"]
  postgres_password = jsondecode(data.aws_secretsmanager_secret_version.postgres.secret_string)["password"]
  postgres_url      = "postgresql://agent_ops:${local.postgres_password}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/agent_operations"
  langfuse_env = {
    LANGFUSE_PUBLIC_KEY = var.langfuse_public_key
    LANGFUSE_SECRET_KEY = var.langfuse_secret_key
    LANGFUSE_HOST       = var.langfuse_host
  }
}
