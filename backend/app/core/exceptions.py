"""业务异常与全局处理。"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class BusinessError(Exception):
    """业务异常：code 为稳定错误码，message 面向用户。"""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )
