import json
import os
import uuid
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG)

class JsonStorage:
    """Custom JSON storage class to manage records with session ID, user email, and timestamps."""
    def __init__(self, filename):
        self.filename = filename
        # Ensure data directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        # Initialize file if it doesn't exist
        if not os.path.exists(filename):
            with open(filename, 'w') as f:
                json.dump([], f)

    def _read(self):
        """Read JSON file content."""
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.exception(f"Error reading {self.filename}: {str(e)}")
            return []

    def _write(self, data):
        """Write data to JSON file."""
        try:
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.exception(f"Error writing to {self.filename}: {str(e)}")

    def append(self, record, user_email=None, session_id=None):
        """Append a record with ID, email, session ID, and timestamp."""
        try:
            records = self._read()
            record_id = str(uuid.uuid4())
            record_with_metadata = {
                "id": record_id,
                "user_email": user_email,
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": record["data"]
            }
            records.append(record_with_metadata)
            self._write(records)
            logging.info(f"Appended record {record_id} to {self.filename}")
            return True
        except Exception as e:
            logging.exception(f"Error appending to {self.filename}: {str(e)}")
            return False

    def filter_by_session(self, session_id):
        """Retrieve records matching the session ID."""
        try:
            records = self._read()
            return [r for r in records if r.get("session_id") == session_id]
        except Exception as e:
            logging.exception(f"Error filtering {self.filename} by session_id {session_id}: {str(e)}")
            return []

    def get_by_id(self, record_id):
        """Retrieve a record by ID."""
        try:
            records = self._read()
            for record in records:
                if record.get("id") == record_id:
                    return record
            return None
        except Exception as e:
            logging.exception(f"Error getting record {record_id} from {self.filename}: {str(e)}")
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
                        "data": updated_record["data"]
                    }
                    self._write(records)
                    logging.info(f"Updated record {record_id} in {self.filename}")
                    return True
            logging.error(f"Record {record_id} not found in {self.filename}")
            return False
        except Exception as e:
            logging.exception(f"Error updating record {record_id} in {self.filename}: {str(e)}")
            return False

    def delete_by_id(self, record_id):
        """Delete a record by ID."""
        try:
            records = self._read()
            initial_len = len(records)
            records = [r for r in records if r.get("id") != record_id]
            if len(records) < initial_len:
                self._write(records)
                logging.info(f"Deleted record {record_id} from {self.filename}")
                return True
            logging.error(f"Record {record_id} not found in {self.filename}")
            return False
        except Exception as e:
            logging.exception(f"Error deleting record {record_id} from {self.filename}: {str(e)}")
            return False
