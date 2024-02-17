from awscrt import mqtt
from awsiot import mqtt_connection_builder
import json

# Define MQTT endpoint, port, credentials, and other configuration parameters
endpoint = "your-iot-endpoint.amazonaws.com"
port = 8883
cert_path = "path/to/your/certificate.pem.crt"
key_path = "path/to/your/private.pem.key"
ca_path = "path/to/AmazonRootCA1.pem"
client_id = "your-client-id"
bastion_topic = "bastion/request"
remote_device_response_topic = "remote/device/response"

# Define the range of ports to use
MIN_PORT = 12345
MAX_PORT = 65535

class PortPool:
    def __init__(self):
        self.available_ports = set(range(MIN_PORT, MAX_PORT + 1))

    def assign_port(self):
        if not self.available_ports:
            raise ValueError("No available ports in the pool")
        
        port = self.available_ports.pop()
        return port

    def release_port(self, port):
        if port < MIN_PORT or port > MAX_PORT:
            raise ValueError("Port is out of range")
        
        self.available_ports.add(port)

# Create an instance of the PortPool
port_pool = PortPool()

def on_message_received(topic, payload, **kwargs):
    print(f"Received message on topic '{topic}': {payload}")

    if topic == bastion_topic:
        handle_bastion_request(payload)

def handle_bastion_request(payload):
    try:
        data = json.loads(payload)
        client_id = data.get("client_id")
        username = data.get("username")
        password = data.get("password")

        if authenticate_client(client_id, username, password):
            port = assign_port()
            send_port_to_remote_device(client_id, port)
    except json.JSONDecodeError:
        print("Error decoding JSON payload")

def authenticate_client(client_id, username, password):
    return True  

def assign_port():
    return port_pool.assign_port()

def send_port_to_remote_device(client_id, port):
    port_assignment_message = {"client_id": client_id, "port": port}
    mqtt_connection.publish(
        topic=remote_device_response_topic,
        payload=json.dumps(port_assignment_message),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )
    print(f"Assigned port {port} for client {client_id}")

def on_connect_success():
    print("Connected to AWS IoT Core")
    mqtt_connection.subscribe(
        topic=bastion_topic,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received
    )
    print(f"Subscribed to topic: {bastion_topic}")

if __name__ == "__main__":
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=endpoint,
        port=port,
        cert_filepath=cert_path,
        pri_key_filepath=key_path,
        client_bootstrap=None,
        ca_filepath=ca_path,
        on_connection_interrupted=None,
        on_connection_resumed=None,
        client_id=client_id,
        clean_session=False,
        keep_alive_secs=6,
    )

    connect_future = mqtt_connection.connect()

    event_loop_group = mqtt.get_event_loop_group(num_event_loops=1)
    event_loop_group.run_forever()

    connect_future.result()
    print("Connected to AWS IoT Core")

    on_connect_success()
