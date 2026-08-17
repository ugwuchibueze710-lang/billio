def register_blueprints(app):
    from app.api.auth import bp as auth_bp
    from app.api.bills import bp as bills_bp
    from app.api.occurrences import bp as occurrences_bp
    from app.api.dashboard import bp as dashboard_bp
    from app.api.history import bp as history_bp
    from app.api.settings import bp as settings_bp
    from app.api.account import bp as account_bp
    from app.api.documents import bp as documents_bp
    from app.api.ai import bp as ai_bp
    from app.api.feedback import bp as feedback_bp
    from app.api.admin import bp as admin_bp
    from app.api.notifications import bp as notifications_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(bills_bp)
    app.register_blueprint(occurrences_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notifications_bp)
