import time, json, socket, struct

HUD_HOST = "127.0.0.1"
HUD_PORT=56000


test_entry = [
    {"name": "John Smith", "age": 30, "city": "New York"},
    {"name": "Jane Doe", "age": 25, "city": "San Francisco"},
    {"name": "Bob Johnson", "age": 40, "city": "Los Angeles"}
]

def send_via_tcp(list_to_send) -> str:

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())

    payload = {
        "type": "card",
        "timestamp": timestamp,
        "results": []
    }

    for entry in list_to_send:
        payload["results"].append(entry)

    print(payload["results"])

    input("Test end, press enter to continue")
    
    payload_json = json.dumps(payload)
    payload_bytes = payload_json.encode("utf-8")
    payload_size = len(payload_bytes)


    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((HUD_HOST, HUD_PORT))
            size_packed = struct.pack("!I", payload_size)
            sock.sendall(size_packed)
            time.sleep(0.1)
            sock.sendall(payload_bytes)

        return f"SUCCESS: Translated clipboard data sent to {HUD_HOST}:{HUD_PORT}"
        
    except ConnectionRefusedError:
        return f"FAILED: Connection refused {HUD_HOST}:{HUD_PORT}"
    except socket.gaierror:
        return f"FAILED: Address-related error connecting to server {HUD_HOST}:{HUD_PORT}"
    except Exception as e:
        return f"FAILED: Something went wrong - {e}"



if __name__ == "__main__":
    print("Starting test...")
    send_via_tcp(test_entry)