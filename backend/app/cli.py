"""
Flask CLI commands. `flask send-reminders` is intended to be invoked by a
Render Cron Job (recommended: hourly, so each user's local reminder window
is caught promptly regardless of timezone -- see README for the exact Render
config). Running it more often than needed is safe: every send is
idempotent via the notifications table's unique constraint.
"""
import click

from app.services.reminder_scheduler import run_reminder_scan


def register_cli(app):
    @app.cli.command("send-reminders")
    def send_reminders():
        """Scan all users' bills and send due reminders (push + email)."""
        stats = run_reminder_scan()
        click.echo(
            f"Scanned {stats['users_scanned']} users. "
            f"Sent {stats['push_sent']} push, {stats['email_sent']} email. "
            f"Errors: {stats['errors']}."
        )
