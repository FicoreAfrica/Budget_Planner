import json
import os.path
import uuid
import logging
from datetime import datetime
from flask import session, has_request_context

class JsonStorage:
    """Custom JSON storage class to manage records with session ID, user email, and timestamps."""
    def __init__(self, filename, logger_instance=None):
        # Use filename as provided, assuming it's relative to project root
        self.filename = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', filename))
        self.logger = logger_instance if logger_instance else logging.getLogger('ficore_app.json_store')
        if not logger_instance:
            self.logger.setLevel(logging.DEBUG)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                self.logger.addHandler(handler)

        # Create directory if it doesn't exist
        dir_path = os.path.dirname(self.filename)
        if dir_path:
            self.logger.debug(f"Creating directory {dir_path} if it does not exist", extra={'session_id': 'init'})
            os.makedirs(dir_path, exist_ok=True)
        else:
            self.logger.warning(f"No directory specified for {self.filename}, using current directory", extra={'session_id': 'init'})

        self.logger.debug(f"Starting initialization for {self.filename}", extra={'session_id': 'init'})
        self._initialize_file()
        self.logger.info(f"Initialized JsonStorage for {os.path.basename(self.filename)} at {self.filename}", extra={'session_id': 'init'})

    def _initialize_file(self):
        """Initialize file if it doesn't exist and check write permissions."""
        self.logger.debug(f"Entering _initialize_file for {self.filename}", extra={'session_id': 'init'})
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, 'w') as f:
                    json.dump([], f)
                self.logger.info(f"Created new file {self.filename}", extra={'session_id': 'init'})
            except Exception as e:
                self.logger.error(f"Failed to create {self.filename}: {str(e)}", exc_info=True, extra={'session_id': 'init'})
                raise

        if not os.access(self.filename, os.W_OK):
            self.logger.error(f"No write permissions for {self.filename}", extra={'session_id': 'init'})
            raise PermissionError(f"Cannot write to {self.filename}")

        self.logger.debug(f"Completed _initialize_file for {self.filename}", extra={'session_id': 'init'})

    def _read(self, session_id=None):
        """Reads all records from the JSON file, handling old/new data structures."""
        current_session_id = session_id or (session.get('sid', 'unknown') if has_request_context() else 'no-request-context')
        self.logger.debug(f"Entering _read for {self.filename}", extra={'session_id': current_session_id})
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    data = json.load(f)

                    if not isinstance(data, list):
                        self.logger.warning(f"Invalid data format in {self.filename}: expected list, got {type(data)}", extra={'session_id': current_session_id})
                        return []

                    # Special handling for courses.json: return raw records
                    if os.path.basename(self.filename) == 'courses.json':
                        valid_records = []
                        for record in data:
                            if not isinstance(record, dict):
                                self.logger.warning(f"Skipping non-dict record in {self.filename}: {record}", extra={'session_id': current_session_id})
                                continue
                            if 'id' not in record or 'title_en' not in record or 'title_ha' not in record:
                                self.logger.warning(f"Skipping course record with missing required keys in {self.filename}: {record}", extra={'session_id': current_session_id})
                                continue
                            valid_records.append(record)
                        self.logger.debug(f"Read {len(valid_records)} course records from {self.filename}", extra={'session_id': current_session_id})
                        return valid_records

                    # Standard handling for other files
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

    def read_all(self, session_id=None):
        """Retrieve all records from the JSON file."""
        current_session_id = session_id or (session.get('sid', 'unknown') if has_request_context() else 'no-request-context')
        self.logger.debug(f"Entering read_all for {self.filename}", extra={'session_id': current_session_id})
        return self._read(session_id=session_id)

    def _write(self, data, session_id=None):
        """Writes data to the JSON file."""
        current_session_id = session_id or (session.get('sid', 'unknown') if has_request_context() else 'no-request-context')
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
        current_session_id = session_id or (session.get('sid', str(uuid.uuid4())) if has_request_context() else str(uuid.uuid4()))
        current_user_email = user_email or (session.get('user_email', 'anonymous') if has_request_context() else 'anonymous')

        self.logger.debug(f"Entering append for {self.filename}, record: {record}", extra={'session_id': current_session_id})
        try:
            records = self._read(session_id=current_session_id)
            record_id = str(uuid.uuid4())
            # Skip metadata wrapping for courses.json
            if os.path.basename(self.filename) == 'courses.json':
                record_with_metadata = record
            else:
                record_with_metadata = {
                    "id": record_id,
                    "user_email": current_user_email,
                    "session_id": current_session_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "data": record
                }
            self.logger.debug(f"Appending record: {record_with_metadata}", extra={'session_id': current_session_id})
            records.append(record_with_metadata)
            if self._write(records, session_id=current_session_id):
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
        current_session_id = session_id or (session.get('sid', 'unknown') if has_request_context() else 'no-request-context')
        self.logger.debug(f"Entering filter_by_session for {self.filename}, session_id: {session_id}", extra={'session_id': current_session_id})
        try:
            records = self._read(session_id=current_session_id)
            if os.path.basename(self.filename) == 'courses.json':
                return records  # Courses are not session-specific
            filtered = [r for r in records if r.get("session_id") == session_id]
            self.logger.debug(f"Filtered {len(filtered)} records for session {session_id}", extra={'session_id': current_session_id})
            return filtered
        except Exception as e:
            self.logger.exception(f"Error filtering {self.filename} by session_id {session_id}: {str(e)}", extra={'session_id': current_session_id})
            return []

    def filter_by_email(self, email, session_id=None):
        """Retrieve records matching the user email."""
        current_session_id = session_id or (session.get('sid', 'unknown') if has_request_context() else 'no-request-context')
        self.logger.debug(f"Entering filter_by_email for {self.filename}, email: {email}", extra={'session_id': current_session_id})
        try:
            records = self._read(session_id=current_session_id)
            if os.path.basename(self.filename) == 'courses.json':
                return []  # Courses are not email-specific
            filtered = [r for r in records if r.get("user_email") == email]
            self.logger.debug(f"Filtered {len(filtered)} records for email {email}", extra={'session_id': current_session_id})
            return filtered
        except Exception as e:
            self.logger.exception(f"Error filtering {self.filename} by email {email}: {str(e)}", extra={'session_id': current_session_id})
            return []

    def get_by_id(self, record_id, session_id=None):
        """Retrieve a record by ID."""
        current_session_id = session_id or (session.get('sid', 'unknown') if has_request_context() else 'no-request-context')
        self.logger.debug(f"Entering get_by_id for {self.filename}, record_id: {record_id}", extra={'session_id': current_session_id})
        try:
            records = self._read(session_id=current_session_id)
            for record in records:
                if record.get("id") == record_id:
                    self.logger.debug(f"Retrieved record {record_id}", extra={'session_id': record.get('session_id', 'unknown')})
                    return record
            self.logger.warning(f"Record {record_id} not found in {self.filename}", extra={'session_id': current_session_id})
            return None
        except Exception as e:
            self.logger.exception(f"Error getting record {record_id} from {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return None

    def update_by_id(self, record_id, updated_record, session_id=None):
        """Update a record by ID."""
        current_session_id = session_id or (session.get('sid', 'unknown') if has_request_context() else 'no-request-context')
        self.logger.debug(f"Entering update_by_id for {self.filename}, record_id: {record_id}", extra={'session_id': current_session_id})
        try:
            records = self._read(session_id=current_session_id)
            found_record = None
            for i, record in enumerate(records):
                if record.get("id") == record_id:
                    found_record = record
                    if os.path.basename(self.filename) == 'courses.json':
                        records[i] = updated_record
                    else:
                        records[i]['data'] = updated_record.get('data', updated_record)
                    break

            if found_record:
                if self._write(records, session_id=current_session_id):
                    self.logger.info(f"Updated record {record_id} in {self.filename}", extra={'session_id': found_record.get('session_id', 'unknown')})
                    return True
                self.logger.error(f"Failed to write updated record {record_id}", extra={'session_id': found_record.get('session_id', 'unknown')})
                return False

            self.logger.error(f"Record {record_id} not found for update in {self.filename}", extra={'session_id': current_session_id})
            return False
        except Exception as e:
            self.logger.exception(f"Error updating record {record_id} in {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return False

    def delete_by_id(self, record_id, session_id=None):
        """Delete a record by ID."""
        current_session_id = session_id or (session.get('sid', 'unknown') if has_request_context() else 'no-request-context')
        self.logger.debug(f"Entering delete_by_id for {self.filename}, record_id: {record_id}", extra={'session_id': current_session_id})
        try:
            records = self._read(session_id=current_session_id)
            initial_len = len(records)
            records = [r for r in records if r.get("id") != record_id]
            if len(records) < initial_len:
                if self._write(records, session_id=current_session_id):
                    self.logger.info(f"Deleted record {record_id} from {self.filename}", extra={'session_id': current_session_id})
                    return True
                self.logger.error(f"Failed to write after deleting record {record_id}", extra={'session_id': current_session_id})
                return False
            self.logger.warning(f"Record {record_id} not found for deletion in {self.filename}", extra={'session_id': current_session_id})
            return False
        except Exception as e:
            self.logger.exception(f"Error deleting record {record_id} from {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return False

    def create(self, data, session_id=None):
        """Initialize the JSON file with the provided data, overwriting any existing content."""
        current_session_id = session_id or (session.get('sid', 'unknown') if has_request_context() else 'no-request-context')
        self.logger.debug(f"Entering create for {self.filename}", extra={'session_id': current_session_id})
        try:
            if not isinstance(data, list):
                self.logger.error(f"Invalid data format for create in {self.filename}: expected list, got {type(data)}", extra={'session_id': current_session_id})
                raise ValueError(f"Data must be a list, got {type(data)}")

            # For courses.json, ensure records have required fields
            if os.path.basename(self.filename) == 'courses.json':
                for record in data:
                    if not isinstance(record, dict) or not all(key in record for key in ['id', 'title_en', 'title_ha']):
                        self.logger.error(f"Invalid course record in create for {self.filename}: {record}", extra={'session_id': current_session_id})
                        raise ValueError(f"Course record missing required keys: {record}")

            if self._write(data, session_id=current_session_id):
                self.logger.info(f"Created {self.filename} with {len(data)} records", extra={'session_id': current_session_id})
                return True
            else:
                self.logger.error(f"Failed to create {self.filename}", extra={'session_id': current_session_id})
                return False
        except Exception as e:
            self.logger.exception(f"Error creating {self.filename}: {str(e)}", extra={'session_id': current_session_id})
            return False
