# ── ArcadeDB on EC2 ────────────────────────────────────────────────────
resource "aws_instance" "arcadedb" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.medium"
  subnet_id              = aws_subnet.private_a.id
  vpc_security_group_ids = [aws_security_group.arcadedb.id]
  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }
  user_data = <<-EOF
    #!/bin/bash
    docker run -d --restart always \
      -p 2480:2480 -p 2424:2424 \
      -v /data/arcadedb:/home/arcadedb/databases \
      -e ARCADEDB_ROOT_PASSWORD="${local.arcadedb_password}" \
      arcadedata/arcadedb:latest
  EOF
  tags = { Name = "agent-ops-arcadedb" }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  owners = ["099720109477"] # Canonical
}

output "arcadedb_private_ip" {
  value = aws_instance.arcadedb.private_ip
}
