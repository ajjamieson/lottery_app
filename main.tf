provider "aws" {
  region     = "us-east-1"
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.3.0"
}

resource "aws_dynamodb_table" "lottery_numbers" {
  name         = "LotteryNumbers"
  billing_mode = "PAY_PER_REQUEST"

  attribute {
    name = "lottery_number"
    type = "S"
  }

  hash_key = "lottery_number"
}

resource "aws_iam_role" "lambda_exec" {
  name = "lottery_lambda_exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action   = "ses:SendEmail"
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "dynamodb:GetItem"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:dynamodb:*:*:table/${aws_dynamodb_table.lottery_numbers.name}"
      }
    ]
  })
}

resource "aws_lambda_function" "lottery_checker" {
  function_name = "lottery_checker"
  runtime       = "python3.9"
  handler       = "lottery_checker.lambda_handler"
  role          = aws_iam_role.lambda_exec.arn

  # Reference the local ZIP file
  filename = "${path.module}/lottery_checker.zip"

  # Include a code hash to trigger updates on changes
  source_code_hash = filebase64sha256("${path.module}/lottery_checker.zip")

  environment {
    variables = {
      MAGAYO_API_KEY = "J9Cf2pWtpLw4xPEmVh"
      MAGAYO_GAME_ID = "us_pa_pick3_eve"
      DDB_TABLE_NAME = "LotteryNumbers"
    }
  }
}

# Example: Schedule the Lambda to run at 7:05 PM EST (12:05 AM UTC)
resource "aws_cloudwatch_event_rule" "daily_trigger" {
  name                = "daily_lottery_trigger"
  schedule_expression = "cron(5 0 * * ? *)" # 12:05 AM UTC
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_trigger.name
  target_id = "lambda"
  arn       = aws_lambda_function.lottery_checker.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lottery_checker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_trigger.arn
}
