from typing import Optional
from werkzeug.exceptions import HTTPException


class ApiException(HTTPException):

    def __init__(self,
                 description: Optional[str] = HTTPException.description,
                 code: Optional[int] = HTTPException.code):
        super().__init__(description, None)
        self.code = code
