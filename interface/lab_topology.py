import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LabTopology:
    """Класс для работы с топологией лаборатории PNET"""
    
    def __init__(self, topology_data: dict):
        """
        Инициализация с данными топологии.
        
        Args:
            topology_data: JSON данные топологии из get_lab_topology
        """
        self.data = topology_data
        self.nodes = topology_data.get('data', {}).get('nodes', {})
        self.networks = topology_data.get('data', {}).get('networks', {})
    
    def get_ssh_nodes(self) -> List[Dict]:
        """
        Получает список нод с SSH консолью.
        
        Returns:
            List[Dict]: Список словарей с информацией о нодах:
                {
                    'id': node_id,
                    'name': node_name,
                    'port': ssh_port,
                    'console': console_type
                }
        """
        ssh_nodes = []
        for node_id, node_data in self.nodes.items():
            console = node_data.get('console', '')
            console_2nd = node_data.get('console_2nd', '')
            
            port = None
            if console == 'ssh':
                port = node_data.get('port')
            elif console_2nd == 'ssh':
                port = node_data.get('port_2nd')
            
            if port:
                ssh_nodes.append({
                    'id': int(node_id),
                    'name': node_data.get('name', ''),
                    'port': port,
                    'console': 'ssh',
                    'template': node_data.get('template', ''),
                    'type': node_data.get('type', '')
                })
        
        return ssh_nodes
    
    def get_node_by_name(self, node_name: str) -> Optional[Dict]:
        """
        Находит ноду по имени.
        
        Args:
            node_name: Имя ноды
        
        Returns:
            Optional[Dict]: Данные ноды или None
        """
        for node_id, node_data in self.nodes.items():
            if node_data.get('name') == node_name:
                return {
                    'id': int(node_id),
                    'name': node_data.get('name', ''),
                    'port': node_data.get('port'),
                    'port_2nd': node_data.get('port_2nd'),
                    'console': node_data.get('console', ''),
                    'console_2nd': node_data.get('console_2nd', ''),
                    'template': node_data.get('template', ''),
                    'type': node_data.get('type', '')
                }
        return None
    
    def get_ssh_port_for_node(self, node_name: str) -> Optional[str]:
        """
        Получает SSH порт для ноды по имени.
        
        Args:
            node_name: Имя ноды
        
        Returns:
            Optional[str]: SSH порт или None
        """
        node = self.get_node_by_name(node_name)
        if not node:
            return None
        
        if node['console'] == 'ssh':
            return node['port']
        elif node['console_2nd'] == 'ssh':
            return node['port_2nd']
        
        return None
    
    def get_all_node_names(self) -> List[str]:
        """Возвращает список имён всех нод в топологии."""
        return [node_data.get('name', '') for node_data in self.nodes.values()]

    def get_all_node_ids(self) -> List[int]:
        """
        Получает список ID всех нод в топологии.
        
        Returns:
            List[int]: Список ID нод
        """
        return [int(node_id) for node_id in self.nodes.keys()]

