from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class DocumentUsage(Base):
    """A document read by a workflow run (Fase B6, V19/V29).

    Written by the runner together with the WorkflowRun row. A document with at least one usage
    row is archived instead of deleted.
    """

    __tablename__ = "document_usage"

    id = Column(Integer, primary_key=True)
    run_id = Column(String, ForeignKey("workflow_runs.run_id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    codes = Column(String, nullable=False)  # comma-separated codes at the time of the run
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
