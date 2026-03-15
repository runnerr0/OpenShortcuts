#!/usr/bin/env python3
"""
Build the Link Saver shortcut as a .shortcut (binary plist) file.

This script generates a fully functional iOS Shortcut that:
1. Receives a URL from the Share Sheet (Safari, Twitter/X, Reddit, YouTube, Instagram, etc.)
2. Detects which platform the link is from
3. Fetches the page content
4. Sends it to an LLM for a concise summary
5. Formats a structured entry with platform tag, date, URL, and summary
6. Appends the entry to a "Saved Links" note in Apple Notes
7. Shows a confirmation notification

Usage:
    python3 build-shortcut.py

Output:
    link-saver.shortcut (binary plist file, installable on iOS)
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


def text_value(string):
    """Create a simple text token string."""
    return {
        "Value": {"string": string},
        "WFSerializationType": "WFTextTokenString",
    }


def text_token_multi(parts):
    """Create a text token string with multiple variable interpolations.

    parts is a list of either plain strings or (uuid, var_name, var_type) tuples.
    """
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
            elif p_type == "ExtensionInput":
                attachment["VariableName"] = p_name
            attachments[f"{{{pos}, 1}}"] = attachment
            pos += 1
    return {
        "Value": {
            "string": full_string,
            "attachmentsByRange": attachments,
        },
        "WFSerializationType": "WFTextTokenString",
    }


def build_shortcut():
    # UUIDs for actions
    uuid_set_url = make_uuid()
    uuid_url_text = make_uuid()
    uuid_endpoint_text = make_uuid()
    uuid_apikey_text = make_uuid()
    uuid_model_text = make_uuid()
    uuid_get_page = make_uuid()
    uuid_prompt_text = make_uuid()
    uuid_json_body = make_uuid()
    uuid_llm_request = make_uuid()
    uuid_get_choices = make_uuid()
    uuid_get_first_choice = make_uuid()
    uuid_get_message = make_uuid()
    uuid_get_content = make_uuid()
    uuid_date = make_uuid()
    uuid_format_date = make_uuid()
    uuid_format_entry = make_uuid()
    uuid_find_notes = make_uuid()
    uuid_count = make_uuid()
    uuid_if_found = make_uuid()
    uuid_append_note = make_uuid()
    uuid_create_note = make_uuid()
    uuid_notification = make_uuid()

    # Variable names
    var_shared_url = "shared_url"
    var_page_content = "page_content"
    var_endpoint = "endpoint_url"
    var_apikey = "api_key"
    var_model = "model"
    var_summary = "summary"
    var_formatted_entry = "formatted_entry"

    # System prompt for the LLM
    system_prompt = (
        "You are a link summarizer that helps people save and organize links from social media and the web. "
        "Given a URL and page content, provide:\n\n"
        "1. A platform tag (e.g. Twitter/X, Reddit, YouTube, Instagram, TikTok, LinkedIn, Mastodon, Threads, Bluesky, Hacker News, Article, Website)\n"
        "2. A short title (the post title, tweet text snippet, or article headline — max 80 chars)\n"
        "3. The author/poster name if visible\n"
        "4. A 2-3 sentence summary of the content\n"
        "5. 2-3 relevant tags/topics\n\n"
        "Format your response EXACTLY like this (keep the emoji prefixes):\n"
        "Platform: [platform name]\n"
        "Title: [title]\n"
        "Author: [name or N/A]\n"
        "Summary: [your summary]\n"
        "Tags: #[tag1] #[tag2] #[tag3]"
    )

    actions = [
        # === SHARE SHEET INPUT ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== SHARE SHEET INPUT ===\nReceives a URL from the Share Sheet (Safari, Twitter/X, Reddit, YouTube, etc.)",
            },
        },
        # --- Set Variable: shared_url (from Share Sheet input) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "UUID": uuid_set_url,
                "WFVariableName": var_shared_url,
                "WFInput": {
                    "Value": {
                        "Type": "ExtensionInput",
                    },
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # --- Get the URL as text for display ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_url_text,
                "WFTextActionText": text_token(None, var_shared_url, "Variable"),
            },
        },

        # === CONFIGURATION ===
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

        # === FETCH PAGE CONTENT ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== FETCH PAGE ===\nDownload the web page content from the shared URL.",
            },
        },
        # --- Get Contents of URL (fetch the page) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_page,
                "WFURL": text_token(None, var_shared_url, "Variable"),
            },
        },
        # --- Set Variable: page_content ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_page_content,
                "WFInput": action_output_ref(uuid_get_page, "Contents of URL"),
            },
        },

        # === BUILD PROMPT & CALL LLM ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== BUILD PROMPT & CALL LLM ===\nSend the URL and page content to the LLM for summarization.",
            },
        },
        # --- Text: Build the user prompt ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_prompt_text,
                "WFTextActionText": text_token_multi([
                    "URL: ",
                    (None, var_shared_url, "Variable"),
                    "\n\nPage Content:\n",
                    (None, var_page_content, "Variable"),
                ]),
            },
        },
        # --- Dictionary: Build JSON body for LLM API ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.dictionary",
            "WFWorkflowActionParameters": {
                "UUID": uuid_json_body,
                "WFItems": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": text_value("model"),
                                "WFValue": text_token(None, var_model, "Variable"),
                            },
                            {
                                "WFItemType": 2,  # Array
                                "WFKey": text_value("messages"),
                                "WFValue": {
                                    "Value": [
                                        {
                                            "WFItemType": 1,  # Dictionary
                                            "WFValue": {
                                                "Value": {
                                                    "WFDictionaryFieldValueItems": [
                                                        {
                                                            "WFItemType": 0,
                                                            "WFKey": text_value("role"),
                                                            "WFValue": text_value("system"),
                                                        },
                                                        {
                                                            "WFItemType": 0,
                                                            "WFKey": text_value("content"),
                                                            "WFValue": text_value(system_prompt),
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
                                                            "WFKey": text_value("role"),
                                                            "WFValue": text_value("user"),
                                                        },
                                                        {
                                                            "WFItemType": 0,
                                                            "WFKey": text_value("content"),
                                                            "WFValue": text_token(uuid_prompt_text, "Text", "ActionOutput"),
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
                            {
                                "WFItemType": 3,  # Number
                                "WFKey": text_value("max_tokens"),
                                "WFValue": text_value("500"),
                            },
                            {
                                "WFItemType": 3,  # Number
                                "WFKey": text_value("temperature"),
                                "WFValue": text_value("0.3"),
                            },
                        ],
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # --- Get Contents of URL: POST to LLM API ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuid_llm_request,
                "WFURL": text_token(None, var_endpoint, "Variable"),
                "WFHTTPMethod": "POST",
                "WFHTTPBodyType": "JSON",
                "WFJSONValues": action_output_ref(uuid_json_body, "Dictionary"),
                "WFHTTPHeaders": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": text_value("Authorization"),
                                "WFValue": text_token_multi([
                                    "Bearer ",
                                    (None, var_apikey, "Variable"),
                                ]),
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
            },
        },

        # === PARSE LLM RESPONSE ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== PARSE LLM RESPONSE ===\nExtract the summary from choices[0].message.content",
            },
        },
        # --- Get Dictionary Value: choices ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_choices,
                "WFInput": action_output_ref(uuid_llm_request, "Contents of URL"),
                "WFDictionaryKey": "choices",
            },
        },
        # --- Get Item from List: first choice ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_first_choice,
                "WFInput": action_output_ref(uuid_get_choices, "Dictionary Value"),
                "WFItemIndex": 1,
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
        # --- Set Variable: summary ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_summary,
                "WFInput": action_output_ref(uuid_get_content, "Dictionary Value"),
            },
        },

        # === FORMAT & SAVE ===
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== FORMAT & SAVE TO NOTES ===\nFormat the entry with date, URL, and summary, then append to Saved Links note.",
            },
        },
        # --- Date: Get current date ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.date",
            "WFWorkflowActionParameters": {
                "UUID": uuid_date,
                "WFDateActionMode": "Current Date",
            },
        },
        # --- Format Date ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.format.date",
            "WFWorkflowActionParameters": {
                "UUID": uuid_format_date,
                "WFDate": action_output_ref(uuid_date, "Date"),
                "WFDateFormatStyle": "Custom",
                "WFDateFormat": "MMM d, yyyy 'at' h:mm a",
            },
        },
        # --- Text: Format the Saved Links entry ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_format_entry,
                "WFTextActionText": text_token_multi([
                    "\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n",
                    "\U0001F4C5 ",
                    (uuid_format_date, "Formatted Date", "ActionOutput"),
                    "\n\U0001F517 ",
                    (None, var_shared_url, "Variable"),
                    "\n\n",
                    (None, var_summary, "Variable"),
                    "\n\n\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n",
                ]),
            },
        },
        # --- Set Variable: formatted_entry ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_formatted_entry,
                "WFInput": action_output_ref(uuid_format_entry, "Text"),
            },
        },
        # --- Find Notes: Search for "Saved Links" ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.filter.notes",
            "WFWorkflowActionParameters": {
                "UUID": uuid_find_notes,
                "WFContentItemFilter": {
                    "Value": {
                        "WFActionParameterFilterPrefix": 1,
                        "WFContentPredicateBoundedDate": False,
                        "WFActionParameterFilterTemplates": [
                            {
                                "Property": "Name",
                                "Operator": 4,
                                "String": "Saved Links",
                                "VariableOverrides": {},
                            },
                        ],
                    },
                    "WFSerializationType": "WFContentPredicateTableTemplate",
                },
            },
        },
        # --- Count: How many notes matched? ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.count",
            "WFWorkflowActionParameters": {
                "UUID": uuid_count,
                "Input": action_output_ref(uuid_find_notes, "Notes"),
            },
        },
        # --- If: Note exists (count > 0) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_if_found,
                "WFControlFlowMode": 0,
                "WFCondition": 2,  # Greater than
                "WFNumberValue": 0,
            },
        },
        # --- Append to Note ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.appendtonote",
            "WFWorkflowActionParameters": {
                "UUID": uuid_append_note,
                "WFNote": action_output_ref(uuid_find_notes, "Notes"),
                "WFInput": text_token(None, var_formatted_entry, "Variable"),
            },
        },
        # --- Otherwise ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_if_found,
                "WFControlFlowMode": 1,
            },
        },
        # --- Create Note: "Saved Links" with first entry ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.createnote",
            "WFWorkflowActionParameters": {
                "UUID": uuid_create_note,
                "WFCreateNoteInput": text_token_multi([
                    "\U0001F516 Saved Links\n",
                    "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n",
                    "Links saved from social media & the web.\n",
                    (None, var_formatted_entry, "Variable"),
                ]),
            },
        },
        # --- End If ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_if_found,
                "WFControlFlowMode": 2,
            },
        },
        # --- Show Notification ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
            "WFWorkflowActionParameters": {
                "UUID": uuid_notification,
                "WFNotificationActionTitle": "Link Saved!",
                "WFNotificationActionBody": "Summary has been added to your Saved Links note.",
            },
        },
    ]

    shortcut = {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "1145.16",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 1440408063,  # Blue
            "WFWorkflowIconGlyphNumber": 61515,       # Bookmark glyph
        },
        "WFWorkflowTypes": ["NCWidget", "WatchKit", "ActionExtension"],
        "WFWorkflowInputContentItemClasses": [
            "WFURLContentItem",
            "WFSafariWebPageContentItem",
            "WFRichTextContentItem",
            "WFStringContentItem",
            "WFArticleContentItem",
        ],
        "WFWorkflowActions": actions,
        "WFWorkflowImportQuestions": [
            {
                "ActionIndex": 4,
                "Category": "Parameter",
                "DefaultValue": "https://api.openai.com/v1/chat/completions",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your LLM API endpoint URL (e.g. OpenAI, Groq, or local):",
            },
            {
                "ActionIndex": 6,
                "Category": "Parameter",
                "DefaultValue": "",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your API key:",
            },
            {
                "ActionIndex": 8,
                "Category": "Parameter",
                "DefaultValue": "gpt-4o-mini",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter the model name (e.g. gpt-4o-mini, llama-3.3-70b-versatile):",
            },
        ],
    }

    # Write as binary plist
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "link-saver.shortcut")
    with open(output_path, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)

    print(f"Built shortcut: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")


if __name__ == "__main__":
    build_shortcut()
