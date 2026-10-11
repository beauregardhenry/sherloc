from wtforms_alchemy import ModelForm

import intake_choices
from web.model import Client
from wtforms.fields import SelectMultipleField
from wtforms.widgets import CheckboxInput, ListWidget
from wtforms import TextAreaField
from wtforms.validators import InputRequired, Optional


class ClientForm(ModelForm):
    class Meta:
        model = Client

    chief_concerns = SelectMultipleField(
        "Chief concerns*",
        choices=intake_choices.CHIEF_CONCERNS,
        coerce=str,
        option_widget=CheckboxInput(),
        widget=ListWidget(prefix_label=False),
        validators=[InputRequired()],
    )

    checkups = SelectMultipleField(
        "List apps/accounts manually checked (Optional)",
        choices=intake_choices.CHECKUPS,
        coerce=str,
        option_widget=CheckboxInput(),
        widget=ListWidget(prefix_label=False),
    )

    vulnerabilities = SelectMultipleField(
        "Vulnerabilities discovered*",
        choices=intake_choices.VULNERABILITIES,
        coerce=str,
        option_widget=CheckboxInput(),
        widget=ListWidget(prefix_label=False),
        validators=[InputRequired()],
    )

    __order = (
        "fjc",
        "consultant_initials",
        "preferred_language",
        "referring_professional",
        "referring_professional_email",
        "referring_professional_phone",
        "caseworker_present",
        "caseworker_present_safety_planning",
        "recorded",
        "caseworker_recorded",
        "chief_concerns",
        "chief_concerns_other",
        "android_phones",
        "android_tablets",
        "iphone_devices",
        "ipad_devices",
        "macbook_devices",
        "windows_devices",
        "echo_devices",
        "other_devices",
        "checkups",
        "checkups_other",
        "vulnerabilities",
        "vulnerabilities_trusted_devices",
        "vulnerabilities_other",
        "safety_planning_onsite",
        "changes_made_onsite",
        "unresolved_issues",
        "follow_ups_todo",
        "general_notes",
        "case_summary",
    )

    chief_concerns_other = TextAreaField(
        "Chief concerns if not listed above (Optional)",
        render_kw={"rows": 5, "cols": 70},
    )
    vulnerabilities_trusted_devices = TextAreaField(
        "List accounts with unknown trusted devices if discovered (Optional)",
        render_kw={"rows": 5, "cols": 70},
    )
    vulnerabilities_other = TextAreaField(
        "Other vulnerabilities discovered (Optional)", render_kw={"rows": 5, "cols": 70}
    )
    changes_made_onsite = TextAreaField(
        "Changes made onsite (Optional)", render_kw={"rows": 5, "cols": 70}
    )
    unresolved_issues = TextAreaField(
        "Unresolved issues (Optional)", render_kw={"rows": 5, "cols": 70}
    )
    follow_ups_todo = TextAreaField(
        "Follow-ups To-do (Optional)", render_kw={"rows": 5, "cols": 70}
    )
    general_notes = TextAreaField(
        "General notes (Optional)", render_kw={"rows": 10, "cols": 70}
    )
    case_summary = TextAreaField(
        'Case Summary (Can fill out after consult, see "Edit previous forms")',
        render_kw={"rows": 10, "cols": 70},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # wtforms_alchemy adds Optional() to every column that has a default,
        # and Optional() ends validation on a blank answer before
        # InputRequired() runs. Drop it where the question is required.
        for field in self._fields.values():
            if any(isinstance(v, InputRequired) for v in field.validators):
                field.validators = [v for v in field.validators if not isinstance(v, Optional)]
                field.flags.optional = False

    def __iter__(self):  # https://stackoverflow.com/a/25323199
        fields = list(super(ClientForm, self).__iter__())
        get_field = lambda field_id: next((fld for fld in fields if fld.id == field_id))
        return (get_field(field_id) for field_id in self.__order)
