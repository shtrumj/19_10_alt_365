"""
MAPI/HTTP Protocol Constants

All constants from Microsoft specifications:
- MS-OXCMAPIHTTP: MAPI/HTTP Transport
- MS-OXCROPS: Remote Operations
- MS-OXCDATA: Data Structures
- MS-OXCFOLD: Folder Operations
- MS-OXCMSG: Message Operations
"""

# ============================================================================
# MAPI/HTTP Commands (MS-OXCMAPIHTTP Section 2.2.2.1)
# ============================================================================

MAPI_CMD_CONNECT = "Connect"
MAPI_CMD_EXECUTE = "Execute"
MAPI_CMD_DISCONNECT = "Disconnect"
MAPI_CMD_NOTIFICATIONWAIT = "NotificationWait"

# ============================================================================
# Property Types (MS-OXCDATA Section 2.11.1)
# ============================================================================

PT_UNSPECIFIED = 0x0000
PT_NULL = 0x0001
PT_I2 = 0x0002  # 16-bit signed integer
PT_LONG = 0x0003  # 32-bit signed integer
PT_R4 = 0x0004  # 4-byte floating point
PT_DOUBLE = 0x0005  # 8-byte floating point
PT_CURRENCY = 0x0006  # 8-byte signed integer (currency)
PT_APPTIME = 0x0007  # 8-byte floating point (application time)
PT_ERROR = 0x000A  # 32-bit error value
PT_BOOLEAN = 0x000B  # 16-bit boolean (0 or 1)
PT_OBJECT = 0x000D  # Object (embedded)
PT_I8 = 0x0014  # 64-bit signed integer
PT_STRING8 = 0x001E  # 8-bit character string
PT_UNICODE = 0x001F  # Unicode character string
PT_SYSTIME = 0x0040  # FILETIME (64-bit)
PT_CLSID = 0x0048  # GUID
PT_SVREID = 0x00FB  # Server Entry ID
PT_SRESTRICT = 0x00FD  # Restriction
PT_ACTIONS = 0x00FE  # Rule actions
PT_BINARY = 0x0102  # Binary data

# Multi-value property types
PT_MV_I2 = 0x1002
PT_MV_LONG = 0x1003
PT_MV_R4 = 0x1004
PT_MV_DOUBLE = 0x1005
PT_MV_CURRENCY = 0x1006
PT_MV_APPTIME = 0x1007
PT_MV_I8 = 0x1014
PT_MV_STRING8 = 0x101E
PT_MV_UNICODE = 0x101F
PT_MV_SYSTIME = 0x1040
PT_MV_CLSID = 0x1048
PT_MV_BINARY = 0x1102

# Property type names for debugging
PROPERTY_TYPE_NAMES = {
    PT_UNSPECIFIED: "PT_UNSPECIFIED",
    PT_NULL: "PT_NULL",
    PT_I2: "PT_I2",
    PT_LONG: "PT_LONG",
    PT_BOOLEAN: "PT_BOOLEAN",
    PT_STRING8: "PT_STRING8",
    PT_UNICODE: "PT_UNICODE",
    PT_SYSTIME: "PT_SYSTIME",
    PT_BINARY: "PT_BINARY",
    PT_MV_STRING8: "PT_MV_STRING8",
    PT_MV_UNICODE: "PT_MV_UNICODE",
}

# ============================================================================
# Common Property Tags (MS-OXPROPS)
# ============================================================================

# Object properties
PR_ENTRYID = 0x0FFF0102  # Entry ID
PR_INSTANCE_KEY = 0x0FF60102  # Instance key
PR_RECORD_KEY = 0x0FF90102  # Record key
PR_OBJECT_TYPE = 0x0FFE0003  # Object type

# Display properties
PR_DISPLAY_NAME = 0x3001001F  # Display name
PR_DISPLAY_NAME_A = 0x3001001E  # Display name (ASCII)
PR_COMMENT = 0x3004001F  # Comment
PR_CREATION_TIME = 0x30070040  # Creation time
PR_LAST_MODIFICATION_TIME = 0x30080040  # Last modification time

