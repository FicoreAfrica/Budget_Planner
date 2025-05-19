import unittest
import os
import json
import uuid
from datetime import datetime
from json_store import JsonStorageManager

class TestJsonStorageManager(unittest.TestCase):
    def setUp(self):
        self.test_file = 'data/test_storage.json'
        self.storage = JsonStorageManager(self.test_file)
        # Ensure clean state
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_save_and_retrieve(self):
        session_id = str(uuid.uuid4())
        data = {'key': 'value'}
        self.storage.save(data, session_id)
        
        records = self.storage.get_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['session_id'], session_id)
        self.assertEqual(records[0]['data'], data)
        self.assertTrue('id' in records[0])
        self.assertTrue('timestamp' in records[0])

    def test_filter_by_session(self):
        session_id1 = str(uuid.uuid4())
        session_id2 = str(uuid.uuid4())
        self.storage.save({'key1': 'value1'}, session_id1)
        self.storage.save({'key2': 'value2'}, session_id2)
        
        records = self.storage.filter_by_session(session_id1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['session_id'], session_id1)
        self.assertEqual(records[0]['data'], {'key1': 'value1'})

    def test_empty_file(self):
        records = self.storage.get_all()
        self.assertEqual(records, [])
        records = self.storage.filter_by_session(str(uuid.uuid4()))
        self.assertEqual(records, [])

    def test_file_creation(self):
        self.assertTrue(os.path.exists(self.test_file))
        with open(self.test_file, 'r') as f:
            data = json.load(f)
        self.assertEqual(data, [])

if __name__ == '__main__':
    unittest.main()