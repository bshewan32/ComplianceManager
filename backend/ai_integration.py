"""
AI Integration Module for Document Generation and Improvement
Supports OpenAI (ChatGPT), Google (Gemini), and DeepSeek
"""

import sqlite3
from typing import Optional, Dict, List
import json

# AI Provider imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

import httpx

DB_PATH = "compliance.db"

class AIDocumentAssistant:
    """AI-powered document generation and improvement assistant"""
    
    def __init__(self):
        self.provider = None
        self.api_key = None
        self.model_name = None
        self.client = None
        self._load_config()
    
    def _load_config(self):
        """Load active AI configuration from database"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT provider, api_key, model_name FROM ai_config WHERE is_active = 1")
        config = cursor.fetchone()
        conn.close()
        
        if config:
            self.provider, self.api_key, self.model_name = config
            self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the appropriate AI client"""
        if self.provider == "openai" and OPENAI_AVAILABLE:
            openai.api_key = self.api_key
            self.client = openai
            if not self.model_name:
                self.model_name = "gpt-4"
        
        elif self.provider == "google" and GOOGLE_AVAILABLE:
            genai.configure(api_key=self.api_key)
            if not self.model_name:
                self.model_name = "gemini-pro"
            self.client = genai.GenerativeModel(self.model_name)
        
        elif self.provider == "deepseek":
            # DeepSeek uses OpenAI-compatible API
            if not self.model_name:
                self.model_name = "deepseek-chat"
    
    def generate_document(self, clause_info: Dict, standard_info: Dict, 
                         document_type: str = "procedure") -> str:
        """
        Generate a new compliance document
        
        Args:
            clause_info: Dict with clause_number, title, description
            standard_info: Dict with standard name, version
            document_type: Type of document to generate (procedure, policy, record, etc.)
        
        Returns:
            Generated document content as string
        """
        if not self.client:
            raise ValueError("AI client not configured. Please configure AI settings first.")
        
        prompt = self._build_generation_prompt(clause_info, standard_info, document_type)
        
        if self.provider == "openai":
            return self._generate_openai(prompt)
        elif self.provider == "google":
            return self._generate_google(prompt)
        elif self.provider == "deepseek":
            return self._generate_deepseek(prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def improve_document(self, current_content: str, clause_info: Dict, 
                        standard_info: Dict) -> Dict[str, any]:
        """
        Analyze and suggest improvements for existing document
        
        Args:
            current_content: Current document text
            clause_info: Dict with clause requirements
            standard_info: Dict with standard details
        
        Returns:
            Dict with 'suggestions', 'improved_content', 'compliance_gaps'
        """
        if not self.client:
            raise ValueError("AI client not configured")
        
        prompt = self._build_improvement_prompt(current_content, clause_info, standard_info)
        
        if self.provider == "openai":
            response = self._generate_openai(prompt)
        elif self.provider == "google":
            response = self._generate_google(prompt)
        elif self.provider == "deepseek":
            response = self._generate_deepseek(prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        return self._parse_improvement_response(response)
    
    def _build_generation_prompt(self, clause_info: Dict, standard_info: Dict, 
                                 doc_type: str) -> str:
        """Build prompt for document generation"""
        prompt = f"""You are a compliance document expert. Generate a comprehensive {doc_type} document for the following compliance requirement:

Standard: {standard_info['name']} {standard_info.get('version', '')}
Clause: {clause_info['clause_number']} - {clause_info['title']}
Description: {clause_info.get('description', '')}

Requirements:
1. Create a professional, compliant {doc_type} that addresses all aspects of this clause
2. Include clear objectives, scope, responsibilities, and procedures
3. Use industry best practices and appropriate terminology
4. Format with proper headers, sections, and structure
5. Include placeholders for company-specific information (e.g., [COMPANY NAME])
6. Ensure the document would satisfy audit requirements

Generate a complete, ready-to-use document."""
        
        return prompt
    
    def _build_improvement_prompt(self, content: str, clause_info: Dict, 
                                  standard_info: Dict) -> str:
        """Build prompt for document improvement"""
        prompt = f"""You are a compliance auditor. Analyze this document and provide improvement suggestions:

Standard: {standard_info['name']} {standard_info.get('version', '')}
Clause: {clause_info['clause_number']} - {clause_info['title']}
Required: {clause_info.get('description', '')}

Current Document:
{content[:3000]}  # Limit content to avoid token limits

Provide your response in this JSON format:
{{
    "compliance_score": <0-100>,
    "gaps": ["gap 1", "gap 2", ...],
    "suggestions": ["suggestion 1", "suggestion 2", ...],
    "critical_issues": ["issue 1", "issue 2", ...],
    "improved_sections": {{
        "section_name": "improved text"
    }}
}}

Focus on:
1. Completeness - does it address all clause requirements?
2. Clarity - is it clear and unambiguous?
3. Structure - is it well-organized?
4. Compliance - does it meet audit standards?
5. Practical - is it implementable?"""
        
        return prompt
    
    def _generate_openai(self, prompt: str) -> str:
        """Generate using OpenAI API"""
        response = self.client.ChatCompletion.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are an expert compliance document writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        return response.choices[0].message.content
    
    def _generate_google(self, prompt: str) -> str:
        """Generate using Google Gemini API"""
        response = self.client.generate_content(prompt)
        return response.text
    
    def _generate_deepseek(self, prompt: str) -> str:
        """Generate using DeepSeek API (OpenAI-compatible)"""
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are an expert compliance document writer."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 3000
        }
        
        response = httpx.post(url, headers=headers, json=data, timeout=60.0)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def _parse_improvement_response(self, response: str) -> Dict:
        """Parse AI improvement response"""
        try:
            # Try to extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "{" in response and "}" in response:
                # Find the JSON object
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
            else:
                json_str = response
            
            return json.loads(json_str)
        except:
            # Fallback if JSON parsing fails
            return {
                "compliance_score": 0,
                "gaps": ["Unable to parse AI response"],
                "suggestions": [response],
                "critical_issues": [],
                "improved_sections": {}
            }
    
    def generate_compliance_recommendations(self, missing_documents: List[Dict], 
                                           element_scores: Dict) -> List[Dict]:
        """
        Generate prioritized recommendations for improving compliance score
        
        Args:
            missing_documents: List of missing document info
            element_scores: Dict of element scores
        
        Returns:
            List of prioritized recommendations with actions
        """
        if not self.client:
            raise ValueError("AI client not configured")
        
        prompt = f"""As a compliance consultant, analyze this compliance situation and provide actionable recommendations:

Missing Documents:
{json.dumps(missing_documents, indent=2)}

Element Scores:
{json.dumps(element_scores, indent=2)}

Provide a prioritized list of 5-10 recommendations in JSON format:
[
    {{
        "priority": "high|medium|low",
        "element": "element number",
        "action": "specific action to take",
        "impact": "expected score improvement",
        "effort": "estimated effort (hours)",
        "documents_needed": ["list of documents"]
    }},
    ...
]

Prioritize based on:
1. Regulatory criticality
2. Quick wins (low effort, high impact)
3. Element weight
4. Dependency on other requirements"""
        
        if self.provider == "openai":
            response = self._generate_openai(prompt)
        elif self.provider == "google":
            response = self._generate_google(prompt)
        elif self.provider == "deepseek":
            response = self._generate_deepseek(prompt)
        
        try:
            if "[" in response:
                start = response.find("[")
                end = response.rfind("]") + 1
                return json.loads(response[start:end])
        except:
            pass
        
        return []


# FastAPI endpoint additions for the backend

def add_ai_endpoints(app):
    """Add AI-related endpoints to FastAPI app"""
    
    @app.post("/api/ai/generate-document")
    async def generate_document_endpoint(
        clause_id: int,
        document_type: str = "procedure"
    ):
        """Generate a new document for a clause using AI"""
        assistant = AIDocumentAssistant()
        
        # Get clause and standard info from database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.clause_number, c.title, c.description, c.standard_id,
                   s.name as standard_name, s.version as standard_version
            FROM clauses c
            JOIN standards s ON c.standard_id = s.id
            WHERE c.id = ?
        """, (clause_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"error": "Clause not found"}
        
        clause_info = {
            "clause_number": row[0],
            "title": row[1],
            "description": row[2]
        }
        
        standard_info = {
            "name": row[4],
            "version": row[5]
        }
        
        try:
            content = assistant.generate_document(clause_info, standard_info, document_type)
            return {
                "success": True,
                "content": content,
                "clause": clause_info
            }
        except Exception as e:
            return {"error": str(e)}
    
    @app.post("/api/ai/improve-document")
    async def improve_document_endpoint(
        document_id: int
    ):
        """Get AI suggestions for improving a document"""
        assistant = AIDocumentAssistant()
        
        # Get document content and associated clause info
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT d.file_path, c.clause_number, c.title, c.description,
                   s.name as standard_name, s.version as standard_version
            FROM documents d
            JOIN clauses c ON d.clause_id = c.id
            JOIN standards s ON c.standard_id = s.id
            WHERE d.id = ?
        """, (document_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"error": "Document not found"}
        
        # Read document content (simplified - would need proper text extraction)
        try:
            with open(row[0], 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return {"error": "Could not read document content"}
        
        clause_info = {
            "clause_number": row[1],
            "title": row[2],
            "description": row[3]
        }
        
        standard_info = {
            "name": row[4],
            "version": row[5]
        }
        
        try:
            improvements = assistant.improve_document(content, clause_info, standard_info)
            return {
                "success": True,
                "improvements": improvements
            }
        except Exception as e:
            return {"error": str(e)}
    
    @app.get("/api/ai/recommendations/{standard_id}")
    async def get_recommendations(standard_id: int):
        """Get AI-powered recommendations for improving compliance"""
        assistant = AIDocumentAssistant()
        
        # Get compliance data
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.clause_number, c.title, c.weight
            FROM clauses c
            LEFT JOIN documents d ON c.id = d.clause_id AND d.status = 'active'
            WHERE c.standard_id = ? AND d.id IS NULL
        """, (standard_id,))
        
        missing = [{"clause_number": r[0], "title": r[1], "weight": r[2]} 
                  for r in cursor.fetchall()]
        
        # Get element scores (simplified)
        element_scores = {}  # Would calculate this properly
        
        conn.close()
        
        try:
            recommendations = assistant.generate_compliance_recommendations(missing, element_scores)
            return {
                "success": True,
                "recommendations": recommendations
            }
        except Exception as e:
            return {"error": str(e)}

# Example usage
if __name__ == "__main__":
    assistant = AIDocumentAssistant()
    
    # Test configuration
    print("AI Provider:", assistant.provider)
    print("Model:", assistant.model_name)
    print("Client initialized:", assistant.client is not None)