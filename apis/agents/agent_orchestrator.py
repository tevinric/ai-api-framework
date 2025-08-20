"""
Agent Orchestrator for Custom Agents and Chaining
Manages custom agent creation and multi-agent workflows
"""

from typing import Dict, List, Optional, Any, Tuple
import json
import uuid
import logging
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from apis.agents.agent_manager import AgentManager
from apis.agents.tool_registry import tool_registry
from apis.utils.databaseService import DatabaseService

logger = logging.getLogger(__name__)

class AgentRole(Enum):
    """Predefined agent roles for business users"""
    ANALYST = "analyst"
    RESEARCHER = "researcher"
    WRITER = "writer"
    CODER = "coder"
    DESIGNER = "designer"
    PROJECT_MANAGER = "project_manager"
    SALES_ASSISTANT = "sales_assistant"
    CUSTOMER_SERVICE = "customer_service"
    DATA_SCIENTIST = "data_scientist"
    FINANCIAL_ADVISOR = "financial_advisor"
    HR_ASSISTANT = "hr_assistant"
    MARKETING_SPECIALIST = "marketing_specialist"
    LEGAL_ADVISOR = "legal_advisor"
    EDUCATOR = "educator"
    TRANSLATOR = "translator"

@dataclass
class AgentTemplate:
    """Template for creating specialized agents"""
    name: str
    role: AgentRole
    description: str
    instructions: str
    default_tools: List[str]
    model: str = "gpt-4o"
    temperature: float = 0.7
    
