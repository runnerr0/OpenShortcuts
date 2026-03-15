#!/usr/bin/env python3
"""
Build the Voice to Structured Notes shortcut as a .shortcut (binary plist) file.

This script generates a fully functional iOS Shortcut that:
1. Records audio
2. Sends it to a configurable STT API endpoint for transcription
3. Sends the transcript to a configurable LLM endpoint for structuring
4. Creates a structured note in Apple Notes
5. Shows a confirmation notification

Usage:
    python3 build-shortcut.py

Output:
    voice-structured-notes.shortcut (binary plist file, installable on iOS)
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
            "string": "\uFFFC",
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


def multi_text_token(parts):
    """Create a text token string from multiple parts (strings and variable refs).

    Each part is either a plain string or a tuple of (uuid, var_name, var_type)
    for variable references.
    """
    full_string = ""
    attachments = {}
    pos = 0

    for part in parts:
        if isinstance(part, str):
            full_string += part
            pos += len(part)
        else:
            # Variable reference: (uuid, var_name, var_type)
            out_uuid, var_name, var_type = part
            full_string += "\uFFFC"
            attachment = {"Type": var_type}
            if var_type == "Variable":
                attachment["VariableName"] = var_name
            else:
                attachment["OutputUUID"] = out_uuid
                attachment["OutputName"] = var_name
            attachments[f"{{{pos}, 1}}"] = attachment
            pos += 1

    result = {
        "Value": {
            "string": full_string,
            "attachmentsByRange": attachments,
        },
        "WFSerializationType": "WFTextTokenString",
    }
    return result


def build_shortcut():
    # UUIDs for each action (used to wire outputs to inputs)
    uuid_stt_endpoint_text = make_uuid()
    uuid_stt_apikey_text = make_uuid()
    uuid_stt_model_text = make_uuid()
    uuid_llm_endpoint_text = make_uuid()
    uuid_llm_apikey_text = make_uuid()
    uuid_llm_model_text = make_uuid()
    uuid_record = make_uuid()
    uuid_stt_http = make_uuid()
    uuid_stt_get_text = make_uuid()
    uuid_system_prompt = make_uuid()
    uuid_llm_body = make_uuid()
    uuid_llm_http = make_uuid()
    uuid_llm_get_choices = make_uuid()
    uuid_llm_get_first = make_uuid()
    uuid_llm_get_message = make_uuid()
    uuid_llm_get_content = make_uuid()
    uuid_create_note = make_uuid()
    uuid_notification = make_uuid()

    # Variable names
    var_stt_endpoint = "stt_endpoint"
    var_stt_apikey = "stt_api_key"
    var_stt_model = "stt_model"
    var_llm_endpoint = "llm_endpoint"
    var_llm_apikey = "llm_api_key"
    var_llm_model = "llm_model"
    var_audio = "Recorded Audio"
    var_transcript = "transcript"

    system_prompt = (
        "You are a note-taking assistant. You will receive a raw transcript of "
        "spoken audio. Your job is to transform it into a well-structured note.\n\n"
        "Output the note in this exact format:\n\n"
        "# [Generated Title]\n\n"
        "## Summary\n"
        "[2-3 sentence summary of the main topic]\n\n"
        "## Key Points\n"
        "- [Key point 1]\n"
        "- [Key point 2]\n"
        "- [Key point 3]\n"
        "...\n\n"
        "## Action Items\n"
        "- [ ] [Action item 1]\n"
        "- [ ] [Action item 2]\n"
        "...\n\n"
        "If there are no action items, omit the Action Items section entirely.\n"
        "Keep the language natural and concise. Do not add information that was "
        "not in the transcript."
    )

    actions = [
        # ===== STT CONFIGURATION =====
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": (
                    "=== STT CONFIGURATION ===\n"
                    "Configure your speech-to-text provider below."
                ),
            },
        },
        # --- Text: STT Endpoint URL ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_stt_endpoint_text,
                "WFTextActionText": "https://api.groq.com/openai/v1/audio/transcriptions",
            },
        },
        # --- Set Variable: stt_endpoint ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_stt_endpoint,
                "WFInput": action_output_ref(uuid_stt_endpoint_text, "Text"),
            },
        },
        # --- Text: STT API Key ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_stt_apikey_text,
                "WFTextActionText": "YOUR_STT_API_KEY_HERE",
            },
        },
        # --- Set Variable: stt_api_key ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_stt_apikey,
                "WFInput": action_output_ref(uuid_stt_apikey_text, "Text"),
            },
        },
        # --- Text: STT Model ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_stt_model_text,
                "WFTextActionText": "whisper-large-v3",
            },
        },
        # --- Set Variable: stt_model ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_stt_model,
                "WFInput": action_output_ref(uuid_stt_model_text, "Text"),
            },
        },
        # ===== LLM CONFIGURATION =====
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": (
                    "=== LLM CONFIGURATION ===\n"
                    "Configure your LLM provider below."
                ),
            },
        },
        # --- Text: LLM Endpoint URL ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_endpoint_text,
                "WFTextActionText": "https://api.groq.com/openai/v1/chat/completions",
            },
        },
        # --- Set Variable: llm_endpoint ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_llm_endpoint,
                "WFInput": action_output_ref(uuid_llm_endpoint_text, "Text"),
            },
        },
        # --- Text: LLM API Key ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_apikey_text,
                "WFTextActionText": "YOUR_LLM_API_KEY_HERE",
            },
        },
        # --- Set Variable: llm_api_key ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_llm_apikey,
                "WFInput": action_output_ref(uuid_llm_apikey_text, "Text"),
            },
        },
        # --- Text: LLM Model ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_model_text,
                "WFTextActionText": "llama-3.3-70b-versatile",
            },
        },
        # --- Set Variable: llm_model ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_llm_model,
                "WFInput": action_output_ref(uuid_llm_model_text, "Text"),
            },
        },
        # ===== RECORD & TRANSCRIBE =====
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== RECORD & PROCESS ===\nRecord audio, transcribe via STT, structure via LLM, save to Notes.",
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
        # ===== STAGE 1: STT API CALL =====
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== STAGE 1: SPEECH-TO-TEXT ===",
            },
        },
        # --- HTTP POST to STT endpoint ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuid_stt_http,
                "WFURL": text_token(uuid_stt_endpoint_text, var_stt_endpoint),
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
                                "WFValue": text_token(uuid_stt_model_text, var_stt_model),
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
                                "WFValue": multi_text_token([
                                    "Bearer ",
                                    (uuid_stt_apikey_text, var_stt_apikey, "Variable"),
                                ]),
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # --- Get Dictionary Value: extract "text" from STT response ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_stt_get_text,
                "WFInput": action_output_ref(uuid_stt_http, "Contents of URL"),
                "WFDictionaryKey": "text",
            },
        },
        # --- Set Variable: transcript ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_transcript,
                "WFInput": action_output_ref(uuid_stt_get_text, "Dictionary Value"),
            },
        },
        # ===== STAGE 2: LLM API CALL =====
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== STAGE 2: LLM STRUCTURING ===",
            },
        },
        # --- Text: System Prompt ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_system_prompt,
                "WFTextActionText": system_prompt,
            },
        },
        # --- Dictionary: LLM Request Body ---
        # Build the JSON body for the chat completions API
        # We use a Text action to construct the JSON with variable interpolation,
        # then parse it as a dictionary.
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_body,
                "WFTextActionText": multi_text_token([
                    '{"model": "',
                    (uuid_llm_model_text, var_llm_model, "Variable"),
                    '", "messages": [{"role": "system", "content": "',
                    (uuid_system_prompt, "system_prompt", "Variable"),
                    '"}, {"role": "user", "content": "',
                    (uuid_stt_get_text, var_transcript, "Variable"),
                    '"}], "temperature": 0.3}',
                ]),
            },
        },
        # --- HTTP POST to LLM endpoint ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_http,
                "WFURL": text_token(uuid_llm_endpoint_text, var_llm_endpoint),
                "WFHTTPMethod": "POST",
                "WFHTTPBodyType": "JSON",
                "WFJSONValues": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [],
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
                                "WFValue": multi_text_token([
                                    "Bearer ",
                                    (uuid_llm_apikey_text, var_llm_apikey, "Variable"),
                                ]),
                            },
                            {
                                "WFItemType": 0,
                                "WFKey": {
                                    "Value": {"string": "Content-Type"},
                                    "WFSerializationType": "WFTextTokenString",
                                },
                                "WFValue": {
                                    "Value": {"string": "application/json"},
                                    "WFSerializationType": "WFTextTokenString",
                                },
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
                "WFRequestVariable": action_output_ref(uuid_llm_body, "Text"),
            },
        },
        # --- Navigate LLM response: choices[0].message.content ---
        # Get "choices" array
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_get_choices,
                "WFInput": action_output_ref(uuid_llm_http, "Contents of URL"),
                "WFDictionaryKey": "choices",
            },
        },
        # Get first item from choices array
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_get_first,
                "WFInput": action_output_ref(uuid_llm_get_choices, "Dictionary Value"),
                "WFItemIndex": 1,  # 1-indexed in Shortcuts
                "WFItemSpecifier": "First Item",
            },
        },
        # Get "message" from first choice
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_get_message,
                "WFInput": action_output_ref(uuid_llm_get_first, "Item from List"),
                "WFDictionaryKey": "message",
            },
        },
        # Get "content" from message
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_get_content,
                "WFInput": action_output_ref(uuid_llm_get_message, "Dictionary Value"),
                "WFDictionaryKey": "content",
            },
        },
        # ===== SAVE TO APPLE NOTES =====
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== SAVE TO NOTES ===",
            },
        },
        # --- Create Note in Apple Notes ---
        {
            "WFWorkflowActionIdentifier": "com.apple.mobilenotes.SharingExtension",
            "WFWorkflowActionParameters": {
                "UUID": uuid_create_note,
                "WFInput": action_output_ref(uuid_llm_get_content, "Dictionary Value"),
            },
        },
        # ===== NOTIFICATION =====
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== CONFIRMATION ===",
            },
        },
        # --- Show Notification ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
            "WFWorkflowActionParameters": {
                "UUID": uuid_notification,
                "WFNotificationActionTitle": "Note Saved",
                "WFNotificationActionBody": "Your voice note has been structured and saved to Apple Notes.",
            },
        },
    ]

    shortcut = {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "1145.16",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4274264077,  # Orange
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
                "Text": "Enter your STT (speech-to-text) API endpoint URL:",
            },
            {
                "ActionIndex": 3,
                "Category": "Parameter",
                "DefaultValue": "",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your STT API key:",
            },
            {
                "ActionIndex": 5,
                "Category": "Parameter",
                "DefaultValue": "whisper-large-v3",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter the STT model name (e.g. whisper-large-v3):",
            },
            {
                "ActionIndex": 8,
                "Category": "Parameter",
                "DefaultValue": "https://api.groq.com/openai/v1/chat/completions",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your LLM API endpoint URL:",
            },
            {
                "ActionIndex": 10,
                "Category": "Parameter",
                "DefaultValue": "",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your LLM API key:",
            },
            {
                "ActionIndex": 12,
                "Category": "Parameter",
                "DefaultValue": "llama-3.3-70b-versatile",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter the LLM model name (e.g. gpt-4o, llama-3.3-70b-versatile):",
            },
        ],
    }

    # Write as binary plist
    output_path = os.path.join(os.path.dirname(__file__), "voice-structured-notes.shortcut")
    with open(output_path, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)

    print(f"Built shortcut: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")


if __name__ == "__main__":
    build_shortcut()
