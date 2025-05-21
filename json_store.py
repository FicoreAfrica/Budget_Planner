import json
import os
import uuid
import logging
from datetime import datetime
from flask import session

# Configure logging
logging.basicConfig(filename='data/storage.txt', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class JsonStorage:
    """Custom JSON storage class to manage records with session ID, user email, and timestamps."""
    def __init__(self, filename):
        self.filename = filename
        # Ensure data directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        # Initialize or validate file
        self._initialize_file()

    def _initialize_file(self):
        """Initialize file if it doesn't exist and check write permissions."""
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w') as f:
                    json.dump([], f)
                logging.info(f"Created new file {self.filename}")
            except Exception as e:
                logging.error(f"Failed to create {self.filename}: {str(e)}")
                raise
        if not os.access(self.filename, os.W_OK):
            logging.error(f"No write permissions for {self.filename}")
            raise PermissionError(f"Cannot write to {self.filename}")

    def _read(self, max_retries=3):
        """Read JSON file content with retry logic."""
        for attempt in range(max_retries):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in {self.filename} (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                return []
            except Exception as e:
                logging.error(f"Error reading {self.filename} (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    return []
                time.sleep(1)  # Brief pause before retry
        return []

    def _write(self, data, max_retries=3):
        """Write data to JSON file with retry logic."""
        for attempt in range(max_retries):
            try:
                with open(self.filename, 'w') as f:
                    json.dump(data, f, indent=2)
                logging.info(f"Successfully wrote to {self.filename}")
                return True
            except Exception as e:
                logging.error(f"Error writing to {self.filename} (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)  # Brief pause before retry
        return False

    def append(self, record, user_email=None, session_id=None):
        """Append a record with ID, email, session ID, and timestamp."""
        try:
            # Default to Flask session ID if not provided
            session_id = session_id or session.get('sid', str(uuid.uuid4()))
            user_email = user_email or session.get('user_email', 'anonymous')
            records = self._read()
            record_id = str(uuid.uuid4())
            record_with_metadata = {
                "id": record_id,
                "user_email": user_email,
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": record.get("data", {})
            }
            logging.debug(f"Appending record: {record_with_metadata}")
            records.append(record_with_metadata)
            if self._write(records):
                logging.info(f"Appended record {record_id} to {self.filename} for session {session_id}")
                return record_id
            else:
                logging.error(f"Failed to write record {record_id} after retries")
                return None
        except Exception as e:
            logging.exception(f"Critical error appending to {self.filename}: {str(e)}")
            return None

    def filter_by_session(self, session_id):
        """Retrieve records matching the session ID."""
        try:
            records = self._read()
            filtered = [r for r in records if r.get("session_id") == session_id]
            logging.debug(f"Filtered {len(filtered)} records for session {session_id}")
            return filtered
        except Exception as e:
            logging.exception(f"Error filtering {self.filename} by session_id {session_id}: {str(e)}")
            return []

    def get_by_id(self, record_id):
        """Retrieve a record by ID."""
        try:
            records = self._read()
            for record in records:
                if record.get("id") == record_id:
                    logging.debug(f"Retrieved record {record_id}")
                    return record
            logging.warning(f"Record {record_id} not found in {self.filename}")
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
                        "data": updated_record.get("data", {})
                    }
                    if self._write(records):
                        logging.info(f"Updated record {record_id} in {self.filename}")
                        return True
                    logging.error(f"Failed to write updated record {record_id}")
                    return False
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
                if self._write(records):
                    logging.info(f"Deleted record {record_id} from {self.filename}")
                    return True
                logging.error(f"Failed to write after deleting record {record_id}")
                return False
            logging.error(f"Record {record_id} not found in {self.filename}")
            return False
        except Exception as e:
            logging.exception(f"Error deleting record {record_id} from {self.filename}: {str(e)}")
            return False

# Instantiate the storage with the financial health file
financial_health_storage = JsonStorage(filename="data/financial_health.json")
