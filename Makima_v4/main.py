import sys
import os

# Point to your existing project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import YOUR existing systems
from core.ai_handler import AIHandler
from agents.web_agent import WebAgent
from core.preferences_manager import PreferencesManager
try:
    from systems.file_manager import FileManager
except ImportError:
    FileManager = None

# Import v4 systems
from Makima_v4.agents.agent_swarm import AgentSwarm
from Makima_v4.learning.continuous_learner import ContinuousLearner
from Makima_v4.memory.knowledge_graph import KnowledgeGraph

class WebSearchAdapter:
    def __init__(self, web_agent):
        self.agent = web_agent
    
    def search(self, query: str) -> list:
        results = self.agent.search(query)
        # Ensure we return a list for v4 expectations
        if isinstance(results, str):
            return [{"title": "Search Result", "snippet": results}]
        return results

class AIHandlerAdapter:
    def __init__(self, ai_handler):
        self.ai = ai_handler
    
    def generate_response(self, system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
        prompt = f"{system_prompt}\nUser Request: {user_message}"
        raw = None
        if self.ai._is_gemini_available():
            raw = self.ai._call_gemini(prompt)
        if not raw:
            raw = self.ai._call_ollama(user_message, system_prompt)
        
        # Clean it
        if raw is None:
            return "[]"
            
        try:
            import json
            data = json.loads(raw)
            if "reply" in data:
                return data["reply"]
        except Exception:
            pass
        return raw

class PreferencesAdapter:
    def __init__(self, prefs):
        self.prefs = prefs
        
    def set_preference(self, key, value):
        self.prefs.set_explicit_preference(str(key), str(value))
        
    def get_preference(self, key):
        return self.prefs.get_preference(str(key))

class MakimaV4:
    def __init__(self, ai_handler=None):
        print("🚀 Initializing Makima v4 Enhanced Engine...")
        
        # Your existing systems
        self.ai = ai_handler if ai_handler else AIHandler()
        self.file_manager = FileManager(self.ai) if FileManager else None
        self.web_agent = WebAgent(self.ai)
        self.preferences = PreferencesManager()

        # v4 systems using your existing tools with adapters
        self.swarm = AgentSwarm(
            ai_handler=AIHandlerAdapter(self.ai),
            integrations={
                'web_search': WebSearchAdapter(self.web_agent),
                'file_manager': self.file_manager,
                'preferences_manager': PreferencesAdapter(self.preferences),
            }
        )

        self.memory = KnowledgeGraph()
        
        self.learner = ContinuousLearner(
            preferences_manager=PreferencesAdapter(self.preferences),
            knowledge_graph=self.memory,
            ai_handler=AIHandlerAdapter(self.ai)
        )
        print("✅ Makima v4 fully initialized!")

    def process(self, user_input: str, context: dict = None) -> str:
        import time
        start = time.time()

        response = self.swarm.process(user_input, context or {})

        self.learner.record_interaction(
            user_input=user_input,
            ai_response=response,
            response_time=time.time() - start
        )

        return response
