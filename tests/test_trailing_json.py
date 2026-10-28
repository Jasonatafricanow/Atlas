import json, unittest
from atlas.tasks.runners import extract_json

class TrailingJson(unittest.TestCase):
    def test_first_object_kept_when_trailing_text(self):
        body = json.dumps({"entities": [], "relations": [], "statements": [{"x": 1}]})
        wrapped = json.dumps({"structuredOutput": None, "text": body + "\n{\"extra\": 1}"})
        self.assertEqual(extract_json(wrapped)["statements"], [{"x": 1}])
        self.assertEqual(extract_json("note " + body + " trailing } text")["statements"], [{"x": 1}])

if __name__ == "__main__":
    unittest.main()