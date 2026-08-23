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

    @app.cli.command("make-admin")
    @click.argument("username")
    def make_admin(username):
        """Flip is_admin=True on an existing account, by username.

        Nothing about admin access is ever hardcoded in source code -- sign
        up normally through the app with your own strong password first,
        then run this once (e.g. via Render's Shell tab: `flask make-admin
        yourusername`) to promote that account.
        """
        from app.extensions import db
        from app.models import User

        user = User.query.filter(db.func.lower(User.username) == username.strip().lower()).first()
        if user is None:
            click.echo(f"No user found with username '{username}'.")
            return
        user.is_admin = True
        db.session.commit()
        click.echo(f"'{user.username}' (id={user.id}) is now an admin.")

    @app.cli.command("test-image")
    @click.argument("path")
    def test_image(path):
        """Run a local image or PDF file through the exact same
        validation + AI extraction pipeline a real bill upload uses, and
        print what comes out -- a quick way to test one specific file
        without going through the browser at all.

        Usage: flask test-image "C:\\Users\\you\\Desktop\\bill test.avif"
        (quote the path if it has spaces in it, like above).
        """
        import json
        import os

        from app.services.groq_client import extract_bills_from_images, GroqUnavailableError
        from app.services.image_validation import is_pdf, validate_bill_image, validate_bill_pdf

        if not os.path.isfile(path):
            click.echo(f"No file found at: {path}")
            return

        class _LocalFile:
            """Minimal stand-in for werkzeug's FileStorage (the object a
            real browser upload arrives as) -- just enough surface area
            (.filename, .stream, .read()) for the real validation
            functions to work on unmodified."""

            def __init__(self, filepath):
                self.filename = os.path.basename(filepath)
                self.stream = open(filepath, "rb")

            def read(self):
                return self.stream.read()

        f = _LocalFile(path)
        click.echo(f"Reading: {path}")

        if is_pdf(f):
            click.echo("Detected as: PDF")
            try:
                pdf_bytes, page_pngs = validate_bill_pdf(f)
            except Exception as exc:
                click.echo(f"REJECTED: {exc}")
                return
            click.echo(f"Valid PDF ({len(pdf_bytes)} bytes) -- rasterized {len(page_pngs)} page(s) for the AI to read.")
            extraction_pages, extraction_content_type = page_pngs, "image/png"
        else:
            click.echo("Detected as: image")
            try:
                extraction_bytes, extraction_content_type = validate_bill_image(f)
            except Exception as exc:
                click.echo(f"REJECTED: {exc}")
                return
            click.echo(f"Valid image -- normalized to {extraction_content_type} ({len(extraction_bytes)} bytes).")
            extraction_pages = [extraction_bytes]

        click.echo("\nAsking the AI to read every bill it can find in this document...\n")
        try:
            bills = extract_bills_from_images(extraction_pages, extraction_content_type)
        except GroqUnavailableError as exc:
            click.echo(f"AI extraction unavailable: {exc}")
            return

        if not bills:
            click.echo("No readable bill was found in this document.")
            return
        click.echo(f"Found {len(bills)} bill(s):\n")
        click.echo(json.dumps(bills, indent=2))
