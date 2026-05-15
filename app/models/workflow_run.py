from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from datetime import datetime
from app.db.base import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, unique=True, nullable=False, index=True)
    workflow = Column(String, nullable=False, index=True)

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    status = Column(String, nullable=False, index=True)
    input_payload = Column(Text, nullable=True)
    context_payload = Column(Text, nullable=True)
    output_payload = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
