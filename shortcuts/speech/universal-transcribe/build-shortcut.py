#!/usr/bin/env python3
"""
Build the Universal Transcribe shortcut as a .shortcut (binary plist) file.

This script generates a fully functional iOS Shortcut that:
1. Records audio
2. Sends it to a configurable transcription API endpoint
3. Parses the JSON response
4. Copies the transcript to the clipboard
5. Provides haptic/notification feedback

Usage:
    python3 build-shortcut.py

Output:
    universal-transcribe.shortcut (binary plist file, installable on iOS)
"""

import plistlib
import uuid
import os


def make_uuid():
    return str(uuid.uuid4()).upper()


def text_token(output_uuid, output_name, var_type="Variable"):
    """Create a text token attachment referencing a previous action's output."""
    return {
        "Value": {
            "string": f"\uFFFC",
            "attachmentsByRange": {
                "{0, 1}": {
                    "Type": var_type,
                    "VariableName" if var_type == "Variable" else "OutputUUID": (
                        output_name if var_type == "Variable" else output_uuid
                    ),
                    **({"OutputUUID": output_uuid, "OutputName": output_name} if var_type == "ActionOutput" else {}),
                },
            },
        },
        "WFSerializationType": "WFTextTokenString",
    }


def action_output_ref(output_uuid, output_name):
    """Create a reference to a previous action's output."""
    return {
        "Value": {
            "Type": "ActionOutput",
            "OutputUUID": output_uuid,
            "OutputName": output_name,
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }


def build_shortcut():
    # UUIDs for each action (used to wire outputs to inputs)
    uuid_record = make_uuid()
    uuid_set_audio = make_uuid()
    uuid_endpoint_text = make_uuid()
    uuid_apikey_text = make_uuid()
    uuid_model_text = make_uuid()
    uuid_http_request = make_uuid()
    uuid_get_dict_value = make_uuid()
    uuid_copy_clipboard = make_uuid()
    uuid_if_iphone = make_uuid()
    uuid_otherwise = make_uuid()
    uuid_endif = make_uuid()
    uuid_notification = make_uuid()

    # Variable names
    var_audio = "Recorded Audio"
    var_endpoint = "endpoint_url"
    var_apikey = "api_key"
    var_model = "model"

    actions = [
        # --- Comment: Configuration Section ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== CONFIGURATION ===\nEdit the three Text blocks below to configure your transcription provider.",
            },
        },
        # --- Text: API Endpoint URL ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_endpoint_text,
                "WFTextActionText": "https://api.groq.com/openai/v1/audio/transcriptions",
            },
        },
        # --- Set Variable: endpoint_url ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_endpoint,
                "WFInput": action_output_ref(uuid_endpoint_text, "Text"),
            },
        },
        # --- Text: API Key ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_apikey_text,
                "WFTextActionText": "YOUR_API_KEY_HERE",
            },
        },
        # --- Set Variable: api_key ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_apikey,
                "WFInput": action_output_ref(uuid_apikey_text, "Text"),
            },
        },
        # --- Text: Model ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_model_text,
                "WFTextActionText": "whisper-large-v3",
            },
        },
        # --- Set Variable: model ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_model,
                "WFInput": action_output_ref(uuid_model_text, "Text"),
            },
        },
        # --- Comment: Recording Section ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== RECORD & TRANSCRIBE ===",
            },
        },
        # --- Record Audio ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.recordaudio",
            "WFWorkflowActionParameters": {
                "UUID": uuid_record,
                "WFRecordingStart": "On Tap",
                "WFRecordingCompression": "AAC",
            },
        },
        # --- Set Variable: Recorded Audio ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_audio,
                "WFInput": action_output_ref(uuid_record, "Recorded Audio"),
            },
        },
        # --- Get Contents of URL (HTTP POST) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuid_http_request,
                "WFURL": text_token(uuid_endpoint_text, var_endpoint),
                "WFHTTPMethod": "POST",
                "WFHTTPBodyType": "Form",
                "WFFormValues": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 4,  # File type
                                "WFKey": {
                                    "Value": {"string": "file"},
                                    "WFSerializationType": "WFTextTokenString",
                                },
                                "WFValue": action_output_ref(uuid_record, "Recorded Audio"),
                            },
                            {
                                "WFItemType": 0,  # Text type
                                "WFKey": {
                                    "Value": {"string": "model"},
                                    "WFSerializationType": "WFTextTokenString",
                                },
                                "WFValue": {
                                    "Value": {"string": "whisper-large-v3"},
                                    "WFSerializationType": "WFTextTokenString",
                                },
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
                "WFHTTPHeaders": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": {
                                    "Value": {"string": "Authorization"},
                                    "WFSerializationType": "WFTextTokenString",
                                },
                                "WFValue": text_token(uuid_apikey_text, var_apikey, "Variable"),
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # --- Get Dictionary Value (extract "text" field) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_dict_value,
                "WFInput": action_output_ref(uuid_http_request, "Contents of URL"),
                "WFDictionaryKey": "text",
            },
        },
        # --- Copy to Clipboard ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setclipboard",
            "WFWorkflowActionParameters": {
                "UUID": uuid_copy_clipboard,
                "WFInput": action_output_ref(uuid_get_dict_value, "Dictionary Value"),
            },
        },
        # --- Comment: Feedback Section ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== FEEDBACK ===\nVibrate on iPhone, show notification on iPad.",
            },
        },
        # --- Get Device Details ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getdevicedetails",
            "WFWorkflowActionParameters": {
                "UUID": make_uuid(),
                "WFDeviceDetail": "Device Model",
            },
        },
        # --- If (device is iPhone) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_if_iphone,
                "WFControlFlowMode": 0,  # Start of If
                "WFCondition": 4,  # Contains
                "WFConditionalActionString": "iPhone",
            },
        },
        # --- Vibrate (iPhone) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.vibrate",
            "WFWorkflowActionParameters": {},
        },
        # --- Otherwise ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_if_iphone,
                "WFControlFlowMode": 1,  # Otherwise
            },
        },
        # --- Show Notification (iPad) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
            "WFWorkflowActionParameters": {
                "WFNotificationActionTitle": "Transcript Ready",
                "WFNotificationActionBody": "Your transcription has been copied to the clipboard.",
            },
        },
        # --- End If ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_if_iphone,
                "WFControlFlowMode": 2,  # End If
            },
        },
    ]

    shortcut = {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "1145.16",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4282601983,  # Blue
            "WFWorkflowIconGlyphNumber": 59746,  # Microphone glyph
        },
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowInputContentItemClasses": [
            "WFAppStoreAppContentItem",
            "WFArticleContentItem",
            "WFContactContentItem",
            "WFDateContentItem",
            "WFEmailAddressContentItem",
            "WFGenericFileContentItem",
            "WFImageContentItem",
            "WFiTunesProductContentItem",
            "WFLocationContentItem",
            "WFDCMapsLinkContentItem",
            "WFAVAssetContentItem",
            "WFPDFContentItem",
            "WFPhoneNumberContentItem",
            "WFRichTextContentItem",
            "WFSafariWebPageContentItem",
            "WFStringContentItem",
            "WFURLContentItem",
        ],
        "WFWorkflowActions": actions,
        "WFWorkflowImportQuestions": [
            {
                "ActionIndex": 1,
                "Category": "Parameter",
                "DefaultValue": "https://api.groq.com/openai/v1/audio/transcriptions",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your transcription API endpoint URL:",
            },
            {
                "ActionIndex": 3,
                "Category": "Parameter",
                "DefaultValue": "",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your API key:",
            },
            {
                "ActionIndex": 5,
                "Category": "Parameter",
                "DefaultValue": "whisper-large-v3",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter the model name (e.g. whisper-large-v3):",
            },
        ],
    }

    # Write as binary plist
    output_path = os.path.join(os.path.dirname(__file__), "universal-transcribe.shortcut")
    with open(output_path, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)

    print(f"Built shortcut: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")


if __name__ == "__main__":
    build_shortcut()
