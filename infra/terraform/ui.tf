# ── Lambda: approval UI ────────────────────────────────────────────────
resource "aws_lambda_function" "ui" {
  function_name = "agent-ops-ui"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.langgraph_agents.repository_url}:latest"
  timeout       = 30
  memory_size   = 256
  environment {
    variables = merge({
      LAMBDA_HANDLER    = "ui"
      UI_USERNAME       = "admin"
      UI_PASSWORD       = local.arcadedb_password
      ARCADEDB_URL      = "http://${aws_instance.arcadedb.private_ip}:2480"
      ARCADEDB_USER     = "root"
      ARCADEDB_PASSWORD = local.arcadedb_password
      OPENROUTER_API_KEY = var.openrouter_api_key
    }, local.langfuse_env)
  }
  vpc_config {
    subnet_ids         = [aws_subnet.private_a.id]
    security_group_ids = [aws_security_group.lambda_to_arcadedb.id]
  }
}

resource "aws_lambda_function_url" "ui" {
  function_name      = aws_lambda_function.ui.function_name
  authorization_type = "NONE"
}

output "ui_function_url" {
  value = aws_lambda_function_url.ui.function_url
}

# ── S3 + CloudFront for static assets ───────────────────────────────────
resource "aws_s3_bucket" "ui_assets" {
  bucket        = "agent-ops-ui-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "ui_assets" {
  bucket                  = aws_s3_bucket.ui_assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "s3" {
  name                              = "s3-ui-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "ui" {
  # S3 origin for static files
  origin {
    domain_name              = aws_s3_bucket.ui_assets.bucket_regional_domain_name
    origin_id                = "s3-static"
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }
  # Lambda origin for API
  origin {
    domain_name = replace(aws_lambda_function_url.ui.function_url, "/^https?://([^/]*).*/", "$1")
    origin_id   = "lambda-api"
    custom_origin_config {
      http_port              = 443
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  enabled             = true
  default_root_object = "index.html"
  default_cache_behavior {
    target_origin_id       = "s3-static"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }
  # Route /api/* to Lambda
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "lambda-api"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    forwarded_values {
      query_string = true
      cookies { forward = "all" }
    }
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  viewer_certificate {
    cloudfront_default_certificate = true
  }
  tags = { Name = "agent-ops-ui" }
}

output "ui_cloudfront_url" {
  value       = aws_cloudfront_distribution.ui.domain_name
  description = "CloudFront distribution domain name"
}

output "ui_assets_bucket" {
  value       = aws_s3_bucket.ui_assets.bucket
  description = "S3 bucket name for UI static assets"
}

output "cloudfront_distribution_id" {
  value       = aws_cloudfront_distribution.ui.id
  description = "CloudFront distribution ID for cache invalidation"
}
