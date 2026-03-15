#!/usr/bin/env python3
"""
Build the Clipboard Rewriter shortcut as a .shortcut (binary plist) file.

This script generates a fully functional iOS Shortcut that:
1. Gets text from the clipboard
2. Presents a menu of rewriting modes
3. Sends the text to an OpenAI-compatible chat completions endpoint
4. Extracts the rewritten text from the JSON response
5. Copies the result to the clipboard
6. Shows a confirmation notification

Usage:
    python3 build-shortcut.py

Output:
    clipboard-rewriter.shortcut (binary plist file, installable on iOS)
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


def text_value(string):
    """Create a simple text token string."""
    return {
        "Value": {"string": string},
        "WFSerializationType": "WFTextTokenString",
    }


def build_shortcut():
    # UUIDs for each action
    uuid_get_clipboard = make_uuid()
    uuid_set_clipboard_var = make_uuid()
    uuid_endpoint_text = make_uuid()
    uuid_apikey_text = make_uuid()
    uuid_model_text = make_uuid()
    uuid_menu = make_uuid()
    uuid_system_prompt_text = make_uuid()
    uuid_ask_custom = make_uuid()
    uuid_json_body = make_uuid()
    uuid_http_request = make_uuid()
    uuid_get_choices = make_uuid()
    uuid_get_first_choice = make_uuid()
    uuid_get_message = make_uuid()
    uuid_get_content = make_uuid()
    uuid_copy_result = make_uuid()
    uuid_notification = make_uuid()

    # Variable names
    var_clipboard = "clipboard_text"
    var_endpoint = "endpoint_url"
    var_apikey = "api_key"
    var_model = "model"
    var_system_prompt = "system_prompt"

    # Menu item UUIDs (one per mode)
    menu_uuid_professional = make_uuid()
    menu_uuid_simplify = make_uuid()
    menu_uuid_grammar = make_uuid()
    menu_uuid_concise = make_uuid()
    menu_uuid_translate_en = make_uuid()
    menu_uuid_translate_es = make_uuid()
    menu_uuid_custom = make_uuid()

    # System prompts for each mode
    prompts = {
        "professional": "You are a writing assistant. Rewrite the following text in a professional tone suitable for business communication. Preserve the original meaning and key information. Return only the rewritten text, no explanations.",
        "simplify": "You are a writing assistant. Simplify the following text so it can be easily understood by a general audience. Use plain language, shorter sentences, and avoid jargon. Return only the simplified text, no explanations.",
        "grammar": "You are a writing assistant. Fix all grammar, spelling, and punctuation errors in the following text. Do not change the tone or meaning. Return only the corrected text, no explanations.",
        "concise": "You are a writing assistant. Make the following text more concise while preserving all key information. Remove filler words, redundancies, and unnecessary phrases. Return only the concise version, no explanations.",
        "translate_en": "You are a translation assistant. Translate the following text into English. Preserve the original meaning, tone, and formatting. Return only the translated text, no explanations.",
        "translate_es": "You are a translation assistant. Translate the following text into Spanish. Preserve the original meaning, tone, and formatting. Return only the translated text, no explanations.",
    }

    actions = [
        # === CONFIGURATION SECTION ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== CONFIGURATION ===\nEdit the three Text blocks below to configure your LLM provider.",
            },
        },
        # --- Text: API Endpoint URL ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_endpoint_text,
                "WFTextActionText": "https://api.openai.com/v1/chat/completions",
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
                "WFTextActionText": "gpt-4o-mini",
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

        # === GET CLIPBOARD ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== GET CLIPBOARD TEXT ===",
            },
        },
        # --- Get Clipboard ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getclipboard",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_clipboard,
            },
        },
        # --- Set Variable: clipboard_text ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_clipboard,
                "WFInput": action_output_ref(uuid_get_clipboard, "Clipboard"),
            },
        },

        # === MODE SELECTION MENU ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== CHOOSE REWRITING MODE ===",
            },
        },
        # --- Choose from Menu ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu,
                "WFControlFlowMode": 0,  # Start of menu
                "WFMenuPrompt": "Choose a rewriting mode:",
                "WFMenuItems": [
                    "Rewrite Professionally",
                    "Simplify",
                    "Fix Grammar",
                    "Make Concise",
                    "Translate to English",
                    "Translate to Spanish",
                    "Custom",
                ],
                "WFMenuItemAttributedTitles": [
                    {"WFItemType": 0, "WFValue": text_value("Rewrite Professionally")},
                    {"WFItemType": 0, "WFValue": text_value("Simplify")},
                    {"WFItemType": 0, "WFValue": text_value("Fix Grammar")},
                    {"WFItemType": 0, "WFValue": text_value("Make Concise")},
                    {"WFItemType": 0, "WFValue": text_value("Translate to English")},
                    {"WFItemType": 0, "WFValue": text_value("Translate to Spanish")},
                    {"WFItemType": 0, "WFValue": text_value("Custom")},
                ],
            },
        },

        # --- Menu Item: Rewrite Professionally ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu,
                "WFControlFlowMode": 1,  # Menu item
                "WFMenuItemTitle": "Rewrite Professionally",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": make_uuid(),
                "WFTextActionText": prompts["professional"],
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_system_prompt,
            },
        },

        # --- Menu Item: Simplify ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Simplify",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": make_uuid(),
                "WFTextActionText": prompts["simplify"],
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_system_prompt,
            },
        },

        # --- Menu Item: Fix Grammar ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Fix Grammar",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": make_uuid(),
                "WFTextActionText": prompts["grammar"],
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_system_prompt,
            },
        },

        # --- Menu Item: Make Concise ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Make Concise",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": make_uuid(),
                "WFTextActionText": prompts["concise"],
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_system_prompt,
            },
        },

        # --- Menu Item: Translate to English ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Translate to English",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": make_uuid(),
                "WFTextActionText": prompts["translate_en"],
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_system_prompt,
            },
        },

        # --- Menu Item: Translate to Spanish ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Translate to Spanish",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": make_uuid(),
                "WFTextActionText": prompts["translate_es"],
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_system_prompt,
            },
        },

        # --- Menu Item: Custom ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Custom",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
            "WFWorkflowActionParameters": {
                "UUID": uuid_ask_custom,
                "WFAskActionPrompt": "Enter your custom instruction:",
                "WFAskActionDefaultAnswer": "Rewrite this text to be more engaging",
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_system_prompt,
                "WFInput": action_output_ref(uuid_ask_custom, "Provided Input"),
            },
        },

        # --- End Menu ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu,
                "WFControlFlowMode": 2,  # End menu
            },
        },

        # === BUILD AND SEND API REQUEST ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== SEND TO LLM API ===\nBuilds a JSON body and POSTs to the chat completions endpoint.",
            },
        },

        # --- Text: JSON Body ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_json_body,
                "WFTextActionText": {
                    "Value": {
                        "string": '{"model": "\uFFFC", "messages": [{"role": "system", "content": "\uFFFC"}, {"role": "user", "content": "\uFFFC"}]}',
                        "attachmentsByRange": {
                            "{10, 1}": {
                                "Type": "Variable",
                                "VariableName": var_model,
                            },
                            "{44, 1}": {
                                "Type": "Variable",
                                "VariableName": var_system_prompt,
                            },
                            "{75, 1}": {
                                "Type": "Variable",
                                "VariableName": var_clipboard,
                            },
                        },
                    },
                    "WFSerializationType": "WFTextTokenString",
                },
            },
        },

        # --- Get Contents of URL (HTTP POST) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuid_http_request,
                "WFURL": text_token(uuid_endpoint_text, var_endpoint),
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
                                "WFKey": text_value("Authorization"),
                                "WFValue": {
                                    "Value": {
                                        "string": "Bearer \uFFFC",
                                        "attachmentsByRange": {
                                            "{7, 1}": {
                                                "Type": "Variable",
                                                "VariableName": var_apikey,
                                            },
                                        },
                                    },
                                    "WFSerializationType": "WFTextTokenString",
                                },
                            },
                            {
                                "WFItemType": 0,
                                "WFKey": text_value("Content-Type"),
                                "WFValue": text_value("application/json"),
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
                "WFRequestBodyText": action_output_ref(uuid_json_body, "Text"),
            },
        },

        # === PARSE RESPONSE ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== PARSE RESPONSE ===\nExtract: choices[0].message.content",
            },
        },

        # --- Get Dictionary Value: choices ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_choices,
                "WFInput": action_output_ref(uuid_http_request, "Contents of URL"),
                "WFDictionaryKey": "choices",
            },
        },
        # --- Get Item from List: first choice ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_first_choice,
                "WFInput": action_output_ref(uuid_get_choices, "Dictionary Value"),
                "WFItemSpecifier": "First Item",
            },
        },
        # --- Get Dictionary Value: message ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_message,
                "WFInput": action_output_ref(uuid_get_first_choice, "Item from List"),
                "WFDictionaryKey": "message",
            },
        },
        # --- Get Dictionary Value: content ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_content,
                "WFInput": action_output_ref(uuid_get_message, "Dictionary Value"),
                "WFDictionaryKey": "content",
            },
        },

        # === COPY RESULT & NOTIFY ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== COPY RESULT & NOTIFY ===",
            },
        },
        # --- Copy to Clipboard ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setclipboard",
            "WFWorkflowActionParameters": {
                "UUID": uuid_copy_result,
                "WFInput": action_output_ref(uuid_get_content, "Dictionary Value"),
            },
        },
        # --- Show Notification ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
            "WFWorkflowActionParameters": {
                "UUID": uuid_notification,
                "WFNotificationActionTitle": "Clipboard Rewriter",
                "WFNotificationActionBody": "Text has been rewritten and copied to your clipboard.",
            },
        },
    ]

    shortcut = {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "1145.16",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 463140863,   # Purple
            "WFWorkflowIconGlyphNumber": 59761,       # Document/text glyph
        },
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowInputContentItemClasses": [
            "WFStringContentItem",
            "WFRichTextContentItem",
            "WFURLContentItem",
        ],
        "WFWorkflowActions": actions,
        "WFWorkflowImportQuestions": [
            {
                "ActionIndex": 1,
                "Category": "Parameter",
                "DefaultValue": "https://api.openai.com/v1/chat/completions",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your chat completions API endpoint URL:",
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
                "DefaultValue": "gpt-4o-mini",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter the model name (e.g. gpt-4o-mini, llama-3.3-70b-versatile):",
            },
        ],
    }

    # Write as binary plist
    output_path = os.path.join(os.path.dirname(__file__), "clipboard-rewriter.shortcut")
    with open(output_path, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)

    print(f"Built shortcut: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")


if __name__ == "__main__":
    build_shortcut()
