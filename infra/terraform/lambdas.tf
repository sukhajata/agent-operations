# ── Lambda functions (scheduled + triggered) ──────────────────────────

# IAM role shared by all Lambda functions
resource "aws_iam_role" "lambda" {
  name = "agent-ops-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_vpc" {
  name = "lambda-vpc"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface",
      ]
      Resource = ["*"]
    }]
  })
}

resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "lambda-bedrock-invoke"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "bedrock:InvokeAgent"
      Resource = "*"
    }]
  })
}

# ── Lambda: orchestrate ────────────────────────────────────────────────
resource "aws_lambda_function" "orchestrate" {
  function_name = "agent-ops-orchestrate"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.langgraph_agents.repository_url}:latest"
  architectures = ["arm64"]
  timeout       = 300
  memory_size   = 512
  environment {
    variables = merge({
      ARCADEDB_URL        = "http://${aws_instance.arcadedb.private_ip}:2480"
      ARCADEDB_DATABASE   = "agent_operations"
      ARCADEDB_USER       = "root"
      ARCADEDB_PASSWORD   = local.arcadedb_password
      CODING_AGENT_ID    = aws_bedrockagent_agent.coding_agent.id
      LAMBDA_HANDLER      = "orchestrate"
    }, local.langfuse_env)
  }
  vpc_config {
    subnet_ids         = [aws_subnet.private_a.id]
    security_group_ids = [aws_security_group.lambda_to_arcadedb.id]
  }
}

resource "aws_cloudwatch_event_rule" "orchestrate_schedule" {
  name                = "orchestrate-every-1-hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "orchestrate_target" {
  rule      = aws_cloudwatch_event_rule.orchestrate_schedule.name
  target_id = "orchestrate"
  arn       = aws_lambda_function.orchestrate.arn
}

resource "aws_lambda_permission" "orchestrate_invoke" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orchestrate.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.orchestrate_schedule.arn
}

# ── Lambda: explore (dispatches mandates to AgentCore) ──────────────────
resource "aws_lambda_function" "explore" {
  function_name = "agent-ops-explore"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.langgraph_agents.repository_url}:latest"
  architectures = ["arm64"]
  timeout       = 300
  memory_size   = 512
  environment {
    variables = merge({
      ARCADEDB_URL       = "http://${aws_instance.arcadedb.private_ip}:2480"
      ARCADEDB_DATABASE  = "agent_operations"
      ARCADEDB_USER      = "root"
      ARCADEDB_PASSWORD  = local.arcadedb_password
      AGENTCORE_AGENT_ID = aws_bedrockagent_agent.exploratory_agent.id
      LAMBDA_HANDLER     = "explore-dispatcher"
    }, local.langfuse_env)
  }
  vpc_config {
    subnet_ids         = [aws_subnet.private_a.id]
    security_group_ids = [aws_security_group.lambda_to_arcadedb.id]
  }
}

resource "aws_cloudwatch_event_rule" "explore_schedule" {
  name                = "explore-every-12-hours"
  schedule_expression = "rate(12 hours)"
}

resource "aws_cloudwatch_event_target" "explore_target" {
  rule      = aws_cloudwatch_event_rule.explore_schedule.name
  target_id = "explore"
  arn       = aws_lambda_function.explore.arn
}

resource "aws_lambda_permission" "explore_invoke" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.explore.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.explore_schedule.arn
}
# ── Lambda: verify (polling worker) ────────────────────────────────────
resource "aws_lambda_function" "verify" {
  function_name = "agent-ops-verify"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.langgraph_agents.repository_url}:latest"
  architectures = ["arm64"]
  timeout       = 300
  memory_size   = 1024
  environment {
    variables = merge({
      ARCADEDB_URL      = "http://${aws_instance.arcadedb.private_ip}:2480"
      ARCADEDB_DATABASE = "agent_operations"
      ARCADEDB_USER     = "root"
      ARCADEDB_PASSWORD = local.arcadedb_password
      OPENROUTER_API_KEY = var.openrouter_api_key
      POSTGRES_URL       = "postgresql://agent_ops:${local.postgres_password}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/agent_operations"
      LAMBDA_HANDLER    = "verify"
    }, local.langfuse_env)
  }
  vpc_config {
    subnet_ids         = [aws_subnet.private_a.id]
    security_group_ids = [aws_security_group.lambda_to_arcadedb.id]
  }
}

resource "aws_cloudwatch_event_rule" "verify_schedule" {
  name                = "verify-every-1-hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "verify_target" {
  rule      = aws_cloudwatch_event_rule.verify_schedule.name
  target_id = "verify"
  arn       = aws_lambda_function.verify.arn
}

resource "aws_lambda_permission" "verify_invoke" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.verify.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.verify_schedule.arn
}
# ── Lambda: migrate (one-shot schema migrations) ────────────────────────
resource "aws_lambda_function" "migrate" {
  function_name = "agent-ops-migrate"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.langgraph_agents.repository_url}:latest"
  timeout       = 120
  memory_size   = 256
  environment {
    variables = merge({
      ARCADEDB_URL      = "http://${aws_instance.arcadedb.private_ip}:2480"
      ARCADEDB_DATABASE = "agent_operations"
      ARCADEDB_USER     = "root"
      ARCADEDB_PASSWORD = local.arcadedb_password
      LAMBDA_HANDLER   = "migrate"
    }, local.langfuse_env)
  }
  vpc_config {
    subnet_ids         = [aws_subnet.private_a.id]
    security_group_ids = [aws_security_group.lambda_to_arcadedb.id]
  }
}

# ── ECR repo for the LangGraph agents image ────────────────────────────
resource "aws_ecr_repository" "langgraph_agents" {
  name                 = "agent-ops/langgraph-agents"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  lifecycle {
    prevent_destroy = false
  }
}
