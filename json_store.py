import json
import logging
import os
import uuid
from datetime import datetime
from flask import session, has_request_context # Keep these imports for session context

# Use the logger from app.py (named 'ficore_app')
logger = logging.getLogger('ficore_app')

class JsonStorage:
    """Custom JSON storage class to manage records with session ID, user email, and timestamps."""
    def __init__(self, filename):
        self.filename = filename
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self._initialize_file()
        logger.info(f"Initialized JsonStorage for {os.path.basename(filename)} at {filename}")

    def _initialize_file(self):
        """Initialize file if it doesn't exist and check write permissions."""
        # Get session_id safely for initial logs
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w') as f:
                    json.dump([], f)
                logger.info(f"Created new file {self.filename}", extra={'session_id': current_session_id})
            except Exception as e:
                logger.error(f"Failed to create {self.filename}: {str(e)}", exc_info=True, extra={'session_id': current_session_id})
                raise # Re-raise to indicate critical failure
        
        if not os.access(self.filename, os.W_OK):
            logger.error(f"No write permissions for {self.filename}", extra={'session_id': current_session_id})
            raise PermissionError(f"Cannot write to {self.filename}")

    def _read(self):
        """Reads all records from the JSON file, handling old/new data structures."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    
                    # Robust validation and cleaning for records
                    cleaned_data = []
                    for record in data:
                        if not isinstance(record, dict):
                            logger.warning(f"Skipping non-dict record found in {self.filename}: {record}", extra={'session_id': current_session_id})
                            continue
                        
                        # Ensure essential top-level keys exist
                        if not all(key in record for key in ['id', 'timestamp', 'data']):
                            logger.warning(f"Skipping record with missing essential keys in {self.filename}: {record}", extra={'session_id': current_session_id})
                            continue

                        # Normalize 'data' structure: ensure it's always {'step': X, 'data': { ... }}
                        # Or if it's an old record, wrap it in this structure for consistent access
                        processed_data = record['data']
                        if isinstance(processed_data, dict) and 'step' in processed_data:
                            # Already in new nested format or has 'step'
                            pass
                        elif isinstance(processed_data, dict):
                            # Old format: data is directly under 'data' key without 'step'
                            # Wrap it to simulate the new structure for consistent access
                            processed_data = {'step': None, 'data': processed_data} # Use None for old step
                        else:
                            logger.warning(f"Skipping record with invalid 'data' type in {self.filename}: {record}", extra={'session_id': current_session_id})
                            continue
                        
                        # Re-assign processed data back to the record
                        record['data'] = processed_data
                        cleaned_data.append(record)
                    
                    return cleaned_data
            return []
        except FileNotFoundError:
            logger.warning(f"File not found: {self.filename}. Returning empty list.", extra={'session_id': current_session_id})
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.filename}: {e}", exc_info=True, extra={'session_id': current_session_id})
            return []
        except Exception as e:
            logger.exception(f"Unexpected error during _read from {self.filename}: {e}", extra={'session_id': current_session_id})
            return []

    def _write(self, data):
        """Writes data to the JSON file."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        try:
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=4) # Use indent=4 for readability
            logger.info(f"Successfully wrote to {self.filename}", extra={'session_id': current_session_id})
            return True
        except IOError as e:
            logger.error(f"Error writing to {self.filename}: {e}", exc_info=True, extra={'session_id': current_session_id})
            return False
        except Exception as e:
            logger.exception(f"Unexpected error during _write to {self.filename}: {e}", extra={'session_id': current_session_id})
            return False

    def append(self, record, user_email=None, session_id=None):
        """Appends a new record to the JSON file."""
        # Determine session_id for logging and record metadata
        current_session_id = session_id
        if not current_session_id and has_request_context():
            current_session_id = session.get('sid', str(uuid.uuid4()))
        elif not current_session_id:
            current_session_id = str(uuid.uuid4()) # Fallback for non-request context

        # Determine user_email for record metadata
        current_user_email = user_email
        if not current_user_email and has_request_context():
            current_user_email = session.get('user_email', 'anonymous')
        elif not current_user_email:
            current_user_email = 'anonymous' # Fallback for non-request context

        try:
            records = self._read()
            record_id = str(uuid.uuid4())
            record_with_metadata = {
                "id": record_id,
                "user_email": current_user_email,
                "session_id": current_session_id, # Crucial for filtering
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": record # This 'data' holds the step-specific data (e.g., {'step': 1, 'data': form_data})
            }
            logger.debug(f"Appending record: {record_with_metadata}", extra={'session_id': current_session_id})
            records.append(record_with_metadata)
            if self._write(records):
                logger.info(f"Appended record {record_id} to {self.filename} for session {current_session_id}", extra={'session_id': current_session_id})
                return record_id
            else:
                logger.error(f"Failed to write record {record_id} after _write operation", extra={'session_id': current_session_id})
                return None
        except Exception as e:
            logger.exception(f"Critical error appending to {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return None

    def filter_by_session(self, session_id):
        """Retrieve records matching the session ID."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        try:
            records = self._read()
            filtered = [r for r in records if r.get("session_id") == session_id]
            logger.debug(f"Filtered {len(filtered)} records for session {session_id}", extra={'session_id': current_session_id})
            return filtered
        except Exception as e:
            logger.exception(f"Error filtering {self.filename} by session_id {session_id}: {str(e)}", extra={'session_id': current_session_id})
            return []

    def get_by_id(self, record_id):
        """Retrieve a record by ID."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        try:
            records = self._read()
            for record in records:
                if record.get("id") == record_id:
                    logger.debug(f"Retrieved record {record_id}", extra={'session_id': record.get('session_id', 'unknown')})
                    return record
            logger.warning(f"Record {record_id} not found in {self.filename}", extra={'session_id': current_session_id})
            return None
        except Exception as e:
            logger.exception(f"Error getting record {record_id} from {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return None

    def update_by_id(self, record_id, updated_record):
        """Update a record by ID."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        try:
            records = self._read()
            found_record = None
            for i, record in enumerate(records):
                if record.get("id") == record_id:
                    found_record = record
                    # Update only the 'data' part, preserve metadata
                    records[i]['data'] = updated_record.get('data', updated_record)
                    break
            
            if found_record:
                if self._write(records):
                    logger.info(f"Updated record {record_id} in {self.filename}", extra={'session_id': found_record.get('session_id', 'unknown')})
                    return True
                logger.error(f"Failed to write updated record {record_id}", extra={'session_id': found_record.get('session_id', 'unknown')})
                return False
            
            logger.error(f"Record {record_id} not found for update in {self.filename}", extra={'session_id': current_session_id})
            return False
        except Exception as e:
            logger.exception(f"Error updating record {record_id} in {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return False

    def delete_by_id(self, record_id):
        """Delete a record by ID."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        try:
            records = self._read()
            initial_len = len(records)
            records = [r for r in records if r.get("id") != record_id]
            if len(records) < initial_len:
                if self._write(records):
                    logger.info(f"Deleted record {record_id} from {self.filename}", extra={'session_id': current_session_id})
                    return True
                logger.error(f"Failed to write after deleting record {record_id}", extra={'session_id': current_session_id})
                return False
            logger.warning(f"Record {record_id} not found for deletion in {self.filename}", extra={'session_id': current_session_id})
            return False
        except Exception as e:
            logger.exception(f"Error deleting record {record_id} from {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return False