# Folder properties
PR_FOLDER_TYPE = 0x36010003  # Folder type
PR_CONTENT_COUNT = 0x36020003  # Content count
PR_CONTENT_UNREAD = 0x36030003  # Unread count
PR_SUBFOLDERS = 0x360A000B  # Has subfolders
PR_PARENT_ENTRYID = 0x0E090102  # Parent entry ID
PR_CONTAINER_CLASS = 0x3613001F  # Container class

# Message properties
PR_MESSAGE_CLASS = 0x001A001F  # Message class
PR_SUBJECT = 0x0037001F  # Subject
PR_SUBJECT_PREFIX = 0x003D001F  # Subject prefix
PR_NORMALIZED_SUBJECT = 0x0E1D001F  # Normalized subject
PR_BODY = 0x1000001F  # Plain text body
PR_BODY_A = 0x1000001E  # Plain text body (ASCII)
PR_HTML = 0x10130102  # HTML body
PR_RTF_COMPRESSED = 0x10090102  # Compressed RTF body
PR_MESSAGE_SIZE = 0x0E080003  # Message size
PR_MESSAGE_FLAGS = 0x0E070003  # Message flags
PR_IMPORTANCE = 0x00170003  # Importance
PR_PRIORITY = 0x00260003  # Priority
PR_SENSITIVITY = 0x00360003  # Sensitivity
PR_CLIENT_SUBMIT_TIME = 0x00390040  # Client submit time
PR_MESSAGE_DELIVERY_TIME = 0x0E060040  # Delivery time
PR_HASATTACH = 0x0E1B000B  # Has attachments

# Recipient properties
PR_RECIPIENT_TYPE = 0x0C150003  # Recipient type
PR_ADDRTYPE = 0x3002001F  # Address type
PR_EMAIL_ADDRESS = 0x3003001F  # Email address
PR_SENDER_NAME = 0x0C1A001F  # Sender name
PR_SENDER_EMAIL_ADDRESS = 0x0C1F001F  # Sender email
PR_SENT_REPRESENTING_NAME = 0x0042001F  # Sent representing name
PR_SENT_REPRESENTING_EMAIL_ADDRESS = 0x0065001F  # Sent representing email

# Attachment properties
PR_ATTACH_NUM = 0x0E210003  # Attachment number
PR_ATTACH_SIZE = 0x0E200003  # Attachment size
PR_ATTACH_FILENAME = 0x3704001F  # Attachment filename
PR_ATTACH_LONG_FILENAME = 0x3707001F  # Attachment long filename
PR_ATTACH_MIME_TAG = 0x370E001F  # MIME type
PR_ATTACH_DATA_BIN = 0x37010102  # Attachment data
PR_ATTACH_METHOD = 0x37050003  # Attachment method

# ============================================================================
# Message Classes (IPM Hierarchy)
# ============================================================================

IPM_NOTE = "IPM.Note"  # Email message
IPM_APPOINTMENT = "IPM.Appointment"  # Calendar appointment
IPM_CONTACT = "IPM.Contact"  # Contact
IPM_TASK = "IPM.Task"  # Task
IPM_STICKYNOTE = "IPM.StickyNote"  # Note
IPM_ACTIVITY = "IPM.Activity"  # Journal entry

# ============================================================================
# Container Classes (Folder Types)
# ============================================================================

IPF_NOTE = "IPF.Note"  # Email folder
IPF_APPOINTMENT = "IPF.Appointment"  # Calendar folder
IPF_CONTACT = "IPF.Contact"  # Contacts folder
IPF_TASK = "IPF.Task"  # Tasks folder
IPF_JOURNAL = "IPF.Journal"  # Journal folder
IPF_STICKYNOTE = "IPF.StickyNote"  # Notes folder

# ============================================================================
# ROP Operation IDs (MS-OXCROPS Section 2.2.1)
# ============================================================================

# Session and object management
ROP_RELEASE = 0x01
ROP_GET_PROPERTIES_SPECIFIC = 0x07
ROP_GET_PROPERTIES_ALL = 0x08
ROP_GET_PROPERTIES_LIST = 0x09
ROP_SET_PROPERTIES = 0x0A
ROP_DELETE_PROPERTIES = 0x0B
ROP_SAVE_CHANGES_MESSAGE = 0x0C
ROP_OPEN_STREAM = 0x2B
ROP_READ_STREAM = 0x2C
ROP_WRITE_STREAM = 0x2D

