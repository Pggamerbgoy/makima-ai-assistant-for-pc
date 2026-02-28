import unittest
from unittest.mock import MagicMock
from makima_tools.tool_registry import ToolRegistry

class MockMakima:
    """Mock Makima instance for ToolRegistry initialization."""
    def __init__(self):
        self.ai = MagicMock()
        self.ai_handler = self.ai
        self.speak = MagicMock()
        self.execute_command = MagicMock()

class TestMakimaToolsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize ToolRegistry once for all tests."""
        cls.makima = MockMakima()
        cls.registry = ToolRegistry(cls.makima)
        cls.registry.initialize_all()

    def test_01_shortcut_expander(self):
        """Test ShortcutExpander inside ToolRegistry."""
        # Clean slate: let's add a fake shortcut manually
        self.registry.shortcuts.shortcuts["tst"] = {"expansion": "run the test suite", "uses": 0}
        # Expanding it should return the long form
        _, expanded = self.registry.process_command("tst")
        self.assertEqual(expanded, "run the test suite")

    def test_02_intent_detector(self):
        """Test IntentDetector inside ToolRegistry."""
        # The detect method should correctly classify "learn how to do math"
        _, expanded = self.registry.process_command("learn how to do math")
        intent = self.registry.intent.detect(expanded)
        self.assertEqual(intent.type, "learn_skill")
        self.assertEqual(intent.entities.get('task'), "do math")

    def test_03_response_cache(self):
        """Test ResponseCache pipeline inside ToolRegistry."""
        query = "what is the capital of france"
        answer = "The capital of France is Paris."
        
        # Ensure it's not cached initially
        self.registry.cache.cache.clear()
        
        # 1st run: Cache miss
        is_cached, _ = self.registry.process_command(query)
        self.assertFalse(is_cached)
        
        # Wrap response (simulating AI response caching)
        self.registry.wrap_response(query, answer)
        
        # 2nd run: Cache hit (process_command returns cached string directly)
        is_cached, result = self.registry.process_command(query)
        self.assertTrue(is_cached)
        self.assertEqual(result, answer)

    def test_04_smart_file_finder(self):
        """Test SmartFileFinder inside ToolRegistry."""
        # Wait a moment for the background indexer to find the new test file
        import time
        time.sleep(1.0)
        # It should be able to find its own test file.
        results = self.registry.finder.find("test_makima_tools")
        self.assertTrue(any("test_makima_tools" in res.get('name', '') for res in results), f"SmartFileFinder failed to locate itself: {results}")

    def test_05_proactive_engine(self):
        """Test ProactiveEngine inside ToolRegistry."""
        # Update context should not crash
        self.registry.proactive.update_context(last_activity_time=1000)
        self.assertTrue(self.registry.proactive._running)

    def test_06_context_compressor(self):
        """Test ContextCompressor inside ToolRegistry."""
        # Should not crash during initialization and have a valid AI handler
        self.assertIsNotNone(self.registry.compressor.ai)

if __name__ == '__main__':
    unittest.main(verbosity=2)
