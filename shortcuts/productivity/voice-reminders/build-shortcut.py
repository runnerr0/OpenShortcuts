#!/usr/bin/env python3
"""
Build the Voice to Reminders shortcut as a .shortcut (binary plist) file.

This script generates a fully functional iOS Shortcut that:
1. Records audio
2. Sends it to a configurable STT API endpoint for transcription
3. Sends the transcript to an LLM to parse natural language into structured tasks
4. Iterates over the parsed tasks and creates iOS Reminders for each one
5. Shows a notification with the count of created reminders

Usage:
    python3 build-shortcut.py

Output:
    voice-reminders.shortcut (binary plist file, installable on iOS)
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


def variable_ref(var_name):
    """Create a reference to a named variable."""
    return {
        "Value": {
            "Type": "Variable",
            "VariableName": var_name,
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }


def text_token_multi(parts):
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
            # It's a variable reference tuple: (uuid, var_name, var_type)
            full_string += "\uFFFC"
            ref_uuid, ref_name, ref_type = part
            attachment = {"Type": ref_type}
            if ref_type == "Variable":
                attachment["VariableName"] = ref_name
            else:
                attachment["OutputUUID"] = ref_uuid
                attachment["OutputName"] = ref_name
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
    uuid_record = make_uuid()
    uuid_stt_endpoint_text = make_uuid()
    uuid_stt_apikey_text = make_uuid()
    uuid_llm_endpoint_text = make_uuid()
    uuid_llm_apikey_text = make_uuid()
    uuid_llm_model_text = make_uuid()
    uuid_stt_http = make_uuid()
    uuid_stt_get_text = make_uuid()
    uuid_llm_prompt = make_uuid()
    uuid_llm_http = make_uuid()
    uuid_llm_get_choices = make_uuid()
    uuid_llm_get_first = make_uuid()
    uuid_llm_get_message = make_uuid()
    uuid_llm_get_content = make_uuid()
    uuid_parse_json = make_uuid()
    uuid_get_tasks = make_uuid()
    uuid_repeat = make_uuid()
    uuid_repeat_item = make_uuid()
    uuid_get_title = make_uuid()
    uuid_get_due_date = make_uuid()
    uuid_get_due_time = make_uuid()
    uuid_get_priority = make_uuid()
    uuid_get_list = make_uuid()
    uuid_add_reminder = make_uuid()
    uuid_end_repeat = make_uuid()
    uuid_count = make_uuid()
    uuid_notification = make_uuid()
    uuid_current_date = make_uuid()
    uuid_format_date = make_uuid()

    # Variable names
    var_stt_endpoint = "stt_endpoint_url"
    var_stt_apikey = "stt_api_key"
    var_llm_endpoint = "llm_endpoint_url"
    var_llm_apikey = "llm_api_key"
    var_llm_model = "llm_model"
    var_transcript = "transcript"
    var_tasks = "tasks"
    var_task_count = "task_count"
    var_today = "today_date"

    actions = [
        # =====================================================================
        # CONFIGURATION SECTION
        # =====================================================================
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": (
                    "=== CONFIGURATION ===\n"
                    "The five Text blocks below are configured during import.\n"
                    "STT = Speech-to-Text provider, LLM = Language Model provider."
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
        # --- Set Variable: stt_endpoint_url ---
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
        # --- Text: LLM Endpoint URL ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_endpoint_text,
                "WFTextActionText": "https://api.groq.com/openai/v1/chat/completions",
            },
        },
        # --- Set Variable: llm_endpoint_url ---
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

        # =====================================================================
        # GET CURRENT DATE (for relative date resolution in LLM prompt)
        # =====================================================================
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== GET TODAY'S DATE ===\nUsed in the LLM prompt so it can resolve relative dates like 'tomorrow'.",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.date",
            "WFWorkflowActionParameters": {
                "UUID": uuid_current_date,
                "WFDateActionMode": "Current Date",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.format.date",
            "WFWorkflowActionParameters": {
                "UUID": uuid_format_date,
                "WFDateFormatStyle": "Custom",
                "WFDateFormat": "yyyy-MM-dd, EEEE",
                "WFDate": action_output_ref(uuid_current_date, "Date"),
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_today,
                "WFInput": action_output_ref(uuid_format_date, "Formatted Date"),
            },
        },

        # =====================================================================
        # RECORD AUDIO
        # =====================================================================
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== RECORD AUDIO ===",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.recordaudio",
            "WFWorkflowActionParameters": {
                "UUID": uuid_record,
                "WFRecordingStart": "On Tap",
                "WFRecordingCompression": "AAC",
            },
        },

        # =====================================================================
        # STAGE 1: SPEECH-TO-TEXT
        # =====================================================================
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== STAGE 1: SPEECH-TO-TEXT ===\nSend recorded audio to the STT API for transcription.",
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
                                "WFValue": text_token(uuid_stt_apikey_text, var_stt_apikey, "Variable"),
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # --- Get Dictionary Value: extract "text" field from STT response ---
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

        # =====================================================================
        # STAGE 2: LLM TASK EXTRACTION
        # =====================================================================
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": (
                    "=== STAGE 2: LLM TASK EXTRACTION ===\n"
                    "Send the transcript to an LLM to parse into structured task JSON."
                ),
            },
        },
        # --- HTTP POST to LLM endpoint (JSON body for chat completions) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_http,
                "WFURL": text_token(uuid_llm_endpoint_text, var_llm_endpoint),
                "WFHTTPMethod": "POST",
                "WFHTTPBodyType": "JSON",
                "WFJSONValues": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,  # Text
                                "WFKey": {
                                    "Value": {"string": "model"},
                                    "WFSerializationType": "WFTextTokenString",
                                },
                                "WFValue": text_token(uuid_llm_model_text, var_llm_model),
                            },
                            {
                                "WFItemType": 2,  # Array
                                "WFKey": {
                                    "Value": {"string": "messages"},
                                    "WFSerializationType": "WFTextTokenString",
                                },
                                "WFValue": {
                                    "Value": [
                                        {
                                            "WFItemType": 1,  # Dictionary
                                            "WFValue": {
                                                "Value": {
                                                    "WFDictionaryFieldValueItems": [
                                                        {
                                                            "WFItemType": 0,
                                                            "WFKey": {
                                                                "Value": {"string": "role"},
                                                                "WFSerializationType": "WFTextTokenString",
                                                            },
                                                            "WFValue": {
                                                                "Value": {"string": "system"},
                                                                "WFSerializationType": "WFTextTokenString",
                                                            },
                                                        },
                                                        {
                                                            "WFItemType": 0,
                                                            "WFKey": {
                                                                "Value": {"string": "content"},
                                                                "WFSerializationType": "WFTextTokenString",
                                                            },
                                                            "WFValue": text_token_multi([
                                                                "You are a task extraction assistant. The user will give you a transcript of spoken text. "
                                                                "Extract all tasks or reminders mentioned and return them as a JSON object.\n\n"
                                                                "Today's date is: ",
                                                                (uuid_format_date, var_today, "Variable"),
                                                                "\n\n"
                                                                "Return ONLY valid JSON with this exact schema:\n"
                                                                '{"tasks": [{"title": "string", "due_date": "YYYY-MM-DD or null", '
                                                                '"due_time": "HH:MM or null", "priority": "high|medium|low|none", '
                                                                '"list": "string"}]}\n\n'
                                                                "Rules:\n"
                                                                "- Extract EVERY distinct task from the transcript\n"
                                                                "- Use concise, actionable titles\n"
                                                                "- Resolve relative dates based on today's date\n"
                                                                '- "morning" = 09:00, "afternoon" = 14:00, "evening" = 18:00, "end of day" = 17:00\n'
                                                                '- Words like "urgent", "ASAP", "important" = priority "high"\n'
                                                                '- Words like "sometime", "whenever" = priority "low"\n'
                                                                "- Default priority is \"none\", default list is \"Reminders\"\n"
                                                                "- If a specific list is mentioned, use that list name\n"
                                                                "- Return ONLY the JSON object, no markdown, no explanation",
                                                            ]),
                                                        },
                                                    ],
                                                },
                                                "WFSerializationType": "WFDictionaryFieldValue",
                                            },
                                        },
                                        {
                                            "WFItemType": 1,  # Dictionary
                                            "WFValue": {
                                                "Value": {
                                                    "WFDictionaryFieldValueItems": [
                                                        {
                                                            "WFItemType": 0,
                                                            "WFKey": {
                                                                "Value": {"string": "role"},
                                                                "WFSerializationType": "WFTextTokenString",
                                                            },
                                                            "WFValue": {
                                                                "Value": {"string": "user"},
                                                                "WFSerializationType": "WFTextTokenString",
                                                            },
                                                        },
                                                        {
                                                            "WFItemType": 0,
                                                            "WFKey": {
                                                                "Value": {"string": "content"},
                                                                "WFSerializationType": "WFTextTokenString",
                                                            },
                                                            "WFValue": text_token(uuid_stt_get_text, var_transcript, "Variable"),
                                                        },
                                                    ],
                                                },
                                                "WFSerializationType": "WFDictionaryFieldValue",
                                            },
                                        },
                                    ],
                                    "WFSerializationType": "WFArrayParameterState",
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
                                "WFValue": text_token(uuid_llm_apikey_text, var_llm_apikey, "Variable"),
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
            },
        },

        # --- Extract LLM response: choices[0].message.content ---
        # Get "choices" array
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_get_choices,
                "WFInput": action_output_ref(uuid_llm_http, "Contents of URL"),
                "WFDictionaryKey": "choices",
            },
        },
        # Get first item from choices
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_get_first,
                "WFInput": action_output_ref(uuid_llm_get_choices, "Dictionary Value"),
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
        # Parse the JSON string content into a dictionary
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.detect.dictionary",
            "WFWorkflowActionParameters": {
                "UUID": uuid_parse_json,
                "WFInput": action_output_ref(uuid_llm_get_content, "Dictionary Value"),
            },
        },
        # Get "tasks" array from parsed JSON
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_tasks,
                "WFInput": action_output_ref(uuid_parse_json, "Dictionary"),
                "WFDictionaryKey": "tasks",
            },
        },
        # --- Save tasks for counting later ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_tasks,
                "WFInput": action_output_ref(uuid_get_tasks, "Dictionary Value"),
            },
        },

        # =====================================================================
        # STAGE 3: CREATE REMINDERS
        # =====================================================================
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": (
                    "=== STAGE 3: CREATE REMINDERS ===\n"
                    "Loop over each task and create an iOS Reminder."
                ),
            },
        },
        # --- Repeat with Each (over tasks array) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.repeat.each",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_repeat,
                "WFControlFlowMode": 0,  # Start
                "WFInput": action_output_ref(uuid_get_tasks, "Dictionary Value"),
            },
        },
        # --- Get title from current task ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_title,
                "WFInput": {
                    "Value": {
                        "Type": "Variable",
                        "VariableName": "Repeat Item",
                    },
                    "WFSerializationType": "WFTextTokenAttachment",
                },
                "WFDictionaryKey": "title",
            },
        },
        # --- Get due_date from current task ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_due_date,
                "WFInput": {
                    "Value": {
                        "Type": "Variable",
                        "VariableName": "Repeat Item",
                    },
                    "WFSerializationType": "WFTextTokenAttachment",
                },
                "WFDictionaryKey": "due_date",
            },
        },
        # --- Get due_time from current task ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_due_time,
                "WFInput": {
                    "Value": {
                        "Type": "Variable",
                        "VariableName": "Repeat Item",
                    },
                    "WFSerializationType": "WFTextTokenAttachment",
                },
                "WFDictionaryKey": "due_time",
            },
        },
        # --- Get priority from current task ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_priority,
                "WFInput": {
                    "Value": {
                        "Type": "Variable",
                        "VariableName": "Repeat Item",
                    },
                    "WFSerializationType": "WFTextTokenAttachment",
                },
                "WFDictionaryKey": "priority",
            },
        },
        # --- Get list from current task ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_list,
                "WFInput": {
                    "Value": {
                        "Type": "Variable",
                        "VariableName": "Repeat Item",
                    },
                    "WFSerializationType": "WFTextTokenAttachment",
                },
                "WFDictionaryKey": "list",
            },
        },
        # --- Add New Reminder ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.addnewreminder",
            "WFWorkflowActionParameters": {
                "UUID": uuid_add_reminder,
                "WFCalendarItemTitle": text_token(uuid_get_title, "Repeat Item", "Variable"),
                "WFCalendarItemNotes": "",
            },
        },
        # --- End Repeat ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.repeat.each",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_repeat,
                "WFControlFlowMode": 2,  # End
            },
        },

        # =====================================================================
        # NOTIFICATION
        # =====================================================================
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== NOTIFICATION ===\nShow how many reminders were created.",
            },
        },
        # --- Count items in tasks array ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.count",
            "WFWorkflowActionParameters": {
                "UUID": uuid_count,
                "Input": variable_ref(var_tasks),
                "WFCountType": "Items",
            },
        },
        # --- Save count ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_task_count,
                "WFInput": action_output_ref(uuid_count, "Count"),
            },
        },
        # --- Show Notification ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
            "WFWorkflowActionParameters": {
                "UUID": uuid_notification,
                "WFNotificationActionTitle": "Voice to Reminders",
                "WFNotificationActionBody": text_token(uuid_count, var_task_count, "Variable"),
            },
        },
    ]

    shortcut = {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "1145.16",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4282601983,  # Blue
            "WFWorkflowIconGlyphNumber": 61457,  # Checklist glyph
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
                "Text": "Enter your Speech-to-Text API endpoint URL:",
            },
            {
                "ActionIndex": 3,
                "Category": "Parameter",
                "DefaultValue": "",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your Speech-to-Text API key:",
            },
            {
                "ActionIndex": 5,
                "Category": "Parameter",
                "DefaultValue": "https://api.groq.com/openai/v1/chat/completions",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your LLM API endpoint URL (chat completions):",
            },
            {
                "ActionIndex": 7,
                "Category": "Parameter",
                "DefaultValue": "",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your LLM API key:",
            },
            {
                "ActionIndex": 9,
                "Category": "Parameter",
                "DefaultValue": "llama-3.3-70b-versatile",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter the LLM model name (e.g. llama-3.3-70b-versatile, gpt-4o-mini):",
            },
        ],
    }

    # Write as binary plist
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice-reminders.shortcut")
    with open(output_path, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)

    print(f"Built shortcut: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")


if __name__ == "__main__":
    build_shortcut()
