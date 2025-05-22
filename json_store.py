# json_store.py
import json
import os
import uuid
import logging
from datetime import datetime
from flask import session, has_request_context

# Use the logger from app.py
logger = logging.getLogger('ficore_app')

class JsonStorage:
    """Custom JSON storage class to manage records with session ID, user email, and timestamps."""
    def __init__(self, filename):
        self.filename = filename
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self._initialize_file()

    def _initialize_file(self):
        """Initialize file if it doesn't exist and check write permissions."""
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w') as f:
                    json.dump([], f)
                logger.info(f"Created new file {self.filename}")
            except Exception as e:
                logger.error(f"Failed to create {self.filename}: {str(e)}")
                raise
        if not os.access(self.filename, os.W_OK):
            logger.error(f"No write permissions for {self.filename}")
            raise PermissionError(f"Cannot write to {self.filename}")

    def _read(self, max_retries=3):
        """Read JSON file content with retry logic."""
        for attempt in range(max_retries):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {self.filename} (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                return []
            except Exception as e:
                logger.error(f"Error reading {self.filename} (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    return []
                time.sleep(1)
        return []

    def _write(self, data, max_retries=3):
        """Write data to JSON file with retry logic."""
        for attempt in range(max_retries):
            try:
                with open(self.filename, 'w') as f:
                    json.dump(data, f, indent=2)
                logger.info(f"Successfully wrote to {self.filename}")
                return True
            except Exception as e:
                logger.error(f"Error writing to {self.filename} (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)
        return False

    def append(self, record, user_email=None, session_id=None):
        """Append a record with ID, email, session ID, and timestamp."""
        try:
            # Default to Flask session ID if not provided and context exists
            if has_request_context():
                session_id = session_id or session.get('sid', str(uuid.uuid4()))
                user_email = user_email or session.get('user_email', 'anonymous')
            else:
                session_id = session_id or str(uuid.uuid4())
                user_email = user_email or 'anonymous'
            records = self._read()
            record_id = str(uuid.uuid4())
            record_with_metadata = {
                "id": record_id,
                "user_email": user_email,
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": record.get("data", record)  # Allow record to be the data itself
            }
            logger.debug(f"Appending record: {record_with_metadata}", extra={'session_id': session_id})
            records.append(record_with_metadata)
            if self._write(records):
                logger.info(f"Appended record {record_id} to {self.filename} for session {session_id}", extra={'session_id': session_id})
                return record_id
            else:
                logger.error(f"Failed to write record {record_id} after retries", extra={'session_id': session_id})
                return None
        except Exception as e:
            logger.exception(f"Critical error appending to {self.filename}: {str(e)}", extra={'session_id': session_id or 'unknown'})
            return None

    def filter_by_session(self, session_id):
        """Retrieve records matching the session ID."""
        try:
            records = self._read()
            filtered = [r for r in records if r.get("session_id") == session_id]
            logger.debug(f"Filtered {len(filtered)} records for session {session_id}", extra={'session_id': session_id})
            return filtered
        except Exception as e:
            logger.exception(f"Error filtering {self.filename} by session_id {session_id}: {str(e)}", extra={'session_id': session_id})
            return []

    def get_by_id(self, record_id):
        """Retrieve a record by ID."""
        try:
            records = self._read()
            for record in records:
                if record.get("id") == record_id:
                    logger.debug(f"Retrieved record {record_id}", extra={'session_id': record.get('session_id', 'unknown')})
                    return record
            logger.warning(f"Record {record_id} not found in {self.filename}", extra={'session_id': 'unknown'})
            return None
        except Exception as e:
            logger.exception(f"Error getting record {record_id} from {self.filename}: {str(e)}", extra={'session_id': 'unknown'})
            return None

    def update_by_id(self, record_id, updated_record):
        """Update a record by ID."""
        try:
            records = self._read()
            for i, record in enumerate(records):
                if record.get("id") == record_id:
                    records[i] = {
                        "id": record_id,
                        "user_email": record.get("user_email"),
                        "session_id": record.get("session_id"),
                        "timestamp": record.get("timestamp"),
                        "data": updated_record.get("data", {})
                    }
                    if self._write(records):
                        logger.info(f"Updated record {record_id} in {self.filename}", extra={'session_id': record.get('session_id', 'unknown')})
                        return True
                    logger.error(f"Failed to write updated record {record_id}", extra={'session_id': record.get('session_id', 'unknown')})
                    return False
            logger.error(f"Record {record_id} not found in {self.filename}", extra={'session_id': 'unknown'})
            return False
        except Exception as e:
            logger.exception(f"Error updating record {record_id} in {self.filename}: {str(e)}", extra={'session_id': 'unknown'})
            return False

    def delete_by_id(self, record_id):
        """Delete a record by ID."""
        try:
            records = self._read()
            initial_len = len(records)
            records = [r for r in records if r.get("id") != record_id]
            if len(records) < initial_len:
                if self._write(records):
                    logger.info(f"Deleted record {record_id} from {self.filename}", extra={'session_id': 'unknown'})
                    return True
                logger.error(f"Failed to write after deleting record {record_id}", extra={'session_id': 'unknown'})
                return False
            logger.error(f"Record {record_id} not found in {self.filename}", extra={'session_id': 'unknown'})
            return False
        except Exception as e:
            logger.exception(f"Error deleting record {record_id} from {self.filename}: {str(e)}", extra={'session_id': 'unknown'})
            return False