class AgentOrchestrator:
    """Orchestrates custom agents and multi-agent workflows"""
    
    def __init__(self):
        self.agent_manager = AgentManager()
        self.templates = self._load_agent_templates()
        
    def _load_agent_templates(self) -> Dict[str, AgentTemplate]:
        """Load predefined agent templates"""
        templates = {}
        
        # Business Analyst Agent
        templates["business_analyst"] = AgentTemplate(
            name="Business Analyst",
            role=AgentRole.ANALYST,
            description="Analyzes business data and provides insights",
            instructions="""You are a professional business analyst. Your role is to:
            - Analyze business data and metrics
            - Identify trends and patterns
            - Provide actionable insights and recommendations
            - Create reports and visualizations
            - Help with strategic decision-making
            Always be data-driven, objective, and focus on business value.""",
            default_tools=["data_analysis", "calculator", "document_generator", "web_search"],
            temperature=0.5
        )
        
        # Research Assistant Agent
        templates["research_assistant"] = AgentTemplate(
            name="Research Assistant",
            role=AgentRole.RESEARCHER,
            description="Conducts thorough research on any topic",
            instructions="""You are an expert research assistant. Your role is to:
            - Conduct comprehensive research on given topics
            - Gather information from multiple sources
            - Verify facts and cite sources
            - Synthesize findings into clear summaries
            - Identify knowledge gaps and suggest further research
            Always provide accurate, well-sourced information.""",
            default_tools=["web_search", "document_generator", "data_analysis"],
            temperature=0.6
        )
        
        # Content Writer Agent
        templates["content_writer"] = AgentTemplate(
            name="Content Writer",
            role=AgentRole.WRITER,
            description="Creates professional written content",
            instructions="""You are a professional content writer. Your role is to:
            - Create engaging and well-structured content
            - Adapt writing style to target audience
            - Ensure clarity and readability
            - Optimize content for SEO when needed
            - Proofread and edit for grammar and style
            Always produce high-quality, original content.""",
            default_tools=["document_generator", "web_search"],
            temperature=0.8
        )
        
        # Project Manager Agent
        templates["project_manager"] = AgentTemplate(
            name="Project Manager",
            role=AgentRole.PROJECT_MANAGER,
            description="Manages projects and coordinates tasks",
            instructions="""You are an experienced project manager. Your role is to:
            - Plan and organize project tasks
            - Create timelines and milestones
            - Track progress and identify risks
            - Coordinate team activities
            - Ensure project delivery on time and budget
            Always focus on efficiency and clear communication.""",
            default_tools=["task_manager", "calendar_manager", "document_generator", "send_email"],
            temperature=0.5
        )
        
        # Sales Assistant Agent
        templates["sales_assistant"] = AgentTemplate(
            name="Sales Assistant",
            role=AgentRole.SALES_ASSISTANT,
            description="Assists with sales activities and customer engagement",
            instructions="""You are a professional sales assistant. Your role is to:
            - Qualify leads and opportunities
            - Prepare sales proposals and presentations
            - Track customer interactions
            - Provide product recommendations
            - Follow up with prospects
            Always be helpful, persuasive, and customer-focused.""",
            default_tools=["send_email", "document_generator", "calendar_manager", "database_query"],
            temperature=0.7
        )
        
        # Customer Service Agent
        templates["customer_service"] = AgentTemplate(
            name="Customer Service Representative",
            role=AgentRole.CUSTOMER_SERVICE,
            description="Handles customer inquiries and support",
            instructions="""You are a friendly customer service representative. Your role is to:
            - Respond to customer inquiries promptly
            - Resolve issues and complaints
            - Provide product/service information
            - Escalate complex issues when needed
            - Ensure customer satisfaction
            Always be empathetic, patient, and solution-oriented.""",
            default_tools=["database_query", "send_email", "task_manager"],
            temperature=0.6
        )
        
        # Data Scientist Agent
        templates["data_scientist"] = AgentTemplate(
            name="Data Scientist",
            role=AgentRole.DATA_SCIENTIST,
            description="Performs advanced data analysis and modeling",
            instructions="""You are an expert data scientist. Your role is to:
            - Analyze complex datasets
            - Build predictive models
            - Identify patterns and correlations
            - Create data visualizations
            - Provide statistical insights
            Always use rigorous methodology and validate findings.""",
            default_tools=["data_analysis", "calculator", "document_generator"],
            model="gpt-4o",
            temperature=0.4
        )
        
        # Financial Advisor Agent
        templates["financial_advisor"] = AgentTemplate(
            name="Financial Advisor",
            role=AgentRole.FINANCIAL_ADVISOR,
            description="Provides financial analysis and advice",
            instructions="""You are a professional financial advisor. Your role is to:
            - Analyze financial statements and metrics
            - Provide investment recommendations
            - Assess financial risks
            - Create financial reports
            - Help with budgeting and planning
            Always provide accurate, compliant advice. Note: This is for informational purposes only.""",
            default_tools=["calculator", "data_analysis", "document_generator", "web_search"],
            temperature=0.4
        )
        
        # HR Assistant Agent
        templates["hr_assistant"] = AgentTemplate(
            name="HR Assistant",
            role=AgentRole.HR_ASSISTANT,
            description="Assists with HR tasks and employee management",
            instructions="""You are a professional HR assistant. Your role is to:
            - Help with recruitment and onboarding
            - Manage employee information
            - Assist with policy questions
            - Schedule interviews and meetings
            - Support performance management
            Always maintain confidentiality and follow HR best practices.""",
            default_tools=["calendar_manager", "send_email", "document_generator", "task_manager"],
            temperature=0.5
        )
        
        # Marketing Specialist Agent
        templates["marketing_specialist"] = AgentTemplate(
            name="Marketing Specialist",
            role=AgentRole.MARKETING_SPECIALIST,
            description="Develops marketing strategies and content",
            instructions="""You are a creative marketing specialist. Your role is to:
            - Develop marketing strategies
            - Create compelling marketing content
            - Analyze market trends
            - Plan campaigns and promotions
            - Track marketing metrics
            Always be creative, data-driven, and customer-centric.""",
            default_tools=["web_search", "document_generator", "data_analysis", "send_email"],
            temperature=0.8
        )
        
        return templates
    
    async def create_custom_agent(
        self,
        user_id: str,
        name: str,
        description: str,
        instructions: str,
        tools: List[str],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        base_template: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a custom agent for a user
        
        Returns:
            Tuple of (agent_id, error_message)
        """
        try:
            # If using a template, merge configurations
            if base_template and base_template in self.templates:
                template = self.templates[base_template]
                
                # Merge instructions
                full_instructions = f"{template.instructions}\n\nAdditional Instructions:\n{instructions}"
                
                # Merge tools
                all_tools = list(set(template.default_tools + tools))
                
                # Use template defaults if not specified
                if not model:
                    model = template.model
                if temperature == 0.7:  # Default value
                    temperature = template.temperature
            else:
                full_instructions = instructions
                all_tools = tools
            
            # Validate tools exist
            available_tools = tool_registry.get_tools_for_user(user_id)
            available_tool_names = {tool.name for tool in available_tools}
            
            valid_tools = [t for t in all_tools if t in available_tool_names]
            if len(valid_tools) < len(all_tools):
                invalid_tools = set(all_tools) - set(valid_tools)
                logger.warning(f"Skipping invalid tools: {invalid_tools}")
            
            # Convert tools to OpenAI format
            tools_config = [
                tool.to_openai_function()
                for tool in available_tools
                if tool.name in valid_tools
            ]
            
            # Create agent using agent manager
            agent_id, error = await self.agent_manager.create_agent(
                user_id=user_id,
                name=name,
                instructions=full_instructions,
                tools=tools_config,
                model=model,
                metadata={
                    "description": description,
                    "custom": True,
                    "base_template": base_template,
                    "created_at": datetime.utcnow().isoformat()
                },
                temperature=temperature
            )
            
            if error:
                return None, error
            
            # Store custom agent configuration
            await self._store_custom_agent(
                user_id=user_id,
                agent_id=agent_id,
                name=name,
                description=description,
                instructions=instructions,
                tools=valid_tools,
                model=model,
                temperature=temperature,
                base_template=base_template
            )
            
            logger.info(f"Created custom agent {agent_id} for user {user_id}")
            return agent_id, None
            
        except Exception as e:
            error_msg = f"Failed to create custom agent: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    async def create_agent_workflow(
        self,
        user_id: str,
        name: str,
        description: str,
        agents: List[Dict[str, Any]],
        flow_type: str = "sequential"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a multi-agent workflow
        
        Args:
            agents: List of agent configurations with roles and connections
            flow_type: "sequential", "parallel", or "conditional"
        
        Returns:
            Tuple of (workflow_id, error_message)
        """
        try:
            workflow_id = str(uuid.uuid4())
            
            # Validate agents exist
            for agent_config in agents:
                agent_id = agent_config.get("agent_id")
                if not await self.agent_manager._verify_agent_ownership(user_id, agent_id):
                    return None, f"Agent {agent_id} not found or unauthorized"
            
            # Store workflow configuration
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO agent_workflows (
                    id, user_id, name, description, 
                    flow_type, agents_config, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, GETUTCDATE()
                )
                """,
                [
                    workflow_id,
                    user_id,
                    name,
                    description,
                    flow_type,
                    json.dumps(agents)
                ]
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Created workflow {workflow_id} with {len(agents)} agents")
            return workflow_id, None
            
        except Exception as e:
            error_msg = f"Failed to create workflow: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    async def execute_workflow(
        self,
        user_id: str,
        workflow_id: str,
        initial_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Execute a multi-agent workflow
        
        Returns:
            Tuple of (job_id, error_message)
        """
        try:
            # Get workflow configuration
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT flow_type, agents_config 
                FROM agent_workflows 
                WHERE id = ? AND user_id = ?
                """,
                [workflow_id, user_id]
            )
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not result:
                return None, "Workflow not found or unauthorized"
            
            flow_type = result[0]
            agents_config = json.loads(result[1])
            
            # Create workflow execution job
            from apis.jobs.job_service import JobService
            job_service = JobService()
            
            job_id, error = job_service.create_job(
                user_id=user_id,
                job_type="workflow_execution",
                parameters={
                    "workflow_id": workflow_id,
                    "flow_type": flow_type,
                    "agents": agents_config,
                    "initial_input": initial_input,
                    "context": context
                }
            )
            
            if error:
                return None, error
            
            # Execute workflow based on type
            if flow_type == "sequential":
                await self._execute_sequential_workflow(
                    job_id, user_id, agents_config, initial_input, context
                )
            elif flow_type == "parallel":
                await self._execute_parallel_workflow(
                    job_id, user_id, agents_config, initial_input, context
                )
            elif flow_type == "conditional":
                await self._execute_conditional_workflow(
                    job_id, user_id, agents_config, initial_input, context
                )
            else:
                return None, f"Unknown flow type: {flow_type}"
            
            return job_id, None
            
        except Exception as e:
            error_msg = f"Failed to execute workflow: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    async def _execute_sequential_workflow(
        self,
        job_id: str,
        user_id: str,
        agents: List[Dict[str, Any]],
        initial_input: str,
        context: Optional[Dict[str, Any]]
    ):
        """Execute agents sequentially, passing output to next agent"""
        try:
            current_input = initial_input
            workflow_results = []
            
            for i, agent_config in enumerate(agents):
                agent_id = agent_config["agent_id"]
                role = agent_config.get("role", f"Agent {i+1}")
                
                # Create thread for this agent
                thread_id, error = await self.agent_manager.create_thread(
                    user_id=user_id,
                    agent_id=agent_id,
                    initial_message=current_input
                )
                
                if error:
                    raise Exception(f"Failed to create thread for {role}: {error}")
                
                # Run agent
                run_id, _, error = await self.agent_manager.run_agent(
                    user_id=user_id,
                    agent_id=agent_id,
                    thread_id=thread_id,
                    message=current_input,
                    metadata={"workflow_job_id": job_id, "step": i+1}
                )
                
                if error:
                    raise Exception(f"Failed to run {role}: {error}")
                
                # Wait for completion and get result
                # (In production, this would be async with proper polling)
                import asyncio
                await asyncio.sleep(5)  # Simplified wait
                
                status_info, error = await self.agent_manager.get_run_status(
                    user_id=user_id,
                    thread_id=thread_id,
                    run_id=run_id
                )
                
                if error:
                    raise Exception(f"Failed to get status for {role}: {error}")
                
                # Store result and use as input for next agent
                result = status_info.get("response", "")
                workflow_results.append({
                    "step": i+1,
                    "agent_id": agent_id,
                    "role": role,
                    "output": result
                })
                
                current_input = result
            
            # Update job with final results
            from apis.jobs.job_service import JobService
            job_service = JobService()
            job_service.update_job_status(
                job_id=job_id,
                status="completed",
                result_data={"workflow_results": workflow_results}
            )
            
        except Exception as e:
            logger.error(f"Sequential workflow failed: {str(e)}")
            from apis.jobs.job_service import JobService
            job_service = JobService()
            job_service.update_job_status(
                job_id=job_id,
                status="failed",
                error_message=str(e)
            )
    
    async def _execute_parallel_workflow(
        self,
        job_id: str,
        user_id: str,
        agents: List[Dict[str, Any]],
        initial_input: str,
        context: Optional[Dict[str, Any]]
    ):
        """Execute agents in parallel and combine results"""
        # TODO: Implement parallel execution
        pass
    
    async def _execute_conditional_workflow(
        self,
        job_id: str,
        user_id: str,
        agents: List[Dict[str, Any]],
        initial_input: str,
        context: Optional[Dict[str, Any]]
    ):
        """Execute agents based on conditions"""
        # TODO: Implement conditional execution
        pass
    
    async def _store_custom_agent(self, **kwargs):
        """Store custom agent configuration"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO custom_agents (
                    id, user_id, agent_id, name, description,
                    instructions, tools, model, temperature,
                    base_template, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETUTCDATE()
                )
                """,
                [
                    str(uuid.uuid4()),
                    kwargs['user_id'],
                    kwargs['agent_id'],
                    kwargs['name'],
                    kwargs['description'],
                    kwargs['instructions'],
                    json.dumps(kwargs['tools']),
                    kwargs['model'],
                    kwargs['temperature'],
                    kwargs.get('base_template')
                ]
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing custom agent: {str(e)}")
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """Get list of available agent templates"""
        templates_list = []
        
        for key, template in self.templates.items():
            templates_list.append({
                "id": key,
                "name": template.name,
                "role": template.role.value,
                "description": template.description,
                "default_tools": template.default_tools,
                "model": template.model,
                "temperature": template.temperature
            })
        
        return templates_list

# Global orchestrator instance
agent_orchestrator = AgentOrchestrator()