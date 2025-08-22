import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import re
from enum import Enum

# Azure OpenAI imports
from openai import AzureOpenAI

# Free search library (no API key required)
from duckduckgo_search import DDGS

class QueryType(Enum):
    """Types of queries the agent can recognize"""
    COMPETITOR_ANALYSIS = "competitor_analysis"
    MARKET_RESEARCH = "market_research"
    TECHNICAL_RESEARCH = "technical_research"
    PRODUCT_COMPARISON = "product_comparison"
    INDUSTRY_TRENDS = "industry_trends"
    COMPANY_RESEARCH = "company_research"
    GENERAL_RESEARCH = "general_research"
    NEWS_ANALYSIS = "news_analysis"
    ACADEMIC_RESEARCH = "academic_research"
    PRICING_RESEARCH = "pricing_research"

class DeepResearchAgent:
    """
    A deep research agent that performs intelligent web searches and analysis
    based on user queries, with specialized capabilities for different types of research.
    """
    
    def __init__(self, 
                 azure_endpoint: str,
                 api_key: str,
                 api_version: str = "2024-02-15-preview",
                 deployment_name: str = "gpt-4",
                 max_search_results: int = 15,
                 max_search_depth: int = 5):
        """
        Initialize the deep research agent.
        """
        self.client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version
        )
        self.deployment_name = deployment_name
        self.max_search_results = max_search_results
        self.max_search_depth = max_search_depth
        self.ddgs = DDGS()
        
    def analyze_query(self, user_query: str) -> Dict:
        """
        Analyze the user's query to determine intent and extract key information.
        """
        analysis_prompt = f"""Analyze this user query and extract key information:

Query: "{user_query}"

Provide a JSON response with:
1. "query_type": One of [competitor_analysis, market_research, technical_research, product_comparison, 
   industry_trends, company_research, general_research, news_analysis, academic_research, pricing_research]
2. "entities": List of companies, products, or topics mentioned
3. "intent": What the user wants to know (be specific)
4. "search_focus": Key aspects to focus on
5. "time_relevance": Whether recent information is critical (yes/no)
6. "comparison_needed": Whether comparing multiple entities (yes/no)
7. "depth_required": How deep the analysis should be (shallow/medium/deep)

Examples:
- "What are Stripe's main competitors?" → competitor_analysis
- "How does React compare to Vue?" → product_comparison
- "Latest AI trends in healthcare" → industry_trends
- "Tesla's revenue last quarter" → company_research
"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are a query analysis expert. Always respond with valid JSON."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            # Parse the JSON response
            analysis_text = response.choices[0].message.content
            # Extract JSON from the response
            json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback if JSON parsing fails
                return {
                    "query_type": "general_research",
                    "entities": [],
                    "intent": user_query,
                    "search_focus": ["general information"],
                    "time_relevance": "no",
                    "comparison_needed": "no",
                    "depth_required": "medium"
                }
                
        except Exception as e:
            print(f"Error analyzing query: {e}")
            return {
                "query_type": "general_research",
                "entities": [],
                "intent": user_query,
                "search_focus": ["general information"],
                "time_relevance": "no",
                "comparison_needed": "no",
                "depth_required": "medium"
            }
    
    def generate_search_queries(self, 
                              user_query: str, 
                              query_analysis: Dict,
                              iteration: int = 1) -> List[str]:
        """
        Generate intelligent search queries based on user intent and query analysis.
        """
        query_type = query_analysis.get("query_type", "general_research")
        entities = query_analysis.get("entities", [])
        intent = query_analysis.get("intent", user_query)
        search_focus = query_analysis.get("search_focus", [])
        
        # Generate base queries
        queries = [user_query]  # Always include the original query
        
        # Add specialized queries based on query type
        if query_type == "competitor_analysis":
            if entities:
                company = entities[0]
                queries.extend([
                    f"{company} competitors",
                    f"{company} vs",
                    f"alternatives to {company}",
                    f"{company} market share",
                    f"{company} competitive advantage"
                ])
        
        elif query_type == "product_comparison":
            if len(entities) >= 2:
                queries.extend([
                    f"{entities[0]} vs {entities[1]}",
                    f"{entities[0]} compared to {entities[1]}",
                    f"difference between {entities[0]} and {entities[1]}",
                    f"{entities[0]} {entities[1]} comparison"
                ])
        
        elif query_type == "market_research":
            for focus in search_focus:
                queries.append(f"{intent} {focus}")
            queries.extend([
                f"{intent} market analysis",
                f"{intent} industry report",
                f"{intent} market trends 2024"
            ])
        
        elif query_type == "company_research":
            if entities:
                company = entities[0]
                for focus in search_focus:
                    queries.append(f"{company} {focus}")
        
        elif query_type == "industry_trends":
            queries.extend([
                f"{intent} latest trends",
                f"{intent} 2024 trends",
                f"{intent} future outlook",
                f"{intent} industry analysis"
            ])
        
        elif query_type == "pricing_research":
            for entity in entities:
                queries.extend([
                    f"{entity} pricing",
                    f"{entity} cost",
                    f"{entity} plans",
                    f"{entity} pricing calculator"
                ])
        
        # Add iteration-specific queries for deeper research
        if iteration > 1:
            queries = self.generate_followup_queries(user_query, queries, query_analysis)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)
        
        return unique_queries[:10]  # Limit to 10 queries
    
    def generate_followup_queries(self, 
                                original_query: str,
                                previous_queries: List[str],
                                query_analysis: Dict) -> List[str]:
        """
        Generate follow-up queries for deeper research.
        """
        prompt = f"""Based on the original research query and previous searches, generate 5 follow-up queries for deeper research.

