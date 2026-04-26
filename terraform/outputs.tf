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

output "deploy_instructions" {
  description = "Next steps after terraform apply"
  value       = <<-EOT
    1. Deploy the app:
       bash scripts/deploy.sh ${aws_eip.vello.public_ip} ~/.ssh/vello.pem

    2. SSH in and fill secrets:
       ssh -i ~/.ssh/vello.pem ubuntu@${aws_eip.vello.public_ip}
       nano /opt/vello/.env

    3. Set up SSL (after DNS propagates ~2 min):
       bash scripts/setup-ssl.sh vello.flexflows.net your@email.com
  EOT
}
