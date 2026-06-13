# ── RDS PostgreSQL ─────────────────────────────────────────────────────
resource "aws_db_instance" "postgres" {
  identifier          = "agent-ops"
  engine              = "postgres"
  engine_version      = "16"
  instance_class      = "db.t4g.micro"
  allocated_storage   = 20
  storage_encrypted   = true
  db_name             = "agent_operations"
  username            = "agent_ops"
  password            = local.postgres_password
  publicly_accessible = false
  skip_final_snapshot = true
  vpc_security_group_ids = [aws_security_group.lambda_to_arcadedb.id]
  db_subnet_group_name = aws_db_subnet_group.main.name
  tags = { Name = "agent-ops-postgres" }
}

resource "aws_db_subnet_group" "main" {
  name       = "agent-ops-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  tags = { Name = "agent-ops-subnet-group" }
}

output "postgres_endpoint" {
  value = aws_db_instance.postgres.endpoint
}
