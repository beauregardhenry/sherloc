import config
import json
from web import app, sa
from web.model import Client
from web.forms import ClientForm
from flask import render_template, request, session, redirect, url_for
from debuglog import debug


@app.route("/form/", methods=["GET", "POST"])
def client_forms():
    if "clientid" not in session:
        return redirect(url_for("index"))

    prev_submitted = Client.query.filter_by(clientid=session["clientid"]).first()
    if prev_submitted:
        return redirect(url_for("edit_forms"))

    # retrieve form defaults from db schema
    client = Client()
    form = ClientForm(request.form)

    if request.method == "POST":
        try:
            if form.validate():
                debug("VALIDATED")
                # convert checkbox lists to json-friendly strings
                for field in form:
                    if field.type == "SelectMultipleField":
                        field.data = json.dumps(field.data)
                form.populate_obj(client)
                client.clientid = session["clientid"]
                sa.session.add(client)
                sa.session.commit()
                return render_template(
                    "main.html", task="form", formdone="yes", title=config.TITLE
                )
        except Exception as e:
            debug("NOT VALIDATED")
            debug(e)
            sa.session.rollback()

    return render_template(
        "main.html",
        task="form",
        form=form,
        title=config.TITLE,
        clientid=session["clientid"],
    )


def _checkbox_answers(value):
    """The saved JSON list for a checkbox question. Old rows may hold ''."""
    if not value:
        return []
    if isinstance(value, list):
        value = "".join(value)
    return json.loads(value)


@app.route("/form/edit/", methods=["GET", "POST"])
def edit_forms():
    if request.method == "POST":
        clientnote = request.form.get("clientnote", request.args.get("clientnote"))

        if clientnote:  # if requesting a form to edit
            form_obj = sa.session.get(Client, clientnote)
            if form_obj is None:
                return redirect(url_for("edit_forms"))
            session["form_edit_pk"] = clientnote  # set session cookie
            form = ClientForm(obj=form_obj)
            for field in form:
                if field.type == "SelectMultipleField":
                    field.data = _checkbox_answers(field.data)
            return render_template(
                "main.html",
                task="form",
                form=form,
                title=config.TITLE,
                clientid=form_obj.clientid,
            )
        else:  # if edits were submitted
            pk = session.get("form_edit_pk")
            form_obj = sa.session.get(Client, pk) if pk else None
            if form_obj is None:
                return redirect(url_for("edit_forms"))
            cid = form_obj.clientid  # preserve before populate_obj
            form = ClientForm(request.form)
            if not form.validate():
                debug("NOT VALIDATED")
                return render_template(
                    "main.html",
                    task="form",
                    form=form,
                    title=config.TITLE,
                    clientid=cid,
                )
            debug("VALIDATED")
            # convert checkbox lists to json-friendly strings
            for field in form:
                if field.type == "SelectMultipleField":
                    field.data = json.dumps(field.data)
            form.populate_obj(form_obj)
            form_obj.clientid = cid
            sa.session.commit()
            return render_template(
                "main.html", task="form", formdone="yes", title=config.TITLE
            )

    clients = Client.query.all()
    return render_template(
        "main.html", clients=clients, task="formedit", title=config.TITLE
    )
