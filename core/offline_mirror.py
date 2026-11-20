import json
from datetime import datetime, timezone
from core.db import get_db

BUCKET_NAME = "voyatrace-backups"

def mirror(filename: str, record: dict):
    """
    Uploads a JSON record to Supabase Storage as an offline backup.
    Creates a new, timestamped file for every backup.
    """
    db = get_db()
    
    # Add a timestamp to the record and generate a unique filename
    record = {**record, "_mirrored_at": datetime.now(timezone.utc).isoformat()}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    # e.g., 'visa_rules_20261120_103000.json'
    file_name = f"{filename.split('.')[0]}_{timestamp}.json"
    
    try:
        # Convert the dictionary to a pretty-printed JSON string and encode it as bytes
        json_bytes = json.dumps([record], indent=2, default=str).encode('utf-8')
        
        # Upload directly to Supabase Storage
        db.storage.from_(BUCKET_NAME).upload(
            path=file_name,
            file=json_bytes,
            file_options={"content-type": "application/json"}
        )
        print(f"✅ Backup successfully uploaded to Supabase Storage: {file_name}")
        
    except Exception as e:
        # We don't want the main app to crash if the backup fails, so we just log it.
        print(f"⚠️ Could not upload backup to Supabase Storage: {e}")
