"""
Email Manager for Assaultron AI
Provides secure email sending/reading with Discord logging and guardrails
Phase 2: Email Identity Implementation
"""

import os
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import logging
import requests
import threading
import time
import re


class EmailManager:
    """Manages AI email operations with security guardrails and Discord logging"""

    def __init__(self):
        # Email configuration from environment
        self.email_address = os.getenv("AI_EMAIL_ADDRESS", "")
        self.email_password = os.getenv("AI_EMAIL_PASSWORD", "")
        self.smtp_server = os.getenv("SMTP_SERVER", "mail.planethoster.net")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.imap_server = os.getenv("IMAP_SERVER", "mail.planethoster.net")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        self.enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"

        # Discord logging
        self.log_webhook_url = os.getenv("DISCORD_LOG_URL", "")

        # Rate limiting
        self.rate_limit = int(os.getenv("EMAIL_RATE_LIMIT", "10"))  # emails per hour
        self.email_timestamps = []
        self.rate_limit_lock = threading.Lock()

        # Allowed domains (comma-separated in .env)
        allowed_domains_str = os.getenv("ALLOWED_EMAIL_DOMAINS", "")
        self.allowed_domains = [d.strip() for d in allowed_domains_str.split(",") if d.strip()]

        # Logging
        self.logger = logging.getLogger('assaultron.email')

        # Validation
        if self.enabled and not self._validate_config():
            self.logger.error("Email configuration incomplete - email functionality disabled")
            self.enabled = False

    def _validate_config(self) -> bool:
        """Validate email configuration"""
        if not self.email_address or not self.email_password:
            self.logger.error("Email address or password not configured")
            return False
        if not self.smtp_server or not self.imap_server:
            self.logger.error("SMTP/IMAP server not configured")
            return False
        if not self.log_webhook_url:
            self.logger.warning("Discord log webhook not configured - logging disabled")
        return True

    def _check_rate_limit(self) -> Tuple[bool, int]:
        """
        Check if rate limit allows sending email

        Returns:
            (can_send: bool, emails_sent_in_window: int)
        """
        with self.rate_limit_lock:
            current_time = time.time()
            # Remove timestamps older than 1 hour
            self.email_timestamps = [t for t in self.email_timestamps if current_time - t < 3600]

            if len(self.email_timestamps) >= self.rate_limit:
                return False, len(self.email_timestamps)

            return True, len(self.email_timestamps)

    def _record_email_sent(self):
        """Record timestamp of sent email for rate limiting"""
        with self.rate_limit_lock:
            self.email_timestamps.append(time.time())

    def _validate_domain(self, email_address: str) -> bool:
        """
        Validate email domain against allowed list

        Args:
            email_address: Email to validate

        Returns:
            True if domain allowed or no restrictions set
        """
        # If no allowed domains specified, allow all
        if not self.allowed_domains:
            return True

        # Extract domain from email
        match = re.search(r'@([\w\.-]+)$', email_address)
        if not match:
            return False

        domain = match.group(1).lower()

        # Check if domain is in allowed list
        return domain in [d.lower() for d in self.allowed_domains]

    def _log_to_discord(self, action: str, details: Dict, success: bool = True, error: Optional[str] = None):
        """
        Log email activity to Discord #logs channel

        Args:
            action: Action performed (e.g., "send_email", "read_email")
            details: Details dict (to, from, subject, etc.)
            success: Whether action succeeded
            error: Error message if failed
        """
        if not self.log_webhook_url:
            return

        try:
            # Create embed
            color = 0x00ff00 if success else 0xff0000  # Green for success, red for error

            # Build description
            description_parts = []
            for key, value in details.items():
                description_parts.append(f"**{key.title()}:** {value}")

            if error:
                description_parts.append(f"\n**Error:** {error}")

            description = "\n".join(description_parts)

            embed = {
                "title": f"📧 Email {action.replace('_', ' ').title()}",
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": f"Assaultron AI - Email Manager"
                }
            }

            payload = {
                "username": "Assaultron AI - Email Log",
                "embeds": [embed]
            }

            response = requests.post(
                self.log_webhook_url,
                json=payload,
                timeout=5
            )

            if response.status_code not in [200, 204]:
                self.logger.error(f"Discord log webhook failed: {response.status_code}")

        except Exception as e:
            self.logger.exception(f"Failed to log to Discord: {e}")

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Send an email with guardrails and logging

        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            body_html: Optional HTML body

        Returns:
            (success: bool, error_message: Optional[str])
        """
        # Check if enabled
        if not self.enabled:
            error = "Email functionality is disabled"
            self.logger.warning(error)
            return False, error

        # Validate recipient domain
        if not self._validate_domain(to):
            error = f"Domain not allowed: {to}"
            self.logger.warning(error)
            self._log_to_discord("send_email", {
                "to": to,
                "subject": subject,
                "status": "blocked"
            }, success=False, error=error)
            return False, error

        # Check rate limit
        can_send, count = self._check_rate_limit()
        if not can_send:
            error = f"Rate limit exceeded: {count}/{self.rate_limit} emails sent in last hour"
            self.logger.warning(error)
            self._log_to_discord("send_email", {
                "to": to,
                "subject": subject,
                "status": "rate_limited"
            }, success=False, error=error)
            return False, error

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_address
            msg['To'] = to
            msg['Subject'] = subject
            msg['Date'] = email.utils.formatdate(localtime=True)

            # Attach plain text
            msg.attach(MIMEText(body, 'plain'))

            # Attach HTML if provided
            if body_html:
                msg.attach(MIMEText(body_html, 'html'))

            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)

            # Record successful send
            self._record_email_sent()

            # Log to Discord
            self._log_to_discord("send_email", {
                "to": to,
                "subject": subject,
                "body_length": f"{len(body)} chars",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, success=True)

            self.logger.info(f"Email sent successfully to {to}")
            return True, None

        except Exception as e:
            error = str(e)
            self.logger.exception(f"Failed to send email: {e}")
            self._log_to_discord("send_email", {
                "to": to,
                "subject": subject
            }, success=False, error=error)
            return False, error

    def read_emails(
        self,
        folder: str = "INBOX",
        limit: int = 10,
        unread_only: bool = True
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Read emails from IMAP server

        Args:
            folder: IMAP folder to read from (default: INBOX)
            limit: Maximum number of emails to fetch
            unread_only: Only fetch unread emails

        Returns:
            (emails: List[Dict], error_message: Optional[str])
        """
        # Check if enabled
        if not self.enabled:
            error = "Email functionality is disabled"
            self.logger.warning(error)
            return [], error

        try:
            # Connect to IMAP server
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as mail:
                mail.login(self.email_address, self.email_password)
                mail.select(folder)

                # Search for emails
                search_criteria = "UNSEEN" if unread_only else "ALL"
                status, messages = mail.search(None, search_criteria)

                if status != "OK":
                    error = "Failed to search emails"
                    self.logger.error(error)
                    return [], error

                email_ids = messages[0].split()
                email_ids = email_ids[-limit:]  # Get most recent emails

                emails = []
                for email_id in email_ids:
                    # Fetch email
                    status, msg_data = mail.fetch(email_id, "(RFC822)")

                    if status != "OK":
                        continue

                    # Parse email
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Extract body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = msg.get_payload(decode=True).decode()

                    emails.append({
                        "id": email_id.decode(),
                        "from": msg.get("From", ""),
                        "to": msg.get("To", ""),
                        "subject": msg.get("Subject", ""),
                        "date": msg.get("Date", ""),
                        "body": body[:500]  # Limit body preview to 500 chars
                    })

                # Log to Discord
                self._log_to_discord("read_emails", {
                    "folder": folder,
                    "count": len(emails),
                    "unread_only": str(unread_only),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, success=True)

                self.logger.info(f"Read {len(emails)} emails from {folder}")
                return emails, None

        except Exception as e:
            error = str(e)
            self.logger.exception(f"Failed to read emails: {e}")
            self._log_to_discord("read_emails", {
                "folder": folder
            }, success=False, error=error)
            return [], error

    def get_status(self) -> Dict:
        """Get email manager status"""
        can_send, count = self._check_rate_limit()

        return {
            "enabled": self.enabled,
            "email_address": self.email_address if self.enabled else "Not configured",
            "smtp_server": self.smtp_server,
            "rate_limit": f"{count}/{self.rate_limit} per hour",
            "can_send": can_send,
            "allowed_domains": self.allowed_domains if self.allowed_domains else ["All domains allowed"],
            "logging_enabled": bool(self.log_webhook_url)
        }


# Global instance
email_manager = None


def get_email_manager() -> EmailManager:
    """Get or create global email manager instance"""
    global email_manager
    if email_manager is None:
        email_manager = EmailManager()
    return email_manager
