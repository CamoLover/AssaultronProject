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

        # Email signature configuration
        self.signature_enabled = os.getenv("EMAIL_SIGNATURE_ENABLED", "true").lower() == "true"
        self.ai_name = os.getenv("AI_NAME", "Assaultron AI")
        self.signature = self._generate_signature()

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

    def _generate_signature(self) -> Dict[str, str]:
        """
        Generate email signature in both plain text and HTML formats

        Returns:
            Dict with 'plain' and 'html' signature versions
        """
        plain_signature = f"\n\n---\n{self.ai_name}\nAutonomous AI Assistant\nEmail: {self.email_address}\nPowered by Camolover"

        html_signature = f"""
        <br><br>
        <div style="border-top: 1px solid #ccc; padding-top: 10px; margin-top: 20px; font-family: Arial, sans-serif; color: #555;">
            <strong style="color: #2c3e50;">{self.ai_name}</strong><br>
            <span style="font-size: 12px;">Autonomous AI Assistant</span><br>
            <span style="font-size: 12px;">Email: <a href="mailto:{self.email_address}" style="color: #3498db;">{self.email_address}</a></span><br>
            <span style="font-size: 11px; color: #888;">Powered by Camolover</span>
        </div>
        """

        return {
            'plain': plain_signature,
            'html': html_signature
        }

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
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        add_signature: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Send an email with guardrails and logging

        Args:
            to: Recipient email address (can be comma-separated list)
            subject: Email subject
            body: Plain text body
            body_html: Optional HTML body
            cc: Optional list of CC recipients
            bcc: Optional list of BCC recipients
            add_signature: Whether to add automatic signature (default: True)

        Returns:
            (success: bool, error_message: Optional[str])
        """
        # Check if enabled
        if not self.enabled:
            error = "Email functionality is disabled"
            self.logger.warning(error)
            return False, error

        # Parse recipients
        to_list = [addr.strip() for addr in to.split(',')] if isinstance(to, str) else to
        cc_list = cc if cc else []
        bcc_list = bcc if bcc else []

        # Validate all recipient domains
        all_recipients = to_list + cc_list + bcc_list
        for recipient in all_recipients:
            if not self._validate_domain(recipient):
                error = f"Domain not allowed: {recipient}"
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
            # Add signature if enabled
            final_body = body
            final_body_html = body_html

            if add_signature and self.signature_enabled:
                final_body = body + self.signature['plain']
                if body_html:
                    final_body_html = body_html + self.signature['html']

            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_address
            msg['To'] = ', '.join(to_list)
            if cc_list:
                msg['Cc'] = ', '.join(cc_list)
            msg['Subject'] = subject
            msg['Date'] = email.utils.formatdate(localtime=True)

            # Attach plain text
            msg.attach(MIMEText(final_body, 'plain'))

            # Attach HTML if provided
            if final_body_html:
                msg.attach(MIMEText(final_body_html, 'html'))

            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)

            # Record successful send
            self._record_email_sent()

            # Log to Discord
            log_details = {
                "to": to,
                "subject": subject,
                "body_length": f"{len(body)} chars",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            if cc_list:
                log_details["cc"] = ', '.join(cc_list)
            if bcc_list:
                log_details["bcc"] = f"{len(bcc_list)} recipient(s)"

            self._log_to_discord("send_email", log_details, success=True)

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

    def reply_to_email(
        self,
        original_email_id: str,
        reply_body: str,
        reply_body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        folder: str = "INBOX"
    ) -> Tuple[bool, Optional[str]]:
        """
        Reply to an existing email

        Args:
            original_email_id: ID of the email to reply to
            reply_body: Plain text reply body
            reply_body_html: Optional HTML reply body
            cc: Optional list of CC recipients
            folder: IMAP folder containing the original email

        Returns:
            (success: bool, error_message: Optional[str])
        """
        try:
            # First, fetch the original email to get details
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as mail:
                mail.login(self.email_address, self.email_password)
                mail.select(folder)

                # Fetch the original email
                status, msg_data = mail.fetch(original_email_id.encode(), "(RFC822)")

                if status != "OK":
                    return False, "Failed to fetch original email"

                # Parse original email
                raw_email = msg_data[0][1]
                original_msg = email.message_from_bytes(raw_email)

                # Extract original details
                original_from = original_msg.get("From", "")
                original_subject = original_msg.get("Subject", "")
                original_date = original_msg.get("Date", "")
                original_message_id = original_msg.get("Message-ID", "")

                # Extract original body for quoting
                original_body = ""
                if original_msg.is_multipart():
                    for part in original_msg.walk():
                        if part.get_content_type() == "text/plain":
                            original_body = part.get_payload(decode=True).decode()
                            break
                else:
                    original_body = original_msg.get_payload(decode=True).decode()

            # Prepare reply subject
            reply_subject = original_subject
            if not reply_subject.lower().startswith("re:"):
                reply_subject = f"Re: {reply_subject}"

            # Quote original message in plain text
            quoted_body = f"{reply_body}\n\n" + "On " + original_date + ", " + original_from + " wrote:\n"
            quoted_body += "\n".join(["> " + line for line in original_body.split("\n")])

            # Quote original message in HTML (if HTML reply provided)
            quoted_html = None
            if reply_body_html:
                quoted_html = f"{reply_body_html}<br><br><div style='border-left: 2px solid #ccc; padding-left: 10px; margin-left: 10px;'>"
                quoted_html += f"<p><strong>On {original_date}, {original_from} wrote:</strong></p>"
                quoted_html += f"<p>{original_body.replace(chr(10), '<br>')}</p></div>"

            # Send the reply using send_email
            success, error = self.send_email(
                to=original_from,
                subject=reply_subject,
                body=quoted_body,
                body_html=quoted_html,
                cc=cc,
                add_signature=True
            )

            if success:
                self.logger.info(f"Reply sent successfully to {original_from}")

            return success, error

        except Exception as e:
            error = str(e)
            self.logger.exception(f"Failed to reply to email: {e}")
            return False, error

    def forward_email(
        self,
        original_email_id: str,
        to: str,
        forward_message: Optional[str] = None,
        cc: Optional[List[str]] = None,
        folder: str = "INBOX"
    ) -> Tuple[bool, Optional[str]]:
        """
        Forward an existing email to another recipient

        Args:
            original_email_id: ID of the email to forward
            to: Recipient email address
            forward_message: Optional message to add before the forwarded content
            cc: Optional list of CC recipients
            folder: IMAP folder containing the original email

        Returns:
            (success: bool, error_message: Optional[str])
        """
        try:
            # Fetch the original email
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as mail:
                mail.login(self.email_address, self.email_password)
                mail.select(folder)

                status, msg_data = mail.fetch(original_email_id.encode(), "(RFC822)")

                if status != "OK":
                    return False, "Failed to fetch original email"

                # Parse original email
                raw_email = msg_data[0][1]
                original_msg = email.message_from_bytes(raw_email)

                # Extract original details
                original_from = original_msg.get("From", "")
                original_to = original_msg.get("To", "")
                original_subject = original_msg.get("Subject", "")
                original_date = original_msg.get("Date", "")

                # Extract original body
                original_body = ""
                if original_msg.is_multipart():
                    for part in original_msg.walk():
                        if part.get_content_type() == "text/plain":
                            original_body = part.get_payload(decode=True).decode()
                            break
                else:
                    original_body = original_msg.get_payload(decode=True).decode()

            # Prepare forward subject
            forward_subject = original_subject
            if not forward_subject.lower().startswith("fwd:"):
                forward_subject = f"Fwd: {forward_subject}"

            # Build forwarded message body
            forward_body = ""
            if forward_message:
                forward_body = f"{forward_message}\n\n"

            forward_body += "---------- Forwarded message ---------\n"
            forward_body += f"From: {original_from}\n"
            forward_body += f"Date: {original_date}\n"
            forward_body += f"Subject: {original_subject}\n"
            forward_body += f"To: {original_to}\n\n"
            forward_body += original_body

            # Build HTML version
            forward_html = ""
            if forward_message:
                forward_html = f"<p>{forward_message}</p><br>"

            forward_html += "<div style='border-top: 1px solid #ccc; margin-top: 20px; padding-top: 10px;'>"
            forward_html += "<p><strong>---------- Forwarded message ---------</strong></p>"
            forward_html += f"<p><strong>From:</strong> {original_from}<br>"
            forward_html += f"<strong>Date:</strong> {original_date}<br>"
            forward_html += f"<strong>Subject:</strong> {original_subject}<br>"
            forward_html += f"<strong>To:</strong> {original_to}</p>"
            forward_html += f"<p>{original_body.replace(chr(10), '<br>')}</p></div>"

            # Send the forwarded email
            success, error = self.send_email(
                to=to,
                subject=forward_subject,
                body=forward_body,
                body_html=forward_html,
                cc=cc,
                add_signature=True
            )

            if success:
                self.logger.info(f"Email forwarded successfully to {to}")
                self._log_to_discord("forward_email", {
                    "original_from": original_from,
                    "forwarded_to": to,
                    "subject": forward_subject
                }, success=True)

            return success, error

        except Exception as e:
            error = str(e)
            self.logger.exception(f"Failed to forward email: {e}")
            self._log_to_discord("forward_email", {
                "email_id": original_email_id,
                "to": to
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
