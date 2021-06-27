import requests
import json
import requests
import json
from ec2_node.nodeCache import NodeCache


class Ec2Node:
    """
    Ec2 Node class for ELB distributed cache system
    """

    def __init__(self, vpc_port):
        self._vpc_port = vpc_port
        self.ip = ""
        self._cache = NodeCache()

    def post_to_target_node(self, key, data, expiration_date, target_node_ip):
        """
        Sends a post request to the target node with the required info
        :param key:             For the target_node to use as the data's cache key
        :param data:            Data needed to be stored on the target_node
        :param expiration_date: Cache item's expiration date
        :param target_node_ip:  IP address of the target_node
        :return:
        """
        try:
            res = requests.post(
                    f'http://{target_node_ip}:{self._vpc_port}/api/set_value?str_key={key}&data={data}&expiration_date={expiration_date}')
            # res = json.dumps({'status_code': 200, "item": res})
        except requests.exceptions.ConnectionError:
            res = json.dumps({'status_code': 404})
        return res

    def get_from_target_node(self, key, target_node_ip):
        """
        Sends a get request to the target node to receive the data of the given key that is in the target nodes cache
        :param key:
        :param target_node_ip:
        :return:
        """
        try:
            res = requests.get(f'http://{target_node_ip}:{self._vpc_port}/api/get_value?str_key={key}')
            # res = json.dumps({'status_code': 200, "item": res})
        except requests.exceptions.ConnectionError:
            res = json.dumps({'status_code': 404})
        return res

    def store_data_and_post_req(self, key, data, expiration_date, target_node_ip):
        """
        Stores data in this nodes cache and then posts it to its balancer target node
        :param key:
        :param data:
        :param expiration_date:
        :param target_node_ip:
        :return:
        """
        has_been_cached = self.store_data(key, data, expiration_date)
        if has_been_cached:
            res = self.post_to_target_node(key, data, expiration_date, target_node_ip)

        return res

    def get_data_and_get_req(self, key, target_node_ip):
        """
        Stores data in this nodes cache and then posts it to its balancer target node
        :param key:
        :param target_node_ip:
        :return:
        """
        data_from_cache = self.get_data_in_cache(key)
        if data_from_cache is None:
            data_from_cache = self.get_from_target_node(key, target_node_ip)

        return data_from_cache

    def store_data(self, key, data, expiration_date):
        return self._cache.put(key, data, expiration_date)

    def get_data_in_cache(self, key):
        return self._cache.get(key)

    def get_cache(self):
        return self._cache.get_full_cache()
