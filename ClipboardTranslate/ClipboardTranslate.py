from OPRDetectRecog.OPRDetectRecog import load_detectors, load_recognizers
from OPRTranslate.OPRTranslate import load_translators
from OPRDetectRecog.Custom.LinguistResult import LinguistResult
from OPRDetectRecog.Custom.Quadbox import QuadBox

from OperaPowerRelay import opr
from dotenv import load_dotenv
import os
import threading
import socket
import struct
import time
from PIL import Image
import json

load_dotenv()

CLIPBOARD_HOST = str(os.getenv("CLIPBOARD_HOST"))
CLIPBOARD_PORT = int(os.getenv("CLIPBOARD_PORT"))

IMAGE_MODE = str(os.getenv("IMAGE_MODE"))

HUD_HOST = str(os.getenv("HUD_HOST"))
HUD_PORT = int(os.getenv("HUD_PORT"))

DEFAULT_SOURCE_LANGUAGE = "japanese"
DEFAULT_TARGET_LANGUAGE = "en"

DETECTOR_NAME = "paddleocr_detector"
RECOGNIZER_NAME = "mangaocr_recognizer"
TRANSLATOR_NAME = "deepl_google"

DETECTOR = None
RECOGNIZER = None
TRANSLATOR = None

CLIPBOARD_STOP_SIGN = threading.Event()

"""

    Clipboard Monitor (probably using autohotkey to monitor the clipboard and call a script) ->
    Retrieve clipboard content -> Check if its an image ->
    Image OCR -> Cached Translator / Translator -> Pipe information


"""



def clipboard_thread():
    
    try:

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((CLIPBOARD_HOST, CLIPBOARD_PORT))
            sock.listen()
            opr.print_from("Clipboard Thread", f"Listening for clipboard content on {CLIPBOARD_HOST}:{CLIPBOARD_PORT}", 1)

            while not CLIPBOARD_STOP_SIGN.is_set():
                conn = None
                addr = None
                try:
                    sock.settimeout(1)
                    conn, addr = sock.accept()
                    opr.print_from("Clipboard Thread", f"Connection from {addr}", 1)
                    if not conn:
                        continue
                    with conn:
                        size_bytes = conn.recv(4)
                        if not size_bytes:
                            opr.print_from("Clipboard Thread", f"Connection closed by {addr}", 1)
                            break
                            
                        opr.print_from("Clipboard Thread", f"Receiving Image Size...", 1)
                        image_size = struct.unpack("!I", size_bytes)[0]
                        opr.print_from("Clipboard Thread", f"Image size: {image_size}", 1)


                        opr.print_from("Clipboard Thread", f"Receiving Image Dimensions...", 1)

                        dimensions = b''
                        bytes_received = 0
                        while bytes_received < 8:
                            chunk = conn.recv(4)
                            if not chunk:
                                opr.print_from("Clipboard Thread", f"Connection closed by {addr}", 1)
                                break
                            dimensions += chunk
                            bytes_received += 4                        

                        if not dimensions:
                            opr.print_from("Clipboard Thread", f"Connection closed by {addr}", 1)
                            break

                        width, height = struct.unpack("!II", dimensions)
                        opr.print_from("Clipboard Thread", f"Image dimensions: {width}x{height}", 1) 


                        image_bytes = b""
                        bytes_received = 0

                        opr.print_from("Clipboard Thread", f"Receiving Image...", 1)

                        while bytes_received < image_size:
                            chunk = conn.recv(4096)
                            if not chunk:
                                opr.print_from("Clipboard Thread", f"Connection closed by {addr}", 1)
                                break
                            image_bytes += chunk
                            bytes_received += len(chunk)

                        if bytes_received != image_size:
                            opr.print_from("Clipboard Thread", f"Expected {image_size} bytes, received {bytes_received}", 1)
                            continue

                        

                        img = Image.frombytes(IMAGE_MODE, (width, height), image_bytes)
                        opr.print_from("Clipboard Thread", f"Received image from {addr}", 1)

                        process_image(img)


                    opr.print_from("Clipboard Thread", f"Connection with {addr} closed", 1)

                except socket.timeout:
                    pass

                except Exception as e:
                    opr.print_from("Clipboard Thread", f"Something went wrong - {e}", 1)
                    break

    except Exception as e:
        opr.print_from("Clipboard Thread", f"Something went wrong - {e}", 1)

    finally:
        opr.print_from("Clipboard Thread", f"Stopping clipboard thread", 1)
        CLIPBOARD_STOP_SIGN.set()



