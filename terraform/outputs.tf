output "server_ip" {
  description = "Public IP of the Vello server"
  value       = aws_eip.vello.public_ip
}

output "domain" {
  description = "Application domain"
  value       = "vello.flexflows.net"
}

output "ssh_command" {
  description = "SSH command to connect to the server"
  value       = "ssh -i ~/.ssh/vello.pem ubuntu@${aws_eip.vello.public_ip}"
}

output "app_url" {
  description = "Application URL"
  value       = "https://vello.flexflows.net"
}

output "ses_sender_domain" {
  description = "Verified SES domain — use *@<this> as the sender"
  value       = aws_ses_domain_identity.vello.domain
}

output "instance_profile" {
  description = "IAM instance profile attached to the EC2 (grants SES + optional S3)"
  value       = aws_iam_instance_profile.vello.name
}

output "deploy_instructions" {
  description = "Next steps after terraform apply"
  value       = <<-EOT
    1. Deploy the app:
       bash scripts/deploy.sh ${aws_eip.vello.public_ip} ~/.ssh/vello.pem

    2. SSH in and fill secrets:
       ssh -i ~/.ssh/vello.pem ubuntu@${aws_eip.vello.public_ip}
       nano /opt/vello/.env

       AWS credentials are NOT needed in .env — the EC2 instance profile
       (${aws_iam_instance_profile.vello.name}) provides ses:SendEmail
       automatically. Just set ANTHROPIC_API_KEY, SECRET_KEY, etc.

    3. Set up SSL (after DNS propagates ~2 min):
       bash scripts/setup-ssl.sh vello.flexflows.net your@email.com

    4. Verify SES is working:
       aws ses get-identity-verification-attributes \\
           --identities ${aws_ses_domain_identity.vello.domain} \\
           --region ${var.aws_region}
       Status should be "Success".
  EOT
}
