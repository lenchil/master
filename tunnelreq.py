import json
import getpass
import subprocess
cmdData = CommandLineUtils.parse_sample_input_pubsub()

received_count = 0
received_all_event = threading.Event()

def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))

def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        resubscribe_future.add_done_callback(on_resubscribe_complete)
        def request_tunnel(port, ssh_key_path, ssh_host):
            message_data = {
                'command': 'Tunnel',
                'port': port
            }
            payload = json.dumps(message_data)

            print("Sending tunnel request to topic '{}'...".format(message_topic))
            mqtt_connection.publish(
                topic=message_topic,
                payload=payload,
                qos=mqtt.QoS.AT_LEAST_ONCE
            )

            print("Initiating reverse SSH tunnel request...")
            subprocess.run(['ssh', '-v', '-N', '-R', f'{port}:localhost:22', '-i', ssh_key_path, ssh_host, '-o', 'StrictHostKeyChecking=yes'])

        if __name__ == '__main__':
            # Set the desired port, SSH key path, and SSH host
            port = 1234
            ssh_key_path = 'path/to/ssh_key.pem'
            ssh_host = 'user@hostname'

            # Connect to the MQTT broker and subscribe to the topic
            # ... (code to establish MQTT connection and subscribe to topic)

            # Request the tunnel
            request_tunnel(port, ssh_key_path, ssh_host)