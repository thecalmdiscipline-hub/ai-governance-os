from sqlalchemy import Column, Date, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="open")  # open / in_progress / closed

    # owner: free text (role or team name, e.g. "Compliance team") — never validated/required as
    # personal data, the UI just warns against entering a person's name. due_date: plain date,
    # display-only "overdue" marker, no reminders/notifications. Both nullable (Batch O2).
    owner = Column(String, nullable=True)
    due_date = Column(Date, nullable=True)

    ai_risk_id = Column(Integer, ForeignKey("ai_risks.id"), index=True)
    ai_incident_id = Column(Integer, ForeignKey("ai_incidents.id"), index=True)

    ai_risk = relationship("AIRisk", back_populates="corrective_actions")
    ai_incident = relationship("AIIncident", back_populates="corrective_actions")