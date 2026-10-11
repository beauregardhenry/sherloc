from flask import render_template

import config
from web import app


@app.route("/instruction", methods=["GET"])
def instruction():
    return render_template(
        "main.html",
        task="instruction",
        title=config.TITLE,
    )
