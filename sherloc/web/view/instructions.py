import config
from flask import render_template
from web import app


@app.route("/instruction", methods=["GET"])
def instruction():
    return render_template(
        "main.html",
        task="instruction",
        title=config.TITLE,
    )
