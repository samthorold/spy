from datetime import datetime
import os

from attrs import define
from jinja2 import (
    Environment as TemplateEnvironment,
    PackageLoader as TemplateLoader,
    select_autoescape,
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

### Domain ###


@define
class FlashCard:
    question: str
    answer: str
    last_seen: datetime


### App ###


APP_DEBUG = bool(os.environ.get("DEBUG", 0))


template_environment = TemplateEnvironment(
    loader=TemplateLoader("main"),
    autoescape=select_autoescape(),
)


async def root(request: Request):
    template = template_environment.get_template("root.html")
    rendered_template = template.render()
    return HTMLResponse(rendered_template)


app = Starlette(
    debug=APP_DEBUG,
    routes=[
        Route("/", root),
        Mount("/static", StaticFiles(directory="static")),
    ],
)
