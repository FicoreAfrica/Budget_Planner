import json
import os
import uuid
import logging
from datetime import datetime
from flask import session, has_request_context, has_app_context

class JsonStorage:
    """Custom JSON storage class to manage records with session ID, user email, and timestamps."""
    def __init__(self, filename, logger_instance=None):
        self.filename = filename
        self.logger = logger_instance if logger_instance else logging.getLogger('ficore_app.json_store')
        if not logger_instance:
            self.logger.setLevel(logging.DEBUG)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                self.logger.addHandler(handler)

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self.logger.debug(f"Starting initialization for {filename}", extra={'session_id': 'init'})
        self._initialize_file()
        self.logger.info(f"Initialized JsonStorage for {os.path.basename(filename)} at {filename}", extra={'session_id': 'init'})

    def _initialize_file(self):
        """Initialize file if it doesn't exist and check write permissions."""
        current_session_id = 'init'
        self.logger.debug(f"Entering _initialize_file for {self.filename}", extra={'session_id': current_session_id})
        
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w') as f:
                    json.dump([], f)
                self.logger.info(f"Created new file {self.filename}", extra={'session_id': current_session_id})
            except Exception as e:
                self.logger.error(f"Failed to create {self.filename}: {str(e)}", exc_info=True, extra={'session_id': current_session_id})
                raise
        
        if not os.access(self.filename, os.W_OK):
            self.logger.error(f"No write permissions for {self.filename}", extra={'session_id': current_session_id})
            raise PermissionError(f"Cannot write to {self.filename}")
        
        self.logger.debug(f"Completed _initialize_file for {self.filename}", extra={'session_id': current_session_id})

    def _read(self):
        """Reads all records from the JSON file, handling old/new data structures."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        self.logger.debug(f"Entering _read for {self.filename}", extra={'session_id': current_session_id})
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    
                    cleaned_data = []
                    for record in data:
                        if not isinstance(record, dict):
                            self.logger.warning(f"Skipping non-dict record in {self.filename}: {record}", extra={'session_id': current_session_id})
                            continue
                        
                        if not all(key in record for key in ['id', 'timestamp', 'data']):
                            self.logger.warning(f"Skipping record with missing keys in {self.filename}: {record}", extra={'session_id': current_session_id})
                            continue

                        processed_data = record['data']
                        if isinstance(processed_data, dict) and 'step' in processed_data:
                            self.logger.debug(f"Record in new format: {record}", extra={'session_id': current_session_id})
                        elif isinstance(processed_data, dict):
                            self.logger.debug(f"Normalizing old format record: {record}", extra={'session_id': current_session_id})
                            processed_data = {'step': None, 'data': processed_data}
                        else:
                            self.logger.warning(f"Skipping record with invalid 'data' type in {self.filename}: {record}", extra={'session_id': current_session_id})
                            continue
                        
                        record['data'] = processed_data
                        cleaned_data.append(record)
                    
                    self.logger.debug(f"Read {len(cleaned_data)} records from {self.filename}", extra={'session_id': current_session_id})
                    return cleaned_data
            self.logger.debug(f"File {self.filename} not found. Returning empty list.", extra={'session_id': current_session_id})
            return []
        except FileNotFoundError:
            self.logger.warning(f"File not found: {self.filename}. Returning empty list.", extra={'session_id': current_session_id})
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON from {self.filename}: {e}", exc_info=True, extra={'session_id': current_session_id})
            return []
        except Exception as e:
            self.logger.exception(f"Unexpected error during _read from {self.filename}: {e}", extra={'session_id': current_session_id})
            return []

    def _write(self, data):
        """Writes data to the JSON file."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        self.logger.debug(f"Entering _write for {self.filename}", extra={'session_id': current_session_id})
        try:
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=4)
            self.logger.info(f"Successfully wrote to {self.filename}", extra={'session_id': current_session_id})
            return True
        except IOError as e:
            self.logger.error(f"Error writing to {self.filename}: {e}", exc_info=True, extra={'session_id': current_session_id})
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected error during _write to {self.filename}: {e}", extra={'session_id': current_session_id})
            return False

    def append(self, record, user_email=None, session_id=None):
        """Appends a new record to the JSON file."""
        current_session_id = session_id
        if not current_session_id and has_request_context():
            current_session_id = session.get('sid', str(uuid.uuid4()))
        elif not current_session_id:
            current_session_id = str(uuid.uuid4())

        current_user_email = user_email
        if not current_user_email and has_request_context():
            current_user_email = session.get('user_email', 'anonymous')
        elif not current_user_email:
            current_user_email = 'anonymous'

        self.logger.debug(f"Entering append for {self.filename}, record: {record}", extra={'session_id': current_session_id})
        try:
            records = self._read()
            record_id = str(uuid.uuid4())
            record_with_metadata = {
                "id": record_id,
                "user_email": current_user_email,
                "session_id": current_session_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": record
            }
            self.logger.debug(f"Appending record: {record_with_metadata}", extra={'session_id': current_session_id})
            records.append(record_with_metadata)
            if self._write(records):
                self.logger.info(f"Appended record {record_id} to {self.filename} for session {current_session_id}", extra={'session_id': current_session_id})
                return record_id
            else:
                self.logger.error(f"Failed to write record {record_id}", extra={'session_id': current_session_id})
                return None
        except Exception as e:
            self.logger.exception(f"Critical error appending to {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return None

    def filter_by_session(self, session_id):
        """Retrieve records matching the session ID."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        self.logger.debug(f"Entering filter_by_session for {self.filename}, session_id: {session_id}", extra={'session_id': current_session_id})
        try:
            records = self._read()
            filtered = [r for r in records if r.get("session_id") == session_id]
            self.logger.debug(f"Filtered {len(filtered)} records for session {session_id}", extra={'session_id': current_session_id})
            return filtered
        except Exception as e:
            self.logger.exception(f"Error filtering {self.filename} by session_id {session_id}: {str(e)}", extra={'session_id': current_session_id})
            return []

    def get_by_id(self, record_id):
        """Retrieve a record by ID."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        self.logger.debug(f"Entering get_by_id for {self.filename}, record_id: {record_id}", extra={'session_id': current_session_id})
        try:
            records = self._read()
            for record in records:
                if record.get("id") == record_id:
                    self.logger.debug(f"Retrieved record {record_id}", extra={'session_id': record.get('session_id', 'unknown')})
                    return record
            self.logger.warning(f"Record {record_id} not found in {self.filename}", extra={'session_id': current_session_id})
            return None
        except Exception as e:
            self.logger.exception(f"Error getting record {record_id} from {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return None

    def update_by_id(self, record_id, updated_record):
        """Update a record by ID."""
        current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        self.logger.debug(f"Entering update_by_id for {self.filename}, record_id: {record_id}", extra={'session_id': current_session_id})
        try:
            records = self._read()
            found_record = None
            for i, record in enumerate(records):
                if record.get("id") == record_id:
                    found_record = record
                    records[i]['data'] = updated_record.get('data', updated_record)
                    break
            
            if found_record:
                if self._write(records):
                    self.logger.info(f"Updated record {record_id} in {self.filename}", extra={'session_id': found_record.get('session_id', 'unknown')})
                    return True
                self.logger.error(f"Failed to write updated record {record_id}", extra={'session_id': found_record.get('session_id', 'unknown')})
                return False
            
            self.logger.error(f"Record {record_id} not found for update in {self.filename}", extra={'session_id': current_session_id})
            return False
        except Exception as e:
            self.logger.exception(f"Error updating record {record_id} in {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return False

    def delete_by_id(self, record_id):
        """Delete a record by ID."""
        try:
            current_session_id = session.get('sid', 'unknown') if has_request_context() else 'no-request-context'
        except RuntimeError:
            current_session_id = 'no-request-context'
        self.logger.debug(f"Entering delete_by_id for {self.filename}, record_id: {record_id}", extra={'session_id': current_session_id})
        try:
            records = self._read()
            initial_len = len(records)
            records = [r for r in records if r.get("id") != record_id]
            if len(records) < initial_len:
                if self._write(records):
                    self.logger.info(f"Deleted record {record_id} from {self.filename}", extra={'session_id': current_session_id})
                    return True
                self.logger.error(f"Failed to write after deleting record {record_id}", extra={'session_id': current_session_id})
                return False
            self.logger.warning(f"Record {record_id} not found for deletion in {self.filename}", extra={'session_id': current_session_id})
            return False
        except Exception as e:
            self.logger.exception(f"Error deleting record {record_id} from {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return False
