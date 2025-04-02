import base64
import json  # Use standard json
import logging
import socket
from typing import Any, Dict, List, Optional, Tuple, Union

import json  # Use standard json
import logging
import socket
from typing import Any, Dict, List, Optional, Tuple, Union

from Crypto.Cipher import AES

# Simplify CipherType to Any for broader compatibility
CipherType = Any

from homeassistant.components.climate.const import HVACMode

_LOGGER = logging.getLogger(__name__)

# Placeholder constants for GCM (might need to be moved/configured)
GCM_IV: bytes = b"\x54\x40\x78\x44\x49\x67\x5a\x51\x6c\x5e\x63\x13"
GCM_ADD: bytes = b"qualcomm-test"


class GreeDeviceApi:
    """Handles communication with a Gree device."""

    # Class Attributes with types
    _host: str
    _port: int
    _mac: str
    _timeout: int
    _encryption_key: Optional[bytes]
    _encryption_version: int
    _cipher: Optional[CipherType]  # Type hint for the cipher object

    def __init__(
        self,
        host: str,
        port: int,
        mac: str,
        timeout: int,
        encryption_key: Optional[bytes] = None,
        encryption_version: int = 1,
    ) -> None:
        """Initialize the API."""
        _LOGGER.debug(
            "Initializing GreeDeviceApi for host %s (version %s)",
            host,
            encryption_version,
        )
        self._host = host
        self._port = port
        self._mac = mac
        self._timeout = timeout
        self._encryption_key = encryption_key
        self._encryption_version = encryption_version
        self._cipher = None

        if self._encryption_key and self._encryption_version == 1:
            # Type checker might complain if AESCipherECB wasn't imported, but Any works
            self._cipher = AES.new(self._encryption_key, AES.MODE_ECB)
        elif not self._encryption_key:
            _LOGGER.debug("Encryption key not provided yet.")
        elif self._encryption_version != 1:
            _LOGGER.debug(
                "Encryption version %s uses different cipher setup.",
                self._encryption_version,
            )

    # Pad helper method to help us get the right string for encrypting
    def _pad(self, s: str) -> str:
        """Pads the string s to a multiple of the AES block size (16)."""
        aes_block_size: int = 16
        return s + (aes_block_size - len(s) % aes_block_size) * chr(
            aes_block_size - len(s) % aes_block_size
        )

    def _fetch_result(self, cipher: CipherType, json_payload: str) -> Dict[str, Any]:
        """Sends a JSON payload to the device and returns the decrypted response pack."""
        _LOGGER.debug(
            "Fetching from %s:%s with timeout %s",
            self._host,
            self._port,
            self._timeout,
        )
        # TODO: Handle socket errors, timeouts, JSON decoding errors, decryption errors gracefully
        client_sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_sock.settimeout(self._timeout)
        data: bytes = b""
        try:
            client_sock.sendto(bytes(json_payload, "utf-8"), (self._host, self._port))
            data, _ = client_sock.recvfrom(64000)
        finally:
            client_sock.close()

        received_json: Dict[str, Any] = json.loads(data)
        pack: str = received_json["pack"]
        base64decoded_pack: bytes = base64.b64decode(pack)

        # Decryption logic
        decrypted_pack: bytes = b""
        if self._encryption_version == 1:
            # Use the stored ECB cipher
            if not self._cipher:
                # This assumes the key/cipher was set via GetDeviceKey previously
                # TODO: Add more robust error handling if cipher is missing
                _LOGGER.error("ECB Cipher not initialized for V1 encryption!")
                # raise SomeAppropriateError("Cipher not ready")
                # For now, try creating it on the fly if key exists
                if self._encryption_key:
                    _LOGGER.warning("Attempting to create ECB cipher on the fly.")
                    self._cipher = AES.new(self._encryption_key, AES.MODE_ECB)
                else:
                    # Cannot proceed without key/cipher
                    raise ValueError("Cannot decrypt V1 data: key/cipher missing.")
            # Assuming self._cipher is EcbMode or compatible
            decrypted_pack = self._cipher.decrypt(base64decoded_pack)
        elif self._encryption_version == 2:
            # Need the GCM cipher passed in (which is the 'cipher' argument).
            # This cipher was created using the appropriate key (generic key for binding,
            # or the device key for subsequent commands/status).
            # Do NOT check self._encryption_key here, as it might be None during binding.
            # For now, assume the passed 'cipher' arg IS the correct GCM cipher for decrypt
            tag_b64: str = received_json["tag"]
            tag: bytes = base64.b64decode(tag_b64)
            # Explicitly try the decryption/verification step
            try:
                _LOGGER.debug("Attempting GCM decrypt_and_verify...")
                # Assuming cipher is GcmMode or compatible
                decrypted_pack = cipher.decrypt_and_verify(base64decoded_pack, tag)
                _LOGGER.debug("GCM decrypt_and_verify successful.")
            except ValueError as e:
                _LOGGER.error(
                    "GCM decryption/verification failed: %s", e, exc_info=True
                )
                # Re-raise the error to be caught by the caller (_fetch_result's caller)
                raise  # Re-raise the ValueError
        else:
            raise ValueError(
                f"Unsupported encryption version: {self._encryption_version}"
            )

        # Decode and remove padding/trailing characters
        decoded_pack: str = decrypted_pack.decode("utf-8")
        # This stripping logic might be fragile, needs review
        # Find the last '}' and strip everything after it
        last_brace_index: int = decoded_pack.rfind("}")
        if last_brace_index != -1:
            replaced_pack: str = decoded_pack[: last_brace_index + 1]
        else:
            # Handle case where '}' is not found, though unlikely for valid JSON
            replaced_pack = decoded_pack

        # Remove potential padding characters like \x0f more robustly if needed
        # replaced_pack = replaced_pack.rstrip('\x0f') # Example if needed

        loaded_json_pack: Dict[str, Any] = json.loads(replaced_pack)
        return loaded_json_pack

    def _get_gcm_cipher(
        self, key: bytes
    ) -> CipherType:  # Return type depends on fallback
        """Creates a GCM cipher instance with the specified key."""
        cipher: CipherType = AES.new(key, AES.MODE_GCM, nonce=GCM_IV)
        # AES.update is part of the cipher object protocol
        cipher.update(GCM_ADD)
        return cipher

    def _encrypt_gcm(self, key: bytes, plaintext: str) -> Tuple[str, str]:
        """Encrypts plaintext using GCM and returns base64 encoded pack and tag."""
        cipher: CipherType = self._get_gcm_cipher(key)
        # AES.encrypt_and_digest is part of the cipher object protocol
        encrypted_data, tag = cipher.encrypt_and_digest(plaintext.encode("utf8"))
        pack_b64: str = base64.b64encode(encrypted_data).decode("utf-8")
        tag_b64: str = base64.b64encode(tag).decode("utf-8")
        return (pack_b64, tag_b64)

    # Add methods for binding, sending commands, receiving status, etc.
    def send_command(
        self, opt_keys: List[str], p_values: List[Any]
    ) -> Optional[Dict[str, Any]]:
        """Sends a command packet to the device."""
        _LOGGER.debug("Preparing to send command with opt=%s, p=%s", opt_keys, p_values)

        # Build the command payload dictionary
        if len(opt_keys) != len(p_values):
            _LOGGER.error(
                "send_command error: opt_keys length (%s) != p_values length (%s)",
                len(opt_keys),
                len(p_values),
            )
            return None  # Or raise ValueError

        # Convert p_values - Note: Gree protocol might expect ints for bools, strings for enums etc.
        # This conversion might need refinement based on actual device behavior.
        converted_p_values: List[Any] = []
        for val in p_values:
            if isinstance(val, bool):
                converted_p_values.append(int(val))
            elif isinstance(val, HVACMode):  # Handle HVACMode enum specifically
                converted_p_values.append(
                    val.value
                )  # Assuming .value gives the right representation
            elif val is None:
                # How should None be represented? Assuming 0 for now.
                _LOGGER.warning(
                    "Encountered None value in command params, representing as 0."
                )
                converted_p_values.append(0)
            elif isinstance(val, (str, int, float)):
                converted_p_values.append(val)
            else:
                _LOGGER.error(
                    "Unsupported type in p_values for send_command: %s (%s)",
                    val,
                    type(val),
                )
                # Decide handling - maybe default to 0 or raise error?
                converted_p_values.append(0)  # Defaulting to 0 for now

        command_payload: Dict[str, Any] = {
            "opt": opt_keys,
            "p": converted_p_values,
            "t": "cmd",
        }

        # Construct the inner JSON command payload string using json
        try:
            state_pack_json: str = json.dumps(command_payload, separators=(",", ":"))
        except TypeError as e:
            _LOGGER.error("Error serializing command payload to JSON: %s", e)
            return None

        _LOGGER.debug("Constructed state_pack_json: %s", state_pack_json)

        sent_json_payload: Optional[str] = None
        cipher_for_fetch: Optional[CipherType] = None  # Cipher needed for _fetch_result

        if self._encryption_version == 1:
            if not self._cipher:
                _LOGGER.error("Cannot send V1 command: ECB cipher not initialized.")
                # Potentially try to bind/get key first? Or just fail.
                return None  # Or raise exception
            cipher_for_fetch = self._cipher  # Use the instance's ECB cipher

            padded_state: bytes = self._pad(state_pack_json).encode("utf8")
            encrypted_pack_bytes: bytes = cipher_for_fetch.encrypt(padded_state)
            encrypted_pack: str = base64.b64encode(encrypted_pack_bytes).decode("utf-8")

            sent_json_payload = (
                f'{{"cid":"app","i":0,"pack":"{encrypted_pack}",'
                f'"t":"pack","tcid":"{self._mac}",'
                f'"uid":0}}'  # Assuming uid 0 for commands, confirm if needed
            )

        elif self._encryption_version == 2:
            if not self._encryption_key:
                _LOGGER.error("Cannot send V2 command: Encryption key missing.")
                # Potentially try to bind/get key first? Or just fail.
                return None  # Or raise exception

            # Encrypt using the instance's key
            pack, tag = self._encrypt_gcm(self._encryption_key, state_pack_json)

            # Get the GCM cipher instance required for decrypting the response in _fetch_result
            cipher_for_fetch = self._get_gcm_cipher(self._encryption_key)

            sent_json_payload = (
                f'{{"cid":"app","i":0,"pack":"{pack}",'
                f'"t":"pack","tcid":"{self._mac}",'
                f'"uid":0,"tag":"{tag}"}}'  # Assuming uid 0 for commands, confirm if needed
            )
        else:
            _LOGGER.error(
                "Unsupported encryption version: %s. Cannot send command.",
                self._encryption_version,
            )
            return None  # Or raise an exception

        if sent_json_payload is None or cipher_for_fetch is None:
            _LOGGER.error("Failed to prepare command payload or cipher.")
            return None  # Should have been caught earlier, but safety check

        try:
            # Call the internal fetch method
            _LOGGER.debug("Sending payload: %s", sent_json_payload)
            received_json_pack: Dict[str, Any] = self._fetch_result(
                cipher_for_fetch, sent_json_payload
            )
            _LOGGER.debug("Received response pack: %s", received_json_pack)
            return received_json_pack
        except (socket.timeout, socket.error) as e:
            _LOGGER.error("Socket error sending command: %s", e)
            return None
        except (json.JSONDecodeError, ValueError) as e:
            _LOGGER.error("Error processing response after sending command: %s", e)
            return None
        except Exception as e:  # Catch any other unexpected errors
            _LOGGER.error("Unexpected error sending command: %s", e, exc_info=True)
            return None

    def get_status(self, property_names: List[str]) -> Optional[Dict[str, Any]]:
        """Fetches the status of specified properties from the device."""
        _LOGGER.debug("Preparing to get status for properties: %s", property_names)

        # Construct the inner JSON status request payload
        try:
            cols_json: str = json.dumps(property_names)
        except TypeError as e:
            _LOGGER.error("Error serializing property names to JSON: %s", e)
            return None

        plaintext_payload: str = (
            f'{{"cols":{cols_json},"mac":"{self._mac}","t":"status"}}'
        )

        sent_json_payload: Optional[str] = None
        cipher_for_fetch: Optional[CipherType] = None  # Cipher needed for _fetch_result

        if self._encryption_version == 1:
            if not self._cipher:
                _LOGGER.error("Cannot get V1 status: ECB cipher not initialized.")
                return None  # Or raise exception
            cipher_for_fetch = self._cipher

            padded_state: bytes = self._pad(plaintext_payload).encode("utf8")
            encrypted_pack_bytes: bytes = cipher_for_fetch.encrypt(padded_state)
            encrypted_pack: str = base64.b64encode(encrypted_pack_bytes).decode("utf-8")

            sent_json_payload = (
                f'{{"cid":"app","i":0,"pack":"{encrypted_pack}",'
                f'"t":"pack","tcid":"{self._mac}",'
                f'"uid":0}}'  # Assuming uid 0 for status, confirm if needed
            )

        elif self._encryption_version == 2:
            if not self._encryption_key:
                _LOGGER.error("Cannot get V2 status: Encryption key missing.")
                return None  # Or raise exception

            # Encrypt using the instance's key
            pack, tag = self._encrypt_gcm(self._encryption_key, plaintext_payload)

            # Get the GCM cipher instance required for decrypting the response
            cipher_for_fetch = self._get_gcm_cipher(self._encryption_key)

            sent_json_payload = (
                f'{{"cid":"app","i":0,"pack":"{pack}",'
                f'"t":"pack","tcid":"{self._mac}",'
                f'"uid":0,"tag":"{tag}"}}'  # Assuming uid 0 for status, confirm if needed
            )
        else:
            _LOGGER.error(
                "Unsupported encryption version: %s. Cannot get status.",
                self._encryption_version,
            )
            return None  # Or raise an exception

        if sent_json_payload is None or cipher_for_fetch is None:
            _LOGGER.error("Failed to prepare status request payload or cipher.")
            return None  # Should have been caught earlier, but safety check

        try:
            # Call the internal fetch method
            _LOGGER.debug("Sending status request payload: %s", sent_json_payload)
            received_json_pack: Dict[str, Any] = self._fetch_result(
                cipher_for_fetch, sent_json_payload
            )
            _LOGGER.debug("Received status response pack: %s", received_json_pack)

            # Extract the 'dat' field which contains the status values
            if "dat" in received_json_pack:
                # Assuming 'dat' contains a list or dict, adjust type if needed
                return received_json_pack["dat"]
            else:
                _LOGGER.error(
                    "'dat' field missing from status response: %s", received_json_pack
                )
                return None
        except (socket.timeout, socket.error) as e:
            _LOGGER.error("Socket error getting status: %s", e)
            return None
        except (json.JSONDecodeError, ValueError) as e:
            _LOGGER.error("Error processing response after getting status: %s", e)
            return None
        except Exception as e:  # Catch any other unexpected errors
            _LOGGER.error("Unexpected error getting status: %s", e, exc_info=True)
            return None

    # Method definition should be at class level indentation
    def update_encryption_key(self, new_key: bytes) -> None:
        """
        Update the internal encryption key and reset the cipher if necessary.

        This is primarily used after a successful V2 (GCM) key binding
        to ensure subsequent API calls use the correct device key.
        It also handles resetting the V1 (ECB) cipher if the key changes.
        """
        _LOGGER.debug("Updating internal API encryption key.")
        self._encryption_key = new_key

        # If using V1 (ECB), the cipher instance depends on the key, so recreate it.
        if self._encryption_version == 1:
            self._cipher = AES.new(self._encryption_key, AES.MODE_ECB)
        # For V2 (GCM) or other versions, we don't store a persistent cipher instance
        # based on the device key in self._cipher. Ensure it's None if set previously.
        elif self._cipher is not None:
            # Only reset if it was somehow set (e.g., during V1 init then version changed)
            self._cipher = None
