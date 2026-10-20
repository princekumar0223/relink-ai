import os
import smtplib
import sqlite3
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, Tuple
from ..config import settings

def get_smtp_credentials() -> Tuple[str, str]:
    """
    Retrieve and sanitize SMTP credentials from env vars, aliases, or database settings.
    Automatically removes spaces commonly present in Google App Passwords (e.g. 'abcd efgh ijkl mnop').
    """
    user = (
        os.getenv("SMTP_USER")
        or os.getenv("GMAIL_USER")
        or os.getenv("EMAIL_USER")
        or os.getenv("MAIL_USERNAME")
        or settings.SMTP_USER
        or ""
    ).strip()

    raw_password = (
        os.getenv("SMTP_PASSWORD")
        or os.getenv("GMAIL_APP_PASSWORD")
        or os.getenv("GMAIL_PASSWORD")
        or os.getenv("EMAIL_PASSWORD")
        or os.getenv("MAIL_PASSWORD")
        or settings.SMTP_PASSWORD
        or ""
    )
    password = raw_password.replace(" ", "").strip()

    # Fallback to database app_settings if not in environment
    if not (user and password):
        try:
            conn = sqlite3.connect(str(settings.DATABASE_PATH))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM app_settings WHERE key IN ('smtp_user', 'smtp_password')")
            rows = dict(cur.fetchall())
            if not user and rows.get("smtp_user"):
                user = rows["smtp_user"].strip()
            if not password and rows.get("smtp_password"):
                password = rows["smtp_password"].replace(" ", "").strip()
            conn.close()
        except Exception:
            pass

    return user, password

def _send_smtp_email(to_email: str, subject: str, text_content: str, html_content: str) -> Tuple[bool, str]:
    """
    Send an actual email via SMTP (Port 587 TLS or Port 465 SSL).
    Returns (success: bool, status_message: str).
    """
    user, password = get_smtp_credentials()

    if not (user and password):
        msg = f"[EMAIL NOTICE] Missing SMTP_USER or SMTP_PASSWORD. Live email to {to_email} not sent."
        print(msg)
        return False, msg

    host = settings.SMTP_HOST.strip() if settings.SMTP_HOST else ("smtp.gmail.com" if "@gmail" in user.lower() else "smtp.gmail.com")
    port = settings.SMTP_PORT or 587
    sender_name = "Relink AI Lost & Found"
    sender_header = f"{sender_name} <{user}>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_header
    msg["To"] = to_email
    msg["Reply-To"] = user

    part1 = MIMEText(text_content, "plain", "utf-8")
    part2 = MIMEText(html_content, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    errors = []

    # Attempt 1: Port 587 with STARTTLS
    try:
        with smtplib.SMTP(host, port, timeout=12) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, password)
            server.sendmail(user, [to_email], msg.as_string())
        success_msg = f"Live email successfully delivered to {to_email} via SMTP ({host}:{port})!"
        print(f"\n[SUCCESS] 🚀 {success_msg}\n")
        return True, success_msg
    except Exception as e587:
        err_str = f"Port {port} STARTTLS failed: {e587}"
        errors.append(err_str)
        print(f"[WARN] {err_str}. Trying direct SSL on port 465...")

    # Attempt 2: Port 465 with SSL (recommended fallback on cloud hosts that block port 587)
    try:
        with smtplib.SMTP_SSL(host, 465, timeout=12) as server:
            server.login(user, password)
            server.sendmail(user, [to_email], msg.as_string())
        success_msg = f"Live email successfully delivered to {to_email} via SMTP_SSL ({host}:465)!"
        print(f"\n[SUCCESS] 🚀 {success_msg}\n")
        return True, success_msg
    except Exception as e465:
        err_str = f"Port 465 SSL failed: {e465}"
        errors.append(err_str)
        print(f"[ERROR] Live email delivery failed to {to_email}: {e465}\n")

    return False, " | ".join(errors)

