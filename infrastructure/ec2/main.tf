
variable "prefix" {
  description = "Prefix for the resources"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket used for deployment"
  type        = string
}

variable "instance_type" {
  description = "Instance type to use"
  type        = string
  default     = "m5.2xlarge"
}

variable "key_name" {
  description = "EC2 key pair name for SSH access"
  type        = string
}

data "aws_ami" "ubuntu_2204" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_security_group" "server" {
  # evita colisiones de nombre usando prefijo
  name_prefix = "${var.prefix}-server-"
  description = "Security group for the server"

  # SSH desde cualquier lugar (ajusta a tu IP si quieres más seguro)
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Egreso a todo
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "this" {
  name = "${var.prefix}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "s3_read" {
  name        = "s3-read-policy-${var.prefix}"
  description = "Allows EC2 instances to read from specified S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect: "Allow",
      Action: ["s3:GetObject", "s3:ListBucket"],
      Resource: [
        "arn:aws:s3:::${var.bucket_name}",
        "arn:aws:s3:::${var.bucket_name}/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "s3_read_attach" {
  role       = aws_iam_role.this.name
  policy_arn = aws_iam_policy.s3_read.arn
}

resource "aws_iam_role_policy_attachment" "ssm_core_attachment" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "this" {
  name = "${var.prefix}-ec2-profile"
  role = aws_iam_role.this.name
}

resource "aws_instance" "this" {
  ami                         = data.aws_ami.ubuntu_2204.id
  instance_type               = var.instance_type
  key_name                    = var.key_name
  vpc_security_group_ids      = [aws_security_group.server.id]
  associate_public_ip_address = true

  iam_instance_profile        = aws_iam_instance_profile.this.name
  user_data_replace_on_change = true

  user_data = <<-EOF
    #!/bin/bash
    set -euxo pipefail

    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3-pip python3-venv openjdk-11-jre-headless awscli \
      build-essential unzip zip

    python3 -m pip install --upgrade pip
    pip install uv pandas polars duckdb pyspark boto3

    # Workspace
    mkdir -p /home/ubuntu/Archive
    chown -R ubuntu:ubuntu /home/ubuntu/Archive

    # Bucket en entorno para comodidad
    echo 'export BUCKET=${var.bucket_name}' >> /home/ubuntu/.bashrc
  EOF

  tags = {
    Name = "${var.prefix}-server"
  }
}
