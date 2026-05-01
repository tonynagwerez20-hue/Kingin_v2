import smtplib
import ssl
from email.message import EmailMessage
import logging
from support.env_loader import get_env, get_int_env

logger = logging.getLogger("AlertManager")

class AlertManager:
    """
    Handles sending system alerts via Email (SMTP).
    """
    def __init__(self):
        self.smtp_server = get_env("SMTP_SERVER")
        self.smtp_port = get_int_env("SMTP_PORT", 587)
        self.smtp_user = get_env("SMTP_USER")
        self.smtp_password = get_env("SMTP_PASSWORD")
        self.recipient = get_env("SMTP_RECIPIENT", "tonynagwerez20@gmail.com")
        self.enabled = all([self.smtp_server, self.smtp_user, self.smtp_password, self.recipient])
        
        if not self.enabled:
            logger.warning("[AlertManager] Email alerts NOT configured. Set SMTP variables in .env")

    def send_email(self, subject: str, body: str):
        """
        Sends an email alert.
        """
        if not self.enabled:
            return False

        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['Subject'] = f"[HEDGE] {subject}"
            msg['From'] = self.smtp_user
            msg['To'] = self.recipient

            context = ssl.create_default_context()
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
                
            logger.info(f"[AlertManager] Email sent: {subject}")
            return True
        except Exception as e:
            logger.error(f"[AlertManager] Failed to send email: {e}")
            return False

# Global instance
alert_manager = AlertManager()
