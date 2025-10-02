#!/usr/bin/env python3
"""Add pending_* columns for two-phase commit"""
from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text('ALTER TABLE activesync_state ADD COLUMN pending_sync_key TEXT'))
        print('✅ Added pending_sync_key')
    except Exception as e:
        print(f'pending_sync_key: {e}')
    
    try:
        conn.execute(text('ALTER TABLE activesync_state ADD COLUMN pending_max_email_id INTEGER'))
        print('✅ Added pending_max_email_id')
    except Exception as e:
        print(f'pending_max_email_id: {e}')
    
    try:
        conn.execute(text('ALTER TABLE activesync_state ADD COLUMN pending_item_ids TEXT'))
        print('✅ Added pending_item_ids')
    except Exception as e:
        print(f'pending_item_ids: {e}')
    
    conn.commit()
    print('✅ Migration complete!')
