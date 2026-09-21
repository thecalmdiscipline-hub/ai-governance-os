from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey, Text, false
from sqlalchemy.orm import relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin / auditor / operator
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    is_super_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, nullable=False)

    organization = relationship("Organization")

    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime, nullable=True)

    # Password change (Batch E). must_change_password blocks every endpoint except
    # change-password / me / the MFA endpoints until the user has chosen a new password.
    must_change_password = Column(Boolean, nullable=False, default=False, server_default=false())
    password_changed_at = Column(DateTime, nullable=True)

    # TOTP second factor (Batch E). The secret is stored Fernet-encrypted, the backup codes as
    # a JSON list of password hashes; a plain secret or code is never persisted.
    mfa_enabled = Column(Boolean, nullable=False, default=False, server_default=false())
    mfa_secret_enc = Column(Text, nullable=True)
    mfa_last_step = Column(Integer, nullable=True)  # last accepted 30 s step (replay protection)
    mfa_backup_codes = Column(Text, nullable=True)
    mfa_failed_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    mfa_locked_until = Column(DateTime, nullable=True)
