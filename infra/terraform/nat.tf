# ── NAT Instance ─────────────────────────────────────────────────────────
# t3.nano NAT instance routing private subnets to internet (~$4/mo vs ~$32 for NAT Gateway)

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "agent-ops-nat-eip" }
}

resource "aws_security_group" "nat" {
  name   = "nat-instance"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/16"]
    description = "Allow all VPC-internal traffic to reach NAT"
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "agent-ops-nat-sg" }
}

data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-minimal-kernel-6.1-arm64"
}

resource "aws_instance" "nat" {
  ami                    = data.aws_ssm_parameter.al2023_arm64.value
  instance_type          = "t4g.nano"
  subnet_id              = aws_subnet.public_a.id
  vpc_security_group_ids = [aws_security_group.nat.id]
  source_dest_check      = false
  user_data = <<-EOF
    #!/bin/bash
    dnf install -y iptables-services
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.d/99-nat.conf
    sysctl -p /etc/sysctl.d/99-nat.conf
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    sysctl -p
  EOF
  metadata_options {
    http_tokens = "required"
  }
  tags = { Name = "agent-ops-nat" }
}

resource "aws_eip_association" "nat" {
  instance_id   = aws_instance.nat.id
  allocation_id = aws_eip.nat.id
}
