#!/usr/bin/env python3
"""Build the Morning Briefing agent shortcut.

This shortcut:
1. Gets the user's current location
2. POSTs to the agent endpoint with lat/lon
3. Receives the briefing text
4. Speaks it aloud using iOS TTS

The agent does all the heavy lifting server-side — weather, news,
calendar, commute — and returns a ready-to-speak briefing.
"""

import plistlib
import uuid
import os


def make_uuid():
    return str(uuid.uuid4()).upper()


def text_token(output_uuid, output_name, var_type="Variable"):
    return {
        "Value": {
            "string": "\uFFFC",
            "attachmentsByRange": {
                "{0, 1}": {
                    "Type": var_type,
                    **({"VariableName": output_name} if var_type == "Variable" else {}),
                    **({"OutputUUID": output_uuid, "OutputName": output_name} if var_type == "ActionOutput" else {}),
                },
            },
        },
        "WFSerializationType": "WFTextTokenString",
    }


def text_token_multi(parts):
    full_string = ""
    attachments = {}
    pos = 0
    for part in parts:
        if isinstance(part, str):
            full_string += part
            pos += len(part)
        else:
            full_string += "\uFFFC"
            p_uuid, p_name, p_type = part
            attachment = {"Type": p_type}
            if p_type == "Variable":
                attachment["VariableName"] = p_name
            elif p_type == "ActionOutput":
                attachment["OutputUUID"] = p_uuid
                attachment["OutputName"] = p_name
            attachments[f"{{{pos}, 1}}"] = attachment
            pos += 1
    return {
        "Value": {
            "string": full_string,
            "attachmentsByRange": attachments,
        },
        "WFSerializationType": "WFTextTokenString",
    }


def action_output_ref(output_uuid, output_name):
    return {
        "Value": {
            "Type": "ActionOutput",
            "OutputUUID": output_uuid,
            "OutputName": output_name,
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }


def text_value(string):
    return {
        "Value": {"string": string},
        "WFSerializationType": "WFTextTokenString",
    }


def build_shortcut():
    # UUIDs
    uuid_endpoint_text = make_uuid()
    uuid_get_location = make_uuid()
    uuid_get_lat = make_uuid()
    uuid_get_lon = make_uuid()
    uuid_json_body = make_uuid()
    uuid_http_request = make_uuid()
    uuid_get_briefing = make_uuid()
    uuid_speak = make_uuid()

    # Variables
    var_endpoint = "agent_endpoint"
    var_latitude = "latitude"
    var_longitude = "longitude"

    actions = [
        # === CONFIGURATION ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": (
                    "=== MORNING BRIEFING AGENT ===\n"
                    "Calls your agent server, which gathers weather, news,\n"
                    "calendar, and commute data, then returns a spoken briefing.\n\n"
                    "Edit the endpoint URL below to point to your agent."
                ),
            },
        },
        # --- Text: Agent Endpoint URL ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_endpoint_text,
                "WFTextActionText": "http://YOUR_AGENT_HOST:8090/briefing",
            },
        },
        # --- Set Variable: agent_endpoint ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_endpoint,
                "WFInput": action_output_ref(uuid_endpoint_text, "Text"),
            },
        },

        # === GET LOCATION ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== GET LOCATION ===\nGet current GPS coordinates to send to the agent.",
            },
        },
        # --- Get Current Location ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.geolocation.get",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_location,
            },
        },
        # --- Get latitude ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.properties.locations",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_lat,
                "WFInput": action_output_ref(uuid_get_location, "Current Location"),
                "WFContentItemPropertyName": "Latitude",
            },
        },
        # --- Set Variable: latitude ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_latitude,
                "WFInput": action_output_ref(uuid_get_lat, "Latitude"),
            },
        },
        # --- Get longitude ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.properties.locations",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_lon,
                "WFInput": action_output_ref(uuid_get_location, "Current Location"),
                "WFContentItemPropertyName": "Longitude",
            },
        },
        # --- Set Variable: longitude ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_longitude,
                "WFInput": action_output_ref(uuid_get_lon, "Longitude"),
            },
        },

        # === CALL AGENT ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== CALL AGENT ===\nPOST location to the agent and wait for the briefing.",
            },
        },
        # --- Dictionary: Build JSON body ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.dictionary",
            "WFWorkflowActionParameters": {
                "UUID": uuid_json_body,
                "WFItems": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 3,  # Number
                                "WFKey": text_value("latitude"),
                                "WFValue": text_token(None, var_latitude, "Variable"),
                            },
                            {
                                "WFItemType": 3,  # Number
                                "WFKey": text_value("longitude"),
                                "WFValue": text_token(None, var_longitude, "Variable"),
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # --- POST to agent endpoint ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuid_http_request,
                "WFURL": text_token(None, var_endpoint, "Variable"),
                "WFHTTPMethod": "POST",
                "WFHTTPBodyType": "JSON",
                "WFJSONValues": action_output_ref(uuid_json_body, "Dictionary"),
                "WFHTTPHeaders": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": text_value("Content-Type"),
                                "WFValue": text_value("application/json"),
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },

        # === PARSE & SPEAK ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== PARSE & SPEAK ===\nExtract briefing text and read it aloud.",
            },
        },
        # --- Get Dictionary Value: briefing ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_briefing,
                "WFInput": action_output_ref(uuid_http_request, "Contents of URL"),
                "WFDictionaryKey": "briefing",
            },
        },
        # --- Speak Text ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.speaktext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_speak,
                "WFText": action_output_ref(uuid_get_briefing, "Dictionary Value"),
                "WFSpeakTextRate": 0.5,  # Medium speed
            },
        },
        # --- Also copy to clipboard ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setclipboard",
            "WFWorkflowActionParameters": {
                "WFInput": action_output_ref(uuid_get_briefing, "Dictionary Value"),
            },
        },
    ]

    shortcut = {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "1145.16",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4251333119,  # Orange
            "WFWorkflowIconGlyphNumber": 59648,  # Sun glyph
        },
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowInputContentItemClasses": [
            "WFStringContentItem",
        ],
        "WFWorkflowActions": actions,
        "WFWorkflowImportQuestions": [
            {
                "ActionIndex": 1,
                "Category": "Parameter",
                "DefaultValue": "http://YOUR_AGENT_HOST:8090/briefing",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your Morning Briefing agent endpoint URL:",
            },
        ],
    }

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "morning-briefing.shortcut")
    with open(output_path, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)

    print(f"Built shortcut: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")


if __name__ == "__main__":
    build_shortcut()