# Logon and mailbox
ROP_LOGON = 0xFE
ROP_GET_RECEIVE_FOLDER = 0x27
ROP_SET_RECEIVE_FOLDER = 0x26

# Folder operations
ROP_OPEN_FOLDER = 0x02
ROP_CREATE_FOLDER = 0x1C
ROP_DELETE_FOLDER = 0x1D
ROP_EMPTY_FOLDER = 0x58
ROP_MOVE_FOLDER = 0x35
ROP_COPY_FOLDER = 0x36
ROP_GET_HIERARCHY_TABLE = 0x04
ROP_GET_CONTENTS_TABLE = 0x05

# Message operations
ROP_OPEN_MESSAGE = 0x03
ROP_CREATE_MESSAGE = 0x06
ROP_DELETE_MESSAGES = 0x1E
ROP_MOVE_MESSAGES = 0x33
ROP_COPY_MESSAGES = 0x34
ROP_SUBMIT_MESSAGE = 0x32
ROP_ABORT_SUBMIT = 0x87

# Table operations
ROP_SET_COLUMNS = 0x12
ROP_SORT_TABLE = 0x13
ROP_RESTRICT = 0x14
ROP_QUERY_ROWS = 0x15
ROP_QUERY_POSITION = 0x17
ROP_SEEK_ROW = 0x18
ROP_FIND_ROW = 0x4F

# Attachment operations
ROP_GET_ATTACHMENT_TABLE = 0x21
ROP_OPEN_ATTACHMENT = 0x22
ROP_CREATE_ATTACHMENT = 0x23
ROP_DELETE_ATTACHMENT = 0x24
ROP_SAVE_CHANGES_ATTACHMENT = 0x25

# Synchronization operations
ROP_SYNCHRONIZATION_CONFIGURE = 0x70
ROP_SYNCHRONIZATION_GET_TRANSFER_STATE = 0x82
ROP_SYNCHRONIZATION_UPLOAD_STATE = 0x75
ROP_SYNCHRONIZATION_IMPORT_MESSAGE_CHANGE = 0x72
ROP_SYNCHRONIZATION_IMPORT_MESSAGE_DELETION = 0x73
ROP_SYNCHRONIZATION_IMPORT_HIERARCHY_CHANGE = 0x71
ROP_SYNCHRONIZATION_IMPORT_HIERARCHY_DELETION = 0x74

# ROP names for debugging
ROP_NAMES = {
    ROP_RELEASE: "RopRelease",
    ROP_GET_PROPERTIES_SPECIFIC: "RopGetPropertiesSpecific",
    ROP_SET_PROPERTIES: "RopSetProperties",
    ROP_LOGON: "RopLogon",
    ROP_OPEN_FOLDER: "RopOpenFolder",
    ROP_CREATE_FOLDER: "RopCreateFolder",
    ROP_GET_HIERARCHY_TABLE: "RopGetHierarchyTable",
    ROP_GET_CONTENTS_TABLE: "RopGetContentsTable",
    ROP_OPEN_MESSAGE: "RopOpenMessage",
    ROP_CREATE_MESSAGE: "RopCreateMessage",
    ROP_QUERY_ROWS: "RopQueryRows",
    ROP_SET_COLUMNS: "RopSetColumns",
}

# ============================================================================
# Error Codes (MS-OXCDATA Section 2.4)
# ============================================================================

# Success codes
SUCCESS = 0x00000000
MAPI_W_NO_SERVICE = 0x00040203
MAPI_W_ERRORS_RETURNED = 0x00040380

