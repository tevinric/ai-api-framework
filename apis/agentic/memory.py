# apis/agentic/memory.py
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from apis.utils.databaseService import DatabaseService

logger = logging.getLogger(__name__)

@dataclass
class Message:
    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None

class ConversationMemory:
    """Manages conversation memory for agents"""
    
    def __init__(self, agent_id: str, max_messages: int = 100):
        self.agent_id = agent_id
        self.max_messages = max_messages
        self.messages: List[Message] = []
        self._load_from_database()
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add a message to memory"""
        message = Message(
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        self.messages.append(message)
        
        # Trim old messages if we exceed max
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        
        # Save to database
        self._save_message(message)
    
    def get_conversation_history(self, max_messages: int = None) -> str:
        """Get formatted conversation history"""
        messages_to_include = self.messages
        
        if max_messages:
            messages_to_include = self.messages[-max_messages:]
        
        formatted_messages = []
        for msg in messages_to_include:
            timestamp_str = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            formatted_messages.append(f"[{timestamp_str}] {msg.role}: {msg.content}")
        
        return "\n".join(formatted_messages)
    
    def get_messages_by_role(self, role: str) -> List[Message]:
        """Get all messages by a specific role"""
        return [msg for msg in self.messages if msg.role == role]
    
    def get_recent_context(self, minutes: int = 30) -> List[Message]:
        """Get messages from the last N minutes"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        return [msg for msg in self.messages if msg.timestamp > cutoff_time]
    
    def clear_memory(self):
        """Clear all messages from memory"""
        self.messages = []
        self._clear_database()
    
    def _save_message(self, message: Message):
        """Save message to database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            INSERT INTO agent_memory (
                id, agent_id, role, content, timestamp, metadata
            )
            VALUES (NEWID(), ?, ?, ?, ?, ?)
            """
            
            cursor.execute(query, [
                self.agent_id,
                message.role,
                message.content,
                message.timestamp,
                json.dumps(message.metadata) if message.metadata else None
            ])
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save message to database: {str(e)}")
    
    def _load_from_database(self):
        """Load recent messages from database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT role, content, timestamp, metadata
            FROM agent_memory
            WHERE agent_id = ?
            ORDER BY timestamp DESC
            OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
            """
            
            cursor.execute(query, [self.agent_id, self.max_messages])
            rows = cursor.fetchall()
            
            for row in reversed(rows):  # Reverse to get chronological order
                metadata = json.loads(row[3]) if row[3] else {}
                message = Message(
                    role=row[0],
                    content=row[1],
                    timestamp=row[2],
                    metadata=metadata
                )
                self.messages.append(message)
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to load messages from database: {str(e)}")
    
    def _clear_database(self):
        """Clear messages from database"""
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            query = "DELETE FROM agent_memory WHERE agent_id = ?"
            cursor.execute(query, [self.agent_id])
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to clear messages from database: {str(e)}")

