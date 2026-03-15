#!/usr/bin/env python3
"""
Build the Receipt Scanner shortcut as a .shortcut (binary plist) file.

This script generates a fully functional iOS Shortcut that:
1. Takes a photo or selects one from the photo library
2. Encodes the image to base64
3. Sends it to an LLM vision API for structured receipt analysis
4. Formats the extracted data with a date stamp
5. Saves to Apple Notes or copies to clipboard
6. Shows a confirmation notification

Usage:
    python3 build-shortcut.py

Output:
    receipt-scanner.shortcut (binary plist file, installable on iOS)
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
            # It's a variable reference tuple: (uuid, var_name, var_type)
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
    # UUIDs for each action (used to wire outputs to inputs)
    uuid_menu_choose = make_uuid()
    uuid_take_photo = make_uuid()
    uuid_set_photo_take = make_uuid()
    uuid_select_photo = make_uuid()
    uuid_set_photo_select = make_uuid()
    uuid_endpoint_text = make_uuid()
    uuid_apikey_text = make_uuid()
    uuid_model_text = make_uuid()
    uuid_base64_encode = make_uuid()
    uuid_json_text = make_uuid()
    uuid_api_request = make_uuid()
    uuid_get_choices = make_uuid()
    uuid_get_first_choice = make_uuid()
    uuid_get_message = make_uuid()
    uuid_get_content = make_uuid()
    uuid_date = make_uuid()
    uuid_format_date = make_uuid()
    uuid_format_entry = make_uuid()
    uuid_save_menu = make_uuid()
    uuid_find_notes = make_uuid()
    uuid_count = make_uuid()
    uuid_if_found = make_uuid()
    uuid_append_note = make_uuid()
    uuid_create_note = make_uuid()
    uuid_clipboard = make_uuid()
    uuid_notification = make_uuid()

    # Variable names
    var_receipt_photo = "receipt_photo"
    var_endpoint = "endpoint_url"
    var_apikey = "api_key"
    var_model = "model"
    var_receipt_base64 = "receipt_base64"
    var_receipt_data = "receipt_data"
    var_formatted_entry = "formatted_entry"

    # System prompt for receipt analysis
    system_prompt = (
        "You are a receipt analysis assistant. Extract the following information "
        "from the receipt image and format it as structured text:\\n\\n"
        "- Store/Vendor Name\\n"
        "- Date of Purchase\\n"
        "- Items (name and price for each)\\n"
        "- Subtotal\\n"
        "- Tax\\n"
        "- Total\\n"
        "- Payment Method (if visible)\\n\\n"
        "Format the output like this:\\n"
        "\U0001F3EA Store: [name]\\n"
        "\U0001F4C5 Date: [date]\\n\\n"
        "\U0001F4CB Items:\\n"
        "  \u2022 [item 1] \u2014 $[price]\\n"
        "  \u2022 [item 2] \u2014 $[price]\\n\\n"
        "\U0001F4B0 Subtotal: $[amount]\\n"
        "\U0001F4CA Tax: $[amount]\\n"
        "\u2705 Total: $[amount]\\n"
        "\U0001F4B3 Payment: [method]\\n\\n"
        "If any field is not visible or unclear, mark it as 'N/A'. Be precise with numbers."
    )

    actions = [
        # --- Comment: Photo Input ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== PHOTO INPUT ===\nTake a photo of a receipt or select one from the photo library.",
            },
        },
        # --- Menu: Choose photo source (start) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu_choose,
                "WFControlFlowMode": 0,
                "WFMenuPrompt": "How would you like to provide the receipt?",
                "WFMenuItems": ["Take Photo", "Choose from Photos"],
            },
        },
        # --- Menu Item: Take Photo ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu_choose,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Take Photo",
            },
        },
        # --- Take Photo ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.takephoto",
            "WFWorkflowActionParameters": {
                "UUID": uuid_take_photo,
            },
        },
        # --- Set Variable: receipt_photo (from camera) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "UUID": uuid_set_photo_take,
                "WFVariableName": var_receipt_photo,
                "WFInput": action_output_ref(uuid_take_photo, "Photo"),
            },
        },
        # --- Menu Item: Choose from Photos ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu_choose,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Choose from Photos",
            },
        },
        # --- Select Photo ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.selectphoto",
            "WFWorkflowActionParameters": {
                "UUID": uuid_select_photo,
            },
        },
        # --- Set Variable: receipt_photo (from gallery) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "UUID": uuid_set_photo_select,
                "WFVariableName": var_receipt_photo,
                "WFInput": action_output_ref(uuid_select_photo, "Photos"),
            },
        },
        # --- Menu: End ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_menu_choose,
                "WFControlFlowMode": 2,
            },
        },
        # --- Comment: Configuration Section ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== CONFIGURATION ===\nEdit the three Text blocks below to configure your LLM provider.",
            },
        },
        # --- Text: LLM API Endpoint URL ---
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
        # --- Comment: Encode Image ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== ENCODE IMAGE ===\nConvert the receipt photo to base64 for the vision API.",
            },
        },
        # --- Base64 Encode the photo ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.base64encode",
            "WFWorkflowActionParameters": {
                "UUID": uuid_base64_encode,
                "WFEncodeMode": "Encode",
                "WFInput": variable_ref(var_receipt_photo),
            },
        },
        # --- Set Variable: receipt_base64 ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_receipt_base64,
                "WFInput": action_output_ref(uuid_base64_encode, "Base64 Encoded"),
            },
        },
        # --- Comment: Build API Request ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== BUILD API REQUEST ===\nConstruct the JSON body for the vision API with the base64 image.",
            },
        },
        # --- Text: Build the JSON body with variable interpolation ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_json_text,
                "WFTextActionText": text_token_multi([
                    '{"model": "',
                    (None, var_model, "Variable"),
                    '", "messages": [{"role": "system", "content": "',
                    system_prompt,
                    '"}, {"role": "user", "content": [{"type": "text", "text": "Analyze this receipt image and extract all information."}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,',
                    (None, var_receipt_base64, "Variable"),
                    '"}}]}], "max_tokens": 1000}',
                ]),
            },
        },
        # --- Comment: POST to API ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== CALL VISION API ===\nSend the base64-encoded receipt image to the LLM for analysis.",
            },
        },
        # --- Get Contents of URL: POST to LLM API ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": uuid_api_request,
                "WFURL": text_token(None, var_endpoint, "Variable"),
                "WFHTTPMethod": "POST",
                "WFHTTPBodyType": "JSON",
                "WFJSONValues": action_output_ref(uuid_json_text, "Text"),
                "WFHTTPHeaders": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": {
                                    "Value": {"string": "Authorization"},
                                    "WFSerializationType": "WFTextTokenString",
                                },
                                "WFValue": text_token_multi([
                                    "Bearer ",
                                    (None, var_apikey, "Variable"),
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
            },
        },
        # --- Comment: Parse Response ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== PARSE LLM RESPONSE ===\nExtract the receipt data from choices[0].message.content",
            },
        },
        # --- Get Dictionary Value: choices ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_choices,
                "WFInput": action_output_ref(uuid_api_request, "Contents of URL"),
                "WFDictionaryKey": "choices",
            },
        },
        # --- Get Item from List: first choice ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
            "WFWorkflowActionParameters": {
                "UUID": uuid_get_first_choice,
                "WFInput": action_output_ref(uuid_get_choices, "Dictionary Value"),
                "WFItemIndex": 1,  # 1-indexed in Shortcuts
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
        # --- Set Variable: receipt_data ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": var_receipt_data,
                "WFInput": action_output_ref(uuid_get_content, "Dictionary Value"),
            },
        },
        # --- Comment: Format & Save ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": "=== FORMAT & SAVE ===\nFormat the extracted receipt data with a date stamp and save it.",
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
        # --- Text: Format the receipt entry ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": uuid_format_entry,
                "WFTextActionText": text_token_multi([
                    "\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n",
                    "\U0001F9FE Scanned: ",
                    (uuid_date, "Date", "ActionOutput"),
                    "\n\n",
                    (None, var_receipt_data, "Variable"),
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
        # --- Menu: Save options (start) ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_save_menu,
                "WFControlFlowMode": 0,
                "WFMenuPrompt": "What would you like to do with the receipt data?",
                "WFMenuItems": ["Save to Notes", "Copy to Clipboard"],
            },
        },
        # --- Menu Item: Save to Notes ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_save_menu,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Save to Notes",
            },
        },
        # --- Find Notes: Search for "Expense Log" ---
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
                                "String": "Expense Log",
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
                "WFCondition": 2,
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
        # --- Create Note: "Expense Log" with first entry ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.createnote",
            "WFWorkflowActionParameters": {
                "UUID": uuid_create_note,
                "WFCreateNoteInput": text_token_multi([
                    "\U0001F9FE Expense Log\n",
                    "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n",
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
        # --- Show Notification: Saved to Notes ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
            "WFWorkflowActionParameters": {
                "WFNotificationActionTitle": "Receipt Saved!",
                "WFNotificationActionBody": "Receipt data has been added to your Expense Log in Apple Notes.",
            },
        },
        # --- Menu Item: Copy to Clipboard ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_save_menu,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": "Copy to Clipboard",
            },
        },
        # --- Copy to Clipboard ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setclipboard",
            "WFWorkflowActionParameters": {
                "UUID": uuid_clipboard,
                "WFInput": variable_ref(var_formatted_entry),
            },
        },
        # --- Show Notification: Copied ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
            "WFWorkflowActionParameters": {
                "UUID": uuid_notification,
                "WFNotificationActionTitle": "Receipt Copied!",
                "WFNotificationActionBody": "Receipt data has been copied to your clipboard.",
            },
        },
        # --- Menu: End ---
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": uuid_save_menu,
                "WFControlFlowMode": 2,
            },
        },
    ]

    shortcut = {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "1145.16",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4274264319,
            "WFWorkflowIconGlyphNumber": 59493,
        },
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowInputContentItemClasses": [
            "WFImageContentItem",
            "WFPhotoMediaContentItem",
        ],
        "WFWorkflowActions": actions,
        "WFWorkflowImportQuestions": [
            {
                "ActionIndex": 10,
                "Category": "Parameter",
                "DefaultValue": "https://api.openai.com/v1/chat/completions",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your LLM API endpoint URL (e.g. OpenAI, Groq, or local):",
            },
            {
                "ActionIndex": 12,
                "Category": "Parameter",
                "DefaultValue": "",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter your API key:",
            },
            {
                "ActionIndex": 14,
                "Category": "Parameter",
                "DefaultValue": "gpt-4o-mini",
                "ParameterKey": "WFTextActionText",
                "Text": "Enter the model name (e.g. gpt-4o-mini, gpt-4o):",
            },
        ],
    }

    # Write as binary plist
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "receipt-scanner.shortcut")
    with open(output_path, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)

    print(f"Built shortcut: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")


if __name__ == "__main__":
    build_shortcut()
