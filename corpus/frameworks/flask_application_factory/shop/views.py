from flask import Blueprint

bp = Blueprint("main", __name__)


@bp.route("/")
def index() -> str:
    return render_page()


def render_page() -> str:
    return "ok"


def unused_helper() -> str:
    return "unused"
