import json
import os
from typing import Any, Callable, Optional

import yaml
from dotenv import load_dotenv
from inflection import underscore

from ..constants import DEFAULT_CPLN_API_URL

load_dotenv()


def kwargs_from_env(environment=None):
    """
    Extract CPLN configuration parameters from environment variables.

    This function reads the standard CPLN environment variables and returns
    them as a dictionary suitable for initializing a CPLN client.

    Args:
        environment (dict, optional): Environment variables dictionary.
            Defaults to None, which uses os.environ.

    Returns:
        dict: Dictionary containing configuration parameters:
            - base_url (str): The CPLN API base URL
            - token (str): The authentication token
            - org (str): The organization name

    Raises:
        ValueError: If CPLN_TOKEN or CPLN_ORG environment variables are not set.

    Environment Variables:
        CPLN_TOKEN: Authorization token for the CPLN API
        CPLN_ORG: Organization name in CPLN
    """
    if not environment:
        environment = os.environ

    base_url = DEFAULT_CPLN_API_URL
    token = environment.get("CPLN_TOKEN")
    org = environment.get("CPLN_ORG")

    params = {}
    if base_url:
        params["base_url"] = base_url

    if token:
        params["token"] = token
    else:
        raise ValueError("CPLN_TOKEN is not set")

    if org:
        params["org"] = org
    else:
        raise ValueError("CPLN_ORG is not set")

    return params


def load_template(template_path: str) -> dict[str, Any]:
    """
    Load a template file from the specified path.

    Supports both JSON and YAML formats. Format is detected automatically
    based on file extension (.json, .yaml, .yml).

    Args:
        template_path (str): Path to the template file

    Returns:
        dict[str, Any]: The loaded template data as a dictionary

    Raises:
        FileNotFoundError: If the template file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
        yaml.YAMLError: If the file contains invalid YAML
        ValueError: If the file format is not supported
    """
    file_ext = os.path.splitext(template_path)[1].lower()

    with open(template_path) as file:
        if file_ext == '.json':
            return json.load(file)
        elif file_ext in ['.yaml', '.yml']:
            return yaml.safe_load(file)
        else:
            # Try to detect format by content
            content = file.read()
            file.seek(0)  # Reset file pointer

            # Try JSON first
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try YAML
                try:
                    return yaml.safe_load(content)
                except yaml.YAMLError:
                    raise ValueError(f"Unsupported template format for file: {template_path}")


def load_yaml_template(template_path: str, variables: Optional[dict[str, str]] = None) -> dict[str, Any]:
    """
    Load and process a YAML template file with variable substitution.

    Args:
        template_path (str): Path to the YAML template file
        variables (Optional[dict[str, str]]): Variables for substitution

    Returns:
        dict[str, Any]: The processed template data

    Raises:
        TemplateNotFoundError: If the template file doesn't exist
        TemplateParsingError: If the YAML file is invalid
        TemplateVariableError: If required variables are missing
    """
    from ..templates import TemplateProcessor

    processor = TemplateProcessor(variables=variables)
    return processor.process_file(template_path)


def get_default_workload_template(workload_type: str) -> dict[str, Any]:
    """
    Get the default template for a specific workload type.

    Args:
        workload_type (str): The type of workload template to retrieve.
            Must be either "serverless" or "standard".

    Returns:
        dict[str, Any]: The default workload template data

    Raises:
        ValueError: If the workload_type is not "serverless" or "standard"
        FileNotFoundError: If the template file doesn't exist
        json.JSONDecodeError: If the template file contains invalid JSON
    """
    if workload_type == "serverless":
        template_path = "../templates/default-serverless-workload.json"
    elif workload_type == "standard":
        template_path = "../templates/default-standard-workload.json"
    else:
        raise ValueError(f"Invalid workload type: {workload_type}")
    spec = load_template(os.path.join(os.path.dirname(__file__), template_path))
    return spec


def convert_dictionary_keys(
    data: dict[str, Any],
    format_func: Callable[[str], str] = underscore,
    key_map: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """
    Recursively convert dictionary keys using a formatting function and key mapping.

    This function transforms dictionary keys by applying a formatting function
    (defaulting to underscore) and optionally using a custom key mapping for
    specific keys. It recursively processes nested dictionaries and lists.

    Args:
        data (dict[str, Any]): The dictionary to transform
        format_func (Callable[[str], str], optional): Function to apply to keys.
            Defaults to inflection.underscore.
        key_map (Optional[dict[str, str]], optional): Custom mapping for specific keys.
            Takes precedence over format_func. Defaults to None.

    Returns:
        dict[str, Any]: A new dictionary with transformed keys

    Example:
        >>> data = {"firstName": "John", "lastName": "Doe"}
        >>> convert_dictionary_keys(data)
        {"first_name": "John", "last_name": "Doe"}
    """
    result = {}
    key_map = key_map or {}
    for key, value in data.items():
        new_key = key_map.get(key, format_func(key))
        if isinstance(value, dict):
            result[new_key] = convert_dictionary_keys(value, format_func, key_map)
        elif isinstance(value, list):
            result[new_key] = [
                convert_dictionary_keys(item, format_func, key_map)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[new_key] = value
    return result
