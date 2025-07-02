# apis/agentic/planner.py
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class TaskType(Enum):
    INFORMATION_GATHERING = "information_gathering"
    DATA_ANALYSIS = "data_analysis"
    FILE_PROCESSING = "file_processing"
    CALCULATION = "calculation"
    CODE_GENERATION = "code_generation"
    CREATIVE_WRITING = "creative_writing"
    PROBLEM_SOLVING = "problem_solving"
    RESEARCH = "research"

@dataclass
class TaskStep:
    step_number: int
    action: str
    tool: Optional[str]
    parameters: Dict[str, Any]
    expected_outcome: str
    dependencies: List[int] = None  # Steps that must complete first
    estimated_time: int = 60  # seconds
    priority: int = 1  # 1-5, higher is more important

class TaskPlanner:
    """Plans and organizes complex tasks"""
    
    def __init__(self):
        self.task_templates = self._load_task_templates()
    
    def analyze_task(self, user_input: str, context: Dict[str, Any] = None) -> TaskType:
        """Analyze user input to determine task type"""
        user_input_lower = user_input.lower()
        
        # Simple keyword-based classification
        if any(word in user_input_lower for word in ['search', 'find', 'lookup', 'what is', 'who is']):
            return TaskType.INFORMATION_GATHERING
        elif any(word in user_input_lower for word in ['analyze', 'compare', 'statistics', 'data']):
            return TaskType.DATA_ANALYSIS
        elif any(word in user_input_lower for word in ['file', 'document', 'upload', 'process']):
            return TaskType.FILE_PROCESSING
        elif any(word in user_input_lower for word in ['calculate', 'compute', 'math', 'equation']):
            return TaskType.CALCULATION
        elif any(word in user_input_lower for word in ['code', 'program', 'script', 'function']):
            return TaskType.CODE_GENERATION
        elif any(word in user_input_lower for word in ['write', 'create', 'story', 'article']):
            return TaskType.CREATIVE_WRITING
        elif any(word in user_input_lower for word in ['research', 'investigate', 'study']):
            return TaskType.RESEARCH
        else:
            return TaskType.PROBLEM_SOLVING
    
    def create_plan(self, user_input: str, task_type: TaskType, context: Dict[str, Any] = None) -> List[TaskStep]:
        """Create a plan for the given task"""
        template = self.task_templates.get(task_type, self.task_templates[TaskType.PROBLEM_SOLVING])
        
        # Customize template based on specific input
        plan = []
        for i, step_template in enumerate(template, 1):
            step = TaskStep(
                step_number=i,
                action=step_template["action"].format(user_input=user_input),
                tool=step_template.get("tool"),
                parameters=step_template.get("parameters", {}),
                expected_outcome=step_template["expected_outcome"],
                dependencies=step_template.get("dependencies", []),
                estimated_time=step_template.get("estimated_time", 60),
                priority=step_template.get("priority", 1)
            )
            plan.append(step)
        
        return plan
    
    def optimize_plan(self, plan: List[TaskStep]) -> List[TaskStep]:
        """Optimize plan execution order based on dependencies and priorities"""
        # Sort by dependencies first, then by priority
        optimized_plan = sorted(plan, key=lambda x: (len(x.dependencies or []), -x.priority))
        
        # Renumber steps
        for i, step in enumerate(optimized_plan, 1):
            step.step_number = i
        
        return optimized_plan
    
    def estimate_total_time(self, plan: List[TaskStep]) -> int:
        """Estimate total execution time for the plan"""
        return sum(step.estimated_time for step in plan)
    
    def get_next_executable_steps(self, plan: List[TaskStep], completed_steps: List[int]) -> List[TaskStep]:
        """Get steps that can be executed now based on completed dependencies"""
        executable_steps = []
        
        for step in plan:
            if step.step_number in completed_steps:
                continue
            
            # Check if all dependencies are completed
            dependencies = step.dependencies or []
            if all(dep in completed_steps for dep in dependencies):
                executable_steps.append(step)
        
        return executable_steps
    
    def _load_task_templates(self) -> Dict[TaskType, List[Dict[str, Any]]]:
        """Load predefined task templates"""
        return {
            TaskType.INFORMATION_GATHERING: [
                {
                    "action": "Search for information about: {user_input}",
                    "tool": "web_search",
                    "parameters": {"query": "{user_input}", "max_results": 5},
                    "expected_outcome": "Gather relevant information from web sources",
                    "estimated_time": 30,
                    "priority": 1
                },
                {
                    "action": "Analyze and synthesize the gathered information",
                    "tool": None,
                    "parameters": {},
                    "expected_outcome": "Provide comprehensive answer based on research",
                    "dependencies": [1],
                    "estimated_time": 60,
                    "priority": 2
                }
            ],
            
            TaskType.DATA_ANALYSIS: [
                {
                    "action": "Identify available data sources for: {user_input}",
                    "tool": "file_operations",
                    "parameters": {"operation": "list"},
                    "expected_outcome": "List of available data files",
                    "estimated_time": 15,
                    "priority": 1
                },
                {
                    "action": "Analyze the data for: {user_input}",
                    "tool": "file_operations",
                    "parameters": {"operation": "analyze"},
                    "expected_outcome": "Statistical analysis and insights",
                    "dependencies": [1],
                    "estimated_time": 120,
                    "priority": 2
                },
                {
                    "action": "Generate summary and recommendations",
                    "tool": None,
                    "parameters": {},
                    "expected_outcome": "Clear summary with actionable insights",
                    "dependencies": [2],
                    "estimated_time": 60,
                    "priority": 3
                }
            ],
            
            TaskType.FILE_PROCESSING: [
                {
                    "action": "List available files",
                    "tool": "file_operations",
                    "parameters": {"operation": "list"},
                    "expected_outcome": "Inventory of available files",
                    "estimated_time": 15,
                    "priority": 1
                },
                {
                    "action": "Process files for: {user_input}",
                    "tool": "file_operations",
                    "parameters": {"operation": "analyze"},
                    "expected_outcome": "Processed file contents and analysis",
                    "dependencies": [1],
                    "estimated_time": 90,
                    "priority": 2
                }
            ],
            
            TaskType.CALCULATION: [
                {
                    "action": "Perform calculation: {user_input}",
                    "tool": "calculator",
                    "parameters": {"expression": "{user_input}", "operation": "basic"},
                    "expected_outcome": "Mathematical result with explanation",
                    "estimated_time": 30,
                    "priority": 1
                }
            ],
            
            TaskType.CODE_GENERATION: [
                {
                    "action": "Design code solution for: {user_input}",
                    "tool": None,
                    "parameters": {},
                    "expected_outcome": "Code design and approach",
                    "estimated_time": 60,
                    "priority": 1
                },
                {
                    "action": "Implement and test the code",
                    "tool": "code_executor",
                    "parameters": {"language": "python"},
                    "expected_outcome": "Working code with test results",
                    "dependencies": [1],
                    "estimated_time": 120,
                    "priority": 2
                }
            ],
            
            TaskType.RESEARCH: [
                {
                    "action": "Conduct web research on: {user_input}",
                    "tool": "web_search",
                    "parameters": {"query": "{user_input}", "max_results": 10},
                    "expected_outcome": "Comprehensive research findings",
                    "estimated_time": 60,
                    "priority": 1
                },
                {
                    "action": "Check for additional data sources",
                    "tool": "database_query",
                    "parameters": {"query_type": "usage_stats"},
                    "expected_outcome": "Additional relevant data",
                    "dependencies": [1],
                    "estimated_time": 30,
                    "priority": 2
                },
                {
                    "action": "Synthesize research findings",
                    "tool": None,
                    "parameters": {},
                    "expected_outcome": "Comprehensive research report",
                    "dependencies": [1, 2],
                    "estimated_time": 90,
                    "priority": 3
                }
            ],
            
            TaskType.PROBLEM_SOLVING: [
                {
                    "action": "Analyze the problem: {user_input}",
                    "tool": None,
                    "parameters": {},
                    "expected_outcome": "Clear problem understanding",
                    "estimated_time": 45,
                    "priority": 1
                },
                {
                    "action": "Gather relevant information",
                    "tool": "web_search",
                    "parameters": {"query": "{user_input}"},
                    "expected_outcome": "Supporting information and context",
                    "dependencies": [1],
                    "estimated_time": 60,
                    "priority": 2
                },
                {
                    "action": "Develop solution approach",
                    "tool": None,
                    "parameters": {},
                    "expected_outcome": "Step-by-step solution",
                    "dependencies": [1, 2],
                    "estimated_time": 90,
                    "priority": 3
                }
            ],
            
            TaskType.CREATIVE_WRITING: [
                {
                    "action": "Plan creative content for: {user_input}",
                    "tool": None,
                    "parameters": {},
                    "expected_outcome": "Content outline and structure",
                    "estimated_time": 45,
                    "priority": 1
                },
                {
                    "action": "Write the creative content",
                    "tool": None,
                    "parameters": {},
                    "expected_outcome": "Complete creative work",
                    "dependencies": [1],
                    "estimated_time": 120,
                    "priority": 2
                },
                {
                    "action": "Review and refine the content",
                    "tool": None,
                    "parameters": {},
                    "expected_outcome": "Polished final version",
                    "dependencies": [2],
                    "estimated_time": 60,
                    "priority": 3
                }
            ]
        }
