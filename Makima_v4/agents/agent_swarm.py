"""
Agent Swarm - Main controller for multi-agent system
"""
from Makima_v4.agents.commander_agent import CommanderAgent
from Makima_v4.agents.research_agent import ResearchAgent
from Makima_v4.agents.code_agent import CodeAgent
from Makima_v4.agents.creative_agent import CreativeAgent
from Makima_v4.agents.executor_agent import ExecutorAgent
from typing import Dict, Any
import time


class AgentSwarm:
    """
    Orchestrates multiple specialized agents working together
    """
    def __init__(self, ai_handler, integrations=None):
        """
        Initialize the swarm with all agents
        
        Args:
            ai_handler: Your existing AI handler
            integrations: Dict of existing integrations (web_search, file_manager, etc.)
        """
        self.ai_handler = ai_handler
        self.integrations = integrations or {}
        
        # Initialize commander
        self.commander = CommanderAgent(ai_handler)
        
        # Initialize specialized agents
        self.research_agent = ResearchAgent(
            ai_handler,
            web_search_tool=self.integrations.get('web_search')
        )
        
        self.code_agent = CodeAgent(
            ai_handler,
            code_analyzer=self.integrations.get('code_analyzer')
        )
        
        self.creative_agent = CreativeAgent(ai_handler)
        
        self.executor_agent = ExecutorAgent(
            ai_handler,
            file_manager=self.integrations.get('file_manager')
        )
        
        # Register all agents with commander
        self.commander.register_agent('research', self.research_agent)
        self.commander.register_agent('code', self.code_agent)
        self.commander.register_agent('creative', self.creative_agent)
        self.commander.register_agent('executor', self.executor_agent)
        
        print("🤖 Agent Swarm initialized with 5 agents")
        
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            
            from Makima_v4.agents.base_agent import BaseAgent, AgentResult

            class V3WebAgentAdapter(BaseAgent):
                def __init__(self, ai_handler):
                    super().__init__("V3 Web Agent", ai_handler)
                    from agents.web_agent import WebAgent
                    self.v3_agent = WebAgent(ai_handler)
                
                def can_handle(self, task: Dict[str, Any]) -> bool:
                    return "search" in task.get("description", "").lower() or "web" in task.get("description", "").lower()
                
                def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
                    try:
                        result = self.v3_agent.search(task.get("description", ""))
                        return AgentResult(success=True, data=result).to_dict()
                    except Exception as e:
                        return AgentResult(success=False, error=str(e)).to_dict()

            class V3AutoCoderAdapter(BaseAgent):
                def __init__(self, ai_handler):
                    super().__init__("V3 Auto Coder", ai_handler)
                    from agents.auto_coder import AutoCoder
                    self.v3_agent = AutoCoder(ai_handler)
                
                def can_handle(self, task: Dict[str, Any]) -> bool:
                    desc = task.get("description", "").lower()
                    return "code" in desc or "script" in desc or "program" in desc
                
                def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
                    """
                    Delegate code-generation tasks to the legacy AutoCoder.
                    """
                    description = task.get("description", "") or ""
                    try:
                        result_msg = self.v3_agent.write(description)
                        return AgentResult(
                            success=True,
                            data=result_msg,
                        ).to_dict()
                    except Exception as e:
                        return AgentResult(success=False, error=str(e)).to_dict()

            try:
                self.commander.register_agent('web_v3', V3WebAgentAdapter(self.ai_handler))
                print("🔗 Linked V3 Custom Agent: WebAgent")
            except Exception as e:
                print(f"⚠️ Couldn't load WebAgent: {e}")
                
            try:
                self.commander.register_agent('coder_v3', V3AutoCoderAdapter(self.ai_handler))
                print("🔗 Linked V3 Custom Agent: AutoCoder")
            except Exception as e:
                print(f"⚠️ Couldn't load AutoCoder: {e}")
                
        except Exception as e:
            print(f"⚠️ Error setting up V3 custom agents: {e}")
    
    def process(self, user_request: str, context: Dict = None) -> str:
        """
        Main entry point - process any user request
        
        Args:
            user_request: User's command/question
            context: Additional context (files, screen content, etc.)
        
        Returns:
            Final response from the swarm
        """
        start_time = time.time()
        
        # Create task
        task = {
            'description': user_request,
            'context': context or {},
            'timestamp': time.time()
        }
        
        # Commander orchestrates everything
        result = self.commander.execute(task)
        
        execution_time = time.time() - start_time
        
        if result['success']:
            print(f"✅ Swarm completed in {execution_time:.2f}s")
            return result['data']
        else:
            print(f"❌ Swarm failed: {result['error']}")
            return f"Sorry, I encountered an error: {result['error']}"
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for all agents
        """
        stats = {
            'commander': self.commander.performance_stats,
            'research': self.research_agent.performance_stats,
            'code': self.code_agent.performance_stats,
            'creative': self.creative_agent.performance_stats,
            'executor': self.executor_agent.performance_stats
        }
        
        return stats
    
    def reset_stats(self):
        """
        Reset all performance statistics
        """
        for agent in [self.commander, self.research_agent, self.code_agent, 
                      self.creative_agent, self.executor_agent]:
            agent.performance_stats = {
                'tasks_completed': 0,
                'success_rate': 0.0,
                'avg_response_time': 0.0
            }
