# ── AgentCore Runtime — coding agent executor ──────────────────────────
# AgentCore invokes the coding-agent-server when a job is ready.
# The orchestration Lambda POSTs to the AgentCore invocation endpoint.

resource "aws_ecr_repository" "coding_agent" {
  name                 = "agent-ops/coding-agent"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_bedrockagent_agent" "coding_agent" {
  agent_name              = "coding-agent"
  agent_resource_role_arn = aws_iam_role.agentcore_role.arn
  foundation_model        = "anthropic.claude-3-5-sonnet-20241022-v2:0"
  instruction             = "Execute approved implementation plans from the orchestration agent."
}

resource "aws_bedrockagent_agent_action_group" "main" {
  agent_id            = aws_bedrockagent_agent.coding_agent.id
  agent_version       = "DRAFT"
  action_group_name   = "coding-agent-actions"
  action_group_state  = "ENABLED"
  action_group_executor {
    lambda = aws_lambda_function.coding_agent_dispatcher.arn
  }
  function_schema {
    member_functions {
      functions {
        name        = "execute_task"
        description = "Execute an approved implementation task"
        parameters {
          map_block_key = "task"
          type          = "string"
          required      = true
          description   = "The task to execute"
        }
        parameters {
          map_block_key = "commitment_id"
          type          = "string"
          required      = true
          description   = "The commitment ID for this task"
        }
      }
    }
  }
}

resource "aws_lambda_function" "coding_agent_dispatcher" {
  function_name = "coding-agent-dispatcher"
  role          = aws_iam_role.agentcore_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.coding_agent.repository_url}:latest"
  architectures = ["arm64"]
  timeout       = 900
  memory_size   = 2048
  environment {
    variables = merge({
      ARCADEDB_URL      = "http://${aws_instance.arcadedb.private_ip}:2480"
      ARCADEDB_DATABASE = "agent_operations"
      ARCADEDB_USER     = "root"
      ARCADEDB_PASSWORD = local.arcadedb_password
      POSTGRES_URL       = local.postgres_url
      LLM_API_KEY        = var.openrouter_api_key
    }, local.langfuse_env)
  }
  vpc_config {
    subnet_ids         = [aws_subnet.private_a.id]
    security_group_ids = [aws_security_group.lambda_to_arcadedb.id]
  }
}

resource "aws_iam_role" "agentcore_role" {
  name = "agentcore-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = ["lambda.amazonaws.com", "bedrock.amazonaws.com"]
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "agentcore_logs" {
  role       = aws_iam_role.agentcore_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "agentcore_vpc" {
  name = "agentcore-vpc"
  role = aws_iam_role.agentcore_role.id
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

resource "aws_iam_role_policy" "agentcore_bedrock" {
  name = "agentcore-bedrock-invoke"
  role = aws_iam_role.agentcore_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "bedrock:InvokeModel"
      Resource = [
        "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude*",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude*",
      ]
    }]
  })
}

# ── AgentCore Runtime — exploratory agent executor ─────────────────────
# AgentCore invokes the exploratory agent when the Lambda dispatcher triggers it.
# The explore Lambda reads mandates from ArcadeDB and invokes this agent for each mandate.

resource "aws_bedrockagent_agent" "exploratory_agent" {
  agent_name              = "exploratory-agent"
  agent_resource_role_arn = aws_iam_role.agentcore_role.arn
  foundation_model        = "anthropic.claude-3-5-sonnet-20241022-v2:0"
  instruction             = "Execute exploratory mandates by investigating domains and emitting novel signals for review."
}

resource "aws_bedrockagent_agent_action_group" "exploratory_actions" {
  agent_id            = aws_bedrockagent_agent.exploratory_agent.id
  agent_version       = "DRAFT"
  action_group_name   = "exploratory-agent-actions"
  action_group_state  = "ENABLED"
  action_group_executor {
    lambda = aws_lambda_function.exploratory_agent_dispatcher.arn
  }
  function_schema {
    member_functions {
      functions {
        name        = "run_mandate"
        description = "Execute an exploratory mandate and return signals"
        parameters {
          map_block_key = "mandate_name"
          type          = "string"
          required      = true
          description   = "The mandate name to execute"
        }
        parameters {
          map_block_key = "domain"
          type          = "string"
          required      = true
          description   = "The domain to explore"
        }
        parameters {
          map_block_key = "agent_type"
          type          = "string"
          required      = false
          description   = "Agent type: free or focus"
        }
      }
    }
  }
}

resource "aws_lambda_function" "exploratory_agent_dispatcher" {
  function_name = "exploratory-agent-dispatcher"
  role          = aws_iam_role.agentcore_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.langgraph_agents.repository_url}:latest"
  architectures = ["arm64"]
  timeout       = 900
  memory_size   = 2048
  environment {
    variables = merge({
      ARCADEDB_URL      = "http://${aws_instance.arcadedb.private_ip}:2480"
      ARCADEDB_DATABASE = "agent_operations"
      ARCADEDB_USER     = "root"
      ARCADEDB_PASSWORD = local.arcadedb_password
      OPENROUTER_API_KEY = var.openrouter_api_key
      POSTGRES_URL       = local.postgres_url
      LAMBDA_HANDLER    = "explore-run"
    }, local.langfuse_env)
  }
  vpc_config {
    subnet_ids         = [aws_subnet.private_a.id]
    security_group_ids = [aws_security_group.lambda_to_arcadedb.id]
  }
}
