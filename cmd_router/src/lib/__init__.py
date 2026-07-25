__all__ = ["CommandRouter"]


class CommandRouter:
    @staticmethod
    def hello() -> str:
        return "Hello from cmd_router!"

    @staticmethod
    def data() -> dict:
        return {"info": "Data from cmd_router!"}
