"""
Transactional email — verification + password reset, sent via AWS SES.

Mirror of Kortex's email pattern. SES is preferred over Resend because:
- production sending access already provisioned in this AWS account
- one less external vendor / billing relationship
- ~$0.10 per 1,000 emails vs Resend's tiered pricing

Requirements (managed in terraform):
  · vello.flexflows.net is a verified SES identity in AWS_REGION
  · DKIM CNAMEs are published in Route 53
  · The runtime has ses:SendEmail permission (instance profile on EC2,
    env vars or ~/.aws/credentials locally)

When SES is unreachable / credentials are missing the senders log a warning
and return False so the dev environment never crashes — the verification
or reset token is still written to the DB so a developer can complete the
flow manually from the URL.
"""
from __future__ import annotations

import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from vello.config import APP_URL, AWS_REGION, BRIEFING_FROM

log = logging.getLogger(__name__)


def _ses():
    return boto3.client("ses", region_name=AWS_REGION)


def _send(to: str, subject: str, html: str) -> bool:
    try:
        _ses().send_email(
            Source=BRIEFING_FROM,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body":    {"Html": {"Data": html, "Charset": "UTF-8"}},
            },
        )
        return True
    except NoCredentialsError:
        log.warning("AWS credentials missing — skipping email to %s (%s)", to, subject)
        return False
    except ClientError as exc:
        log.error("SES send failed: %s — to=%s subject=%s",
                  exc.response.get("Error", {}).get("Message", str(exc)), to, subject)
        return False
    except (BotoCoreError, Exception) as exc:
        log.error("SES send error: %s — to=%s subject=%s", exc, to, subject)
        return False


def send_verification_email(to: str, token: str) -> bool:
    verify_url = f"{APP_URL}/verify-email?token={token}"
    html = f"""<!DOCTYPE html>
<html><body style="font-family:Inter,system-ui,sans-serif;max-width:560px;margin:40px auto;color:#111">
  <h1 style="font-family:Georgia,serif;font-size:22px;font-weight:400">Verify your email for Vello</h1>
  <p>Click the link below to confirm this email address. The link expires in 24 hours.</p>
  <p><a href="{verify_url}" style="display:inline-block;padding:12px 22px;background:#f59e0b;color:#000;text-decoration:none;border-radius:6px;font-weight:600">Verify email</a></p>
  <p style="font-size:12px;color:#666">Or paste this URL into your browser:<br>{verify_url}</p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:11px;color:#999">If you didn't sign up for Vello, you can ignore this message.</p>
</body></html>"""
    return _send(to, "Verify your Vello email", html)


def send_password_reset_email(to: str, token: str) -> bool:
    reset_url = f"{APP_URL}/reset-password?token={token}"
    html = f"""<!DOCTYPE html>
<html><body style="font-family:Inter,system-ui,sans-serif;max-width:560px;margin:40px auto;color:#111">
  <h1 style="font-family:Georgia,serif;font-size:22px;font-weight:400">Reset your Vello password</h1>
  <p>We received a request to reset your password. Click below to choose a new one. The link expires in 1 hour.</p>
  <p><a href="{reset_url}" style="display:inline-block;padding:12px 22px;background:#f59e0b;color:#000;text-decoration:none;border-radius:6px;font-weight:600">Reset password</a></p>
  <p style="font-size:12px;color:#666">Or paste this URL into your browser:<br>{reset_url}</p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:11px;color:#999">If you didn't request a reset, you can ignore this email — your password won't change.</p>
</body></html>"""
    return _send(to, "Reset your Vello password", html)
