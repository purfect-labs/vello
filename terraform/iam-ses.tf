# ── IAM instance profile ──────────────────────────────────────────────────────
# Attaches to the EC2 so boto3 calls (SES for email, optional S3 for Litestream
# backups) authenticate without long-lived access keys in the .env file.

resource "aws_iam_role" "vello" {
  name = "${var.app_name}-instance-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = { Name = "${var.app_name}-instance-role" }
}

resource "aws_iam_instance_profile" "vello" {
  name = "${var.app_name}-instance-profile"
  role = aws_iam_role.vello.name
}

# AWS Systems Manager — gives the EC2 a registered SSM agent presence,
# enabling SSH-less ops (aws ssm start-session, parameter store reads).
# AmazonSSMManagedInstanceCore is the AWS-managed minimum-privilege policy.
resource "aws_iam_role_policy_attachment" "vello_ssm" {
  role       = aws_iam_role.vello.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Send-only SES policy, scoped to the verified sender domain. ses:SendRawEmail
# is included so future MIME / attachment use (calendar invites, etc.) works
# without re-applying terraform.
resource "aws_iam_role_policy" "ses_send" {
  name = "${var.app_name}-ses-send"
  role = aws_iam_role.vello.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ses:SendEmail",
        "ses:SendRawEmail",
      ]
      Resource = "*"
      Condition = {
        StringLike = { "ses:FromAddress" = "*@${var.sender_domain}" }
      }
    }]
  })
}

# Litestream S3 backup policy — only created when a bucket is configured.
# Keeps least-privilege scope: read/write/delete the named bucket only.
resource "aws_iam_role_policy" "litestream_s3" {
  count = var.litestream_bucket != "" ? 1 : 0
  name  = "${var.app_name}-litestream-s3"
  role  = aws_iam_role.vello.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
      ]
      Resource = [
        "arn:aws:s3:::${var.litestream_bucket}",
        "arn:aws:s3:::${var.litestream_bucket}/*",
      ]
    }]
  })
}

# ── SES domain identity for vello.flexflows.net ───────────────────────────────
# Production access at the account level was already requested manually; this
# adds the domain identity + DKIM CNAMEs so SES will accept sends from
# *@vello.flexflows.net.

resource "aws_ses_domain_identity" "vello" {
  domain = var.sender_domain
}

resource "aws_ses_domain_dkim" "vello" {
  domain = aws_ses_domain_identity.vello.domain
}

# Three CNAMEs published in Route 53 — SES rotates between them.
resource "aws_route53_record" "vello_dkim" {
  count   = 3
  zone_id = data.aws_route53_zone.flexflows.zone_id
  name    = "${aws_ses_domain_dkim.vello.dkim_tokens[count.index]}._domainkey.${var.sender_domain}"
  type    = "CNAME"
  ttl     = 300
  records = ["${aws_ses_domain_dkim.vello.dkim_tokens[count.index]}.dkim.amazonses.com"]
}

# Block until SES confirms ownership via DKIM. terraform apply will hang here
# briefly the first time (~30s) — that's expected.
resource "aws_ses_domain_identity_verification" "vello" {
  domain     = aws_ses_domain_identity.vello.id
  depends_on = [aws_route53_record.vello_dkim]
}

# SPF — tells receiving servers Amazon SES is authorized to send for this
# subdomain. Published at the same name as the A record; both records can
# coexist (different RRTypes).
resource "aws_route53_record" "vello_spf" {
  zone_id = data.aws_route53_zone.flexflows.zone_id
  name    = var.sender_domain
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:amazonses.com ~all"]
}

# DMARC — relaxed policy by default (no quarantine/reject) so misconfigured
# senders don't bounce silently. Tighten to p=quarantine or p=reject after
# observing a few weeks of SPF/DKIM alignment in real traffic.
resource "aws_route53_record" "vello_dmarc" {
  zone_id = data.aws_route53_zone.flexflows.zone_id
  name    = "_dmarc.${var.sender_domain}"
  type    = "TXT"
  ttl     = 300
  records = ["v=DMARC1; p=none;"]
}
