"""Handles direct communication (UDP) with Gree V2 climate devices."""

import base64
import json
import logging
import socket
from typing import Any, Dict, List, Optional, Tuple  # Removed unused Union

# Third-party imports
from Crypto.Cipher import AES

# Removed incorrect AESCipher import

# Home Assistant imports
from homeassistant.components.climate import HVACMode  # Corrected import path

# Simplify CipherType to Any for broader compatibility, or use specific types
# from Crypto.Cipher.AES import AESCipher # Example if using specific type
CipherType = Any

_LOGGER = logging.getLogger(__name__)

# Import constants
from . import const


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

    _is_bound: bool = False

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
        # self._is_bound initialized earlier

        if self._encryption_key:
            self._is_bound = True  # If a key is provided, assume it's bound
            if self._encryption_version == 1:
                # Type checker might complain if AESCipherECB wasn't imported, but Any works
                self._cipher = AES.new(self._encryption_key, AES.MODE_ECB)
                _LOGGER.debug(
                    "Initialized with V1 key, cipher created, marked as bound."
                )
            else:  # V2 or other
                _LOGGER.debug(
                    "Initialized with V2 key, marked as bound (no cipher created on init)."
                )
        else:
            self._is_bound = False  # Explicitly set if no key provided
            _LOGGER.debug("Encryption key not provided yet, marked as not bound.")

    async def _bind_and_get_key_v1(self) -> bool:
        """Retrieve device encryption key (V1/ECB)."""
        _LOGGER.info("Attempting V1 (ECB) binding to retrieve encryption key.")
        GENERIC_GREE_DEVICE_KEY: str = "a3K8Bx%2r8Y7#xDh"  # Specific to V1 binding
        try:
            # Create cipher with generic key
            generic_cipher: CipherType = AES.new(
                GENERIC_GREE_DEVICE_KEY.encode("utf8"), AES.MODE_ECB
            )
            # Prepare bind payload
            bind_payload: str = '{"mac":"' + str(self._mac) + '","t":"bind","uid":0}'
            padded_data: bytes = self._pad(bind_payload).encode("utf8")
            encrypted_pack_bytes: bytes = generic_cipher.encrypt(padded_data)
            pack: str = base64.b64encode(encrypted_pack_bytes).decode("utf-8")
            json_payload_to_send: str = (
                '{"cid": "app","i": 1,"pack": "'
                + pack
                + '","t":"pack","tcid":"'
                + str(self._mac)
                + '","uid": 0}'
            )
            # Fetch result using generic cipher
            result: Dict[str, Any] = await self._fetch_result(
                generic_cipher, json_payload_to_send
            )
            new_key_str: str = result["key"]
            self._encryption_key = new_key_str.encode("utf8")
            # Update the internal cipher instance
            self._cipher = AES.new(self._encryption_key, AES.MODE_ECB)
            self._is_bound = True
            _LOGGER.info("V1 (ECB) binding successful. Key: %s", self._encryption_key)
            return True
        # FIX: Catch more specific exceptions
        except (socket.timeout, socket.error, ConnectionError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            _LOGGER.error("Error during V1 (ECB) binding! Error: %s", e, exc_info=True)
            self._is_bound = False
            return False

    async def _bind_and_get_key_v2(self) -> bool:
        """Retrieve device encryption key (V2/GCM)."""
        _LOGGER.info("Attempting V2 (GCM) binding to retrieve encryption key.")
        # Use the default GCM key from const for binding
        generic_gcm_key: bytes = const.GCM_DEFAULT_KEY.encode("utf8")
        try:
            plaintext: str = (
                '{"cid":"'
                + str(self._mac)
                + '", "mac":"'
                + str(self._mac)
                + '","t":"bind","uid":0}'
            )
            # Encrypt using generic key
            pack, tag = self._encrypt_gcm(generic_gcm_key, plaintext)
            json_payload_to_send: str = (
                '{"cid": "app","i": 1,"pack": "'
                + pack
                + '","t":"pack","tcid":"'
                + str(self._mac)
                + '","uid": 0, "tag" : "'
                + tag
                + '"}'
            )
            # Get GCM cipher using the generic key for fetching the result
            cipher_gcm: CipherType = self._get_gcm_cipher(generic_gcm_key)
            result: Dict[str, Any] = await self._fetch_result(
                cipher_gcm, json_payload_to_send
            )
            new_key_str: str = result["key"]
            self._encryption_key = new_key_str.encode("utf8")
            # No persistent cipher needed for V2, just store the key
            self._is_bound = True
            _LOGGER.info("V2 (GCM) binding successful. Key: %s", self._encryption_key)
            return True
        # FIX: Catch more specific exceptions
        except (socket.timeout, socket.error, ConnectionError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            _LOGGER.error("Error during V2 (GCM) binding! Error: %s", e, exc_info=True)
            self._is_bound = False
            return False

    async def bind_and_get_key(self) -> bool:
        """Binds to the device and retrieves the encryption key based on version."""
        if self._is_bound:
            _LOGGER.debug("API already bound.")
            return True

        _LOGGER.info(
            "Attempting to bind and get encryption key (Version: %s)",
            self._encryption_version,
        )
        key_retrieved: bool = False
        if self._encryption_version == 1:
            key_retrieved = await self._bind_and_get_key_v1()
        elif self._encryption_version == 2:
            key_retrieved = await self._bind_and_get_key_v2()
        else:
            _LOGGER.error(
                "Unsupported encryption version %s for binding.",
                self._encryption_version,
            )
            self._is_bound = False  # Ensure bound is false
            return False

        if not key_retrieved:
            _LOGGER.warning("Failed to bind and retrieve encryption key.")
            self._is_bound = False  # Ensure bound is false
        else:
            _LOGGER.info("Successfully bound and retrieved key.")
            # _is_bound is set within the private methods on success

        return self._is_bound  # Return the final bound state

    # Pad helper method to help us get the right string for encrypting
    def _pad(self, s: str) -> str:
        """Pads the string s to a multiple of the AES block size (16)."""
        aes_block_size: int = 16
        return s + (aes_block_size - len(s) % aes_block_size) * chr(
            aes_block_size - len(s) % aes_block_size
        )

    async def _fetch_result(
        self, cipher: CipherType, json_payload: str
    ) -> Dict[str, Any]:
        """Sends a JSON payload to the device and returns the decrypted response pack."""
        _LOGGER.debug(
            "Fetching from %s:%s with timeout %s",
            self._host,
            self._port,
            self._timeout,
        )
        # Note: Socket/JSON/Decryption errors are handled by caller or specific except blocks below.
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
                _LOGGER.error("ECB Cipher not initialized for V1 encryption!")
                # Attempting to create on the fly below, or raise ValueError if key missing.
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
        cipher: CipherType = AES.new(key, AES.MODE_GCM, nonce=const.GCM_IV)
        # AES.update is part of the cipher object protocol
        cipher.update(const.GCM_ADD)
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
    async def send_command(
        self, opt_keys: List[str], p_values: List[Any]
    ) -> Optional[Dict[str, Any]]:
        """Sends a command packet to the device."""
        if not self._is_bound:
            _LOGGER.error("Cannot send command: API is not bound (key missing).")
            return None

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
            received_json_pack: Dict[str, Any] = await self._fetch_result(
                cipher_for_fetch, sent_json_payload
            )
            _LOGGER.debug("Received response pack: %s", received_json_pack)
            return received_json_pack
        except (socket.timeout, socket.error, ConnectionError) as e: # FIX: Catch specific socket/connection errors
            _LOGGER.error("Socket/Connection error sending command: %s", e)
            return None
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e: # FIX: Catch specific data processing errors
            _LOGGER.error("Error processing response after sending command: %s", e)
            return None
        # FIX: Removed broad Exception catch

    async def get_status(
        self, property_names: List[str]
    ) -> Optional[List[Any]]:  # Changed return type hint
        """Fetches the status of specified properties from the device."""
        if not self._is_bound:
            _LOGGER.error("Cannot get status: API is not bound (key missing).")
            return None

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
            received_json_pack: Dict[str, Any] = (
                await self._fetch_result(  # <<< Added await here
                    cipher_for_fetch, sent_json_payload
                )
            )
            _LOGGER.debug("Received status response pack: %s", received_json_pack)

            # Extract the 'dat' field which should contain the list of status values
            if "dat" in received_json_pack and isinstance(
                received_json_pack["dat"], list
            ):
                status_list: List[Any] = received_json_pack["dat"]
                # Optional: Validate list length against requested property_names length
                if len(status_list) == len(property_names):
                    return status_list
                else:
                    _LOGGER.error(
                        "Status response list length mismatch. Expected %d, got %d: %s",
                        len(property_names),
                        len(status_list),
                        status_list,
                    )
                    return None  # Length mismatch
            elif "dat" not in received_json_pack:
                _LOGGER.error(
                    "'dat' field missing from status response: %s", received_json_pack
                )
                return None
            else:  # 'dat' exists but is not a list
                _LOGGER.error(
                    "'dat' field in status response is not a list: %s",
                    received_json_pack["dat"],
                )
                return None
        except (socket.timeout, socket.error, ConnectionError) as e: # FIX: Catch specific socket/connection errors
            _LOGGER.error("Socket/Connection error getting status: %s", e)
            return None
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e: # FIX: Catch specific data processing errors
            _LOGGER.error("Error processing response after getting status: %s", e)
            return None
        # FIX: Removed broad Exception catch

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