# Error codes
MAPI_E_NO_SUPPORT = 0x80040102
MAPI_E_BAD_CHARWIDTH = 0x80040103
MAPI_E_STRING_TOO_LONG = 0x80040105
MAPI_E_UNKNOWN_FLAGS = 0x80040106
MAPI_E_INVALID_ENTRYID = 0x80040107
MAPI_E_INVALID_OBJECT = 0x80040108
MAPI_E_OBJECT_CHANGED = 0x80040109
MAPI_E_OBJECT_DELETED = 0x8004010A
MAPI_E_BUSY = 0x8004010B
MAPI_E_NOT_ENOUGH_DISK = 0x8004010D
MAPI_E_NOT_ENOUGH_RESOURCES = 0x8004010E
MAPI_E_NOT_FOUND = 0x8004010F
MAPI_E_VERSION = 0x80040110
MAPI_E_LOGON_FAILED = 0x80040111
MAPI_E_SESSION_LIMIT = 0x80040112
MAPI_E_USER_CANCEL = 0x80040113
MAPI_E_UNABLE_TO_ABORT = 0x80040114
MAPI_E_NETWORK_ERROR = 0x80040115
MAPI_E_DISK_ERROR = 0x80040116
MAPI_E_TOO_COMPLEX = 0x80040117
MAPI_E_BAD_COLUMN = 0x80040118
MAPI_E_COMPUTED = 0x8004011A
MAPI_E_CORRUPT_DATA = 0x8004011B
MAPI_E_UNCONFIGURED = 0x8004011C
MAPI_E_FAILONEPROVIDER = 0x8004011D
MAPI_E_UNKNOWN_CPID = 0x8004011E
MAPI_E_UNKNOWN_LCID = 0x8004011F
MAPI_E_CALL_FAILED = 0x80004005
MAPI_E_NOT_INITIALIZED = 0x80040102
MAPI_E_NO_ACCESS = 0x80070005
MAPI_E_COLLISION = 0x80040604
MAPI_E_NOT_ENOUGH_MEMORY = 0x8007000E

# ============================================================================
# Folder Types (MS-OXCFOLD Section 2.2.2.2.2.2)
# ============================================================================

FOLDER_ROOT = 0x00
FOLDER_GENERIC = 0x01
FOLDER_SEARCH = 0x02

# ============================================================================
# Object Types (MS-OXCDATA Section 2.2.1.2)
# ============================================================================

MAPI_STORE = 0x01
MAPI_ADDRBOOK = 0x02
MAPI_FOLDER = 0x03
MAPI_ABCONT = 0x04
MAPI_MESSAGE = 0x05
MAPI_MAILUSER = 0x06
MAPI_ATTACH = 0x07
MAPI_DISTLIST = 0x08
MAPI_PROFSECT = 0x09
MAPI_STATUS = 0x0A
MAPI_SESSION = 0x0B
MAPI_FORMINFO = 0x0C

# ============================================================================
# Recipient Types (MS-OXCMSG Section 2.2.1.4)
# ============================================================================

MAPI_TO = 0x00000001  # To recipient
MAPI_CC = 0x00000002  # CC recipient
MAPI_BCC = 0x00000003  # BCC recipient

# ============================================================================
# Message Flags (MS-OXCMSG Section 2.2.1.6)
# ============================================================================

MSGFLAG_READ = 0x00000001  # Message has been read
MSGFLAG_UNMODIFIED = 0x00000002  # Message has not been modified
MSGFLAG_SUBMIT = 0x00000004  # Message is being sent
MSGFLAG_UNSENT = 0x00000008  # Message has not been sent
MSGFLAG_HASATTACH = 0x00000010  # Message has attachments
MSGFLAG_FROMME = 0x00000020  # User is the sender
MSGFLAG_ASSOCIATED = 0x00000040  # FAI message
MSGFLAG_RESEND = 0x00000080  # Message is being resent
MSGFLAG_RN_PENDING = 0x00000100  # Read receipt pending
MSGFLAG_NRN_PENDING = 0x00000200  # Non-read receipt pending

# ============================================================================
# Table Status (MS-OXCTABL Section 2.2.2.1.3)
# ============================================================================

TBLSTAT_COMPLETE = 0x00  # All rows available
TBLSTAT_SORTING = 0x09  # Table is being sorted
TBLSTAT_SORT_ERROR = 0x0A  # Sort error occurred
TBLSTAT_SETTING_COLS = 0x0B  # Columns are being set
TBLSTAT_SETCOL_ERROR = 0x0D  # SetColumns error occurred
TBLSTAT_RESTRICTING = 0x0E  # Restriction being applied
TBLSTAT_RESTRICT_ERROR = 0x0F  # Restriction error occurred
