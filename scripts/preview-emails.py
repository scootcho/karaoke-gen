#!/usr/bin/env python
"""
Preview all email templates by rendering them to HTML files.

Usage:
    python scripts/preview-emails.py [--output-dir /path/to/output]

This will render all email templates to HTML files that you can open in a browser.
"""

import argparse
import logging
import os
import sys
import webbrowser
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.email_service import EmailService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def render_all_emails(output_dir: Path) -> list[str]:
    """Render all email templates and return list of output files."""

    service = EmailService()
    output_files = []

    # Override frontend URL for preview
    service.frontend_url = "https://gen.nomadkaraoke.com"
    service.buy_url = "https://gen.nomadkaraoke.com"

    # 1. Magic Link Email
    logger.info("Rendering: Magic Link Email")
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
        }}
        .logo {{
            font-size: 24px;
            font-weight: bold;
            color: #3b82f6;
        }}
        .button {{
            display: inline-block;
            background-color: #3b82f6;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #666;
        }}
        .warning {{
            background-color: #fef3c7;
            border: 1px solid #fcd34d;
            border-radius: 4px;
            padding: 12px;
            margin: 20px 0;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🎤 Nomad Karaoke</div>
    </div>

    <p>Hi there,</p>

    <p>Click the button below to sign in to Nomad Karaoke:</p>

    <p style="text-align: center;">
        <a href="#" class="button">Sign In</a>
    </p>

    <div class="warning">
        ⏰ This link expires in 15 minutes and can only be used once.
    </div>

    <p>If the button doesn't work, copy and paste this link into your browser:</p>
    <p style="word-break: break-all; font-size: 14px; color: #666;">
        https://gen.nomadkaraoke.com/auth/verify?token=example-token-here
    </p>

    <p>If you didn't request this email, you can safely ignore it.</p>

    <div class="footer">
        <p>© 2026 Nomad Karaoke. All rights reserved.</p>
        <p>This is an automated message, please do not reply.</p>
    </div>
</body>
</html>
"""
    path = output_dir / "01_magic_link.html"
    path.write_text(html)
    output_files.append(str(path))

    # 2. Credits Added Email
    logger.info("Rendering: Credits Added Email")
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
        }}
        .logo {{
            font-size: 24px;
            font-weight: bold;
            color: #3b82f6;
        }}
        .credits-box {{
            background-color: #ecfdf5;
            border: 2px solid #10b981;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            margin: 20px 0;
        }}
        .credits-number {{
            font-size: 48px;
            font-weight: bold;
            color: #10b981;
        }}
        .button {{
            display: inline-block;
            background-color: #3b82f6;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🎤 Nomad Karaoke</div>
    </div>

    <p>Great news! 🎉</p>

    <p><strong>5 credits</strong> have been added to your account.</p>

    <div class="credits-box">
        <div>Your balance:</div>
        <div class="credits-number">10</div>
        <div>credits</div>
    </div>

    <p>Each credit lets you create one professional karaoke video with:</p>
    <ul>
        <li>AI-powered vocal/instrumental separation</li>
        <li>Synchronized lyrics with word-level timing</li>
        <li>4K video output</li>
        <li>YouTube upload</li>
    </ul>

    <p style="text-align: center;">
        <a href="#" class="button">Create Karaoke Now</a>
    </p>

    <div class="footer">
        <p>© 2026 Nomad Karaoke. All rights reserved.</p>
    </div>
</body>
</html>
"""
    path = output_dir / "02_credits_added.html"
    path.write_text(html)
    output_files.append(str(path))

    # 3. Welcome Email
    logger.info("Rendering: Welcome Email")
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
        }}
        .logo {{
            font-size: 24px;
            font-weight: bold;
            color: #3b82f6;
        }}
        .button {{
            display: inline-block;
            background-color: #3b82f6;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .feature {{
            display: flex;
            align-items: flex-start;
            margin: 16px 0;
        }}
        .feature-icon {{
            font-size: 24px;
            margin-right: 12px;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🎤 Nomad Karaoke</div>
    </div>

    <p>Welcome to Nomad Karaoke!</p>

    <p>Turn any song into a professional karaoke video in minutes. You have <strong>3 credits</strong> to get started!</p>

    <p><strong>Here's how it works:</strong></p>

    <div class="feature">
        <span class="feature-icon">🎵</span>
        <div>
            <strong>1. Search for a song</strong><br>
            Enter the artist and title, and we'll find high-quality audio.
        </div>
    </div>

    <div class="feature">
        <span class="feature-icon">✨</span>
        <div>
            <strong>2. AI does the magic</strong><br>
            We separate vocals, transcribe lyrics, and sync everything perfectly.
        </div>
    </div>

    <div class="feature">
        <span class="feature-icon">✏️</span>
        <div>
            <strong>3. Review & customize</strong><br>
            Fine-tune the lyrics if needed, choose your instrumental.
        </div>
    </div>

    <div class="feature">
        <span class="feature-icon">🎬</span>
        <div>
            <strong>4. Get your video</strong><br>
            Download your 4K karaoke video or upload directly to YouTube.
        </div>
    </div>

    <p style="text-align: center;">
        <a href="#" class="button">Get Started</a>
    </p>

    <div class="footer">
        <p>Questions? Reply to this email and we'll help you out.</p>
        <p>© 2026 Nomad Karaoke. All rights reserved.</p>
    </div>
</body>
</html>
"""
    path = output_dir / "03_welcome.html"
    path.write_text(html)
    output_files.append(str(path))

    # 4. Beta Welcome Email
    logger.info("Rendering: Beta Welcome Email")
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
        }}
        .logo {{
            font-size: 24px;
            font-weight: bold;
            color: #3b82f6;
        }}
        .beta-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #8b5cf6, #ec4899);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 8px;
        }}
        .credits-box {{
            background-color: #ecfdf5;
            border: 2px solid #10b981;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            margin: 20px 0;
        }}
        .credits-number {{
            font-size: 48px;
            font-weight: bold;
            color: #10b981;
        }}
        .reminder {{
            background-color: #fef3c7;
            border: 1px solid #fcd34d;
            border-radius: 8px;
            padding: 16px;
            margin: 20px 0;
        }}
        .button {{
            display: inline-block;
            background-color: #3b82f6;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <span class="logo">🎤 Nomad Karaoke</span>
        <span class="beta-badge">BETA TESTER</span>
    </div>

    <p>Thank you for joining our beta program! 🎉</p>

    <p>As promised, here's your free credit to create a karaoke video:</p>

    <div class="credits-box">
        <div>Your balance:</div>
        <div class="credits-number">1</div>
        <div>free credit</div>
    </div>

    <div class="reminder">
        <strong>📝 Your Promise:</strong><br>
        Remember, as a beta tester you agreed to:
        <ul style="margin: 10px 0; padding-left: 20px;">
            <li>Review and correct any lyrics timing issues</li>
            <li>Share your honest feedback after trying the tool</li>
        </ul>
        We'll send you a quick feedback form after your job completes!
    </div>

    <p style="text-align: center;">
        <a href="#" class="button">Create Your Karaoke Video</a>
    </p>

    <p>Thanks for helping us make Nomad Karaoke better!</p>

    <div class="footer">
        <p>© 2026 Nomad Karaoke. All rights reserved.</p>
    </div>
</body>
</html>
"""
    path = output_dir / "04_beta_welcome.html"
    path.write_text(html)
    output_files.append(str(path))

    # 5. Feedback Request Email
    logger.info("Rendering: Feedback Request Email")
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
        }}
        .logo {{
            font-size: 24px;
            font-weight: bold;
            color: #3b82f6;
        }}
        .feedback-box {{
            background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
            border: 2px solid #3b82f6;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            margin: 20px 0;
        }}
        .stars {{
            font-size: 36px;
            margin: 10px 0;
        }}
        .button {{
            display: inline-block;
            background-color: #3b82f6;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .time-note {{
            background-color: #fef3c7;
            border-radius: 8px;
            padding: 12px;
            margin: 20px 0;
            font-size: 14px;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🎤 Nomad Karaoke</div>
    </div>

    <p>Hi there!</p>

    <p>Hope you enjoyed creating your karaoke video for <strong>Lionel Richie - Hello</strong>! As a beta tester, your feedback is super valuable to us.</p>

    <div class="feedback-box">
        <div class="stars">⭐⭐⭐⭐⭐</div>
        <p><strong>How was your experience?</strong></p>
        <p>Quick 2-minute survey - we'd love to hear your thoughts!</p>
    </div>

    <p style="text-align: center;">
        <a href="#" class="button">Share Your Feedback</a>
    </p>

    <div class="time-note">
        ⏱️ This takes less than 2 minutes and helps us improve the tool for everyone!
    </div>

    <p>Specifically, we'd love to know:</p>
    <ul>
        <li>How easy was it to use?</li>
        <li>Were the lyrics accurate?</li>
        <li>How was the correction experience?</li>
        <li>What could we improve?</li>
    </ul>

    <p>Thanks for being part of making Nomad Karaoke better! 🙏</p>

    <div class="footer">
        <p>© 2026 Nomad Karaoke. All rights reserved.</p>
    </div>
</body>
</html>
"""
    path = output_dir / "05_feedback_request.html"
    path.write_text(html)
    output_files.append(str(path))

    # 6. Job Completion Email (with signature)
    logger.info("Rendering: Job Completion Email")
    signature = service._get_email_signature()
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            white-space: pre-wrap;
        }}
        .content {{
            white-space: pre-wrap;
            font-size: 14px;
        }}
        .signature {{
            margin-top: 30px;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="content">Hi Andrew,

Your karaoke video for "Hello" by Lionel Richie is ready!

NOMAD-1234

📥 Downloads:
- YouTube: https://www.youtube.com/watch?v=example
- Google Drive: https://drive.google.com/file/d/example
- Dropbox: https://www.dropbox.com/s/example

🎬 Video Details:
- Resolution: 4K (3840x2160)
- Format: MP4 (H.265)
- Duration: 4:32

Thank you for using Nomad Karaoke!</div>

    <div class="signature">
        {signature}
    </div>
</body>
</html>
"""
    path = output_dir / "06_job_completion.html"
    path.write_text(html)
    output_files.append(str(path))

    # 7. Action Reminder Email
    logger.info("Rendering: Action Reminder Email")
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .alert {{
            background-color: #fef3c7;
            border: 1px solid #fcd34d;
            border-radius: 8px;
            padding: 16px;
            margin: 20px 0;
            text-align: center;
        }}
        .content {{
            white-space: pre-wrap;
            font-size: 14px;
        }}
        .signature {{
            margin-top: 30px;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="alert">
        ⏰ Your karaoke video is waiting for you!
    </div>

    <div class="content">Hi there,

Your karaoke video for "Hello" by Lionel Richie is almost ready - just needs your review!

🔗 Review your lyrics here:
https://gen.nomadkaraoke.com/app?job=abc123

The lyrics have been transcribed and are ready for you to:
- Check for any errors
- Adjust timing if needed
- Approve and generate the final video

This usually only takes a few minutes!

Click the link above to continue.</div>

    <div class="signature">
        {signature}
    </div>
</body>
</html>
"""
    path = output_dir / "07_action_reminder.html"
    path.write_text(html)
    output_files.append(str(path))

    # Create index page
    logger.info("Creating index page...")
    index_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Nomad Karaoke - Email Templates Preview</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #3b82f6;
        }
        .email-list {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .email-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }
        .email-item:last-child {
            border-bottom: none;
        }
        .email-name {
            font-weight: 500;
        }
        .email-link {
            color: #3b82f6;
            text-decoration: none;
        }
        .email-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <h1>🎤 Nomad Karaoke Email Templates</h1>
    <div class="email-list">
        <div class="email-item">
            <span class="email-name">1. Magic Link (Sign In)</span>
            <a href="01_magic_link.html" class="email-link" target="_blank">Preview →</a>
        </div>
        <div class="email-item">
            <span class="email-name">2. Credits Added</span>
            <a href="02_credits_added.html" class="email-link" target="_blank">Preview →</a>
        </div>
        <div class="email-item">
            <span class="email-name">3. Welcome Email</span>
            <a href="03_welcome.html" class="email-link" target="_blank">Preview →</a>
        </div>
        <div class="email-item">
            <span class="email-name">4. Beta Welcome</span>
            <a href="04_beta_welcome.html" class="email-link" target="_blank">Preview →</a>
        </div>
        <div class="email-item">
            <span class="email-name">5. Feedback Request</span>
            <a href="05_feedback_request.html" class="email-link" target="_blank">Preview →</a>
        </div>
        <div class="email-item">
            <span class="email-name">6. Job Completion</span>
            <a href="06_job_completion.html" class="email-link" target="_blank">Preview →</a>
        </div>
        <div class="email-item">
            <span class="email-name">7. Action Reminder (Review Lyrics)</span>
            <a href="07_action_reminder.html" class="email-link" target="_blank">Preview →</a>
        </div>
    </div>
</body>
</html>
"""
    path = output_dir / "index.html"
    path.write_text(index_html)
    output_files.insert(0, str(path))

    return output_files


def main():
    parser = argparse.ArgumentParser(
        description="Preview email templates"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save HTML files (default: /tmp/email_preview)"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically"
    )

    args = parser.parse_args()

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path("/tmp/email_preview")

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("EMAIL TEMPLATE PREVIEW")
    logger.info("=" * 60)
    logger.info(f"Output directory: {output_dir}")
    logger.info("")

    output_files = render_all_emails(output_dir)

    logger.info("")
    logger.info("=" * 60)
    logger.info("PREVIEW READY")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Generated {len(output_files)} files:")
    for f in output_files:
        logger.info(f"  - {f}")
    logger.info("")

    index_path = output_dir / "index.html"
    if not args.no_browser:
        logger.info(f"Opening: {index_path}")
        webbrowser.open(f"file://{index_path}")
    else:
        logger.info(f"Open in browser: file://{index_path}")


if __name__ == "__main__":
    main()
