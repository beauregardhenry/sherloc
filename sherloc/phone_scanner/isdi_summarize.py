"""Summarize the intake forms: how often each checkbox answer was given.

Run from the sherloc/ folder: python -m phone_scanner.isdi_summarize
"""

import os
import sqlite3
from collections import defaultdict

import pandas as pd

import config
import intake_choices


class ISDiSummary:
    def __init__(self, db_path):
        assert os.path.isfile(db_path), "ISDi db path {!r} was not found.".format(db_path)
        self.app_info_conn = sqlite3.connect(db_path, check_same_thread=False)
        self.df = pd.read_sql("select * from clients_notes", self.app_info_conn)
        self.checkbox_hists = {}

    def hist_checkbox(self, cbox_col, hreadable=None):
        hist = defaultdict(int)
        multibox_counts = defaultdict(int)
        for _, client in self.df.iterrows():
            checkboxes = intake_choices.checkbox_answers(client[cbox_col])
            multibox_counts[len(checkboxes)] += 1
            for cbox in checkboxes:
                # human readable dict passed for coded checkboxes
                hist[hreadable[cbox] if hreadable else cbox] += 1
        self.checkbox_hists[cbox_col] = (hist, multibox_counts)
        return hist, multibox_counts

    def devices_scanned(self):
        return int(
            self.app_info_conn.cursor()
            .execute("select count(distinct(serial)) from scan_res;")
            .fetchall()[0][0]
        )

    def __str__(self):
        rep = ["ISDi data summary", "-" * 80]
        rep.append("Number of devices scanned (iOS or Android): {}".format(self.devices_scanned()))
        for cbox_col, hist in self.checkbox_hists.items():
            c = cbox_col.replace("_", " ")
            rep += ["", "{}:".format(c.title()), "-" * 80]
            for k, v in hist[0].items():
                rep.append(str(k) + ": " + str(v))
            rep += ["", "Overlap (Multiple boxes checked):"]
            for k, v in sorted(hist[1].items()):
                rep.append("Number of clients with " + str(k) + " " + str(c) + ": " + str(v))
        return "\n".join(rep)


def main():
    summ = ISDiSummary(config.SQL_DB_PATH.replace("sqlite:///", ""))
    summ.hist_checkbox("vulnerabilities", dict(intake_choices.VULNERABILITIES))
    summ.hist_checkbox("chief_concerns", dict(intake_choices.CHIEF_CONCERNS))
    print(summ)


if __name__ == "__main__":
    main()
