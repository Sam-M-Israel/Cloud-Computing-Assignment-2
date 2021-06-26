from datetime import datetime
from uhashring import HashRing


class NodeHashRing:
    """
    Our Hash ring object
    """
    def __init__(self, db_table, logger):
        self.dynamo_table = db_table
        self.live_nodes = self.get_live_node_list()
        self.hash_ring = HashRing(nodes=self.live_nodes)
        self.flask_logger = logger
        self._last_updated = 0
        self.get_current_time()

    def get_live_node_list(self) -> []:
        """
        Set value in our node's cache
        :return:
        """
        try:
            self.flask_logger.info('Here in get_live_node_list')
            response = self.dynamo_table.scan()
            self.flask_logger.info(f'Table scan response: {response}')
            self.get_current_time()
            self.live_nodes = [item['IP'] for item in response['Items'] if
                          float(item['lastActiveTime']) >= self._last_updated - 60000]
        except Exception as e:
            self.flask_logger.info(f'Error in get_live_node_list: {e}')

        return self.live_nodes

    def get_target_node(self, key):
        return self.hash_ring.get_node(key)

    def get_target_and_alt_node_ips(self, key):
        self.update_live_nodes()
        main_node = self.hash_ring.get_node(key)
        if main_node is None:
            self.update_live_nodes()
        self.hash_ring.remove_node(main_node)
        alt_node = self.hash_ring.get_node(key)

        if alt_node is None:
            alt_node = -1
        self.hash_ring.add_node(main_node)

        return main_node, alt_node

    def update_live_nodes(self):
        live_nodes_list = self.get_live_node_list()

        for node in live_nodes_list:
            if node not in self.hash_ring.get_nodes():
                self.hash_ring.add_node(node)

        for node_key in self.hash_ring.get_nodes():
            if node_key not in live_nodes_list:
                self.hash_ring.remove_node(node_key)

    def get_current_time(self):
        self._last_updated = round(datetime.now().timestamp())
        return self._last_updated

    def to_string(self):
        return str(self.hash_ring.nodes)
