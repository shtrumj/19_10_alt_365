from __future__ import annotations

import logging
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from ..database import Contact, ContactFolder

logger = logging.getLogger(__name__)


WELL_KNOWN_CONTACT_FOLDERS = {
    "contacts": {
        "display_name": "Contacts",
        "is_default": True,
    },
    "contacts_archive": {
        "display_name": "Suggested Contacts",
        "is_default": False,
    },
}


class ContactService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    # Folder helpers -----------------------------------------------------------------
    def ensure_default_folders(self) -> List[ContactFolder]:
        folders = (
            self.db.query(ContactFolder)
            .filter(ContactFolder.owner_id == self.user_id)
            .all()
        )
        existing = {f.well_known_name: f for f in folders if f.well_known_name}

        created = []
        for well_known, cfg in WELL_KNOWN_CONTACT_FOLDERS.items():
            if well_known in existing:
                continue
            folder = ContactFolder(
                owner_id=self.user_id,
                parent_id=None,
                display_name=cfg["display_name"],
                well_known_name=well_known,
                is_default=cfg.get("is_default", False),
            )
            self.db.add(folder)
            self.db.flush()
            created.append(folder)

        if created:
            self.db.commit()
            folders.extend(created)

        return folders

    def list_folders(self) -> List[ContactFolder]:
        self.ensure_default_folders()
        folders = (
            self.db.query(ContactFolder)
            .filter(ContactFolder.owner_id == self.user_id)
            .order_by(ContactFolder.display_name.asc())
            .all()
        )
        return folders

    def get_folder_by_uuid(self, folder_uuid: str) -> Optional[ContactFolder]:
        return (
            self.db.query(ContactFolder)
            .filter(
                ContactFolder.owner_id == self.user_id,
                ContactFolder.uuid == folder_uuid,
            )
            .first()
        )

    def create_subfolder(
        self,
        display_name: str,
        parent_uuid: Optional[str] = None,
        well_known_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ContactFolder:
        parent = None
        if parent_uuid:
            parent = self.get_folder_by_uuid(parent_uuid)
            if not parent:
                raise ValueError("Parent folder not found")

        folder = ContactFolder(
            owner_id=self.user_id,
            parent_id=parent.id if parent else None,
            display_name=display_name,
            well_known_name=well_known_name,
            description=description,
        )
        self.db.add(folder)
        self.db.commit()
        self.db.refresh(folder)
        return folder

    # Contact helpers ----------------------------------------------------------------
    def _normalize_children(self, children: Optional[Iterable[str]]) -> Optional[str]:
        if children is None:
            return None
        if isinstance(children, str):
            return children
        return ";".join(
            [child.strip() for child in children if child and child.strip()]
        )

    def _apply_contact_fields(self, contact: Contact, data: dict):
        for field, value in data.items():
            if not hasattr(contact, field):
                continue
            if field == "children" and value is not None:
                value = self._normalize_children(value)
            setattr(contact, field, value)

    def create_contact(self, data: dict) -> Contact:
        folder_uuid = data.pop("folder_uuid", None)
        folder_id = None
        if folder_uuid:
            folder = self.get_folder_by_uuid(folder_uuid)
            if not folder:
                raise ValueError("Contact folder not found")
            folder_id = folder.id
        else:
            default_folder = (
                self.db.query(ContactFolder)
                .filter(
                    ContactFolder.owner_id == self.user_id,
                    ContactFolder.is_default.is_(True),
                )
                .first()
            )
            if default_folder:
                folder_id = default_folder.id

        contact = Contact(owner_id=self.user_id, folder_id=folder_id)
        self._apply_contact_fields(contact, data)
        if contact.display_name is None:
            contact.display_name = self._derive_display_name(contact)
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def _derive_display_name(self, contact: Contact) -> str:
        parts = [contact.given_name, contact.middle_name, contact.surname]
        candidate = " ".join([p for p in parts if p])
        return candidate or contact.email_address_1 or contact.nick_name or "(No Name)"

    def update_contact(self, contact_uuid: str, data: dict) -> Contact:
        contact = (
            self.db.query(Contact)
            .filter(
                Contact.owner_id == self.user_id,
                Contact.uuid == contact_uuid,
            )
            .first()
        )
        if not contact:
            raise ValueError("Contact not found")

        folder_uuid = data.pop("folder_uuid", None)
        if folder_uuid:
            folder = self.get_folder_by_uuid(folder_uuid)
            if not folder:
                raise ValueError("Contact folder not found")
            contact.folder_id = folder.id

        self._apply_contact_fields(contact, data)
        if not contact.display_name:
            contact.display_name = self._derive_display_name(contact)
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def delete_contact(self, contact_uuid: str) -> bool:
        contact = (
            self.db.query(Contact)
            .filter(
                Contact.owner_id == self.user_id,
                Contact.uuid == contact_uuid,
            )
            .first()
        )
        if not contact:
            return False
        self.db.delete(contact)
        self.db.commit()
        return True

    def get_contact(self, contact_uuid: str) -> Optional[Contact]:
        return (
            self.db.query(Contact)
            .filter(
                Contact.owner_id == self.user_id,
                Contact.uuid == contact_uuid,
            )
            .first()
        )

    def list_contacts(self, folder_uuid: Optional[str] = None) -> List[Contact]:
        query = self.db.query(Contact).filter(Contact.owner_id == self.user_id)
        if folder_uuid:
            folder = self.get_folder_by_uuid(folder_uuid)
            if not folder:
                raise ValueError("Contact folder not found")
            query = query.filter(Contact.folder_id == folder.id)
        return query.order_by(Contact.display_name.asc()).all()

    # Tree ---------------------------------------------------------------------------
    def build_folder_tree(self) -> List[dict]:
        folders = self.list_folders()
        folder_map = {folder.id: folder for folder in folders}
        tree_nodes = []
        for folder in folders:
            node = {
                "uuid": folder.uuid,
                "display_name": folder.display_name,
                "well_known_name": folder.well_known_name,
                "is_default": folder.is_default,
                "children": [],
            }
            if folder.parent_id and folder.parent_id in folder_map:
                parent = folder_map[folder.parent_id]
                if not hasattr(parent, "_tree_children"):
                    parent._tree_children = []  # type: ignore[attr-defined]
                parent._tree_children.append(node)  # type: ignore[attr-defined]
            else:
                tree_nodes.append(node)
            folder._tree_node = node  # type: ignore[attr-defined]

        for folder in folders:
            if hasattr(folder, "_tree_children"):
                folder._tree_node["children"] = folder._tree_children  # type: ignore[attr-defined]
        return tree_nodes
