import json
import os
import logging
from datetime import datetime

class JsonStorageManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler('data/storage.log')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump([], f)

    def save(self, data, session_id):
        try:
            with open(self.file_path, 'r') as f:
                records = json.load(f)
        except Exception as e:
            self.logger.error(f"Error reading {self.file_path}: {e}")
            records = []
        
        record = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        records.append(record)
        
        try:
            with open(self.file_path, 'w') as f:
                json.dump(records, f, indent=2)
            self.logger.info(f"Saved record to {self.file_path} with session_id {session_id}")
        except Exception as e:
            self.logger.error(f"Error saving to {self.file_path}: {e}")
            raise

    def filter_by_session(self, session_id):
        try:
            with open(self.file_path, 'r') as f:
                records = json.load(f)
            return [r for r in records if r['session_id'] == session_id]
        except Exception as e:
            self.logger.error(f"Error filtering {self.file_path} by session_id {session_id}: {e}")
            return []

    def get_all(self):
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error reading {self.file_path}: {e}")
            return []