def test_smtp_delivery(target_email: Optional[str] = None) -> Dict[str, Any]:
    """
    Diagnostic tool to test live SMTP credentials and dispatch a test alert.
    """
    user, password = get_smtp_credentials()
    to_email = (target_email or user or "").strip()

    if not to_email:
        return {
            "success": False,
            "smtp_user": user or "NOT CONFIGURED",
            "password_configured": bool(password),
            "password_length": len(password) if password else 0,
            "error": "No recipient email provided and SMTP_USER is empty.",
            "suggestion": "Set SMTP_USER and SMTP_PASSWORD in Render Environment Variables or .env"
        }

    subject = "⚡ Relink AI - Live SMTP Diagnostics Test"
    text_content = f"Hello,\n\nThis is a test notification confirming that Relink AI email dispatch is working!\nSender: {user}\nRecipient: {to_email}\n"
    html_content = f"""
    <div style="font-family:sans-serif; background:#0f172a; color:#f8fafc; padding:24px; border-radius:12px;">
      <h2 style="color:#a855f7;">⚡ Relink AI Email System Verified!</h2>
      <p>Your SMTP credentials are functioning correctly.</p>
      <p>Automated match alerts (>= 70%) will now be sent directly to lost item owners.</p>
    </div>
    """

    success, message = _send_smtp_email(to_email, subject, text_content, html_content)
    return {
        "success": success,
        "recipient": to_email,
        "smtp_user": user,
        "password_configured": bool(password),
        "password_clean_len": len(password) if password else 0,
        "detail": message,
        "troubleshooting": (
            "If 535 error occurs: Google has rejected the App Password. Generate a new 16-character App Password at https://myaccount.google.com/apppasswords with 2-Step Verification enabled."
            if not success and "535" in message else None
        )
    }

def _deliver_and_record(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: str,
    match_id: Optional[int] = None
):
    """Deliver email via SMTP and mark matches.email_notified = 1 only on actual success."""
    success, detail = _send_smtp_email(to_email, subject, text_content, html_content)
    if success and match_id:
        try:
            conn = sqlite3.connect(str(settings.DATABASE_PATH))
            cur = conn.cursor()
            cur.execute("UPDATE matches SET email_notified = 1 WHERE id = ?", (match_id,))
            cur.execute("UPDATE notifications SET status = 'delivered' WHERE match_id = ?", (match_id,))
            conn.commit()
            conn.close()
            print(f"[SUCCESS] Marked match #{match_id} as email_notified=1")
        except Exception as e:
            print(f"[WARN] Failed to update match #{match_id} email_notified status: {e}")

