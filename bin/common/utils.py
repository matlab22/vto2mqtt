import hashlib
import json
import logging

from common.consts import JSON_START_PATTERN

_LOGGER = logging.getLogger(__name__)


def parse_data(data):
    _LOGGER.debug(f"Parsing data, Content: {data}")

    data_items = bytearray()

    for data_item in data:
        data_item_char = chr(data_item)
        parsed_char = ascii(data_item_char).replace("'", "")
        is_valid = data_item_char == parsed_char or data_item_char in ['\n', '\'']

        if is_valid:
            data_items.append(data_item)

    messages = data_items.decode("unicode-escape").split("\n")

    _LOGGER.debug(f"Data cleaned up, Messages: {messages}")

    return messages


def parse_message(message_data):
    result = None

    try:
        if message_data is not None and JSON_START_PATTERN in message_data:
            idx = message_data.index(JSON_START_PATTERN)
            message = message_data[idx:]

            if message is not None:
                result = json.loads(message)

    except Exception as e:
        error_message = (
            f"Failed to read data: {message_data}, "
            f"Error: {e}"
        )

        raise Exception(error_message)

    return result


def get_hashed_password(random, realm, username, password):
    password_str = f"{username}:{realm}:{password}"
    password_bytes = password_str.encode('utf-8')
    password_hash = hashlib.md5(password_bytes).hexdigest().upper()

    random_str = f"{username}:{random}:{password_hash}"
    random_bytes = random_str.encode('utf-8')
    random_hash = hashlib.md5(random_bytes).hexdigest().upper()

    return random_hash
