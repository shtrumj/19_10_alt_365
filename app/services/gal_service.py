from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import (
    GlobalAddressEntry,
    User,
    sync_gal_entry_for_user,
)


class GalService:
    """Service helpers for managing the Global Address List (GAL)."""

    def __init__(self, db: Session):
        self.db = db

    # --- Synchronisation -------------------------------------------------

    def sync_from_users(self, users: Optional[Iterable[User]] = None) -> None:
        """Ensure every active user has a GAL entry.

        When called without `users`, all users in the database are synchronised.
        """
        if users is None:
            users = self.db.query(User).all()

        for user in users:
            sync_gal_entry_for_user(self.db, user)
        self.db.commit()

    # --- Queries ---------------------------------------------------------

    def search(self, query: Optional[str], limit: int = 25) -> List[GlobalAddressEntry]:
        """Search GAL entries by display name, email, company, or department."""
        q = (
            self.db.query(GlobalAddressEntry)
            .filter(GlobalAddressEntry.is_active.is_(True))
            .order_by(GlobalAddressEntry.display_name.asc())
        )
        if query:
            pattern = f"%{query}%"
            q = q.filter(
                or_(
                    GlobalAddressEntry.display_name.ilike(pattern),
                    GlobalAddressEntry.email.ilike(pattern),
                    GlobalAddressEntry.company.ilike(pattern),
                    GlobalAddressEntry.department.ilike(pattern),
                )
            )
        return q.limit(limit).all()

    def get_all(self, limit: int = 200) -> List[GlobalAddressEntry]:
        """Return up to `limit` GAL entries."""
        return (
            self.db.query(GlobalAddressEntry)
            .filter(GlobalAddressEntry.is_active.is_(True))
            .order_by(GlobalAddressEntry.display_name.asc())
            .limit(limit)
            .all()
        )

    def get_by_email(self, email: str) -> Optional[GlobalAddressEntry]:
        """Fetch a GAL entry by primary email."""
        return (
            self.db.query(GlobalAddressEntry)
            .filter(GlobalAddressEntry.email == email)
            .one_or_none()
        )

    # --- Mutations -------------------------------------------------------

    def upsert_entry(
        self,
        *,
        email: str,
        display_name: Optional[str] = None,
        company: Optional[str] = None,
        department: Optional[str] = None,
        job_title: Optional[str] = None,
        office_location: Optional[str] = None,
        business_phone: Optional[str] = None,
        mobile_phone: Optional[str] = None,
        source: str = "manual",
    ) -> GlobalAddressEntry:
        """Create or update a manual GAL entry."""
        entry = (
            self.db.query(GlobalAddressEntry)
            .filter(GlobalAddressEntry.email == email)
            .one_or_none()
        )
        if entry is None:
            entry = GlobalAddressEntry(email=email, display_name=display_name or email)
            entry.source = source
            self.db.add(entry)

        if display_name:
            entry.display_name = display_name
        if company:
            entry.company = company
        if department:
            entry.department = department
        if job_title:
            entry.job_title = job_title
        if office_location:
            entry.office_location = office_location
        if business_phone:
            entry.business_phone = business_phone
        if mobile_phone:
            entry.mobile_phone = mobile_phone
        entry.is_active = True
        return entry

    def deactivate_entry(self, entry: GlobalAddressEntry) -> None:
        """Soft-delete a GAL entry."""
        entry.is_active = False
        self.db.add(entry)
