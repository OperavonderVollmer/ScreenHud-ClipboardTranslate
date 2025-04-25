
from PIL import ImageGrab, Image
import socket
from OperaPowerRelay import opr
import os
import time
from dotenv import load_dotenv
import struct

"""

    A simple script to retrieve an image from the clipboard to be sent to the server

"""


load_dotenv()

CLIPBOARD_HOST = str(os.getenv("CLIPBOARD_HOST"))
CLIPBOARD_PORT = int(os.getenv("CLIPBOARD_PORT"))
IMAGE_MODE = str(os.getenv("IMAGE_MODE"))

def clipboard_image_snatch() -> Image.Image | None:

    try:
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            return img
        else:
            return None
    except Exception:
        return None
    
def send_via_tcp(img: Image.Image) -> str:
    try:
        img_bytes = img.tobytes()
        dimensions = img.size

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((CLIPBOARD_HOST, CLIPBOARD_PORT))
            size_packed = struct.pack("!I", len(img_bytes))
            width_packed = struct.pack("!I", dimensions[0])
            height_packed = struct.pack("!I", dimensions[1])
            sock.sendall(size_packed)
            sock.sendall(width_packed)
            sock.sendall(height_packed)
            time.sleep(0.1)
            sock.sendall(img_bytes)

        return f"SUCCESS: Clipboard image sent to {CLIPBOARD_HOST}:{CLIPBOARD_PORT}"
        
    except ConnectionRefusedError:
        return f"FAILED: Connection refused {CLIPBOARD_HOST}:{CLIPBOARD_PORT}"
    except socket.gaierror:
        return f"FAILED: Address-related error connecting to server {CLIPBOARD_HOST}:{CLIPBOARD_PORT}"
    except Exception as e:
        return f"FAILED: Something went wrong - {e}"

def main():


    global IMAGE_MODE


    path = os.path.join(os.path.dirname(os.path.abspath(__file__)))

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())

    img = clipboard_image_snatch()

    if img is None:
        print("Clipboard is empty or not an image")
        return

    if img.mode != IMAGE_MODE:
        img = img.convert(IMAGE_MODE)

    print(img.mode)

    result = send_via_tcp(img)    

    img.close()

    log_message = f"{timestamp} - {result}\n"    

    opr.write_log("ClipboardTranslate", path, "clipboard-snatch.log", log_message, "INFO")
    return

main()
input("Press enter to exit")