Original query: {original_query}
Query type: {query_analysis.get('query_type')}
Previous searches: {', '.join(previous_queries[:5])}

Generate queries that:
1. Dig deeper into specific aspects
2. Look for recent updates or changes
3. Find expert opinions or detailed analysis
4. Explore related topics not yet covered

Return only the queries, one per line:"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "Generate focused follow-up search queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            queries = response.choices[0].message.content.strip().split('\n')
            return [q.strip() for q in queries if q.strip()][:5]
            
        except Exception as e:
            print(f"Error generating follow-up queries: {e}")
            return []
    
    def search_web(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """
        Search the web using DuckDuckGo (no API key required).
        """
        max_results = max_results or self.max_search_results
        
        try:
            results = []
            search_results = self.ddgs.text(
                keywords=query,
                max_results=max_results,
                safesearch='moderate'
            )
            
            for result in search_results:
                results.append({
                    'title': result.get('title', ''),
                    'body': result.get('body', ''),
                    'href': result.get('href', ''),
                    'source': 'DuckDuckGo'
                })
                
            return results
            
        except Exception as e:
            print(f"Search error for '{query}': {e}")
            return []
    
    def extract_insights(self, 
                        search_results: List[Dict], 
                        user_query: str,
                        query_analysis: Dict) -> str:
        """
        Extract key insights from search results based on user intent.
        """
        # Combine search results
        combined_text = ""
        for i, result in enumerate(search_results[:10]):  # Limit to top 10 results
            combined_text += f"\n\nSource {i+1}: {result['title']}\n{result['body']}\n"
        
        # Create extraction prompt based on query type
        query_type = query_analysis.get("query_type", "general_research")
        intent = query_analysis.get("intent", user_query)
        
        extraction_prompts = {
            "competitor_analysis": f"""Extract competitive intelligence from these search results for the query: "{user_query}"
            
Focus on:
1. Main competitors mentioned
2. Competitive advantages and disadvantages
3. Market positioning
4. Key differentiators
5. Pricing comparisons if available

Search results:
{combined_text}""",

            "product_comparison": f"""Create a comparison based on these search results for: "{user_query}"

Focus on:
1. Key differences between products/services
2. Pros and cons of each
3. Use cases and target audiences
4. Pricing differences
5. User preferences and recommendations

Search results:
{combined_text}""",

            "market_research": f"""Extract market insights from these search results for: "{user_query}"

Focus on:
1. Market size and growth
2. Key trends and drivers
3. Major players
4. Challenges and opportunities
5. Future outlook

Search results:
{combined_text}""",

            "general_research": f"""Extract key information from these search results for: "{user_query}"

Provide:
1. Direct answer to the query
2. Important facts and details
3. Different perspectives if any
4. Supporting evidence
5. Additional context

Search results:
{combined_text}"""
        }
        
        prompt = extraction_prompts.get(query_type, extraction_prompts["general_research"])
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are an expert at extracting and synthesizing information from search results."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error extracting insights: {e}")
            return "Error processing search results"
    
    def synthesize_research(self, 
                          user_query: str,
                          query_analysis: Dict,
                          all_insights: List[Dict],
                          search_history: List[str]) -> Dict:
        """
        Synthesize all research findings into a comprehensive response.
        """
        # Combine all insights
        combined_insights = "\n\n---\n\n".join([
            f"Search: {insight['query']}\nFindings: {insight['insights']}"
            for insight in all_insights
        ])
        
        # Create synthesis prompt
        synthesis_prompt = f"""Create a comprehensive response to this user query: "{user_query}"

Query Analysis:
- Type: {query_analysis.get('query_type')}
- Intent: {query_analysis.get('intent')}
- Entities: {', '.join(query_analysis.get('entities', []))}

Research Findings:
{combined_insights}

Provide:
1. A direct, concise answer (2-3 sentences)
2. Detailed findings organized by relevance
3. Key takeaways
4. Any limitations or gaps in the research
5. Suggestions for further research if applicable

Make the response clear, well-structured, and directly addressing the user's question."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are an expert research analyst providing comprehensive, actionable insights."},
                    {"role": "user", "content": synthesis_prompt}
                ],
                temperature=0.5,
                max_tokens=2500
            )
            
            return {
                'user_query': user_query,
                'query_analysis': query_analysis,
                'response': response.choices[0].message.content,
                'search_queries': search_history,
                'sources_count': sum(len(i.get('sources', [])) for i in all_insights),
                'research_depth': len(all_insights),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error synthesizing research: {e}")
            return {
                'user_query': user_query,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def research(self, user_query: str, max_depth: Optional[int] = None) -> Dict:
        """
        Main method to perform deep research based on user query.
        """
        print(f"\n🔍 Starting deep research for: '{user_query}'")
        
        # Analyze the query
        print("📊 Analyzing query intent...")
        query_analysis = self.analyze_query(user_query)
        print(f"Query type: {query_analysis.get('query_type')}")
        print(f"Entities found: {', '.join(query_analysis.get('entities', []))}")
        
        # Determine research depth
        depth_map = {
            "shallow": 1,
            "medium": 3,
            "deep": 5
        }
        research_depth = max_depth or depth_map.get(
            query_analysis.get("depth_required", "medium"), 3
        )
        
        # Perform iterative research
        all_insights = []
        all_search_queries = []
        all_sources = []
        
        for iteration in range(1, research_depth + 1):
            print(f"\n📍 Research iteration {iteration}/{research_depth}")
            
            # Generate search queries
            search_queries = self.generate_search_queries(
                user_query, 
                query_analysis, 
                iteration
            )
            
            iteration_insights = []
            iteration_sources = []
            
            # Perform searches
            for query in search_queries[:5]:  # Limit queries per iteration
                print(f"  🔎 Searching: '{query}'")
                results = self.search_web(query, max_results=10)
                
                if results:
                    # Extract insights from results
                    insights = self.extract_insights(results, user_query, query_analysis)
                    
                    iteration_insights.append({
                        'query': query,
                        'insights': insights,
                        'sources': [{'title': r['title'], 'url': r['href']} for r in results[:5]]
                    })
                    
                    iteration_sources.extend(results)
                    all_search_queries.append(query)
            
            # Add iteration insights to overall insights
            if iteration_insights:
                all_insights.extend(iteration_insights)
                all_sources.extend(iteration_sources)
            
            # Check if we have enough information
            if len(all_insights) >= 10:  # Sufficient insights gathered
                print("✅ Sufficient information gathered")
                break
        
        # Synthesize final response
        print("\n🔄 Synthesizing research findings...")
        final_response = self.synthesize_research(
            user_query,
            query_analysis,
            all_insights,
            all_search_queries
        )
        
        # Add sources to response
        final_response['sources'] = [
            {'title': s['title'], 'url': s['href']} 
            for s in all_sources[:20]  # Top 20 sources
        ]
        
        return final_response
    
    def quick_answer(self, user_query: str) -> str:
        """
        Get a quick answer for simple queries (single search iteration).
        """
        result = self.research(user_query, max_depth=1)
        
        # Extract just the direct answer portion
        response = result.get('response', '')
        # Try to extract the first paragraph or direct answer
        lines = response.split('\n')
        for line in lines:
            if line.strip():
                return line.strip()
        
        return response

# Example usage and helper functions
def save_research_report(result: Dict, filename: Optional[str] = None):
    """Save research results to a JSON file."""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_slug = re.sub(r'[^\w\s-]', '', result['user_query'])[:50]
        query_slug = re.sub(r'[-\s]+', '-', query_slug)
        filename = f"research_{query_slug}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    return filename

def print_research_summary(result: Dict):
    """Print a formatted summary of research results."""
    print(f"\n{'='*60}")
    print(f"📋 RESEARCH SUMMARY")
    print(f"{'='*60}")
    print(f"Query: {result['user_query']}")
    print(f"Type: {result['query_analysis']['query_type']}")
    print(f"Timestamp: {result['timestamp']}")
    print(f"\n📊 Statistics:")
    print(f"  - Search queries performed: {len(result['search_queries'])}")
    print(f"  - Sources analyzed: {result['sources_count']}")
    print(f"  - Research depth: {result['research_depth']} iterations")
    print(f"\n📝 Response:")
    print(result['response'])
    print(f"\n🔗 Top Sources:")
    for i, source in enumerate(result.get('sources', [])[:5], 1):
        print(f"  {i}. {source['title']}")
        print(f"     {source['url']}")

# Main execution
if __name__ == "__main__":
    # Configure your Azure OpenAI settings
    AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
    AZURE_OPENAI_KEY = "your-api-key"
    DEPLOYMENT_NAME = "gpt-4"
    
    # Initialize the research agent
    agent = DeepResearchAgent(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        deployment_name=DEPLOYMENT_NAME,
        max_search_results=15,
        max_search_depth=5
    )
    
    # Example queries demonstrating different capabilities
    example_queries = [
        # Competitor analysis
        "What are Stripe's main competitors and how do they compare?",
        "Who competes with Tesla in the electric vehicle market?",
        
        # Product comparison
        "Compare React vs Vue vs Angular for web development",
        "What's the difference between ChatGPT and Claude?",
        
        # Market research
        "What's the current state of the AI market in healthcare?",
        "Renewable energy market trends in 2024",
        
        # Company research
        "Tell me about OpenAI's latest developments and products",
        "What is Apple's strategy for AI integration?",
        
        # Technical research
        "How does transformer architecture work in LLMs?",
        "Best practices for microservices architecture",
        
        # General research
        "What are the health benefits of intermittent fasting?",
        "History and impact of the Internet",
        
        # Pricing research
        "Compare AWS, Azure, and Google Cloud pricing for compute instances",
        
        # Industry trends
        "Latest trends in sustainable technology",
        "Future of remote work post-2024"
    ]
    
    # Interactive mode
    print("🤖 Deep Research Agent Ready!")
    print("Type 'exit' to quit, 'examples' to see example queries")
    print("-" * 60)
    
    while True:
        user_input = input("\n🔍 Enter your research query: ").strip()
        
        if user_input.lower() == 'exit':
            print("👋 Goodbye!")
            break
        
        elif user_input.lower() == 'examples':
            print("\n📚 Example queries:")
            for i, query in enumerate(example_queries, 1):
                print(f"{i}. {query}")
            continue
        
        elif user_input:
            # Perform research
            result = agent.research(user_input)
            
            # Display summary
            print_research_summary(result)
            
            # Save results
            filename = save_research_report(result)
            print(f"\n💾 Full report saved to: {filename}")
            
            # Ask for follow-up
            follow_up = input("\n🔄 Would you like to research a related topic? (yes/no): ")
            if follow_up.lower() != 'yes':
                continue