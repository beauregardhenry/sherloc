"""Choices for the intake form's checkbox questions.

The form (web/forms/client.py) and the summary script
(phone_scanner/isdi_summarize.py) both read these. No Flask imports, so the
script can use them without starting the app.
"""

import json

CHIEF_CONCERNS = [
    ("spyware", "Worried about spyware/tracking"),
    ("hacked", "Abuser hacked accounts or knows secrets"),
    ("location", "Worried abuser was tracking their location"),
    ("glitchy", "Phone is glitchy"),
    ("unknown_calls", "Abuser calls/texts from unknown numbers"),
    ("social_media", "Social media concerns (e.g., fake accounts, harassment)"),
    ("child_devices", "Concerns about child device(s), e.g., unknown apps"),
    (
        "financial_concerns",
        "Financial concerns, e.g., fraud, money missing from bank account",
    ),
    ("curious", "Curious and want to learn about privacy"),
    ("sms", "SMS texts"),
    ("other", "Other chief concern (write in next question)"),
]

CHECKUPS = [
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("snapchat", "SnapChat"),
    ("google", "Google (including GMail)"),
    ("icloud", "iCloud"),
    ("whatsapp", "WhatsApp"),
    ("other", "Other apps/accounts (write in next question)"),
]

VULNERABILITIES = [
    ("none", "None"),
    ("shared plan", "Shared plan / abuser pays for plan"),
    (
        "password:observed compromise",
        "Observed compromise (e.g., client reports abuser shoulder-surfed, or told them password)",
    ),
    ("password:guessable", "Surfaced guessable passwords"),
    (
        "cloud:stored passwords",
        "Stored passwords in app that is synced to cloud (e.g., passwords written in Notes and backed up)",
    ),
    (
        "cloud:passwords synced/password manager",
        "Password syncing (e.g., iCloud Keychain)",
    ),
    (
        "unknown trusted device",
        "Found an account with an active login from a device not under client's control; trusted device",
    ),
    ("ISDi:found dual-use apps/spyware", "ISDi found dual-use apps/spyware"),
    ("ISDi:false positive", "ISDi false positive as confirmed by client"),
    ("browser extension", "Browser extension potential spyware"),
    ("desktop potential spyware", "Desktop application potential spyware"),
]


def checkbox_answers(value):
    """The saved answers to a checkbox question, as a list.

    They are stored as a JSON list. Rows from older versions may hold ''.
    """
    if not value:
        return []
    if isinstance(value, list):
        value = "".join(value)
    return json.loads(value)
