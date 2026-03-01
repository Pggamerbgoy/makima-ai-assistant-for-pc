"""
Knowledge Graph - Contextual Relational Memory Engine using NetworkX
Fast, local, entirely in-memory during execution.
"""
import os
import time
from typing import Dict, List, Any, Optional
import networkx as nx

class KnowledgeGraph:
    """
    Graph-based memory system storing and retrieving context via Entities and Relationships.
    Uses NetworkX for optimized local pathing and relationship traversals.
    """
    def __init__(self, storage_path: str = "data/knowledge_graph.graphml"):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        self.graph = self._load_graph()
        self.last_save = time.time()
        print("🧩 Contextual Knowledge Graph initialized (Optimized NetworkX Engine)")
    
    def _load_graph(self) -> nx.DiGraph:
        """Load graph from a GraphML file if it exists, else create new directed graph."""
        if os.path.exists(self.storage_path):
            try:
                return nx.read_graphml(self.storage_path)
            except Exception as e:
                print(f"⚠️ Graph load failed, starting fresh: {e}")
                return nx.DiGraph()
        return nx.DiGraph()
    
    def _save_graph(self):
        """
        Save graph to file.

        Throttled to prevent disk spamming during rapid inserts:
        we only persist at most once every 5 seconds.
        """
        now = time.time()
        if now - self.last_save < 5.0:
            return
        try:
            nx.write_graphml(self.graph, self.storage_path)
            self.last_save = now
        except Exception as e:
            print(f"⚠️ Graph serialization failed: {e}")

    def add_node(self, node_id: str, node_type: str, properties: Dict = None) -> bool:
        """Add an entity node to the network."""
        node_id = str(node_id).strip().lower()
        if not properties:
            properties = {}
            
        self.graph.add_node(node_id, type=node_type, **properties)
        self._save_graph()
        return True
    
    def add_edge(self, from_id: str, to_id: str, relationship: str, properties: Dict = None):
        """Connect two entities with a directed relationship."""
        from_id = str(from_id).strip().lower()
        to_id = str(to_id).strip().lower()
        if not properties:
            properties = {}
            
        # Ensure nodes exist before tying them together to prevent graph islands
        if not self.graph.has_node(from_id):
            self.add_node(from_id, "Entity")
        if not self.graph.has_node(to_id):
            self.add_node(to_id, "Entity")
            
        self.graph.add_edge(from_id, to_id, relationship=relationship, **properties)
        self._save_graph()
    
    def find_related(self, node_id: str, relationship: str = None) -> List[Dict]:
        """Traverse the graph to find connected nodes. Highly optimized O(1) adjacency lookup."""
        node_id = str(node_id).strip().lower()
        if not self.graph.has_node(node_id):
            return []
            
        related = []
        # Get nodes that this node points to
        for successor_id in self.graph.successors(node_id):
            edge_data = self.graph.get_edge_data(node_id, successor_id)
            if relationship is None or edge_data.get('relationship') == relationship:
                node_data = self.graph.nodes[successor_id]
                related.append({
                    'id': successor_id,
                    'type': node_data.get('type', 'Unknown'),
                    'via': edge_data.get('relationship', 'connected_to'),
                    'properties': {k: v for k, v in node_data.items() if k != 'type'}
                })
        return related
    
    def search(self, query: str) -> List[Dict]:
        """Simple fuzzy search across all nodes in the graph."""
        query_lower = str(query).lower()
        results = []
        
        for node_id, data in self.graph.nodes(data=True):
            # Check ID
            if query_lower in str(node_id).lower():
                results.append({'id': node_id, **data})
                continue
                
            # Check properties
            for k, v in data.items():
                if query_lower in str(v).lower():
                    results.append({'id': node_id, **data})
                    break
                    
        return results

    def get_contextual_subgraph(self, starting_nodes: List[str], depth: int = 1) -> str:
        """
        Extracts a localized contextual textual summary for LLM consumption.
        Walks `depth` steps outwards from a list of trigger nodes.
        """
        context_lines = []
        for start_id in starting_nodes:
            start_id = str(start_id).strip().lower()
            if not self.graph.has_node(start_id):
                continue
                
            # Get ego graph (neighborhood up to radius `depth`)
            sub = nx.ego_graph(self.graph, start_id, radius=depth)
            
            for u, v, d in sub.edges(data=True):
                rel = d.get('relationship', 'is related to')
                context_lines.append(f"[{u}] --({rel})--> [{v}]")
                
        # Deduplicate and return
        return "\n".join(list(set(context_lines)))
    
    def get_stats(self) -> Dict:
        """Get highly optimized graph statistics"""
        return {
            'nodes': self.graph.number_of_nodes(),
            'edges': self.graph.number_of_edges()
        }
