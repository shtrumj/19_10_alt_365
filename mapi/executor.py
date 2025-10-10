"""
MAPI ROP Executor

Executes ROP (Remote Operations) commands and generates responses.
"""

import logging
from typing import List, Optional

from .constants import *
from .properties import (
    PropertyStore,
    create_folder_properties,
    create_message_properties,
    get_property_name,
)
from .rop import *
from .session import MapiContext

logger = logging.getLogger(__name__)


class RopExecutor:
    """
    Executes ROP commands within a MAPI context.

    Dispatches to specific ROP handlers based on ROP type.
    """

    def __init__(self, context: MapiContext):
        self.context = context

    def execute_rop_buffer(self, rop_buffer: RopBuffer) -> List[RopResponse]:
        """
        Execute all ROPs in a buffer.

        Returns list of responses (one per ROP).
        """
        responses = []

        for rop in rop_buffer.rop_list:
            try:
                logger.debug(f"Executing {rop}")
                response = self.execute_rop(rop)
                responses.append(response)

                # Stop on first error if critical
                if response.error_code != SUCCESS and response.rop_id == ROP_LOGON:
                    logger.error(f"Critical ROP failed: {rop}, stopping execution")
                    break

            except Exception as e:
                logger.error(f"ROP execution failed: {rop}, error: {e}", exc_info=True)
                # Return error response
                error_response = self._create_error_response(rop, MAPI_E_CALL_FAILED)
                responses.append(error_response)
                break

        return responses

    def execute_rop(self, rop: RopRequest) -> RopResponse:
        """
        Execute a single ROP command.

        Dispatches to specific handler based on ROP ID.
        """

        if isinstance(rop, RopLogonRequest):
            return self.handle_logon(rop)

        elif isinstance(rop, RopGetHierarchyTableRequest):
            return self.handle_get_hierarchy_table(rop)

        elif isinstance(rop, RopGetContentsTableRequest):
            return self.handle_get_contents_table(rop)

        elif isinstance(rop, RopSetColumnsRequest):
            return self.handle_set_columns(rop)

        elif isinstance(rop, RopQueryRowsRequest):
            return self.handle_query_rows(rop)

        elif isinstance(rop, RopOpenFolderRequest):
            return self.handle_open_folder(rop)

        elif isinstance(rop, RopOpenMessageRequest):
            return self.handle_open_message(rop)

        elif isinstance(rop, RopGetPropertiesSpecificRequest):
            return self.handle_get_properties_specific(rop)

        elif isinstance(rop, RopReleaseRequest):
            return self.handle_release(rop)

        else:
            logger.warning(f"Unhandled ROP type: {type(rop).__name__}")
            return self._create_error_response(rop, MAPI_E_NO_SUPPORT)

    def handle_logon(self, rop: RopLogonRequest) -> RopLogonResponse:
        """
        Handle RopLogon - establish mailbox session.

        Returns well-known folder IDs.
        """
        logger.info(f"RopLogon for user {self.context.user.email}")

        # Allocate logon handle (mailbox root)
        logon_obj = self.context.object_manager.allocate_handle(
            object_type="mailbox", entity_type="user", entity_id=self.context.user.id
        )

        # Well-known folder IDs (simplified)
        folder_ids = [
            1,  # Inbox
            2,  # Drafts
            3,  # Sent Items
            4,  # Deleted Items
            5,  # Outbox
            6,  # Junk Email
            7,  # Search Folders
            8,  # Calendar
            9,  # Contacts
            10,  # Tasks
            11,  # Notes
            12,  # Journal
            13,  # Root Folder
        ]

        return RopLogonResponse(
            rop_id=ROP_LOGON,
            handle_index=logon_obj.handle,
            error_code=SUCCESS,
            logon_flags=rop.logon_flags,
            folder_ids=folder_ids,
        )

    def handle_get_hierarchy_table(
        self, rop: RopGetHierarchyTableRequest
    ) -> RopGetHierarchyTableResponse:
        """
        Handle RopGetHierarchyTable - get folder tree.

        Opens a table view of the folder hierarchy.
        """
        logger.info(f"RopGetHierarchyTable handle={rop.handle_index}")

        # Get folders
        folders = self.context.get_user_folders()

        # Allocate table handle
        table_obj = self.context.object_manager.allocate_handle(
            object_type="table", entity_type="folder_hierarchy"
        )

        # Store table data in properties
        # TODO: Store actual folder data for QueryRows

        return RopGetHierarchyTableResponse(
            rop_id=ROP_GET_HIERARCHY_TABLE,
            handle_index=table_obj.handle,
            error_code=SUCCESS,
            row_count=len(folders),
        )

    def handle_get_contents_table(
        self, rop: RopGetContentsTableRequest
    ) -> RopGetContentsTableResponse:
        """
        Handle RopGetContentsTable - get folder contents.

        Opens a table view of messages in a folder.
        """
        logger.info(f"RopGetContentsTable handle={rop.handle_index}")

        # Get folder object
        folder_obj = self.context.object_manager.get_object(rop.handle_index)
        if not folder_obj:
            return RopGetContentsTableResponse(
                rop_id=ROP_GET_CONTENTS_TABLE,
                handle_index=rop.handle_index,
                error_code=MAPI_E_INVALID_OBJECT,
                row_count=0,
            )

        # Get messages in folder
        folder_id = folder_obj.entity_id or self.context.get_user_inbox_id()
        messages = self.context.get_folder_messages(folder_id)

        # Allocate table handle
        table_obj = self.context.object_manager.allocate_handle(
            object_type="table", entity_type="folder_contents", entity_id=folder_id
        )

        # Store message IDs for QueryRows
        # TODO: Store in table properties

        return RopGetContentsTableResponse(
            rop_id=ROP_GET_CONTENTS_TABLE,
            handle_index=table_obj.handle,
            error_code=SUCCESS,
            row_count=len(messages),
        )

    def handle_set_columns(self, rop: RopSetColumnsRequest) -> RopSetColumnsResponse:
        """
        Handle RopSetColumns - set table columns.

        Specifies which properties to return in QueryRows.
        """
        logger.info(
            f"RopSetColumns handle={rop.handle_index} columns={len(rop.property_tags)}"
        )

        # Log requested columns
        for tag in rop.property_tags:
            logger.debug(f"  Column: {get_property_name(tag)}")

        # Store column configuration in table object
        table_obj = self.context.object_manager.get_object(rop.handle_index)
        if not table_obj:
            return RopSetColumnsResponse(
                rop_id=ROP_SET_COLUMNS,
                handle_index=rop.handle_index,
                error_code=MAPI_E_INVALID_OBJECT,
                table_status=TBLSTAT_COMPLETE,
            )

        # Store columns in properties
        # TODO: Actually store column configuration

        return RopSetColumnsResponse(
            rop_id=ROP_SET_COLUMNS,
            handle_index=rop.handle_index,
            error_code=SUCCESS,
            table_status=TBLSTAT_COMPLETE,
        )

    def handle_query_rows(self, rop: RopQueryRowsRequest) -> RopQueryRowsResponse:
        """
        Handle RopQueryRows - query table rows.

        Returns rows from a table (folder hierarchy or contents).
        """
        logger.info(f"RopQueryRows handle={rop.handle_index} count={rop.row_count}")

        # Get table object
        table_obj = self.context.object_manager.get_object(rop.handle_index)
        if not table_obj:
            return RopQueryRowsResponse(
                rop_id=ROP_QUERY_ROWS,
                handle_index=rop.handle_index,
                error_code=MAPI_E_INVALID_OBJECT,
                origin=0,
                row_data=[],
            )

        # Generate rows based on table type
        if table_obj.entity_type == "folder_hierarchy":
            row_data = self._generate_folder_rows(rop.row_count)
        elif table_obj.entity_type == "folder_contents":
            row_data = self._generate_message_rows(table_obj.entity_id, rop.row_count)
        else:
            logger.warning(f"Unknown table type: {table_obj.entity_type}")
            row_data = []

        return RopQueryRowsResponse(
            rop_id=ROP_QUERY_ROWS,
            handle_index=rop.handle_index,
            error_code=SUCCESS,
            origin=0,  # BOOKMARK_BEGINNING
            row_data=row_data,
        )

    def handle_open_folder(self, rop: RopOpenFolderRequest) -> RopOpenFolderResponse:
        """
        Handle RopOpenFolder - open a folder.

        Allocates a handle for the folder.
        """
        logger.info(f"RopOpenFolder folder_id={rop.folder_id}")

        # Allocate folder handle
        folder_obj = self.context.object_manager.allocate_handle(
            object_type="folder", entity_type="folder", entity_id=rop.folder_id
        )

        return RopOpenFolderResponse(
            rop_id=ROP_OPEN_FOLDER,
            handle_index=folder_obj.handle,
            error_code=SUCCESS,
            has_rules=False,
            is_ghost=False,
        )

    def handle_open_message(self, rop: RopOpenMessageRequest) -> RopOpenMessageResponse:
        """
        Handle RopOpenMessage - open a message.

        Allocates a handle for the message.
        """
        logger.info(f"RopOpenMessage message_id={rop.message_id}")

        # Allocate message handle
        message_obj = self.context.object_manager.allocate_handle(
            object_type="message", entity_type="email", entity_id=rop.message_id
        )

        # TODO: Load actual message and extract subject

        return RopOpenMessageResponse(
            rop_id=ROP_OPEN_MESSAGE,
            handle_index=message_obj.handle,
            error_code=SUCCESS,
            has_named_properties=False,
            subject_prefix="",
            normalized_subject="Email Subject",
            recipient_count=1,
            recipient_columns=[],
        )

    def handle_get_properties_specific(
        self, rop: RopGetPropertiesSpecificRequest
    ) -> RopGetPropertiesSpecificResponse:
        """
        Handle RopGetPropertiesSpecific - get object properties.

        Returns requested properties from an object.
        """
        logger.info(
            f"RopGetPropertiesSpecific handle={rop.handle_index} props={len(rop.property_tags)}"
        )

        # Get object
        obj = self.context.object_manager.get_object(rop.handle_index)
        if not obj:
            return RopGetPropertiesSpecificResponse(
                rop_id=ROP_GET_PROPERTIES_SPECIFIC,
                handle_index=rop.handle_index,
                error_code=MAPI_E_INVALID_OBJECT,
                row_data=[],
            )

        # Get properties
        prop_store = self.context.object_manager.get_properties(rop.handle_index)
        if not prop_store:
            # Create default properties based on object type
            if obj.object_type == "message":
                prop_store = create_message_properties(
                    message_id=obj.entity_id or 0,
                    folder_id=0,
                    subject="Test Email",
                    body="This is a test email body.",
                )
            elif obj.object_type == "folder":
                prop_store = create_folder_properties(
                    folder_id=obj.entity_id or 0, display_name="Inbox"
                )
            else:
                prop_store = PropertyStore()

        # Build response with requested properties
        row_data = []
        for tag in rop.property_tags:
            if prop_store.has(tag):
                row_data.append(PropertyValue(tag, prop_store.get(tag)))
            else:
                # Return PT_ERROR for missing property
                error_tag = (tag & 0xFFFF0000) | PT_ERROR
                row_data.append(PropertyValue(error_tag, MAPI_E_NOT_FOUND))

        return RopGetPropertiesSpecificResponse(
            rop_id=ROP_GET_PROPERTIES_SPECIFIC,
            handle_index=rop.handle_index,
            error_code=SUCCESS,
            row_data=row_data,
        )

    def handle_release(self, rop: RopReleaseRequest) -> RopReleaseResponse:
        """
        Handle RopRelease - release object handle.

        Frees the handle for reuse.
        """
        logger.info(f"RopRelease handle={rop.handle_index}")

        self.context.object_manager.release_handle(rop.handle_index)

        return RopReleaseResponse(
            rop_id=ROP_RELEASE, handle_index=rop.handle_index, error_code=SUCCESS
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _generate_folder_rows(self, max_rows: int) -> List[List[PropertyValue]]:
        """Generate rows for folder hierarchy table."""
        folders = self.context.get_user_folders()
        rows = []

        for folder in folders[:max_rows]:
            row = [
                PropertyValue(PR_ENTRYID, folder["id"].to_bytes(8, "little")),
                PropertyValue(PR_DISPLAY_NAME, folder["name"]),
                PropertyValue(PR_CONTAINER_CLASS, folder["type"]),
                PropertyValue(PR_CONTENT_COUNT, 0),
                PropertyValue(PR_CONTENT_UNREAD, 0),
            ]
            rows.append(row)

        return rows

    def _generate_message_rows(
        self, folder_id: int, max_rows: int
    ) -> List[List[PropertyValue]]:
        """Generate rows for folder contents table."""
        messages = self.context.get_folder_messages(folder_id)
        rows = []

        for msg in messages[:max_rows]:
            row = [
                PropertyValue(PR_ENTRYID, msg.id.to_bytes(8, "little")),
                PropertyValue(PR_SUBJECT, msg.subject or "(No Subject)"),
                PropertyValue(PR_SENDER_NAME, msg.sender_email or "Unknown"),
                PropertyValue(PR_MESSAGE_DELIVERY_TIME, msg.created_at),
                PropertyValue(PR_MESSAGE_FLAGS, MSGFLAG_READ if msg.is_read else 0),
            ]
            rows.append(row)

        return rows

    def _create_error_response(self, rop: RopRequest, error_code: int) -> RopResponse:
        """Create a generic error response."""
        # Map ROP types to response types
        response_map = {
            ROP_LOGON: RopLogonResponse,
            ROP_GET_HIERARCHY_TABLE: RopGetHierarchyTableResponse,
            ROP_GET_CONTENTS_TABLE: RopGetContentsTableResponse,
            ROP_SET_COLUMNS: RopSetColumnsResponse,
            ROP_QUERY_ROWS: RopQueryRowsResponse,
            ROP_OPEN_FOLDER: RopOpenFolderResponse,
            ROP_OPEN_MESSAGE: RopOpenMessageResponse,
            ROP_GET_PROPERTIES_SPECIFIC: RopGetPropertiesSpecificResponse,
            ROP_RELEASE: RopReleaseResponse,
        }

        response_class = response_map.get(rop.rop_id)
        if not response_class:
            # Generic response
            return RopResponse(
                rop_id=rop.rop_id, handle_index=rop.handle_index, error_code=error_code
            )

        # Create error response with minimal data
        if rop.rop_id == ROP_LOGON:
            return RopLogonResponse(
                rop_id=rop.rop_id,
                handle_index=rop.handle_index,
                error_code=error_code,
                logon_flags=0,
                folder_ids=[],
            )
        elif rop.rop_id in (ROP_GET_HIERARCHY_TABLE, ROP_GET_CONTENTS_TABLE):
            return response_class(
                rop_id=rop.rop_id,
                handle_index=rop.handle_index,
                error_code=error_code,
                row_count=0,
            )
        elif rop.rop_id == ROP_QUERY_ROWS:
            return RopQueryRowsResponse(
                rop_id=rop.rop_id,
                handle_index=rop.handle_index,
                error_code=error_code,
                origin=0,
                row_data=[],
            )
        else:
            # For other ROPs, use base response
            return RopResponse(
                rop_id=rop.rop_id, handle_index=rop.handle_index, error_code=error_code
            )
