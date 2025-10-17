import json

from websocket import WebSocketApp

from ..errors import (
    WebSocketConnectionError,
    WebSocketExitCodeError,
    WebSocketOperationError,
)
from .exit_codes import AwsExitCode, GenericExitCode, PostgresExitCode


class WebSocketAPI:
    """
    WebSocket API client for executing commands in Control Plane workload containers.

    This class provides a WebSocket-based interface to execute commands within
    running workload containers through the Control Plane API.

    Attributes:
        remote_wss (str): The WebSocket URL for the remote container
        verbose (bool): Whether to enable verbose logging
    """

    def __init__(self, remote_wss: str, verbose: bool = False):
        """
        Initialize the WebSocket API client.

        Args:
            remote_wss (str): The WebSocket URL for the remote container
            verbose (bool, optional): Enable verbose logging. Defaults to False.
        """
        self.remote_wss = remote_wss
        self._request = None
        self._error = None
        self.verbose = verbose

    def exec(self, **kwargs):
        """
        Execute a command in the remote container via WebSocket.

        Args:
            **kwargs: Command execution parameters including:
                - token: Authentication token
                - org: Organization name
                - gvc: Global Virtual Cluster name
                - container: Container name
                - pod: Pod name
                - command: Command to execute

        Returns:
            dict: The original request parameters

        Raises:
            WebSocketConnectionError: If connection fails
            WebSocketExitCodeError: If command exits with non-zero code
            WebSocketOperationError: If operation fails
        """
        self._request = kwargs
        self._error = None
        ws = self.websocket()
        ws.run_forever()

        if self._error:
            raise self._error

        return self._request

    def websocket(self):
        """
        Create and configure a WebSocket connection.

        Returns:
            WebSocketApp: Configured WebSocket application instance
        """
        ws = WebSocketApp(
            self.remote_wss,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )
        return ws

    def _on_message(self, ws: WebSocketApp, message: str):
        try:
            decoded_message = message.decode()
            exit_code = 0

            # Check for non-zero exit code
            if "exit code" in decoded_message.lower():
                try:
                    exit_code = decoded_message.split("exit code")[-1].strip()
                    exit_code = int(exit_code)
                except ValueError:
                    pass

            if exit_code != 0:
                command = self._request.get("command", [])
                if isinstance(command, list):
                    command = command[0] if command else ""

                if command == "aws":
                    if AwsExitCode.is_error(exit_code):
                        error_type = AwsExitCode.get_error_type(exit_code)
                        error_message = AwsExitCode.get_message(exit_code)
                elif command in ["pg_dump", "pg_restore"]:
                    if PostgresExitCode.is_error(exit_code):
                        error_type = PostgresExitCode.get_error_type(exit_code)
                        error_message = PostgresExitCode.get_message(exit_code, command)
                else:
                    if GenericExitCode.is_error(exit_code):
                        error_type = GenericExitCode.get_error_type(exit_code)
                        error_message = GenericExitCode.get_message(exit_code)

                self._error = WebSocketExitCodeError(
                    f"{error_type if error_type else 'Error'} (exit code {exit_code}): {error_message}\n"
                    f"Full message: {decoded_message}",
                    exit_code=exit_code
                )

                return exit_code

            # Check for error messages
            if "error" in decoded_message.lower():
                self._error = WebSocketOperationError(
                    f"Error in message: {decoded_message}"
                )
                return

            # Check for failure messages
            if "failed" in decoded_message.lower():
                self._error = WebSocketOperationError(
                    f"Operation failed: {decoded_message}"
                )
                return

            print(decoded_message)
            return exit_code

        except Exception as e:
            ws.sock.close()
            self._error = WebSocketOperationError(f"Error processing message: {str(e)}")

    def _on_error(self, ws: WebSocketApp, error: str):
        # Check if this is a normal close frame (opcode 8 with code 1000)
        # These appear as errors but are actually normal closures
        error_str = str(error)
        if "opcode=8" in error_str and "\\x03\\xe8" in error_str:
            # This is a normal close (1000), not an error
            return
        self._error = WebSocketConnectionError(f"WebSocket error: {error}")

    def _on_close(self, ws: WebSocketApp, close_status_code: int, close_msg: str):
        if not (
            close_status_code == 1000 or close_status_code is None
        ):  # 1000 is normal closure
            self._error = WebSocketConnectionError(
                f"Connection closed unexpectedly with code {close_status_code}: {close_msg}"
            )
        if self.verbose:
            print(f"Connection closed, exit code: {close_status_code}")

    def _on_open(self, ws: WebSocketApp):
        if self.verbose:
            print("Connection opened")
        try:
            ws.send(json.dumps(self._request, indent=4))
        except Exception as e:
            self._error = WebSocketConnectionError(
                f"Error sending initial request: {str(e)}"
            )
            ws.sock.close()
