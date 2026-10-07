import csv
from io import BytesIO, StringIO

from flask import Blueprint, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Font

from app.database import get_applications
from app.exports import (
    EXPORT_COLUMN_WIDTHS,
    EXPORT_HEADERS,
    application_export_row,
)
from app.presentation import (
    prepare_application_rows,
)


exports_bp = Blueprint(
    "exports",
    __name__,
)


def filtered_applications():
    return prepare_application_rows(
        get_applications(),
        status_filter=request.args.get(
            "status",
            "",
        ).strip(),
        search=request.args.get(
            "q",
            "",
        ).strip(),
        mailbox_filter=request.args.get(
            "mailbox",
            "",
        ).strip(),
    )


@exports_bp.get("/export/csv")
def export_csv():
    applications = (
        filtered_applications()
    )

    with StringIO() as output:
        writer = csv.writer(
            output,
            delimiter=";",
        )

        writer.writerow(
            EXPORT_HEADERS
        )

        writer.writerows(
            application_export_row(
                application
            )
            for application
            in applications
        )

        content = output.getvalue()

    from flask import current_app

    response = (
        current_app.response_class(
            "\ufeff" + content,
            mimetype=(
                "text/csv; charset=utf-8"
            ),
        )
    )

    response.headers[
        "Content-Disposition"
    ] = (
        "attachment; "
        "filename=candidatures.csv"
    )

    return response


@exports_bp.get("/export/xlsx")
def export_xlsx():
    applications = (
        filtered_applications()
    )

    workbook = Workbook()

    sheet = workbook.active

    if sheet is None:
        sheet = (
            workbook.create_sheet()
        )

    sheet.title = "Candidatures"

    sheet.append(
        list(EXPORT_HEADERS)
    )

    for cell in sheet[1]:
        cell.font = Font(
            bold=True
        )

    for application in applications:
        sheet.append(
            application_export_row(
                application
            )
        )

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = (
        sheet.dimensions
    )

    for (
        column,
        width,
    ) in EXPORT_COLUMN_WIDTHS.items():
        sheet.column_dimensions[
            column
        ].width = width

    output = BytesIO()

    workbook.save(output)

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=(
            "candidatures.xlsx"
        ),
        mimetype=(
            "application/"
            "vnd.openxmlformats-"
            "officedocument."
            "spreadsheetml.sheet"
        ),
    )