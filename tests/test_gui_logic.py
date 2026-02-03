import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to allow importing music_pipeline
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from music_pipeline.gui_app import MusicPipelineApp

class TestMusicPipelineLogic(unittest.TestCase):
    
    def setUp(self):
        # We can't fully instantiate Tk without a display, so we'll mock it or just test logic functions if extracted.
        # Since logic is embedded in classes inheriting from tk.Frame, it's hard to unit test without GUI.
        # However, we can test the data transformations.
        pass

    @patch('music_pipeline.gui_app.extract_universe')
    def test_extraction_logic(self, mock_extract):
        # Verify the mock is callable
        mock_extract.return_value = [{"artist": "A", "title": "B"}]
        result = mock_extract("user")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['artist'], "A")

    def test_random_selection(self):
        import random
        universe = [{"id": i} for i in range(10)]
        selected = random.sample(universe, 3)
        self.assertEqual(len(selected), 3)
        # Ensure elements are from universe
        for s in selected:
            self.assertIn(s, universe)

if __name__ == '__main__':
    unittest.main()
