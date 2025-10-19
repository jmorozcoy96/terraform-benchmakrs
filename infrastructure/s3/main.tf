terraform {
  backend "s3" {
    encrypt = true
    bucket  = "juan-orozco-state-bucket"
    key     = "benchmark"
    region  = "us-east-1"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.83"
    }
  }
}

variable "prefix" {
  description = "Prefix for the bucket"
  type        = string
}


resource "aws_s3_bucket" "create_bucket" {
  bucket        = "${var.prefix}-${random_id.server.hex}"
  force_destroy = true

}

resource "random_id" "server" {

  byte_length = 8
}