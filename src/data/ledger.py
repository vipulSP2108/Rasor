import json
import os
from datetime import datetime
from typing import Any, Dict

class AuditLedger:
    """An append-only ledger for tracking agentic commerce decisions."""
    
    def __init__(self, file_path: str = "scratch/audit_ledger.jsonl"):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
    def log_event(self, event_type: str, details: Dict[str, Any]):
        """Logs an event to the ledger."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "details": details
        }
        
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
    def get_entries(self) -> list[Dict[str, Any]]:
        """Reads all entries from the ledger (for UI display)."""
        if not os.path.exists(self.file_path):
            return []
            
        entries = []
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries
