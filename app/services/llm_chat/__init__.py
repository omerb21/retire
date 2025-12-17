def get_agent_state_json(*args, **kwargs):
    from .state_tools import get_agent_state_json as _get_agent_state_json

    return _get_agent_state_json(*args, **kwargs)


def get_tools_definitions_json(*args, **kwargs):
    from .state_tools import get_tools_definitions_json as _get_tools_definitions_json

    return _get_tools_definitions_json(*args, **kwargs)
