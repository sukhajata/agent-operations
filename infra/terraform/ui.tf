# ── Lambda: approval UI ────────────────────────────────────────────────
resource "aws_lambda_function" "ui" {
  function_name = "agent-ops-ui"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.langgraph_agents.repository_url}:latest"
  architectures = ["arm64"]
  timeout       = 30
  memory_size   = 256
  environment {
    variables = merge({
      LAMBDA_HANDLER    = "ui"
      UI_USERNAME       = "admin"
      UI_PASSWORD       = var.ui_password
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
  count = var.enable_cloudfront ? 1 : 0
  name                              = "s3-ui-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "ui" {
  count = var.enable_cloudfront ? 1 : 0
  # S3 origin for static files
  origin {
    domain_name              = aws_s3_bucket.ui_assets.bucket_regional_domain_name
    origin_id                = "s3-static"
    origin_access_control_id = aws_cloudfront_origin_access_control.s3[0].id
  }
  # Lambda origin for API
  origin {
    domain_name = element(split("/", trimprefix(aws_lambda_function_url.ui.function_url, "https://")), 0)
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
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6"  # CachingOptimized
  }
  # Route /api/* to Lambda
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "lambda-api"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"  # CachingDisabled
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"  # AllViewerExceptHostHeader
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
  value       = var.enable_cloudfront ? aws_cloudfront_distribution.ui[0].domain_name : aws_lambda_function_url.ui.function_url
  description = "CloudFront distribution domain name"
}

output "ui_assets_bucket" {
  value       = aws_s3_bucket.ui_assets.bucket
  description = "S3 bucket name for UI static assets"
}

output "cloudfront_distribution_id" {
  value       = var.enable_cloudfront ? aws_cloudfront_distribution.ui[0].id : "disabled"
  description = "CloudFront distribution ID for cache invalidation"
}
