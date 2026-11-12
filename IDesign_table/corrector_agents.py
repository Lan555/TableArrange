import autogen
from autogen.agentchat.groupchat import GroupChat
from autogen.agentchat.agent import Agent
from autogen.agentchat.user_proxy_agent import UserProxyAgent
from autogen.agentchat.assistant_agent import AssistantAgent
from copy import deepcopy
from jsonschema import validate
import json
import re

from schemas import layout_corrector_schema, deletion_schema
from agents import is_termination_msg

class JSONSchemaAgent(UserProxyAgent):
    def __init__(self, name : str, is_termination_msg):
        super().__init__(name, is_termination_msg=is_termination_msg)

    def get_human_input(self, prompt: str) -> str:
        message = self.last_message()
        preps_layout = ["on", "in the corner", "in the middle"]
        preps_objs = ['on', 'left of', 'right of', 'in front', 'behind', 'under', 'above']

        pattern = r'```json\s*([^`]+)\s*```' # Match the json object
        match = re.search(pattern, message["content"], re.DOTALL).group(1)

        json_obj_new = json.loads(match)

        is_success  = False
        try:
            validate(instance=json_obj_new, schema=layout_corrector_schema)
            is_success = True
        except Exception as e:
            feedback = str(e.message)
            if e.validator == "enum":
                if str(preps_objs) in e.message:
                    feedback += f"Change the preposition {e.instance} to something suitable with the intended positioning from the list {preps_objs}"
                elif str(preps_layout) in e.message:
                    feedback += f"Change the preposition {e.instance} to something suitable with the intended positioning from the list {preps_layout}"
        if is_success:
            return "SUCCESS"
        return feedback

config_list_gpt4 = autogen.config_list_from_json(
    "OAI_CONFIG_LIST.json",
    filter_dict={
        "model": ["gpt-4.1-mini-2025-04-14"],
    },
)

gpt4_config = {
    "cache_seed": 42,
    "temperature": 0.0,
    "config_list": config_list_gpt4,
    "timeout": 600,
}
gpt4_json_config = deepcopy(gpt4_config)
gpt4_json_config["config_list"][0]["response_format"] = { "type": "json_object" }

def get_corrector_agents():
    user_proxy = autogen.UserProxyAgent(
        name="Admin",
        system_message = "A human admin.",
        is_termination_msg = is_termination_msg,
        human_input_mode = "NEVER",
        code_execution_config=False
    )

    json_schema_debugger = JSONSchemaAgent(
        name = "Json_schema_debugger",
        is_termination_msg = is_termination_msg,
    )

    spatial_corrector_agent = AssistantAgent(
        name="Spatial_corrector_agent",
        llm_config=gpt4_config,
        is_termination_msg=is_termination_msg,
        human_input_mode="NEVER",
        system_message=f"""
        Spatial Corrector Agent. Whenever a user provides an object that doesn't fit the table for various spatial conflicts,
        you are going to make changes to its "placement" and "facing" keys so that these conflicts are removed. 
        You are going to use the JSON Schema to validate the JSON object that the user provides.

        For relative placement with other objects on the table use the prepositions "on", "left of", "right of", "in front", "behind", "under", "above".
        For relative placement with the table layout elements (edges, the middle of the table) use the prepositions "on", "in the corner".

        Use only the following JSON Schema to save the JSON object:
        {layout_corrector_schema}
        """
    )

    object_deletion_agent = AssistantAgent(
        name="Object_deletion_agent",
        llm_config=gpt4_json_config,
        is_termination_msg=is_termination_msg,
        human_input_mode="NEVER",
        system_message=f"""
        Object Deletion Agent. When a user provides a list of objects that doesn't fit the table, select one object to delete that would be less essential for the table.

        An example JSON output:
        {deletion_schema}
        """
    )
    return user_proxy, json_schema_debugger, spatial_corrector_agent, object_deletion_agent