def send_match_notification(
    lost_item: Dict[str, Any],
    found_item: Dict[str, Any],
    match_data: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Sends an automated email alert to the lost item owner when AI match score >= 70%.
    Stores notification in database and logs details for transparency.
    """
    composite_score = float(match_data.get("composite_score", 0.0))
    score_pct = int(round(composite_score * 100))

    # Verify threshold (must be >= 70%)
    if composite_score < settings.EMAIL_ALERT_THRESHOLD:
        return {"status": "skipped", "reason": f"Score {score_pct}% below 70% threshold"}

    recipient_email = (lost_item.get("contact_email") or "").strip()
    recipient_name = (lost_item.get("contact_name") or "Owner").strip()

    if not recipient_email or "@" not in recipient_email:
        return {"status": "skipped", "reason": "No valid contact email for lost item owner"}

    lost_title = lost_item.get("title", "Lost Item")
    found_title = found_item.get("title", "Found Item")
    found_location = found_item.get("location_name", "Campus")
    custody_location = found_item.get("custody_location") or "Campus Security Desk / Office"
    founder_name = found_item.get("contact_name", "Anonymous Finder")
    distance_m = match_data.get("distance_meters")
    dist_str = f"{int(round(distance_m))} meters" if distance_m is not None else "Nearby"

    subject = f"🎯 [Relink AI Alert] Your lost '{lost_title}' has a {score_pct}% AI match!"

    text_content = f"""Hello {recipient_name},

Great news from Relink AI! An item matching your lost report has just been identified with a {score_pct}% AI confidence match.

--- MATCH DETAILS ---
• Your Lost Item: {lost_title} ({lost_item.get('category', 'General')})
• Matched Found Item: {found_title}
• Found Location: {found_location} (approx. {dist_str} from where you lost it)
• Safe Custody Spot: {custody_location}
• Reported By: {founder_name}
• AI Confidence: {score_pct}% (Visual: {int(round(match_data.get('visual_score', 0)*100))}%, Text: {int(round(match_data.get('text_score', 0)*100))}%, Geo: {int(round(match_data.get('geo_score', 0)*100))}%)

--- WHAT TO DO NEXT ---
1. Visit Relink AI at {settings.APP_URL}
2. Open the 'Discover Matches' tab and click 'Inspect & Verify Ownership'.
3. Answer the ownership verification questions to safely claim your item from {custody_location}.

Best regards,
Relink AI Team
Multimodal Lost & Found Intelligence System
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f19; color: #f1f5f9; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #131b2e; border: 1px solid #334155; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
    .header {{ background: linear-gradient(135deg, #7c3aed, #2563eb); padding: 24px; text-align: center; color: white; }}
    .content {{ padding: 24px; }}
    .badge {{ display: inline-block; background: rgba(124, 58, 237, 0.2); border: 1px solid #7c3aed; color: #c4b5fd; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 14px; margin-bottom: 12px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 16px; margin: 16px 0; }}
    .btn {{ display: inline-block; background: linear-gradient(135deg, #7c3aed, #2563eb); color: white !important; font-weight: bold; padding: 14px 28px; border-radius: 10px; text-decoration: none; text-align: center; margin: 20px 0; }}
    .footer {{ padding: 16px 24px; background: #0f172a; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #1e293b; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1 style="margin:0; font-size:22px;">⚡ Relink AI</h1>
      <p style="margin:6px 0 0; opacity:0.9; font-size:13px;">Multimodal Lost & Found Intelligence Alert</p>
    </div>
    <div class="content">
      <div class="badge">🎯 {score_pct}% High-Confidence Match Found</div>
      <h2 style="margin: 0 0 12px; color: #ffffff;">Hello {recipient_name},</h2>
      <p style="line-height:1.5; color:#cbd5e1; font-size:14px;">
        Our multimodal AI engine just matched your lost <strong>"{lost_title}"</strong> with a recently reported found item!
      </p>

      <div class="card">
        <h3 style="margin-top:0; font-size:15px; color:#38bdf8;">📦 Found Item Information</h3>
        <p style="margin:6px 0; font-size:13px; color:#e2e8f0;"><strong>Item:</strong> {found_title}</p>
        <p style="margin:6px 0; font-size:13px; color:#e2e8f0;"><strong>Location:</strong> {found_location} ({dist_str} away)</p>
        <p style="margin:6px 0; font-size:13px; color:#10b981;"><strong>Safe Custody Spot:</strong> {custody_location}</p>
        <p style="margin:6px 0; font-size:13px; color:#94a3b8;"><strong>Reported By:</strong> {founder_name}</p>
      </div>

      <div style="text-align: center;">
        <a href="{settings.APP_URL}" class="btn">Inspect & Verify Ownership Now →</a>
      </div>

      <p style="font-size:12px; color:#94a3b8; line-height:1.4;">
        💡 <em>Once you inspect the match and provide ownership verification answers, the founder / security desk can approve the claim and hand over your item.</em>
      </p>
    </div>
    <div class="footer">
      Relink AI • Automated Campus Intelligence System<br>
      Protecting student belongings through multimodal AI vision, semantics & GPS.
    </div>
  </div>
</body>
</html>
"""

    match_id = match_data.get("id")

    # Store in database notifications table
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO notifications (
                recipient_email, recipient_name, item_id, match_id,
                subject, body, match_score, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                recipient_email,
                recipient_name,
                lost_item.get("id"),
                match_id,
                subject,
                text_content,
                composite_score,
                "queued"
            ))
            conn.commit()
        except Exception as e:
            print(f"[WARN] Failed to record notification in DB: {e}")

    # Deliver directly via SMTP in background thread and update match row on real success
    threading.Thread(
        target=_deliver_and_record,
        args=(recipient_email, subject, text_content, html_content, match_id),
        daemon=True
    ).start()

    print("\n" + "=" * 65)
    print(f"📧 [RELINK AI EMAIL ALERT TRIGGERED] (Match: {score_pct}% >= 70%)")
    print(f"   To      : {recipient_email} ({recipient_name})")
    print(f"   Subject : {subject}")
    print(f"   Action  : Direct SMTP Email Delivery Dispatched")
    print("=" * 65 + "\n")

    return {
        "status": "success",
        "recipient_email": recipient_email,
        "score_pct": score_pct,
        "subject": subject,
        "delivery_mode": "smtp"
    }
