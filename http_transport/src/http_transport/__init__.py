import requests

from sync_tooling_msgs.graph_update_pb2 import GraphUpdate


class HttpClient:
    def __init__(self, endpoint_url: str) -> None:
        self.session_ = requests.Session()
        self.endpoint_ = endpoint_url

    def send(self, obj: GraphUpdate):
        serialized = obj.SerializeToString()

        response = self.session_.post(
            self.endpoint_,
            serialized,
            headers={"Content-Type": "application/octet-stream"},
        )

        if response.status_code != 200:
            raise requests.HTTPError(response=response)
