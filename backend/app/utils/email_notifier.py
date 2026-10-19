import os
import smtplib
import sqlite3
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from ..config import settings

def _send_smtp_email(to_email: str, subject: str, text_content: str, html_content: str) -> bool:
    """Send an actual email via SMTP if credentials are configured."""
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        return False
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email
        
        part1 = MIMEText(text_content, "plain", "utf-8")
        part2 = MIMEText(html_content, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[WARN] SMTP delivery failed to {to_email}: {e}")
        return False

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

    # Check if SMTP is available
    delivered_via_smtp = False
    if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
        # Deliver in background thread so HTTP response is fast
        threading.Thread(
            target=_send_smtp_email,
            args=(recipient_email, subject, text_content, html_content),
            daemon=True
        ).start()
        delivered_via_smtp = True
        status_text = "sent"
    else:
        status_text = "logged"

    print("\n" + "=" * 65)
    print(f"📧 [RELINK AI EMAIL ALERT TRIGGERED] (Match: {score_pct}% >= 70%)")
    print(f"   To      : {recipient_email} ({recipient_name})")
    print(f"   Subject : {subject}")
    print(f"   Status  : {'Sent via SMTP Server' if delivered_via_smtp else 'Logged & Recorded (Configure SMTP in .env for inbox delivery)'}")
    print("=" * 65 + "\n")

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
                match_data.get("id"),
                subject,
                text_content,
                composite_score,
                status_text
            ))
            conn.commit()
        except Exception as e:
            print(f"[WARN] Failed to record notification in DB: {e}")

    return {
        "status": "success",
        "recipient_email": recipient_email,
        "score_pct": score_pct,
        "subject": subject,
        "delivery_mode": "smtp" if delivered_via_smtp else "logged"
    }