def check_library(word: str) -> str | None:

    library = opr.load_json("ClipboardTranslate", os.path.dirname(os.path.abspath(__file__)), "library.json")

    if word in library:
        return library[word]

    return None

def write_library(word: str, translation: str) -> None:

    library = opr.load_json("ClipboardTranslate", os.path.dirname(os.path.abspath(__file__)), "library.json")

    library[word] = translation

    opr.save_json("ClipboardTranslate", os.path.dirname(os.path.abspath(__file__)), library, "library.json")


def process_image(img: Image.Image):
    
    threading.Thread(target=_process_image, args=(img,), daemon=True).start()
    
    return

def _process_image(img: Image.Image):

    global DETECTOR
    global RECOGNIZER
    global TRANSLATOR

    print("Now processing...")

    detection_results = DETECTOR.detect_and_crop(img)
    recognition_results = []

    for bbox, _, image in detection_results:
        translated = RECOGNIZER.recognize(image, bbox)
        for r in translated:
            recognition_results.append(r)

    translation_results = []

    for r in recognition_results:

        translated = check_library(r.Text)

        if translated is None:
            translated = TRANSLATOR.translate(r.Text)
            write_library(r.Text, translated)

        result = LinguistResult(r.QuadBox, r.Text, translated, r.Confidence)
        translation_results.append(result)

    final_results = translation_results[::-1]

    for r in final_results:
        opr.print_from("Clipboard Translate - Result", f"{r.Text} at {r.QuadBox} with {r.Confidence} confidence")

    send_via_tcp(final_results)


def send_via_tcp(list_of_linguist_results: list[LinguistResult]) -> str:

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())

    payload = {
        "type": "card",
        "timestamp": timestamp,
        "results": []
    }

    for linguist_result in list_of_linguist_results:
        payload["results"].append({
            "Translated": linguist_result.Translated,
            "Original": linguist_result.Original,
            "Confidence": linguist_result.Confidence
        })

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



def load_models():

    

    global DETECTOR_NAME
    global RECOGNIZER_NAME
    global TRANSLATOR_NAME
    global DETECTOR
    global RECOGNIZER
    global TRANSLATOR

    global DEFAULT_SOURCE_LANGUAGE
    global DEFAULT_TARGET_LANGUAGE

    DETECTOR = load_detectors(DETECTOR_NAME)
    DETECTOR.initialize(language=DEFAULT_SOURCE_LANGUAGE)
    opr.print_from("Clipboard Translate - Model Loader", f"{{gre}}Loaded detector {DETECTOR_NAME}{{def}}", 1)

    RECOGNIZER = load_recognizers(RECOGNIZER_NAME)
    RECOGNIZER.initialize(language=DEFAULT_TARGET_LANGUAGE)
    opr.print_from("Clipboard Translate - Model Loader", f"{{gre}}Loaded recognizer {RECOGNIZER_NAME}{{def}}", 1)

    TRANSLATOR = load_translators(TRANSLATOR_NAME)
    TRANSLATOR.initialize(source_language=DEFAULT_SOURCE_LANGUAGE, target_language=DEFAULT_TARGET_LANGUAGE)
    opr.print_from("Clipboard Translate - Model Loader", f"{{gre}}Loaded translator {TRANSLATOR_NAME}{{def}}", 1)


def main():

    

    load_models()


    CLIPBOARD_THREAD = threading.Thread(target=clipboard_thread, daemon=True)
    CLIPBOARD_THREAD.start()
    
    try:
        print("Press Ctrl+C to stop")
        while not CLIPBOARD_STOP_SIGN.is_set():
            time.sleep(1)

    except KeyboardInterrupt:
        pass

    finally:
        CLIPBOARD_STOP_SIGN.set()
    

    CLIPBOARD_THREAD.join()














