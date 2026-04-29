import hashlib
import json
import logging
import struct

from common.consts import PLACE_HOLDERS, UNICODE_APOSTROPHES

_LOGGER = logging.getLogger(__name__)


def get_hashed_password(random, realm, username, password):
    password_str = f"{username}:{realm}:{password}"
    password_bytes = password_str.encode('utf-8')
    password_hash = hashlib.md5(password_bytes).hexdigest().upper()

    random_str = f"{username}:{random}:{password_hash}"
    random_bytes = random_str.encode('utf-8')
    random_hash = hashlib.md5(random_bytes).hexdigest().upper()

    return random_hash


def convert_message(data):
    message_data = json.dumps(data, indent=4)

    header = struct.pack(">L", 0x20000000)
    header += struct.pack(">L", 0x44484950)
    header += struct.pack(">d", 0)
    header += struct.pack("<L", len(message_data))
    header += struct.pack("<L", 0)
    header += struct.pack("<L", len(message_data))
    header += struct.pack("<L", 0)

    message = header + message_data.encode("utf-8")

    return message


def get_decoded_line(line, is_ascii: bool) -> str:
    if is_ascii:
        decoded_line = line.decode("unicode-escape")
    else:
        decoded_line = line.encode().decode("utf-8")
        for apostrophe in UNICODE_APOSTROPHES:
            decoded_line = decoded_line.replace(apostrophe, "\"")

    return decoded_line


def get_start_index(decoded_line) -> int | None:
    start_index = None

    for place_holder in PLACE_HOLDERS:
        if place_holder in decoded_line:
            start_index = decoded_line.index(place_holder)
            break

    return start_index
