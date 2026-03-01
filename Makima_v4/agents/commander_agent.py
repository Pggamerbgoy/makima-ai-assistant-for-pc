"""
Commander Agent - Orchestrates the entire swarm
"""
from typing import Dict, Any, List
from Makima_v4.agents.base_agent import BaseAgent, AgentTask, AgentResult
import json
import time


class CommanderAgent(BaseAgent):
    """
    The commander analyzes requests and delegates to specialized agents
    """
    def __init__(self, ai_handler):
        super().__init__("Commander", ai_handler)
        self.capabilities = ['planning', 'delegation', 'synthesis']
        self.available_agents = {}
    
    def register_agent(self, agent_type: str, agent: BaseAgent):
        """
        Register a specialized agent
        """
        self.available_agents[agent_type] = agent
        self.log(f"Registered {agent_type} agent: {agent.name}")
    
    def can_handle(self, task: Dict[str, Any]) -> bool:
        """
        Commander can handle any task by delegating
        """
        return True
    
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution: Analyze → Plan → Delegate → Synthesize
        """
        start_time = time.time()
        
        try:
            self.log(f"Analyzing task: {task.get('description', 'Unknown')}")
            
            # Step 1: Create execution plan
            plan = self.create_plan(task)
            
            # Step 2: Execute plan
            results = self.execute_plan(plan)
            
            # Step 3: Synthesize results
            final_result = self.synthesize_results(results, task)
            
            self.track_performance(start_time, True)
            return AgentResult(success=True, data=final_result).to_dict()
            
        except Exception as e:
            self.log(f"Error in execution: {e}", "ERROR")
            self.track_performance(start_time, False)
            return AgentResult(success=False, error=str(e)).to_dict()
    
    def create_plan(self, task: Dict[str, Any]) -> List[AgentTask]:
        """
        Analyze task and create execution plan
        """
        # Let the LLM know exactly which agents are currently plugged in
        agent_descriptions = []
        for agent_key, agent_obj in self.available_agents.items():
            agent_descriptions.append(f"        - {agent_key}: {agent_obj.name}")
            
        agents_list_str = "\n".join(agent_descriptions)
        
        system_prompt = f"""
        You are the Commander Agent. Analyze the user's request and break it into subtasks.
        
        Available agents:
{agents_list_str}
        
        Return a JSON array of subtasks, where "agent" is one of the strictly available agents above:
        [
            {{
                "agent": "research",
                "description": "Specific subtask instructions",
                "priority": 1
            }}
        ]
        
        Return ONLY the JSON array, no explanation.
        """
        
        user_request = task.get('description', '')
        
        # Use AI to create plan
        response = self.ai_handler.generate_response(
            system_prompt=system_prompt,
            user_message=f"Break down this task: {user_request}",
            temperature=0.3
        )
        
        try:
            # Parse JSON response
            subtasks_data = json.loads(response)
            
            # Create AgentTask objects
            subtasks = []
            for i, subtask_data in enumerate(subtasks_data):
                subtask = AgentTask(
                    task_type=subtask_data.get('agent', 'executor'),
                    description=subtask_data.get('description', ''),
                    context=task.get('context', {}),
                    priority=subtask_data.get('priority', i + 1)
                )
                subtasks.append(subtask)
            
            self.log(f"Created plan with {len(subtasks)} subtasks")
            return subtasks
            
        except json.JSONDecodeError:
            # Fallback: single executor task
            self.log("Failed to parse plan, using fallback", "WARNING")
            return [AgentTask(
                task_type='executor',
                description=user_request,
                context=task.get('context', {})
            )]
    
    def execute_plan(self, plan: List[AgentTask]) -> List[Dict[str, Any]]:
        """
        Execute all subtasks (parallel when possible)
        """
        import threading
        
        results = []
        threads = []
        
        def execute_subtask(subtask: AgentTask):
            agent = self.available_agents.get(subtask.task_type)
            
            if agent and agent.can_handle(subtask.to_dict()):
                result = agent.execute(subtask.to_dict())
                results.append({
                    'task': subtask.to_dict(),
                    'result': result
                })
            else:
                self.log(f"No agent for task type: {subtask.task_type}", "WARNING")
                results.append({
                    'task': subtask.to_dict(),
                    'result': AgentResult(
                        success=False,
                        error=f"No agent available for {subtask.task_type}"
                    ).to_dict()
                })
        
        # Execute tasks in parallel
        for subtask in plan:
            thread = threading.Thread(target=execute_subtask, args=(subtask,))
            threads.append(thread)
            thread.start()
        
        # Wait for all
        for thread in threads:
            thread.join()
        
        return results
    
    def synthesize_results(self, results: List[Dict], original_task: Dict) -> str:
        """
        Combine all agent results into coherent response
        """
        system_prompt = """
        You are the Commander Agent. Synthesize the results from multiple specialized agents
        into a coherent, helpful response for the user.
        
        Be concise but complete. Focus on what the user asked for.
        """
        
        # Prepare context
        results_summary = []
        for item in results:
            task = item['task']
            result = item['result']
            
            if result['success']:
                results_summary.append(f"✅ {task['description']}: {result['data']}")
            else:
                results_summary.append(f"❌ {task['description']}: {result['error']}")
        
        synthesis_prompt = f"""
        Original Request: {original_task.get('description', '')}
        
        Agent Results:
        {chr(10).join(results_summary)}
        
        Synthesize these results into a helpful response.
        """
        
        final_response = self.ai_handler.generate_response(
            system_prompt=system_prompt,
            user_message=synthesis_prompt,
            temperature=0.5
        )
        
        return final_response
    
    def get_system_prompt(self) -> str:
        return """
        You are the Commander Agent, the orchestrator of a multi-agent AI system.
        Your role is to:
        1. Analyze complex user requests
        2. Break them into subtasks
        3. Delegate to specialized agents
        4. Synthesize results into coherent responses
        
        You have access to: Research, Code, Creative, Executor, Analyst, and Memory agents.
        """
