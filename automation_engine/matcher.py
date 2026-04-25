"""
Flow matcher module.
Finds published flows that match incoming events.
"""

from typing import List, Dict, Any
from db import get_supabase


class Flow:
    """Simple Flow class to represent a matched flow."""
    def __init__(self, id: str, name: str, definition: Dict[str, Any]):
        self.id = id
        self.name = name
        self.definition = definition

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "definition": self.definition
        }


async def match_flows(event_name: str, user_id: str) -> List[Flow]:
    """
    Find all published flows that match the given event.

    Args:
        event_name: The name of the event (e.g., "test.ping")
        user_id: The user ID to filter flows by

    Returns:
        List of Flow objects that have triggers matching the event_name
    """
    supabase = get_supabase()

    # Query flows where:
    # - status = 'published'
    # - user_id matches
    # - definition->'steps'->0->>'event_name' matches the input event_name
    result = supabase.table('flows').select('id, name, definition').eq('status', 'published').eq('user_id', user_id).execute()

    matching_flows = []

    for flow_data in result.data:
        definition = flow_data['definition']

        # Check if the flow has steps and the first step is a trigger with matching event_name
        if (definition and
            'steps' in definition and
            len(definition['steps']) > 0 and
            definition['steps'][0].get('type') == 'trigger' and
            definition['steps'][0].get('config', {}).get('event_name') == event_name):

            flow = Flow(
                id=flow_data['id'],
                name=flow_data['name'],
                definition=definition
            )
            matching_flows.append(flow)

    return matching_flows
