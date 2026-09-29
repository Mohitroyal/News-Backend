import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.core.config import settings
import structlog

logger = structlog.get_logger()

class EmailService:
    @property
    def smtp_host(self):
        return settings.SMTP_HOST

    @property
    def smtp_port(self):
        return settings.SMTP_PORT

    @property
    def smtp_user(self):
        return settings.SMTP_USER

    @property
    def smtp_password(self):
        return settings.SMTP_PASSWORD

    @property
    def smtp_tls(self):
        return settings.SMTP_TLS

    @property
    def from_email(self):
        return settings.EMAILS_FROM_EMAIL or "noreply@newscraft.ai"

    def send_clipping_status_email(
        self,
        user_email: str,
        headline: str,
        status: str,
        png_url: Optional[str] = None,
        pdf_url: Optional[str] = None
    ) -> bool:
        """
        Sends an email notification to the user about their newspaper clipping generation status.
        If SMTP is not configured, it prints a debug message to stdout with the email details.
        """
        subject = f"NewsCraft AI — Clipping Ready: {headline}" if status == "completed" else f"NewsCraft AI — Clipping Failed: {headline}"
        
        # Premium HTML Template
        if status == "completed":
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Newspaper Clipping Ready</title>
                <style>
                    body {{
                        margin: 0;
                        padding: 0;
                        background-color: #0A0A0A;
                        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        color: #E5E5E5;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 40px auto;
                        padding: 32px;
                        background-color: #121212;
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        border-radius: 16px;
                        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                    }}
                    .logo {{
                        font-size: 24px;
                        font-weight: 800;
                        color: #FFFFFF;
                        letter-spacing: -0.5px;
                        margin-bottom: 24px;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }}
                    .logo-accent {{
                        color: #3B82F6;
                    }}
                    .badge {{
                        display: inline-block;
                        padding: 6px 12px;
                        font-size: 11px;
                        font-weight: 700;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        background-color: rgba(59, 130, 246, 0.1);
                        color: #3B82F6;
                        border-radius: 9999px;
                        margin-bottom: 16px;
                    }}
                    h1 {{
                        font-size: 22px;
                        font-weight: 700;
                        color: #FFFFFF;
                        margin-top: 0;
                        margin-bottom: 12px;
                        line-height: 1.3;
                    }}
                    p {{
                        font-size: 14px;
                        color: #9CA3AF;
                        line-height: 1.6;
                        margin-bottom: 24px;
                    }}
                    .clipping-card {{
                        background-color: rgba(255, 255, 255, 0.03);
                        border: 1px solid rgba(255, 255, 255, 0.05);
                        border-radius: 12px;
                        padding: 20px;
                        margin-bottom: 30px;
                    }}
                    .clipping-headline {{
                        font-size: 16px;
                        font-weight: 600;
                        color: #FFFFFF;
                        margin: 0 0 8px 0;
                    }}
                    .button-group {{
                        display: flex;
                        gap: 12px;
                        margin-top: 16px;
                    }}
                    .btn {{
                        display: inline-block;
                        padding: 10px 20px;
                        font-size: 13px;
                        font-weight: 600;
                        text-decoration: none;
                        border-radius: 8px;
                        transition: all 0.2s ease;
                        text-align: center;
                    }}
                    .btn-primary {{
                        background-color: #3B82F6;
                        color: #FFFFFF;
                    }}
                    .btn-secondary {{
                        background-color: rgba(255, 255, 255, 0.08);
                        color: #E5E5E5;
                        border: 1px solid rgba(255, 255, 255, 0.1);
                    }}
                    .footer {{
                        margin-top: 40px;
                        padding-top: 20px;
                        border-top: 1px solid rgba(255, 255, 255, 0.05);
                        font-size: 11px;
                        color: #6B7280;
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">
                        NewsCraft<span class="logo-accent">AI</span>
                    </div>
                    <div class="badge">Generation Complete</div>
                    <h1>Your Newspaper Clipping is Ready!</h1>
                    <p>Great news! Our AI engine has formatted and generated your high-quality newspaper clipping. You can view or download the exports using the buttons below.</p>
                    
                    <div class="clipping-card">
                        <div class="clipping-headline">"{headline}"</div>
                        <div class="button-group">
                            {f'<a href="{png_url}" class="btn btn-primary" target="_blank">Download PNG</a>' if png_url else ''}
                            {f'<a href="{pdf_url}" class="btn btn-secondary" target="_blank">Download PDF</a>' if pdf_url else ''}
                        </div>
                    </div>
                    
                    <p>Thank you for using NewsCraft AI to capture your stories.</p>
                    
                    <div class="footer">
                        Sent automatically by NewsCraft AI. Please do not reply to this email.<br>
                        © 2026 NewsCraft AI. All rights reserved.
                    </div>
                </div>
            </body>
            </html>
            """
        else:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Newspaper Clipping Failed</title>
                <style>
                    body {{
                        margin: 0;
                        padding: 0;
                        background-color: #0A0A0A;
                        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        color: #E5E5E5;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 40px auto;
                        padding: 32px;
                        background-color: #121212;
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        border-radius: 16px;
                        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                    }}
                    .logo {{
                        font-size: 24px;
                        font-weight: 800;
                        color: #FFFFFF;
                        letter-spacing: -0.5px;
                        margin-bottom: 24px;
                    }}
                    .logo-accent {{
                        color: #EF4444;
                    }}
                    .badge {{
                        display: inline-block;
                        padding: 6px 12px;
                        font-size: 11px;
                        font-weight: 700;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        background-color: rgba(239, 68, 68, 0.1);
                        color: #EF4444;
                        border-radius: 9999px;
                        margin-bottom: 16px;
                    }}
                    h1 {{
                        font-size: 22px;
                        font-weight: 700;
                        color: #FFFFFF;
                        margin-top: 0;
                        margin-bottom: 12px;
                        line-height: 1.3;
                    }}
                    p {{
                        font-size: 14px;
                        color: #9CA3AF;
                        line-height: 1.6;
                        margin-bottom: 24px;
                    }}
                    .clipping-card {{
                        background-color: rgba(255, 255, 255, 0.03);
                        border: 1px solid rgba(255, 255, 255, 0.05);
                        border-radius: 12px;
                        padding: 20px;
                        margin-bottom: 30px;
                    }}
                    .clipping-headline {{
                        font-size: 16px;
                        font-weight: 600;
                        color: #FFFFFF;
                        margin: 0;
                    }}
                    .footer {{
                        margin-top: 40px;
                        padding-top: 20px;
                        border-top: 1px solid rgba(255, 255, 255, 0.05);
                        font-size: 11px;
                        color: #6B7280;
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">
                        NewsCraft<span class="logo-accent">AI</span>
                    </div>
                    <div class="badge">Generation Failed</div>
                    <h1>Clipping Generation Failed</h1>
                    <p>We encountered an unexpected error while formatting or rendering your newspaper clipping. Please review your source content and try generating it again.</p>
                    
                    <div class="clipping-card">
                        <div class="clipping-headline">"{headline}"</div>
                    </div>
                    
                    <p>If you continue to experience issues, please contact our support team.</p>
                    
                    <div class="footer">
                        Sent automatically by NewsCraft AI. Please do not reply to this email.<br>
                        © 2026 NewsCraft AI. All rights reserved.
                    </div>
                </div>
            </body>
            </html>
            """

        # Log or send
        if not self.smtp_host or not self.smtp_user:
            logger.info("SMTP not configured. Simulating email update.", 
                        to=user_email, 
                        subject=subject, 
                        status=status,
                        png_url=png_url,
                        pdf_url=pdf_url)
            print(f"\n=======================================================")
            print(f"[MOCK EMAIL SENT] to {user_email}")
            print(f"Subject: {subject}")
            print(f"Status: {status.upper()}")
            if png_url: print(f"PNG: {png_url}")
            if pdf_url: print(f"PDF: {pdf_url}")
            print(f"=======================================================\n")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = user_email

            # Add plain text fallback
            text_fallback = f"NewsCraft AI Clipping Status Update:\n\nHeadline: {headline}\nStatus: {status}\n"
            if png_url: text_fallback += f"PNG URL: {png_url}\n"
            if pdf_url: text_fallback += f"PDF URL: {pdf_url}\n"
            
            msg.attach(MIMEText(text_fallback, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # Connect and send
            port = self.smtp_port or (587 if self.smtp_tls else 25)
            if self.smtp_tls:
                server = smtplib.SMTP(self.smtp_host, port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, port)

            if self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)

            server.sendmail(self.from_email, [user_email], msg.as_string())
            server.quit()
            logger.info("Email update sent successfully via SMTP.", to=user_email)
            return True
        except Exception as e:
            logger.error("Failed to send email update via SMTP", error=repr(e))
            return False

    def send_verification_email(self, user_email: str, token: str) -> bool:
        """
        Sends an account verification email containing the verification link.
        """
        verification_link = f"http://localhost:8000/api/v1/auth/verify?token={token}"
        subject = "NewsCraft AI — Verify Your Email Address"
        
        # Premium HTML Template for Email Verification
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verify Your Email</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background-color: #0A0A0A;
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    color: #E5E5E5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 40px auto;
                    padding: 32px;
                    background-color: #121212;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 16px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: 800;
                    color: #FFFFFF;
                    letter-spacing: -0.5px;
                    margin-bottom: 24px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                .logo-accent {{
                    color: #6366F1;
                }}
                .badge {{
                    display: inline-block;
                    padding: 6px 12px;
                    font-size: 11px;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    background-color: rgba(99, 102, 241, 0.1);
                    color: #6366F1;
                    border-radius: 9999px;
                    margin-bottom: 16px;
                }}
                h1 {{
                    font-size: 22px;
                    font-weight: 700;
                    color: #FFFFFF;
                    margin-top: 0;
                    margin-bottom: 12px;
                    line-height: 1.3;
                }}
                p {{
                    font-size: 14px;
                    color: #9CA3AF;
                    line-height: 1.6;
                    margin-bottom: 24px;
                }}
                .verification-section {{
                    text-align: center;
                    padding: 20px 0;
                    margin-bottom: 30px;
                }}
                .btn {{
                    display: inline-block;
                    padding: 14px 28px;
                    font-size: 14px;
                    font-weight: 600;
                    text-decoration: none;
                    border-radius: 8px;
                    background-color: #6366F1;
                    color: #FFFFFF;
                    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
                    transition: all 0.2s ease;
                }}
                .fallback-link {{
                    font-size: 11px;
                    color: #6B7280;
                    word-break: break-all;
                    margin-top: 20px;
                }}
                .fallback-link a {{
                    color: #6366F1;
                    text-decoration: none;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid rgba(255, 255, 255, 0.05);
                    font-size: 11px;
                    color: #6B7280;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">
                    NewsCraft<span class="logo-accent">AI</span>
                </div>
                <div class="badge">Account Verification</div>
                <h1>Confirm Your Email Address</h1>
                <p>Welcome to NewsCraft AI! Before we get started, please verify your email address by clicking the button below. This ensures your account security and avoids duplicates.</p>
                
                <div class="verification-section">
                    <a href="{verification_link}" class="btn" target="_blank">Verify Email Address</a>
                    <div class="fallback-link">
                        If the button doesn't work, copy and paste this link in your browser:<br>
                        <a href="{verification_link}">{verification_link}</a>
                    </div>
                </div>
                
                <p>Note: This link is valid for 24 hours. If you did not sign up for a NewsCraft AI account, you can safely ignore this email.</p>
                
                <div class="footer">
                    Sent automatically by NewsCraft AI. Please do not reply to this email.<br>
                    © 2026 NewsCraft AI. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """

        # Log or send
        if not self.smtp_host or not self.smtp_user:
            logger.info("SMTP not configured. Simulating verification email.", 
                        to=user_email, 
                        subject=subject,
                        verification_link=verification_link)
            print(f"\n=======================================================")
            print(f"[MOCK VERIFICATION EMAIL SENT] to {user_email}")
            print(f"Subject: {subject}")
            print(f"Link: {verification_link}")
            print(f"=======================================================\n")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = user_email

            # Add plain text fallback
            text_fallback = f"NewsCraft AI Account Verification:\n\nPlease verify your email by opening the following link in your browser:\n{verification_link}\n"
            
            msg.attach(MIMEText(text_fallback, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # Connect and send
            port = self.smtp_port or (587 if self.smtp_tls else 25)
            if self.smtp_tls:
                server = smtplib.SMTP(self.smtp_host, port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, port)

            if self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)

            server.sendmail(self.from_email, [user_email], msg.as_string())
            server.quit()
            logger.info("Verification email sent successfully via SMTP.", to=user_email)
            return True
        except Exception as e:
            logger.error("Failed to send verification email via SMTP", error=repr(e))
            return False

email_service = EmailService()
